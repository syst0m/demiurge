#!/usr/bin/env python3
"""
anchor_claims.py - One-off bootstrap of claim anchors and the sources sidecar.

Usage:
    python scripts/research/anchor_claims.py --idmap scratch/idmap.tsv [--research research/RESEARCH.md]
                                             [--sources research/sources.yaml] [--stats] [--write] [--force]

Reads an id map (TSV: ``line<TAB>id[<TAB>kind]``, 1-based line numbers of the
unanchored file; ``#`` lines, blank lines and a ``line`` header row are
ignored). An id starting with ``R-`` is a rule anchor, any other id a claim
anchor. Every graded line outside the legend, change log and fences that the
map does not name gets the default id ``sec.s<section>-l<line>``.

Anchors go after the list or blockquote marker, inside the first table cell,
after the heading hashes, or at the start of a prose line. Each insertion is
``<!-- claim:<id> --> `` so that stripping anchors restores the input byte for
byte. The sidecar skeleton takes its grades from the markers and its sources
from the markdown links on the line, typed by host with ``HOST_TYPES``. It
carries no caps; ``grade_cap.py`` computes them.

Without ``--write`` the planned anchors are printed and nothing changes.
``--stats`` prints ``markers_found=N markers_assigned=N claims=C rules=R`` and
exits 1 when the two marker counts differ. ``--write`` refuses when the counts
differ, when the result fails ``research_lib.validate``, when the file already
carries anchors, or when the sidecar exists and ``--force`` is absent.
``--force`` still refuses a sidecar that git tracks and that has uncommitted
changes.

Exit codes:
    0  clean
    1  marker counts differ, or the anchored result does not validate
    2  usage error: bad id map, unreadable input, or a refused overwrite
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

import research_lib as rl

KIND_BULLET = "bullet"
KIND_TABLE = "table_row"
KIND_HEADER = "header"
KIND_PROSE = "prose"

DEFAULT_ID_PREFIX = "sec"

# Host suffix -> source type. The longest matching suffix wins; ``www.`` is ignored.
HOST_TYPES: Dict[str, str] = {
    "consensus.app": "aggregator",
    "scholar.google.com": "aggregator",
    "semanticscholar.org": "aggregator",
    "elicit.com": "aggregator",
    "scite.ai": "aggregator",
    "arxiv.org": "preprint",
    "biorxiv.org": "preprint",
    "medrxiv.org": "preprint",
    "ssrn.com": "preprint",
    "openreview.net": "preprint",
    "huggingface.co": "preprint",
    "doi.org": "peer",
    "aclanthology.org": "peer",
    "proceedings.neurips.cc": "peer",
    "proceedings.mlr.press": "peer",
    "dl.acm.org": "peer",
    "ieeexplore.ieee.org": "peer",
    "link.springer.com": "peer",
    "nature.com": "peer",
    "science.org": "peer",
    "sciencedirect.com": "peer",
    "usenix.org": "peer",
    "modelcontextprotocol.io": "spec",
    "agentskills.io": "spec",
    "aaif.io": "spec",
    "w3.org": "spec",
    "ietf.org": "spec",
    "rfc-editor.org": "spec",
    "owasp.org": "spec",
    "nist.gov": "spec",
    "anthropic.com": "vendor",
    "claude.com": "vendor",
    "openai.com": "vendor",
    "cursor.com": "vendor",
    "cognition.ai": "vendor",
    "manus.im": "vendor",
    "deepmind.google": "vendor",
    "ai.google.dev": "vendor",
    "blog.google": "vendor",
    "microsoft.com": "vendor",
    "github.blog": "vendor",
    "langchain.com": "vendor",
    "github.com": "practitioner",
    "github.io": "practitioner",
    "medium.com": "practitioner",
    "substack.com": "practitioner",
    "simonwillison.net": "practitioner",
    "martinfowler.com": "practitioner",
}
# arXiv DOIs resolve to preprints, not to peer-reviewed venues.
DOI_PREPRINT_PREFIXES = ("10.48550/",)
UNKNOWN_HOST_TYPE = "practitioner"

SECTION_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s*(.*?)\s*$")
NEGATE_SECTION_TITLES = {"hype"}
LINK_RE = re.compile(r"(?<!!)\[(?P<title>[^\]]*)\]\((?P<url>https?://[^)\s]+)\)")
VENDOR_TAG_AFTER_LINK_RE = re.compile(r"\s*`\[VENDOR\]`")
SCOPE_AFTER_MARKER_RE = re.compile(r"^\s+(?:as|for)\s+([^.,;:`(\[]+?)\s*(?=[.,;:`(\[]|$)")
TABLE_PREFIX_RE = re.compile(r"^\s*\|")
HEADER_PREFIX_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+")
LIST_PREFIX_RE = re.compile(r"^(?P<quote>(?:[ \t]*>[ \t]?)*)(?P<list>[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]+)?")
IDMAP_KINDS = (KIND_PROSE, KIND_BULLET, KIND_TABLE, KIND_HEADER)


class UsageError(Exception):
    """A bad id map or a refused operation; exit code 2."""


@dataclass
class Placement:
    line_no: int
    anchor_id: str
    is_rule: bool
    kind: str
    offset: int
    defaulted: bool = False


@dataclass
class Plan:
    placements: List[Placement] = field(default_factory=list)
    anchored_text: str = ""
    sidecar: Dict[str, Any] = field(default_factory=dict)
    markers_found: int = 0
    markers_assigned: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def claim_count(self) -> int:
        return sum(1 for p in self.placements if not p.is_rule)

    @property
    def rule_count(self) -> int:
        return sum(1 for p in self.placements if p.is_rule)

    @property
    def defaulted_count(self) -> int:
        return sum(1 for p in self.placements if p.defaulted)

    def stats_line(self) -> str:
        return (
            f"markers_found={self.markers_found} markers_assigned={self.markers_assigned} "
            f"claims={self.claim_count} rules={self.rule_count}"
        )


# --------------------------------------------------------------------------- #
# Id map
# --------------------------------------------------------------------------- #

def parse_idmap(text: str) -> List[Tuple[int, str, Optional[str]]]:
    """Parse ``line<TAB>id[<TAB>kind]`` rows; raise UsageError on any bad row."""
    rows: List[Tuple[int, str, Optional[str]]] = []
    seen_lines: Dict[int, str] = {}
    seen_ids: Dict[str, int] = {}
    for row_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        cols = [col.strip() for col in raw.split("\t")]
        if row_no == 1 and cols[0].lower() == "line":
            continue
        if len(cols) < 2 or len(cols) > 3:
            raise UsageError(f"idmap row {row_no}: expected line<TAB>id[<TAB>kind], got {raw!r}")
        if not cols[0].isdigit() or int(cols[0]) < 1:
            raise UsageError(f"idmap row {row_no}: line {cols[0]!r} is not a positive integer")
        line_no, anchor_id = int(cols[0]), cols[1]
        kind = cols[2] if len(cols) == 3 and cols[2] else None
        is_rule = anchor_id.startswith("R-")
        pattern = rl.RULE_ID_RE if is_rule else rl.CLAIM_ID_RE
        if not pattern.match(anchor_id):
            raise UsageError(f"idmap row {row_no}: id {anchor_id!r} does not match {pattern.pattern}")
        if kind is not None and kind not in IDMAP_KINDS:
            raise UsageError(f"idmap row {row_no}: kind {kind!r} not in {{{', '.join(IDMAP_KINDS)}}}")
        if line_no in seen_lines:
            raise UsageError(f"idmap row {row_no}: line {line_no} already mapped to {seen_lines[line_no]}")
        if anchor_id in seen_ids:
            raise UsageError(f"idmap row {row_no}: id {anchor_id} already mapped to line {seen_ids[anchor_id]}")
        seen_lines[line_no] = anchor_id
        seen_ids[anchor_id] = line_no
        rows.append((line_no, anchor_id, kind))
    return rows


# --------------------------------------------------------------------------- #
# Line analysis
# --------------------------------------------------------------------------- #

def line_kind_and_offset(line: str) -> Tuple[str, int]:
    """Where an anchor goes on ``line`` and the kind of line it is."""
    table = TABLE_PREFIX_RE.match(line)
    if table:
        return KIND_TABLE, table.end() + (1 if line[table.end() : table.end() + 1] == " " else 0)
    header = HEADER_PREFIX_RE.match(line)
    if header:
        return KIND_HEADER, header.end()
    prefix = LIST_PREFIX_RE.match(line)
    offset = prefix.end() if prefix else 0
    if prefix and prefix.group("list"):
        return KIND_BULLET, offset
    return KIND_PROSE, offset


def section_map(lines: Sequence[str]) -> Tuple[List[int], List[str]]:
    """Section number and section title in force at each line (0 and '' before the first)."""
    numbers: List[int] = []
    titles: List[str] = []
    number, title = 0, ""
    for line in lines:
        match = SECTION_HEADING_RE.match(line)
        if match:
            number, title = int(match.group(1)), match.group(2)
        elif line.startswith("## "):
            number, title = 0, line[3:].strip()
        numbers.append(number)
        titles.append(title)
    return numbers, titles


def classify_url(url: str) -> str:
    """Source type for ``url`` from ``HOST_TYPES``; unknown hosts are practitioner sources."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "doi.org" or host == "dx.doi.org":
        doi = parts.path.lstrip("/").lower()
        if doi.startswith(DOI_PREPRINT_PREFIXES):
            return "preprint"
    best = ""
    for suffix in HOST_TYPES:
        if (host == suffix or host.endswith("." + suffix)) and len(suffix) > len(best):
            best = suffix
    return HOST_TYPES[best] if best else UNKNOWN_HOST_TYPE


