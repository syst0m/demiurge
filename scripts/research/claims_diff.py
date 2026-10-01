#!/usr/bin/env python3
"""
claims_diff.py - Classify the grade changes between two states of the claims ledger.

Reads ``research/RESEARCH.md`` and ``research/sources.yaml`` at a base ref and
at a head ref (or the working tree), recomputes every grade with
``grade_cap.evaluate`` on both sides and reports what moved. Stored caps in
the sidecar are ignored, so a PR cannot hide an upgrade by editing them.

The diff is ``upgrade`` when any of these holds:
  - an asserted or effective grade rises
  - a new claim has an effective grade of CONTESTED or higher
  - a claim is removed, or a claim's grade count changes
  - ``meta.enforced`` changes from true to false
  - the changed paths touch ``scripts/research/**``, ``.github/**`` or
    ``requirements-dev.txt``
Otherwise it is ``downgrade-or-sourcing``.

Usage:
    python scripts/research/claims_diff.py --base origin/main --head HEAD --json
    python scripts/research/claims_diff.py --base origin/main --head WORKTREE --markdown

Path flags (--research, --sources) are repo-relative; --repo defaults to this
checkout. Markdown is the default output.

Exit codes:
    0  downgrade-or-sourcing
    1  git or input error
    2  usage error or missing dependency
    10 upgrade
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import grade_cap as gc
import research_lib as rl

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RESEARCH = "research/RESEARCH.md"
DEFAULT_SOURCES = "research/sources.yaml"
WORKTREE = "WORKTREE"
DIFF_SCHEMA = "demiurge.claims_diff.v1"

UPGRADE = "upgrade"
DOWNGRADE_OR_SOURCING = "downgrade-or-sourcing"
EXIT_UPGRADE = 10

# requirements-dev.txt is here because it decides which packages the gate scripts import.
TOOLING_PREFIXES = ("scripts/research/", ".github/", "requirements-dev.txt")
SCOPE_PREFIXES = ("research/", "skills/marcus/references/")
NEW_CLAIM_UPGRADE_RANK = rl.GRADE_RANK["CONTESTED"]


class DiffError(RuntimeError):
    """Raised when git or an input file cannot be read."""


# --------------------------------------------------------------------------- #
# Reading a ledger state
# --------------------------------------------------------------------------- #

def git(repo: Path, args: Sequence[str]) -> bytes:
    proc = subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise DiffError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout


def read_at(repo: Path, ref: str, rel: str) -> Optional[str]:
    """File text at ``ref`` (or the working tree), or None when the file is absent there."""
    if ref == WORKTREE:
        path = repo / rel
        if not path.is_file():
            return None
        return path.read_bytes().decode("utf-8")
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{rel}"], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
        return None
    return git(repo, ["show", f"{ref}:{rel}"]).decode("utf-8")


@dataclass
class LedgerState:
    sources: Dict[str, Any]
    anchors: Dict[str, rl.ClaimAnchor]
    results: Dict[str, gc.ClaimResult]

    @property
    def enforced(self) -> bool:
        return bool((self.sources.get("meta") or {}).get("enforced"))

    @property
    def claims(self) -> Dict[str, Any]:
        return self.sources.get("claims") or {}

    @property
    def rules(self) -> Dict[str, Any]:
        return self.sources.get("rules") or {}

    def claim_sha256(self, cid: str) -> str:
        line = self.anchors[cid].text if cid in self.anchors else ""
        return rl.claim_sha256(cid, line, self.claims[cid].get("sources") or [])


def load_state(repo: Path, ref: str, research_rel: str, sources_rel: str) -> LedgerState:
    sources_text = read_at(repo, ref, sources_rel)
    research_text = read_at(repo, ref, research_rel) or ""
    sources: Dict[str, Any] = {}
    if sources_text is not None:
        loaded = rl.yaml.safe_load(sources_text)
        if not isinstance(loaded, dict):
            raise DiffError(f"{ref}:{sources_rel}: top level is not a mapping")
        sources = loaded
    anchors = rl.parse_research(research_text).claim_map()
    return LedgerState(sources, anchors, gc.evaluate(sources))


def changed_paths(repo: Path, base: str, head: str) -> List[str]:
    """Paths changed since the merge base of ``base`` and ``head``; untracked files count for WORKTREE."""
    if head == WORKTREE:
        merge_base = git(repo, ["merge-base", base, "HEAD"]).decode("ascii").strip()
        out = git(repo, ["diff", "--name-only", merge_base])
        out += git(repo, ["ls-files", "--others", "--exclude-standard"])
    else:
        out = git(repo, ["diff", "--name-only", f"{base}...{head}"])
    return sorted({line for line in out.decode("utf-8").splitlines() if line})


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #

def _rank(grade: Optional[str]) -> int:
    return rl.GRADE_RANK.get(grade or "", 0)


def _grade_view(grade: gc.GradeResult) -> Dict[str, Any]:
    return {
        "scope": grade.scope,
        "asserted": grade.asserted,
        "effective": grade.effective,
        "unverified": grade.unverified,
    }


def _source_ids(claim: Mapping[str, Any], predicate) -> set:
    return {str(s.get("id")) for s in claim.get("sources") or [] if isinstance(s, dict) and predicate(s)}


def _is_contrasting(source: Mapping[str, Any]) -> bool:
    return source.get("supports") == "contrasts"


def _is_retracted(source: Mapping[str, Any]) -> bool:
    reception = source.get("reception")
    return isinstance(reception, dict) and bool(reception.get("retracted"))


def _source_key(source: Mapping[str, Any]) -> str:
    return json.dumps(source, sort_keys=True, default=str)


def compare_claim(cid: str, base: LedgerState, head: LedgerState) -> Dict[str, Any]:
    """One entry of the ``claims`` list: status, grade moves and source changes."""
    in_base, in_head = cid in base.claims, cid in head.claims
    base_claim = base.claims.get(cid) or {}
    head_claim = head.claims.get(cid) or {}
    base_grades = base.results[cid].grades if in_base else []
    head_grades = head.results[cid].grades if in_head else []

    upgrade_reasons: List[str] = []
    moves = []
    if in_base and in_head:
        for index, (old, new) in enumerate(zip(base_grades, head_grades)):
            if (old.asserted, old.effective, old.unverified) == (new.asserted, new.effective, new.unverified):
                continue
            rose = _rank(new.asserted) > _rank(old.asserted) or _rank(new.effective) > _rank(old.effective)
            fell = _rank(new.asserted) < _rank(old.asserted) or _rank(new.effective) < _rank(old.effective)
            direction = "up" if rose else "down" if fell else "flag"
            moves.append({"index": index, "base": _grade_view(old), "head": _grade_view(new), "direction": direction})
            if _rank(new.asserted) > _rank(old.asserted):
                upgrade_reasons.append(f"grade {index} asserted {old.asserted}→{new.asserted}")
            if _rank(new.effective) > _rank(old.effective):
                upgrade_reasons.append(f"grade {index} effective {old.effective}→{new.effective}")
        if len(base_grades) != len(head_grades):
            upgrade_reasons.append(f"grade count {len(base_grades)}→{len(head_grades)}")
        status = "changed"
    elif in_head:
        status = "new"
        top = max((g.effective for g in head_grades), key=_rank, default=None)
        if _rank(top) >= NEW_CLAIM_UPGRADE_RANK:
            upgrade_reasons.append(f"new claim at {top}")
    else:
        status = "removed"
        upgrade_reasons.append("claim removed")

    base_sources = {_source_key(s) for s in base_claim.get("sources") or []}
    head_sources = {_source_key(s) for s in head_claim.get("sources") or []}
    sources_changed = in_base and in_head and base_sources != head_sources
    base_ids = _source_ids(base_claim, lambda s: True)
    head_ids = _source_ids(head_claim, lambda s: True)
    new_contrasting = sorted(_source_ids(head_claim, _is_contrasting) - _source_ids(base_claim, _is_contrasting))
    new_retracted = sorted(_source_ids(head_claim, _is_retracted) - _source_ids(base_claim, _is_retracted))

    text_changed = False
    if in_base and in_head:
        text_changed = base.claim_sha256(cid) != head.claim_sha256(cid)
    if status == "changed" and not moves and not upgrade_reasons and not sources_changed and not text_changed:
        status = "unchanged"

    return {
        "id": cid,
        "status": status,
        "section": (head_claim or base_claim).get("section"),
        "upgrade": bool(upgrade_reasons),
        "upgrade_reasons": upgrade_reasons,
        "base": {"grades": [_grade_view(g) for g in base_grades], "claim_sha256": base.claim_sha256(cid)} if in_base else None,
        "head": {"grades": [_grade_view(g) for g in head_grades], "claim_sha256": head.claim_sha256(cid)} if in_head else None,
        "grade_moves": moves,
        "sources_changed": sources_changed,
        "text_changed": text_changed,
        "sources_added": sorted(head_ids - base_ids) if in_base else [],
        "sources_removed": sorted(base_ids - head_ids) if in_head else [],
        "new_contrasting": new_contrasting,
        "new_retracted": new_retracted,
    }


def rule_floor(state: LedgerState, rule: Mapping[str, Any]) -> Optional[str]:
    """Lowest effective grade among the claims a rule cites; None when it cites none."""
    grades = [
        g.effective
        for cid in (rule or {}).get("claims") or []
        if cid in state.results
        for g in state.results[cid].grades
    ]
    return min(grades, key=_rank, default=None)


def rule_consequences(base: LedgerState, head: LedgerState, touched: set) -> List[Dict[str, Any]]:
    """Rules whose cited claims moved, or whose citations or basis changed."""
    out = []
    for rule_id in sorted(set(base.rules) | set(head.rules)):
        old = base.rules.get(rule_id)
        new = head.rules.get(rule_id)
        old_claims = list((old or {}).get("claims") or [])
        new_claims = list((new or {}).get("claims") or [])
        moved = sorted(touched & (set(old_claims) | set(new_claims)))
        edited = old is None or new is None or old_claims != new_claims or (old or {}).get("basis") != (new or {}).get("basis")
        if not moved and not edited:
            continue
        out.append(
            {
                "id": rule_id,
                "status": "new" if old is None else "removed" if new is None else "changed",
                "basis": {"base": (old or {}).get("basis"), "head": (new or {}).get("basis")},
                "claims": {"base": old_claims, "head": new_claims},
                "moved_claims": moved,
                "floor": {
                    "base": rule_floor(base, old) if old is not None else None,
                    "head": rule_floor(head, new) if new is not None else None,
                },
            }
        )
    return out


def build_diff(repo: Path, base_ref: str, head_ref: str, research_rel: str, sources_rel: str) -> Dict[str, Any]:
    base = load_state(repo, base_ref, research_rel, sources_rel)
    head = load_state(repo, head_ref, research_rel, sources_rel)
    paths = changed_paths(repo, base_ref, head_ref)
    tooling = [p for p in paths if p.startswith(TOOLING_PREFIXES)]
    out_of_scope = [p for p in paths if not p.startswith(SCOPE_PREFIXES)]

    ids = list(base.claims) + [cid for cid in head.claims if cid not in base.claims]
    claims = [compare_claim(cid, base, head) for cid in ids]
    touched = {c["id"] for c in claims if c["status"] != "unchanged"}

    reasons: List[str] = []
    for entry in claims:
        reasons.extend(f"{entry['id']}: {reason}" for reason in entry["upgrade_reasons"])
    if base.enforced and not head.enforced:
        reasons.append("meta.enforced true→false")
    if tooling:
        reasons.append("tooling changed: " + ", ".join(tooling))

    upgraded = [c["id"] for c in claims if c["upgrade"] and c["status"] != "removed"]
    new = [c["id"] for c in claims if c["status"] == "new"]
    verify_ids = upgraded + [cid for cid in new if cid not in upgraded]
    by_id = {c["id"]: c for c in claims}
    return {
        "schema": DIFF_SCHEMA,
        "base": base_ref,
        "head": head_ref,
        "class": UPGRADE if reasons else DOWNGRADE_OR_SOURCING,
        "upgrade_reasons": reasons,
        "tooling_changed": bool(tooling),
        "changed_paths": paths,
        "out_of_scope_paths": out_of_scope,
        "enforced": {"base": base.enforced, "head": head.enforced},
        "upgraded_claims": upgraded,
        "new_claims": new,
        "removed_claims": [c["id"] for c in claims if c["status"] == "removed"],
        "needs_verification": [{"id": cid, "claim_sha256": by_id[cid]["head"]["claim_sha256"]} for cid in verify_ids],
        "claims": claims,
        "rules": rule_consequences(base, head, touched),
    }


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #

def _grades_text(side: Optional[Mapping[str, Any]]) -> str:
    if not side:
        return "-"
    parts = []
    for g in side["grades"]:
        text = g["effective"] if g["effective"] == g["asserted"] else f"{g['effective']} (asserted {g['asserted']})"
        parts.append(text + _flag(g))
    return ", ".join(parts) or "no grades"


def _flag(grade: Mapping[str, Any]) -> str:
    return " UNVERIFIED" if grade["unverified"] else ""


def _move_text(move: Mapping[str, Any]) -> str:
    old, new = move["base"], move["head"]
    return (
        f"grade {move['index']}: {old['asserted']}/{old['effective']}{_flag(old)} → "
        f"{new['asserted']}/{new['effective']}{_flag(new)} ({move['direction']})"
    )


def render_markdown(diff: Mapping[str, Any]) -> str:
    claims = diff["claims"]
    lines = [
        f"# Claims diff: {diff['base']} → {diff['head']}",
        "",
        f"Class: **{diff['class']}**. Enforced: {str(diff['enforced']['base']).lower()} → "
        f"{str(diff['enforced']['head']).lower()}. Tooling changed: {str(diff['tooling_changed']).lower()}.",
        "",
    ]
    if diff["upgrade_reasons"]:
        lines.append("Upgrade reasons:")
        lines.append("")
        lines.extend(f"- {reason}" for reason in diff["upgrade_reasons"])
        lines.append("")
    if diff["out_of_scope_paths"]:
        lines.append("Paths outside `research/**` and `skills/marcus/references/**`:")
        lines.append("")
        lines.extend(f"- `{path}`" for path in diff["out_of_scope_paths"])
        lines.append("")

    def section(title: str, rows: List[str]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.extend(rows or ["None."])
        lines.append("")

    section(
        "New findings",
        [f"- `{c['id']}` (section {c['section']}): {_grades_text(c['head'])}" for c in claims if c["status"] == "new"],
    )
    section(
        "Reclassifications",
        [
            f"- `{c['id']}`: " + "; ".join(_move_text(m) for m in c["grade_moves"])
            for c in claims
            if c["grade_moves"]
        ],
    )
    section(
        "Contradictions",
        [
            f"- `{c['id']}`: new contrasting source(s) {', '.join(c['new_contrasting'])}"
            for c in claims
            if c["new_contrasting"]
        ],
    )
    retractions = [f"- `{c['id']}`: claim removed (was {_grades_text(c['base'])})" for c in claims if c["status"] == "removed"]
    retractions += [
        f"- `{c['id']}`: retracted source(s) {', '.join(c['new_retracted'])}" for c in claims if c["new_retracted"]
    ]
    section("Retractions", retractions)

    unchanged = [c for c in claims if c["status"] == "unchanged"]
    sourcing = [c for c in claims if c["status"] == "changed" and not c["grade_moves"] and not c["upgrade"]]
    unchanged_rows = [f"{len(unchanged)} claim(s) unchanged."]
    if sourcing:
        unchanged_rows.append("")
        unchanged_rows.append("Grades unchanged, text or sources edited:")
        unchanged_rows.append("")
        unchanged_rows.extend(
            f"- `{c['id']}`: +{len(c['sources_added'])}/-{len(c['sources_removed'])} source ids"
            + ("; sources edited" if c["sources_changed"] else "")
            + ("; text edited" if c["text_changed"] else "")
            for c in sourcing
        )
    section("Unchanged", unchanged_rows)

    rule_rows = []
    for rule in diff["rules"]:
        floor = rule["floor"]
        text = f"- `{rule['id']}` ({rule['status']}): floor {floor['base'] or '-'} → {floor['head'] or '-'}"
        if rule["moved_claims"]:
            text += "; moved claims " + ", ".join(f"`{cid}`" for cid in rule["moved_claims"])
        if rule["claims"]["base"] != rule["claims"]["head"]:
            text += "; citations edited"
        if rule["basis"]["base"] != rule["basis"]["head"]:
            text += f"; basis {rule['basis']['base']} → {rule['basis']['head']}"
        rule_rows.append(text)
    section("Marcus rule consequences", rule_rows)
    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify grade changes between two ledger states.")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="checkout root (default: this checkout)")
    parser.add_argument("--base", required=True, help="base git ref")
    parser.add_argument("--head", required=True, help=f"head git ref, or {WORKTREE} for the working tree")
    parser.add_argument("--research", default=DEFAULT_RESEARCH, help="repo-relative RESEARCH.md path")
    parser.add_argument("--sources", default=DEFAULT_SOURCES, help="repo-relative sources.yaml path")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="print the diff as JSON")
    output.add_argument("--markdown", action="store_true", help="print the diff as markdown (default)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    gc.use_utf8_output()
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        diff = build_diff(repo, args.base, args.head, args.research, args.sources)
    except (DiffError, rl.yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(diff, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(diff), end="")
    return EXIT_UPGRADE if diff["class"] == UPGRADE else 0


if __name__ == "__main__":
    sys.exit(main())
