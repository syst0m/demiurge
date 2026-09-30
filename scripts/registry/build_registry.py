#!/usr/bin/env python3
"""
build_registry.py - Build the local skill registry from PROVENANCE and evals.

The registry is derived, never hand-maintained, and never committed: the repo
is public and the installed library is private. It reads every skill's
``PROVENANCE.md`` (YAML header, ``## Revision N`` blocks, ``## Addendum``
blocks or plain prose), its ``evals/evals.json`` (a ``cases`` list or a
``suites`` mapping) and any recorded results (``evals/results-*.json``,
``evals/last_run.json``), and writes one YAML document outside every git
working tree.

A missing ``trust_tier`` defaults to T4. A results file is ``stale`` when the
number of cases it scored differs from the current number of eval cases.

Usage:
    python scripts/registry/build_registry.py
    python scripts/registry/build_registry.py --check
    python scripts/registry/build_registry.py --repo-only --check
    python scripts/registry/build_registry.py --propose-backfill [DIR]

``--repo-only --check`` is the CI mode: it parses the repo skills only, prints
their findings and writes nothing. Every mode that writes refuses a target
inside a git working tree.

Exit codes:
    0  success
    1  a PROVENANCE or evals file failed to parse, the written registry is out
       of date (--check), or a write was refused
    2  usage error or missing dependency
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required: python -m pip install -r requirements-dev.txt", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LIBRARY = "~/.claude/skills"
DEFAULT_REPO_SKILLS = "skills"
DEFAULT_OUT = "~/.demiurge/registry.yaml"
DEFAULT_BACKFILL = "~/.demiurge/backfill"
DEFAULT_CLAIMS_JSON = "skills/marcus/references/claims.json"
SCHEMA_VERSION = 1
DEFAULT_TIER = "T4"

FENCE_OPEN_RE = re.compile(r"^```\s*ya?ml\s*$", re.IGNORECASE)
FENCE_CLOSE_RE = re.compile(r"^```\s*$")
HEADING_RE = re.compile(r"^##\s+(.*\S)\s*$")
REVISION_RE = re.compile(r"^Revision\s+(\d+)\b", re.IGNORECASE)
ADDENDUM_RE = re.compile(r"^Addendum\b", re.IGNORECASE)
TIER_RE = re.compile(r"\bT[1-4](?:-conditional)?\b")
GATE_RE = re.compile(r"\bG[0-6]\b")
FRONTMATTER_NAME_RE = re.compile(r"^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.MULTILINE)
PROVENANCE_KEYS = {"skill", "name", "trust_tier", "gate_reached", "revision", "created"}
SKIP_PARTS = {"__pycache__", "node_modules", ".git"}

PARSE_ERROR = "parse_error"


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

@dataclass
class YamlBlock:
    kind: str
    heading: Optional[str]
    line_no: int
    data: Dict[str, Any]


@dataclass
class Finding:
    skill: str
    code: str
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return {"skill": self.skill, "code": self.code, "detail": self.detail}


@dataclass
class SkillEntry:
    name: str
    origin: str
    data: Dict[str, Any] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)

    def add(self, code: str, detail: str) -> None:
        self.findings.append(Finding(self.name, code, detail))


# --------------------------------------------------------------------------- #
# PROVENANCE parser
# --------------------------------------------------------------------------- #

def _yaml_blocks(text: str) -> Tuple[List[Tuple[Optional[str], int, str]], List[str]]:
    """Return (heading, first line number, body) for each fenced YAML block.

    Headings inside any fenced block are ignored, so a code sample cannot
    reclassify the blocks that follow it.
    """
    blocks: List[Tuple[Optional[str], int, str]] = []
    errors: List[str] = []
    heading: Optional[str] = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("```"):
            start = i + 1
            j = start
            while j < len(lines) and not FENCE_CLOSE_RE.match(lines[j].strip()):
                j += 1
            if j >= len(lines):
                errors.append(f"line {i + 1}: unterminated code fence")
                break
            if FENCE_OPEN_RE.match(stripped):
                blocks.append((heading, start + 1, "\n".join(lines[start:j])))
            i = j + 1
            continue
        match = HEADING_RE.match(lines[i])
        if match:
            heading = match.group(1)
        i += 1
    return blocks, errors


def parse_provenance(text: str) -> Tuple[List[YamlBlock], List[str]]:
    """Classify each provenance-shaped YAML block as header, revision or addendum."""
    raw_blocks, errors = _yaml_blocks(text)
    blocks: List[YamlBlock] = []
    for heading, line_no, body in raw_blocks:
        try:
            data = yaml.safe_load(body)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = line_no + mark.line if mark is not None else line_no
            errors.append(f"line {where}: invalid yaml ({getattr(exc, 'problem', None) or 'parse error'})")
            continue
        if not isinstance(data, dict):
            continue
        if heading is not None and REVISION_RE.match(heading):
            kind = "revision"
        elif heading is not None and ADDENDUM_RE.match(heading):
            kind = "addendum"
        elif not blocks and heading is None:
            kind = "header"
        elif PROVENANCE_KEYS & set(data):
            kind = "header" if not any(b.kind == "header" for b in blocks) and "revision" not in data else "revision"
        else:
            continue
        blocks.append(YamlBlock(kind, heading, line_no, data))
    return blocks, errors


def provenance_format(blocks: Sequence[YamlBlock]) -> str:
    kinds = [b.kind for b in blocks]
    parts = [k for k in ("header", "revision", "addendum") if k in kinds]
    if not parts:
        return "prose"
    names = {"header": "yaml-header", "revision": "revisions", "addendum": "addenda"}
    return "+".join(names[p] for p in parts)


def _first(pattern: re.Pattern[str], value: Any) -> Optional[str]:
    if value is None:
        return None
    match = pattern.search(str(value))
    return match.group(0) if match else None


def _latest(blocks: Sequence[YamlBlock], key: str) -> Tuple[Any, Optional[YamlBlock]]:
    """Latest value of ``key``: the last revision that sets it, else the header."""
    for block in reversed(blocks):
        if block.kind == "revision" and block.data.get(key) is not None:
            return block.data[key], block
    for block in blocks:
        if block.kind == "header" and block.data.get(key) is not None:
            return block.data[key], block
    return None, None


def _error_text(exc: BaseException) -> str:
    """Describe an error without echoing the file path an OSError carries."""
    if isinstance(exc, OSError):
        return exc.strerror or type(exc).__name__
    return str(exc)


def _date_str(value: Any) -> Optional[str]:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value) if value is not None else None


# --------------------------------------------------------------------------- #
# evals parser
# --------------------------------------------------------------------------- #

def _suite_cases(value: Any) -> Optional[List[Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("cases"), list):
        return value["cases"]
    return None


def parse_evals(data: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Count eval cases for the ``cases`` and ``suites`` shapes."""
    if not isinstance(data, dict):
        return None, "top level is not an object"
    counts = {"regression": 0, "capability": 0}
    if isinstance(data.get("cases"), list):
        shape = "cases"
        for case in data["cases"]:
            suite = case.get("suite", "capability") if isinstance(case, dict) else "capability"
            counts[str(suite)] = counts.get(str(suite), 0) + 1
    elif isinstance(data.get("suites"), dict):
        shape = "suites"
        for suite, value in data["suites"].items():
            cases = _suite_cases(value)
            if cases is None:
                return None, f"suites.{suite} is neither a list nor an object with cases"
            counts[str(suite)] = counts.get(str(suite), 0) + len(cases)
    else:
        return None, "no cases list and no suites object"
    return {"shape": shape, "total": sum(counts.values()), **counts}, None