def link_sources(line: str) -> List[Dict[str, Any]]:
    """One skeleton source per markdown link on ``line``, in reading order."""
    sources: List[Dict[str, Any]] = []
    for match in LINK_RE.finditer(line):
        source_type = classify_url(match.group("url"))
        if VENDOR_TAG_AFTER_LINK_RE.match(line, match.end()):
            source_type = "vendor"
        sources.append(
            {
                "id": f"s{len(sources) + 1}",
                "url": match.group("url"),
                "title": " ".join(match.group("title").split()),
                "type": source_type,
                "resolves_to": None,
                "resolves_to_type": None,
                "independence_group": None,
                "supports": "confirms",
                "quote": None,
                "accessed": None,
                "reception": {"checked": False, "retracted": None, "scite_supporting": None, "scite_contrasting": None},
            }
        )
    return sources


def marker_scope(line: str, marker: rl.Marker) -> Optional[str]:
    """The ``as ...`` or ``for ...`` phrase right after a marker, without the preposition."""
    match = SCOPE_AFTER_MARKER_RE.match(line[marker.end :])
    return match.group(1) if match else None


def skeleton_grades(line: str) -> List[Dict[str, Any]]:
    return [
        {
            "scope": marker_scope(line, marker),
            "asserted": marker.grade,
            "cap": None,
            "cap_evidence": None,
            "unverified": False,
            "cap_reasons": [],
        }
        for marker in rl.find_markers(line)
    ]


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #

