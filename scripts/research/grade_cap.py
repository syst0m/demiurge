#!/usr/bin/env python3
"""
grade_cap.py - Cap RESEARCH.md grades by the sources recorded in sources.yaml.

Each claim in ``research/sources.yaml`` carries its asserted grades and its
sources. This script derives the reasons a claim falls short of the research
methodology, turns them into a cap and lowers the grade shown in RESEARCH.md
to ``lower(asserted, cap)``. It never raises a grade and never edits
``asserted``.

Evidence reasons lower the grade at once. Debt reasons lower it only when
``meta.enforced`` is true; until then they flag the grade with
``[UNVERIFIED]``. ``polarity: negate`` claims are skipped.

Usage:
    python scripts/research/grade_cap.py --check
    python scripts/research/grade_cap.py --write
    python scripts/research/grade_cap.py --stats
    python scripts/research/grade_cap.py --debt [--limit 10] [--json]
    python scripts/research/grade_cap.py --changelog-row --version X --by Y
    python scripts/research/grade_cap.py --check-changelog --base <ref>

Path flags (--research, --sources, --claims-json) resolve against --repo,
which defaults to this checkout.

Exit codes:
    0  success
    1  check failed, or --write refused
    2  usage error or missing dependency
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import research_lib as rl

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RESEARCH = "research/RESEARCH.md"
DEFAULT_SOURCES = "research/sources.yaml"
DEFAULT_CLAIMS_JSON = "skills/marcus/references/claims.json"
COMPILED_SCHEMA = "demiurge.claims.compiled.v1"

PRIMARY_TYPES = {"peer", "preprint", "spec"}
UNCOUNTED_TYPES = {"aggregator", "none"}
RECEPTION_TYPES = {"peer", "preprint"}
BLOCKING = {
    "contrasting_source",
    "vendor_gt1",
    "lt3_independent",
    "lt2_primary",
    "independence_unset",
    "reception_unchecked",
    "unretrieved_source",
}
UNSET_GROUP = "_unset"
UNVERIFIED_FLAG = "`[UNVERIFIED]`"
VERSION_RE = re.compile(r"^version:\s*(\S+)\s*$", re.MULTILINE)


# --------------------------------------------------------------------------- #
# Algorithm
# --------------------------------------------------------------------------- #

def _reception(source: Mapping[str, Any]) -> Mapping[str, Any]:
    reception = source.get("reception")
    return reception if isinstance(reception, dict) else {}


def etype(source: Mapping[str, Any]) -> Optional[str]:
    """Effective source type: a resolved aggregator counts as what it resolves to."""
    if source.get("type") == "aggregator" and source.get("resolves_to"):
        return source.get("resolves_to_type")
    return source.get("type")


def _unresolved_aggregator(source: Mapping[str, Any]) -> bool:
    return source.get("type") == "aggregator" and not source.get("resolves_to")


def counted_sources(sources: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """Confirming sources of a countable type that are not retracted."""
    return [
        s
        for s in sources
        if s.get("supports") == "confirms"
        and etype(s) not in UNCOUNTED_TYPES
        and not _reception(s).get("retracted")
    ]


def _group(source: Mapping[str, Any]) -> str:
    return source.get("independence_group") or UNSET_GROUP


def compute_reasons(sources: Sequence[Mapping[str, Any]]) -> List[str]:
    """Reasons a claim falls short, in ``research_lib.REASONS`` order."""
    counted = counted_sources(sources)
    members: Dict[str, List[Mapping[str, Any]]] = {}
    for s in counted:
        members.setdefault(_group(s), []).append(s)
    primary = [g for g, group in members.items() if any(etype(s) in PRIMARY_TYPES for s in group)]
    vgroups = [g for g, group in members.items() if all(etype(s) == "vendor" for s in group)]

    found = set()
    if any(s.get("supports") == "contrasts" and etype(s) not in UNCOUNTED_TYPES for s in sources):
        found.add("contrasting_source")
    if any(_reception(s).get("retracted") for s in sources):
        found.add("retracted_source")
    if len(vgroups) > 1:
        found.add("vendor_gt1")
    # Uncounted sources (unresolved aggregators, type none) weigh nothing here, so adding one can
    # never lift a vendor-only claim out of the VENDOR cap.
    if counted and all(etype(s) == "vendor" for s in counted):
        found.add("vendor_only")
    if not counted:
        found.add("no_countable_sources")
    if any(_unresolved_aggregator(s) for s in sources):
        found.add("aggregator_unresolved")
    if 0 < len(members) < 3:
        found.add("lt3_independent")
    if len(primary) < 2:
        found.add("lt2_primary")
    if any(not s.get("independence_group") for s in counted):
        found.add("independence_unset")
    if any(etype(s) in RECEPTION_TYPES and not _reception(s).get("checked") for s in counted):
        found.add("reception_unchecked")
    if any(not s.get("quote") or not s.get("accessed") for s in counted):
        found.add("unretrieved_source")
    return [reason for reason in rl.REASONS if reason in found]


def cap_for(reasons: Sequence[str]) -> str:
    """The highest grade a claim with these reasons can hold."""
    reason_set = set(reasons)
    if "vendor_only" in reason_set:
        return "VENDOR"
    if "no_countable_sources" in reason_set:
        return "EMERGING"
    if reason_set & BLOCKING:
        return "CONTESTED"
    return "SETTLED"


@dataclass
class GradeResult:
    scope: Any
    asserted: str
    cap: Optional[str]
    cap_evidence: Optional[str]
    effective: str
    unverified: bool
    reasons: List[str]


@dataclass
class ClaimResult:
    id: str
    skipped: bool
    reasons: List[str]
    grades: List[GradeResult] = field(default_factory=list)


def evaluate_claim(claim_id: str, claim: Mapping[str, Any], enforced: bool) -> ClaimResult:
    """Cap every grade of one claim. Negated claims keep their asserted grade."""
    grades = claim.get("grades") or []
    if claim.get("polarity") == "negate":
        results = [
            GradeResult(g.get("scope"), g["asserted"], None, None, g["asserted"], False, [])
            for g in grades
        ]
        return ClaimResult(claim_id, True, [], results)
    reasons = compute_reasons(claim.get("sources") or [])
    cap = cap_for(reasons)
    cap_evidence = cap_for([r for r in reasons if r in rl.EVIDENCE_REASONS])
    has_debt = any(r in rl.DEBT_REASONS for r in reasons)
    results = []
    for g in grades:
        asserted = g["asserted"]
        effective = rl.lower_grade(asserted, cap if enforced else cap_evidence)
        # Flag only a grade shown above what the full cap allows; a grade already at its cap has
        # nothing left for enforcement to lower.
        unverified = rl.GRADE_RANK[cap] < rl.GRADE_RANK[effective] and has_debt
        results.append(GradeResult(g.get("scope"), asserted, cap, cap_evidence, effective, unverified, list(reasons)))
    return ClaimResult(claim_id, False, reasons, results)


def evaluate(sources: Mapping[str, Any]) -> Dict[str, ClaimResult]:
    enforced = bool((sources.get("meta") or {}).get("enforced"))
    return {cid: evaluate_claim(cid, claim, enforced) for cid, claim in (sources.get("claims") or {}).items()}


# --------------------------------------------------------------------------- #
# Prose markers
# --------------------------------------------------------------------------- #

def render_marker(line: str, marker: rl.Marker, grade: str, unverified: bool) -> str:
    """Marker text with ``grade`` in place of the old grade, qualifier kept, flag set."""
    core_end = line.index("]`", marker.start) + 2
    text = "`[" + grade + line[marker.start + 2 + len(marker.grade) : core_end]
    return text + (" " + UNVERIFIED_FLAG if unverified else "")


def rewrite_line(line: str, targets: Sequence[Tuple[str, bool]]) -> str:
    """Rewrite the grade markers on ``line`` to ``targets`` (grade, unverified), in order."""
    markers = rl.find_markers(line)
    if len(markers) != len(targets):
        raise ValueError(f"{len(markers)} markers, {len(targets)} grades")
    for marker, (grade, unverified) in reversed(list(zip(markers, targets))):
        line = line[: marker.start] + render_marker(line, marker, grade, unverified) + line[marker.end :]
    return line


def marker_drift(parsed: rl.ParsedResearch, results: Mapping[str, ClaimResult]) -> List[str]:
    errors = []
    anchors = parsed.claim_map()
    for cid, result in results.items():
        anchor = anchors.get(cid)
        if anchor is None or len(anchor.markers) != len(result.grades):
            continue
        for index, (marker, grade) in enumerate(zip(anchor.markers, result.grades)):
            if marker.grade != grade.effective or marker.unverified != grade.unverified:
                shown = marker.grade + (" UNVERIFIED" if marker.unverified else "")
                want = grade.effective + (" UNVERIFIED" if grade.unverified else "")
                errors.append(f"RESEARCH.md:{anchor.line_no}: claim {cid} marker {index} is {shown}, sidecar says {want}")
    return errors


# --------------------------------------------------------------------------- #
# Sidecar fields and compiled JSON
# --------------------------------------------------------------------------- #

def stored_fields(grade: Mapping[str, Any]) -> Tuple[Any, Any, Any, List[str]]:
    return (grade.get("cap"), grade.get("cap_evidence"), grade.get("unverified"), list(grade.get("cap_reasons") or []))


def expected_fields(result: GradeResult) -> Tuple[Any, Any, Any, List[str]]:
    return (result.cap, result.cap_evidence, result.unverified, result.reasons)


def stale_caps(sources: Mapping[str, Any], results: Mapping[str, ClaimResult]) -> List[str]:
    errors = []
    for cid, result in results.items():
        if result.skipped:
            continue
        grades = sources["claims"][cid].get("grades") or []
        for index, (grade, want) in enumerate(zip(grades, result.grades)):
            if stored_fields(grade) != expected_fields(want):
                errors.append(f"claim {cid} grade {index}: stored cap fields are stale; run grade_cap.py --write")
    return errors


def apply_caps(sources: Dict[str, Any], results: Mapping[str, ClaimResult]) -> None:
    """Store cap, cap_evidence, unverified and cap_reasons on each non-skipped grade."""
    for cid, result in results.items():
        if result.skipped:
            continue
        for grade, want in zip(sources["claims"][cid].get("grades") or [], result.grades):
            grade["cap"] = want.cap
            grade["cap_evidence"] = want.cap_evidence
            grade["unverified"] = want.unverified
            grade["cap_reasons"] = list(want.reasons)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot_sha256(research_sha: str, sources_sha: str) -> str:
    """Hash of both file hashes, research first, joined by a newline."""
    return sha256_bytes(f"{research_sha}\n{sources_sha}".encode("ascii"))


def research_version(text: str) -> Optional[str]:
    match = VERSION_RE.search(text)
    return match.group(1) if match else None


def rules_citing(sources: Mapping[str, Any]) -> Dict[str, List[str]]:
    citing: Dict[str, List[str]] = {}
    for rule_id, rule in (sources.get("rules") or {}).items():
        for cid in (rule or {}).get("claims") or []:
            citing.setdefault(cid, []).append(rule_id)
    return citing


def compile_claims(
    sources: Mapping[str, Any],
    research_text: str,
    research_bytes: bytes,
    sources_bytes: bytes,
    results: Mapping[str, ClaimResult],
) -> Dict[str, Any]:
    parsed = rl.parse_research(research_text)
    anchors = parsed.claim_map()
    citing = rules_citing(sources)
    research_sha = sha256_bytes(research_bytes)
    sources_sha = sha256_bytes(sources_bytes)
    counts = {grade: 0 for grade in rl.GRADES}
    counts["UNVERIFIED"] = 0
    claims = []
    for cid, claim in (sources.get("claims") or {}).items():
        result = results[cid]
        grades = []
        for grade in result.grades:
            counts[grade.effective] += 1
            counts["UNVERIFIED"] += int(grade.unverified)
            grades.append(
                {"scope": grade.scope, "asserted": grade.asserted, "effective": grade.effective, "unverified": grade.unverified}
            )
        line = anchors[cid].text if cid in anchors else ""
        claims.append(
            {
                "id": cid,
                "section": claim.get("section"),
                "grades": grades,
                "claim_sha256": rl.claim_sha256(cid, line, claim.get("sources") or []),
                "rules": citing.get(cid, []),
            }
        )
    rules = [
        {"id": rule_id, "basis": (rule or {}).get("basis"), "claims": list((rule or {}).get("claims") or [])}
        for rule_id, rule in (sources.get("rules") or {}).items()
    ]
    return {
        "schema": COMPILED_SCHEMA,
        "research_version": research_version(research_text),
        "sources_sha256": sources_sha,
        "research_sha256": research_sha,
        "snapshot_sha256": snapshot_sha256(research_sha, sources_sha),
        "enforced": bool((sources.get("meta") or {}).get("enforced")),
        "claims": claims,
        "rules": rules,
        "counts": counts,
    }


def dump_compiled(compiled: Mapping[str, Any]) -> str:
    return json.dumps(compiled, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------- #
# Change log
# --------------------------------------------------------------------------- #

def changelog_row(results: Mapping[str, ClaimResult], version: str, by: str, date: str) -> str:
    """One change-log row naming each grade that sits below its asserted grade."""
    moves = []
    flagged = 0
    for cid, result in results.items():
        for index, grade in enumerate(result.grades):
            flagged += int(grade.unverified)
            if grade.effective != grade.asserted:
                where = cid if len(result.grades) == 1 else f"{cid}#{index}"
                moves.append(f"{where} {grade.asserted}→{grade.effective}")
    lowered = f"{len(moves)} grade{'s' if len(moves) != 1 else ''} lowered"
    if moves:
        lowered += " (" + ", ".join(moves) + ")"
    change = f"grade_cap: {lowered}; {flagged} flagged `[UNVERIFIED]`."
    return f"| {version} | {date} | {by} | {change} |"


def check_changelog(base_text: str, head_text: str) -> Tuple[bool, str]:
    base_rows = rl.parse_research(base_text).changelog_rows
    head_rows = rl.parse_research(head_text).changelog_rows
    if head_rows[: len(base_rows)] != base_rows:
        for index, (old, new) in enumerate(zip(base_rows, head_rows)):
            if old != new:
                return False, f"ERROR: change-log row {index + 1} was edited; the change log is append-only"
        return False, f"ERROR: change log lost rows ({len(base_rows)} in base, {len(head_rows)} in head)"
    return True, f"OK: changelog append-only (+{len(head_rows) - len(base_rows)} rows)"


# --------------------------------------------------------------------------- #
# Debt queue and stats
# --------------------------------------------------------------------------- #

def source_work(source: Mapping[str, Any], counted_ids: set) -> List[str]:
    """What a single source still needs before it supports SETTLED."""
    needs = []
    if _unresolved_aggregator(source):
        needs.append("resolve")
    if id(source) in counted_ids:
        if not source.get("independence_group"):
            needs.append("independence_group")
        if etype(source) in RECEPTION_TYPES and not _reception(source).get("checked"):
            needs.append("reception")
        if not source.get("quote"):
            needs.append("quote")
        if not source.get("accessed"):
            needs.append("accessed")
    return needs


def debt_queue(sources: Mapping[str, Any], results: Mapping[str, ClaimResult]) -> List[Dict[str, Any]]:
    citing = rules_citing(sources)
    queue = []
    for cid, result in results.items():
        if result.skipped or not any(r in rl.DEBT_REASONS for r in result.reasons):
            continue
        claim_sources = sources["claims"][cid].get("sources") or []
        counted_ids = {id(s) for s in counted_sources(claim_sources)}
        work = {}
        for s in claim_sources:
            needs = source_work(s, counted_ids)
            if needs:
                work[str(s.get("id"))] = needs
        top = max((g.asserted for g in result.grades), key=lambda g: rl.GRADE_RANK[g], default=None)
        score = (
            3 * len(citing.get(cid, []))
            + 2 * int(top == "SETTLED")
            + int("aggregator_unresolved" in result.reasons)
        )
        cap = result.grades[0].cap if result.grades else cap_for(result.reasons)
        queue.append({"id": cid, "score": score, "asserted": top, "cap": cap, "reasons": result.reasons, "sources": work})
    queue.sort(key=lambda item: (-item["score"], item["id"]))
    return queue


def stats_lines(results: Mapping[str, ClaimResult]) -> List[str]:
    effective = {grade: 0 for grade in rl.GRADES}
    settled_if_enforced = 0
    unverified = 0
    histogram: Dict[str, int] = {reason: 0 for reason in rl.REASONS}
    skipped = 0
    for result in results.values():
        if result.skipped:
            skipped += 1
        for reason in result.reasons:
            histogram[reason] += 1
        for grade in result.grades:
            effective[grade.effective] += 1
            unverified += int(grade.unverified)
            # Negated claims have no methodology to survive, so they are counted only as skipped.
            if not result.skipped:
                settled_if_enforced += int(rl.lower_grade(grade.asserted, grade.cap) == "SETTLED")
    lines = [f"{grade}={count}" for grade, count in effective.items()]
    lines.append(f"SETTLED if enforced={settled_if_enforced}")
    lines.append(f"UNVERIFIED={unverified}")
    lines.append("reasons (claims):")
    lines.extend(f"  {reason}={count}" for reason, count in histogram.items() if count)
    lines.append(f"skipped_negate={skipped}")
    return lines


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

@dataclass
class Paths:
    repo: Path
    research: Path
    sources: Path
    claims_json: Path


def resolve_paths(args: argparse.Namespace) -> Paths:
    repo = Path(args.repo).resolve()

    def under_repo(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo / path

    return Paths(repo, under_repo(args.research), under_repo(args.sources), under_repo(args.claims_json))


def read_text(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _date_value(value: Any) -> Optional[dt.date]:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def load_inputs(paths: Paths) -> Tuple[Dict[str, Any], str]:
    return rl.load_sources(paths.sources), read_text(paths.research)


def cmd_check(paths: Paths) -> int:
    sources_text = read_text(paths.sources)
    research_text = read_text(paths.research)
    errors = rl.check_no_comments(sources_text)
    sources = rl.load_sources(paths.sources)
    parsed = rl.parse_research(research_text)
    errors += rl.validate(sources, parsed)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    results = evaluate(sources)
    errors += stale_caps(sources, results)
    errors += marker_drift(parsed, results)
    expected = compile_claims(sources, research_text, paths.research.read_bytes(), paths.sources.read_bytes(), results)
    name = paths.claims_json.name
    if not paths.claims_json.is_file():
        errors.append(f"{name}: missing; run grade_cap.py --write")
    else:
        try:
            stored = json.loads(read_text(paths.claims_json))
        except json.JSONDecodeError as exc:
            stored = {}
            errors.append(f"{name}: not valid JSON ({exc})")
        if stored and stored != expected:
            stale = [key for key in ("research_sha256", "sources_sha256") if stored.get(key) != expected[key]]
            errors.extend(f"{name}: {key} is stale; run grade_cap.py --write" for key in stale)
            if not stale:
                errors.append(f"{name}: content is stale; run grade_cap.py --write")

    meta = sources.get("meta") or {}
    enforced = bool(meta.get("enforced"))
    enforce_after = _date_value(meta.get("enforce_after"))
    if not enforced and enforce_after is not None and dt.date.today() >= enforce_after:
        message = f"enforce_after {enforce_after.isoformat()} has passed and meta.enforced is still false"
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::warning title=grade_cap::{message}")
        print(f"WARNING: {message}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    grade_count = sum(len(result.grades) for result in results.values())
    print(f"OK: {len(results)} claims, {grade_count} grades, caps current (enforced={str(enforced).lower()})")
    return 0


def cmd_write(paths: Paths) -> int:
    sources_text = read_text(paths.sources)
    comment_errors = rl.check_no_comments(sources_text)
    if comment_errors:
        for error in comment_errors:
            print(f"ERROR: {error}")
        return 1
    sources = rl.load_sources(paths.sources)
    research_text = read_text(paths.research)
    parsed = rl.parse_research(research_text)
    errors = rl.validate(sources, parsed)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("ERROR: fix the errors above before --write")
        return 1

    results = evaluate(sources)
    before = {cid: [stored_fields(g) for g in (sources["claims"][cid].get("grades") or [])] for cid in results}
    apply_caps(sources, results)

    lines = research_text.split("\n")
    anchors = parsed.claim_map()
    changes = []
    for cid, result in results.items():
        anchor = anchors[cid]
        old_line = lines[anchor.line_no - 1]
        new_line = rewrite_line(old_line, [(g.effective, g.unverified) for g in result.grades])
        lines[anchor.line_no - 1] = new_line
        if result.skipped:
            continue
        for index, grade in enumerate(result.grades):
            old_marker = anchor.markers[index]
            old = old_marker.grade + (" UNVERIFIED" if old_marker.unverified else "")
            new = grade.effective + (" UNVERIFIED" if grade.unverified else "")
            if old != new or before[cid][index] != expected_fields(grade):
                changes.append((cid, index, old, new, before[cid][index][0], grade.cap, ",".join(grade.reasons)))

    new_research = "\n".join(lines)
    rl.dump_sources(sources, paths.sources)
    write_text(paths.research, new_research)
    compiled = compile_claims(sources, new_research, paths.research.read_bytes(), paths.sources.read_bytes(), results)
    paths.claims_json.parent.mkdir(parents=True, exist_ok=True)
    write_text(paths.claims_json, dump_compiled(compiled))

    if changes:
        print("| claim | grade | marker | cap | reasons |")
        print("|---|---|---|---|---|")
        for cid, index, old, new, old_cap, new_cap, reasons in changes:
            print(f"| {cid} | {index} | {old} → {new} | {old_cap} → {new_cap} | {reasons} |")
    print(f"Wrote {len(changes)} change(s); compiled {len(results)} claims to {paths.claims_json.name}")
    return 0


def cmd_stats(paths: Paths) -> int:
    sources = rl.load_sources(paths.sources)
    for line in stats_lines(evaluate(sources)):
        print(line)
    return 0


def cmd_debt(paths: Paths, limit: int, as_json: bool) -> int:
    sources = rl.load_sources(paths.sources)
    queue = debt_queue(sources, evaluate(sources))[:limit]
    if as_json:
        print(json.dumps(queue, indent=2, ensure_ascii=False))
        return 0
    for item in queue:
        work = "; ".join(f"{sid}: {','.join(needs)}" for sid, needs in item["sources"].items()) or "-"
        print(f"{item['id']}\t{item['asserted']}→{item['cap']}\t{','.join(item['reasons'])}\t{work}")
    return 0


def cmd_changelog_row(paths: Paths, version: str, by: str, date: Optional[str]) -> int:
    sources = rl.load_sources(paths.sources)
    print(changelog_row(evaluate(sources), version, by, date or dt.date.today().isoformat()))
    return 0


def cmd_check_changelog(paths: Paths, base: str) -> int:
    try:
        rel = paths.research.resolve().relative_to(paths.repo).as_posix()
    except ValueError:
        print(f"ERROR: {paths.research.name} is outside --repo")
        return 2
    proc = subprocess.run(
        ["git", "show", f"{base}:{rel}"],
        cwd=paths.repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        print(f"ERROR: git show {base}:{rel} failed: {proc.stderr.strip()}")
        return 1
    ok, message = check_changelog(proc.stdout, read_text(paths.research))
    print(message)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cap RESEARCH.md grades by the sources in sources.yaml.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="store caps, rewrite markers, compile claims.json")
    mode.add_argument("--check", action="store_true", help="exit 1 when caps, markers or claims.json are stale")
    mode.add_argument("--stats", action="store_true", help="grade counts, reason histogram, skipped_negate")
    mode.add_argument("--debt", action="store_true", help="claims with source debt, highest score first")
    mode.add_argument("--changelog-row", action="store_true", help="print a change-log row for the grade moves")
    mode.add_argument("--check-changelog", action="store_true", help="exit 1 unless the change log only grew")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="checkout root; path flags resolve against it")
    parser.add_argument("--research", default=DEFAULT_RESEARCH)
    parser.add_argument("--sources", default=DEFAULT_SOURCES)
    parser.add_argument("--claims-json", default=DEFAULT_CLAIMS_JSON)
    parser.add_argument("--limit", type=int, default=10, help="--debt: rows to print")
    parser.add_argument("--json", action="store_true", help="--debt: print JSON")
    parser.add_argument("--version", help="--changelog-row: RESEARCH.md version")
    parser.add_argument("--by", help="--changelog-row: author column")
    parser.add_argument("--date", help="--changelog-row: date column (default today)")
    parser.add_argument("--base", help="--check-changelog: git ref to compare against")
    return parser


def use_utf8_output() -> None:
    """Print arrows and names as UTF-8 even where the console default is a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    use_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.changelog_row and not (args.version and args.by):
        parser.error("--changelog-row needs --version and --by")
    if args.check_changelog and not args.base:
        parser.error("--check-changelog needs --base")
    paths = resolve_paths(args)
    try:
        if args.check_changelog:
            return cmd_check_changelog(paths, args.base)
        if args.write:
            return cmd_write(paths)
        if args.check:
            return cmd_check(paths)
        if args.stats:
            return cmd_stats(paths)
        if args.debt:
            return cmd_debt(paths, args.limit, args.json)
        return cmd_changelog_row(paths, args.version, args.by, args.date)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc.filename}: not found")
        return 1
    except (rl.SourcesError, rl.yaml.YAMLError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