def parse_results(path: Path, current_total: Optional[int]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Summarise a recorded results file and apply the stale rule."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{path.name}: {_error_text(exc)}"
    if not isinstance(data, dict):
        return None, f"{path.name}: top level is not an object"
    if path.name == "last_run.json":
        entry: Dict[str, Any] = {
            "file": f"evals/{path.name}",
            "gate": "deterministic",
            "date": data.get("date"),
            "passed": data.get("passed"),
            "total": data.get("total"),
            "n_cases_at_run": None,
            "stale": None,
        }
        return entry, None
    cases = data.get("cases")
    n_cases = len(cases) if isinstance(cases, list) else None
    stale = None
    if n_cases is not None and current_total is not None:
        stale = n_cases != current_total
    pair = data.get("model_harness_pair")
    entry = {
        "file": f"evals/{path.name}",
        "gate": data.get("gate"),
        "mode": data.get("mode"),
        "date": data.get("date"),
        "k": data.get("k"),
        "skills_isolated": data.get("skills_isolated"),
        "judge": pair.get("judge") if isinstance(pair, dict) else None,
        "pass_pow_k_overall": data.get("pass_pow_k_overall"),
        "pass_pow_k_regression": data.get("pass_pow_k_regression"),
        "n_cases_at_run": n_cases,
        "stale": stale,
    }
    return entry, None


# --------------------------------------------------------------------------- #
# Skill scan
# --------------------------------------------------------------------------- #

def frontmatter_name(skill_md: Path) -> Optional[str]:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    match = FRONTMATTER_NAME_RE.search(text[3:end])
    return match.group(1).strip() if match else None


def content_sha256(skill_dir: Path) -> str:
    """Hash every file under a skill (relative posix path plus raw bytes)."""
    digest = hashlib.sha256()
    files = sorted(
        p for p in skill_dir.rglob("*")
        if p.is_file() and not SKIP_PARTS & set(p.relative_to(skill_dir).parts)
    )
    for path in files:
        digest.update(path.relative_to(skill_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def skill_dirs(root: Path) -> List[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def scan_skill(skill_dir: Path, origin: str, current_snapshot: Optional[str]) -> SkillEntry:
    entry = SkillEntry(skill_dir.name, origin)
    name = skill_dir.name
    data: Dict[str, Any] = {"name": name, "origin": origin}

    fm_name = frontmatter_name(skill_dir / "SKILL.md")
    if fm_name is not None and fm_name != name:
        entry.add("name_mismatch", f"SKILL.md frontmatter name {fm_name!r} differs from the directory name")

    prov_path = skill_dir / "PROVENANCE.md"
    aliases: List[str] = []
    if not prov_path.is_file():
        blocks: List[YamlBlock] = []
        data["provenance"] = {"file": None, "format": "missing"}
        entry.add("provenance_missing", "no PROVENANCE.md")
    else:
        try:
            text = prov_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            text = ""
            entry.add(PARSE_ERROR, f"PROVENANCE.md: {_error_text(exc)}")
        blocks, errors = parse_provenance(text)
        for error in errors:
            entry.add(PARSE_ERROR, f"PROVENANCE.md {error}")
        revisions = [b for b in blocks if b.kind == "revision"]
        latest_date, _ = _latest(blocks, "date")
        data["provenance"] = {
            "file": "PROVENANCE.md",
            "format": provenance_format(blocks),
            "revisions": len(revisions),
            "latest_date": _date_str(latest_date if revisions else None),
        }
        if not blocks:
            entry.add("provenance_unstructured", "PROVENANCE.md has no yaml block")
        for block in blocks:
            if block.kind != "header":
                continue
            declared = block.data.get("skill") or block.data.get("name")
            if declared is not None and str(declared) != name:
                aliases.append(str(declared))
                entry.add("name_mismatch", f"PROVENANCE.md names the skill {str(declared)!r}")

    tier_raw, _ = _latest(blocks, "trust_tier")
    tier = _first(TIER_RE, tier_raw)
    if tier is None:
        tier = DEFAULT_TIER
        entry.add("tier_default", f"no trust_tier recorded; defaulting to {DEFAULT_TIER}")
    gate_raw, _ = _latest(blocks, "gate_reached")
    data["aliases"] = aliases
    data["trust_tier"] = tier
    data["trust_tier_declared"] = str(tier_raw) if tier_raw is not None else None
    data["gate_reached"] = _first(GATE_RE, gate_raw)

    snapshot, _ = _latest(blocks, "research_snapshot")
    claims, _ = _latest(blocks, "research_claims")
    snap_sha = snapshot.get("snapshot_sha256") if isinstance(snapshot, dict) else None
    data["research_snapshot"] = {
        "version": snapshot.get("version") if isinstance(snapshot, dict) else None,
        "snapshot_sha256": snap_sha,
    }
    data["research_claims"] = [str(c) for c in claims] if isinstance(claims, list) else []
    if snap_sha and current_snapshot and snap_sha != current_snapshot:
        entry.add("research_snapshot_behind", "built from a RESEARCH.md snapshot other than the current one")

    evals_path = next(
        (p for p in (skill_dir / "evals" / "evals.json", skill_dir / "evals.json") if p.is_file()),
        None,
    )
    current_total: Optional[int] = None
    if evals_path is None:
        data["evals"] = {"file": None, "shape": "missing"}
        entry.add("evals_missing", "no evals.json")
    else:
        rel = evals_path.relative_to(skill_dir).as_posix()
        try:
            raw = evals_path.read_bytes()
            summary, error = parse_evals(json.loads(raw.decode("utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            summary, error = None, _error_text(exc)
        if summary is None:
            data["evals"] = {"file": rel, "shape": "invalid"}
            entry.add(PARSE_ERROR, f"{rel}: {error}")
        else:
            current_total = summary["total"]
            data["evals"] = {"file": rel, **summary, "sha256": hashlib.sha256(raw).hexdigest()}

    results: List[Dict[str, Any]] = []
    evals_dir = skill_dir / "evals"
    result_files = sorted(evals_dir.glob("results-*.json")) if evals_dir.is_dir() else []
    if (evals_dir / "last_run.json").is_file():
        result_files.append(evals_dir / "last_run.json")
    for path in result_files:
        summary, error = parse_results(path, current_total)
        if summary is None:
            entry.add(PARSE_ERROR, f"evals/{error}")
            continue
        results.append(summary)
        if summary["stale"]:
            entry.add(
                "stale_results",
                f"{summary['file']} scored {summary['n_cases_at_run']} cases; evals.json now has {current_total}",
            )
    data["results"] = results
    entry.data = data
    return entry


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

def load_snapshot(claims_json: Path) -> Dict[str, Any]:
    try:
        data = json.loads(claims_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"version": None, "snapshot_sha256": None}
    return {"version": data.get("research_version"), "snapshot_sha256": data.get("snapshot_sha256")}


def build(
    repo_skills: Path,
    library: Optional[Path],
    claims_json: Path,
) -> Tuple[Dict[str, Any], List[SkillEntry]]:
    """Scan the repo skills and, unless ``library`` is None, the library."""
    snapshot = load_snapshot(claims_json)
    current = snapshot.get("snapshot_sha256")
    entries: List[SkillEntry] = []
    repo_dirs = {d.name: d for d in skill_dirs(repo_skills)}
    library_dirs = {d.name: d for d in skill_dirs(library)} if library is not None else {}

    for name, skill_dir in repo_dirs.items():
        entry = scan_skill(skill_dir, "repo", current)
        if library is not None:
            deployed = library_dirs.get(name)
            entry.data["deployed"] = deployed is not None
            entry.data["deploy_in_sync"] = (
                content_sha256(deployed) == content_sha256(skill_dir) if deployed is not None else None
            )
            if deployed is not None and not entry.data["deploy_in_sync"]:
                entry.add("deploy_drift", "installed copy differs from the repo copy")
        entries.append(entry)
    for name, skill_dir in library_dirs.items():
        if name in repo_dirs:
            continue
        entry = scan_skill(skill_dir, "library", current)
        entry.data["deployed"] = True
        entry.data["deploy_in_sync"] = None
        entries.append(entry)

    entries.sort(key=lambda e: e.name)
    registry = {
        "schema_version": SCHEMA_VERSION,
        "research_snapshot": snapshot,
        "skills": [e.data for e in entries],
        "findings": [f.as_dict() for e in entries for f in e.findings],
    }
    return registry, entries


def dump_registry(registry: Dict[str, Any]) -> str:
    return yaml.safe_dump(registry, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100)


def without_last_built(registry: Any) -> Any:
    if isinstance(registry, dict):
        return {k: v for k, v in registry.items() if k != "last_built"}
    return registry


def inside_git_tree(path: Path) -> Optional[Path]:
    """Return the working-tree root that contains ``path``, if any."""
    resolved = path.expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def backfill_header(entry: SkillEntry) -> str:
    aliases = entry.data.get("aliases") or []
    lines = [
        f"# PROVENANCE backfill proposal: {entry.name}",
        "",
        "Review before copying into the skill's PROVENANCE.md. The tier stays T4",
        "until the skill's gates are recorded.",
        "",
        "```yaml",
        f"skill: {entry.name}",
    ]
    if aliases:
        lines.append("aliases: [" + ", ".join(aliases) + "]")
    lines += [
        f"trust_tier: {entry.data.get('trust_tier') or DEFAULT_TIER}",
        f"gate_reached: {entry.data.get('gate_reached') or 'null'}",
        "research_snapshot: null",
        "research_claims: []",
        "```",
        "",
    ]
    return "\n".join(lines)


def needs_backfill(entry: SkillEntry) -> bool:
    codes = {f.code for f in entry.findings}
    return bool(codes & {"provenance_missing", "provenance_unstructured", "tier_default", "name_mismatch"})


def print_findings(entries: Sequence[SkillEntry]) -> None:
    for entry in entries:
        for finding in entry.findings:
            print(f"{finding.skill}: {finding.code}: {finding.detail}")


def _resolve(repo: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo / path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--library", default=DEFAULT_LIBRARY, help="installed skill library")
    parser.add_argument("--repo-skills", default=DEFAULT_REPO_SKILLS, help="repo skills directory")
    parser.add_argument("--out", default=DEFAULT_OUT, help="registry output path")
    parser.add_argument("--repo-only", action="store_true", help="scan the repo skills only")
    parser.add_argument("--check", action="store_true", help="parse and report; write nothing")
    parser.add_argument(
        "--propose-backfill",
        nargs="?",
        const=DEFAULT_BACKFILL,
        default=None,
        metavar="DIR",
        help="write proposed PROVENANCE headers for skills that lack tier or gate",
    )
    parser.add_argument("--claims-json", default=DEFAULT_CLAIMS_JSON, help=argparse.SUPPRESS)
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.check and args.propose_backfill is not None:
        print("ERROR: --propose-backfill writes files; it cannot run with --check", file=sys.stderr)
        return 2

    repo = args.repo.resolve()
    repo_skills = _resolve(repo, args.repo_skills)
    if not repo_skills.is_dir():
        print(f"ERROR: repo skills directory not found: {args.repo_skills}", file=sys.stderr)
        return 2
    library = None if args.repo_only else Path(args.library).expanduser()
    out = Path(args.out).expanduser()

    targets: List[Path] = []
    if not args.check:
        targets.append(out)
    if args.propose_backfill is not None:
        targets.append(Path(args.propose_backfill).expanduser())
    for target in targets:
        if inside_git_tree(target) is not None:
            print(
                f"ERROR: refusing to write {target.name!r} inside a git working tree; "
                "the registry is local only",
                file=sys.stderr,
            )
            return 1

    registry, entries = build(repo_skills, library, _resolve(repo, args.claims_json))
    print_findings(entries)
    parse_failures = [f for e in entries for f in e.findings if f.code == PARSE_ERROR]
    scope = "repo skills" if args.repo_only else "skills"

    if args.check:
        if parse_failures:
            print(f"FAIL: {len(parse_failures)} parse failure(s) in {len(entries)} {scope}")
            return 1
        if not args.repo_only and out.is_file():
            try:
                existing = yaml.safe_load(out.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError):
                existing = None
            if without_last_built(existing) != without_last_built(yaml.safe_load(dump_registry(registry))):
                print(f"DRIFT: {out.name} is out of date; rerun without --check")
                return 1
        print(f"OK: {len(entries)} {scope} parsed")
        return 0

    registry = {**registry, "last_built": dt.date.today().isoformat()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump_registry(registry), encoding="utf-8")
    written = 0
    if args.propose_backfill is not None:
        backfill_dir = Path(args.propose_backfill).expanduser()
        backfill_dir.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            if needs_backfill(entry):
                (backfill_dir / f"{entry.name}.PROVENANCE.md").write_text(backfill_header(entry), encoding="utf-8")
                written += 1
    print(f"wrote {out.name}: {len(entries)} {scope}, {len(registry['findings'])} findings")
    if args.propose_backfill is not None:
        print(f"proposed {written} PROVENANCE backfill(s)")
    if parse_failures:
        print(f"FAIL: {len(parse_failures)} parse failure(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