def build_plan(research_text: str, idmap_rows: Sequence[Tuple[int, str, Optional[str]]]) -> Plan:
    """Place anchors, build the sidecar skeleton and count markers; does not write."""
    if rl.ANY_ANCHOR_RE.search(research_text):
        raise UsageError("research file already carries claim or rule anchors; bootstrap runs once")
    lines = research_text.split("\n")
    plan = Plan()

    original = rl.parse_research(research_text)
    plan.markers_found = sum(len(rl.find_markers(lines[n - 1])) for n in original.unanchored_marker_lines)

    mapped: Dict[int, Tuple[str, Optional[str]]] = {}
    for line_no, anchor_id, kind in idmap_rows:
        if line_no > len(lines):
            raise UsageError(f"idmap line {line_no} is past the end of the file ({len(lines)} lines)")
        if not lines[line_no - 1].strip():
            raise UsageError(f"idmap line {line_no} is blank")
        mapped[line_no] = (anchor_id, kind)

    numbers, _ = section_map(lines)
    defaulted = set()
    for line_no in original.unanchored_marker_lines:
        if line_no not in mapped:
            default_id = f"{DEFAULT_ID_PREFIX}.s{numbers[line_no - 1]}-l{line_no}"
            if default_id in {anchor_id for anchor_id, _ in mapped.values()}:
                raise UsageError(f"idmap already uses the default id {default_id} for another line")
            mapped[line_no] = (default_id, None)
            defaulted.add(line_no)

    for line_no in sorted(mapped):
        anchor_id, kind_override = mapped[line_no]
        kind, offset = line_kind_and_offset(lines[line_no - 1])
        plan.placements.append(
            Placement(
                line_no=line_no,
                anchor_id=anchor_id,
                is_rule=anchor_id.startswith("R-"),
                kind=kind_override or kind,
                offset=offset,
                defaulted=line_no in defaulted,
            )
        )

    anchored = list(lines)
    for placement in plan.placements:
        tag = "rule" if placement.is_rule else "claim"
        line = anchored[placement.line_no - 1]
        anchored[placement.line_no - 1] = (
            line[: placement.offset] + f"<!-- {tag}:{placement.anchor_id} --> " + line[placement.offset :]
        )
    plan.anchored_text = "\n".join(anchored)

    parsed = rl.parse_research(plan.anchored_text)
    placed_claims = {c.id: c for c in parsed.claims}
    placed_rules = {r.id for r in parsed.rules}
    for placement in plan.placements:
        found = placed_rules if placement.is_rule else placed_claims
        if placement.anchor_id not in found:
            plan.errors.append(
                f"line {placement.line_no}: {placement.anchor_id} sits in a fence, the legend or the change log"
            )
    plan.markers_assigned = sum(len(c.markers) for c in parsed.claims)
    plan.sidecar = build_sidecar(lines, plan.placements)
    if plan.markers_found == plan.markers_assigned:
        plan.errors.extend(rl.validate(plan.sidecar, parsed))
    return plan


def build_sidecar(lines: Sequence[str], placements: Sequence[Placement]) -> Dict[str, Any]:
    numbers, titles = section_map(lines)
    claims: Dict[str, Any] = {}
    rules: Dict[str, Any] = {}
    for placement in placements:
        line = lines[placement.line_no - 1]
        section = numbers[placement.line_no - 1]
        if placement.is_rule:
            rules[placement.anchor_id] = {"section": section, "basis": None, "claims": []}
            continue
        negate = titles[placement.line_no - 1].strip().lower() in NEGATE_SECTION_TITLES
        claims[placement.anchor_id] = {
            "section": section,
            "kind": placement.kind,
            "population": "any",
            "polarity": "negate" if negate else "affirm",
            "grades": skeleton_grades(line),
            "sources": link_sources(line),
            "duplicates": [],
            "last_verified": None,
            "verified_by": None,
            "notes": "",
        }
    return {
        "schema": rl.SOURCES_SCHEMA,
        "meta": {"enforced": False, "enforce_after": None},
        "claims": claims,
        "rules": rules,
    }


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

def _git(args: Sequence[str], cwd: Path) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)
    except OSError:
        return None


def sidecar_is_tracked_and_dirty(path: Path) -> bool:
    """True when git tracks ``path`` and it differs from HEAD or the index."""
    cwd = path.parent if path.parent.is_dir() else Path.cwd()
    tracked = _git(["ls-files", "--error-unmatch", "--", path.name], cwd)
    if tracked is None or tracked.returncode != 0:
        return False
    status = _git(["status", "--porcelain", "--", path.name], cwd)
    return status is not None and bool(status.stdout.strip())


def check_overwrite(sources_path: Path, force: bool) -> None:
    if not sources_path.exists():
        return
    if not force:
        raise UsageError(f"{sources_path} exists; pass --force to overwrite it")
    if sidecar_is_tracked_and_dirty(sources_path):
        raise UsageError(f"{sources_path} is tracked and has uncommitted changes; commit or discard them first")


def write_outputs(plan: Plan, research_path: Path, sources_path: Path) -> None:
    sidecar_text = rl.dump_sources(plan.sidecar)
    comment_errors = rl.check_no_comments(sidecar_text)
    if comment_errors:
        raise UsageError("generated sidecar carries YAML comments: " + "; ".join(comment_errors))
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    sources_path.write_bytes(sidecar_text.encode("utf-8"))
    research_path.write_bytes(plan.anchored_text.encode("utf-8"))


def format_plan(plan: Plan) -> str:
    rows = ["line\tanchor\tkind\tgrades\tsources"]
    for placement in plan.placements:
        if placement.is_rule:
            rows.append(f"{placement.line_no}\t{placement.anchor_id}\trule\t-\t-")
            continue
        claim = plan.sidecar["claims"].get(placement.anchor_id, {})
        grades = ",".join(g["asserted"] for g in claim.get("grades", [])) or "-"
        marker = " (default id)" if placement.defaulted else ""
        rows.append(
            f"{placement.line_no}\t{placement.anchor_id}{marker}\t{placement.kind}\t{grades}\t{len(claim.get('sources', []))}"
        )
    return "\n".join(rows)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap claim anchors in RESEARCH.md and the sources.yaml skeleton.")
    parser.add_argument("--research", default="research/RESEARCH.md", help="RESEARCH.md to anchor")
    parser.add_argument("--idmap", required=True, help="TSV id map: line<TAB>id[<TAB>kind]")
    parser.add_argument("--sources", help="sidecar to write (default: sources.yaml beside --research)")
    parser.add_argument("--stats", action="store_true", help="print marker counts; exit 1 if found != assigned")
    parser.add_argument("--write", action="store_true", help="write the anchored file and the sidecar")
    parser.add_argument("--force", action="store_true", help="overwrite an existing sidecar that has no uncommitted changes")
    args = parser.parse_args(argv)

    research_path = Path(args.research)
    sources_path = Path(args.sources) if args.sources else research_path.parent / "sources.yaml"
    try:
        research_text = research_path.read_bytes().decode("utf-8")
        idmap_text = Path(args.idmap).read_text(encoding="utf-8")
        plan = build_plan(research_text, parse_idmap(idmap_text))
        if args.write:
            check_overwrite(sources_path, args.force)
    except (OSError, UnicodeDecodeError, UsageError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    mismatch = plan.markers_found != plan.markers_assigned
    if not args.stats:
        print(format_plan(plan))
    print(plan.stats_line())
    if plan.defaulted_count:
        print(f"default_ids={plan.defaulted_count}")
    if mismatch:
        print(
            f"ERROR: {plan.markers_found - plan.markers_assigned} graded markers sit on lines without a claim anchor",
            file=sys.stderr,
        )
        return 1
    if plan.errors:
        for error in plan.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.write:
        try:
            write_outputs(plan, research_path, sources_path)
        except (OSError, UsageError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {research_path} and {sources_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
