#!/usr/bin/env python3
"""Deterministic script for updating Marcus himself against upstream research snapshots.

Enforces:
1. Version and content synchronization between research/RESEARCH.md and skills/marcus/references/RESEARCH.md.
2. Alignment between derived_from in AGENT_ARCHITECTURE.md and RESEARCH.md version.
3. Rule diff inspection across confidence markers ([SETTLED], [CONTESTED], [VENDOR], [EMERGING]).
4. Grade counts from references/claims.json, whose research_sha256 and sources_sha256 must match
   research/RESEARCH.md and research/sources.yaml (a mismatch is DRIFT; rerun grade_cap.py --write).
5. The derived_from line `RESEARCH.md v<version> (<snapshot_date>) snapshot_sha256:<hex>`, whose
   date must match RESEARCH.md and whose hash must match claims.json. --apply re-pins that one line
   to the current version, date and hash when claims.json is fresh; rule text is never edited.
6. Rule citation tokens, checked by scripts/research/check_rule_citations.py when the repo has it.
   A docs/AGENT_DESIGN.md derived_from line behind RESEARCH.md or AGENT_ARCHITECTURE.md is a WARNING.
7. Execution of Marcus's deterministic gate test suite (run_gate_tests.py) and validator (validate_skill.py).

Usage:
    python skills/marcus/scripts/update_marcus.py --check   # Report drift (exit 1 if drift)
    python skills/marcus/scripts/update_marcus.py --apply   # Sync references, re-pin derived_from, check gates
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RESEARCH_VERSION_PATTERN = re.compile(r"^version:\s*(?P<version>[\d\.]+)", re.MULTILINE)
SNAPSHOT_DATE_PATTERN = re.compile(r"^snapshot_date:\s*(?P<date>[\d-]+)", re.MULTILINE)
DERIVED_RESEARCH_PATTERN = re.compile(r"RESEARCH\.md\s+v(?P<version>[\d\.]+)", re.MULTILINE)
DERIVED_SNAPSHOT_PATTERN = re.compile(
    r"RESEARCH\.md\s+v(?P<version>[\d\.]+)\s+\((?P<date>[\d-]+)\)\s+snapshot_sha256:(?P<sha>[0-9a-f]{64})\b"
)
DERIVED_LINE_PATTERN = re.compile(
    r"^(?P<prefix>[ \t]*-[ \t]+)RESEARCH\.md[ \t]+v[\d.]+[ \t]+\([\d-]+\)[ \t]+snapshot_sha256:[0-9a-f]{64}(?P<suffix>.*)$",
    re.MULTILINE,
)
DESIGN_DERIVED_PATTERN = re.compile(
    r"^derived_from:\s*RESEARCH\.md\s+v(?P<research>[\d\.]+)\s*·\s*AGENT_ARCHITECTURE\.md\s+v(?P<arch>[\d\.]+)",
    re.MULTILINE,
)

MARKERS = ["[SETTLED]", "[CONTESTED]", "[VENDOR]", "[EMERGING]"]
MARKER_PATTERN = re.compile(r"`?\[(SETTLED|CONTESTED|VENDOR|EMERGING)(?::[^\]]*)?\]`?")
LINK_SUFFIX_PATTERN = re.compile(r"\]\([^)\s]*\)\s*$")
CHANGELOG_HEADING_PATTERN = re.compile(r"^## Change log", re.MULTILINE)
GATE_SUMMARY_PATTERN = re.compile(r"^(\d+)/(\d+) passing", re.MULTILINE)

GRADE_COUNT_KEYS = ["SETTLED", "CONTESTED", "EMERGING", "VENDOR", "UNVERIFIED"]
HASHED_INPUTS = (("research_sha256", "RESEARCH.md"), ("sources_sha256", "sources.yaml"))
REGRADE_HINT = "run python scripts/research/grade_cap.py --write"


def extract_metadata(text: str) -> Tuple[Optional[str], Optional[str]]:
    ver_match = RESEARCH_VERSION_PATTERN.search(text)
    date_match = SNAPSHOT_DATE_PATTERN.search(text)
    ver = ver_match.group("version") if ver_match else None
    date = date_match.group("date") if date_match else None
    return ver, date


def count_markers(text: str) -> Dict[str, int]:
    """Count confidence markers above the change log.

    A `[VENDOR]` placed directly after a `](...)` link tags that source, not a rule, so it is skipped.
    """
    heading = CHANGELOG_HEADING_PATTERN.search(text)
    body = text[: heading.start()] if heading else text
    counts: Dict[str, int] = {marker: 0 for marker in MARKERS}
    for match in MARKER_PATTERN.finditer(body):
        name = match.group(1)
        if name == "VENDOR" and LINK_SUFFIX_PATTERN.search(body, 0, match.start()):
            continue
        counts[f"[{name}]"] += 1
    return counts


def load_claims(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Read the compiled claims.json; return (data, None) or (None, reason)."""
    if not path.is_file():
        return None, f"{path.name} is missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{path.name} is unreadable ({exc})"
    if not isinstance(data, dict) or not isinstance(data.get("counts"), dict):
        return None, f"{path.name} has no counts object"
    return data, None


def claims_counts(claims: Dict[str, Any]) -> Dict[str, int]:
    """Effective grade counts (plus UNVERIFIED) as compiled by grade_cap.py."""
    counts = claims.get("counts") or {}
    return {key: int(counts.get(key, 0)) for key in GRADE_COUNT_KEYS}


def snapshot_sha256(research_sha: str, sources_sha: str) -> str:
    """Hash of both file hashes, research first, joined by a newline, as grade_cap.py writes it."""
    return hashlib.sha256(f"{research_sha}\n{sources_sha}".encode("ascii")).hexdigest()


def claims_hash_drift(claims: Dict[str, Any], research: Path, sources: Path) -> List[str]:
    """Name each hashed input whose bytes no longer match the hash stored in claims.json."""
    stale = []
    for (key, label), path in zip(HASHED_INPUTS, (research, sources)):
        if not path.is_file():
            stale.append(f"{label} is missing")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if claims.get(key) != actual:
            stale.append(f"{key} does not match {label}")
    research_sha, sources_sha = claims.get("research_sha256"), claims.get("sources_sha256")
    hashes_present = isinstance(research_sha, str) and isinstance(sources_sha, str)
    if not hashes_present or claims.get("snapshot_sha256") != snapshot_sha256(research_sha, sources_sha):
        stale.append("snapshot_sha256 does not match research_sha256 and sources_sha256")
    return stale


def derived_snapshot_drift(
    arch_text: str, canon_date: Optional[str], claims: Optional[Dict[str, Any]]
) -> List[str]:
    """Check the date and hash on the derived_from RESEARCH.md line against RESEARCH.md and claims.json."""
    match = DERIVED_SNAPSHOT_PATTERN.search(arch_text)
    if not match:
        return ["derived_from has no `RESEARCH.md v<version> (<date>) snapshot_sha256:<hex>` line"]
    problems = []
    if match.group("date") != canon_date:
        problems.append(f"derived_from date {match.group('date')} does not match snapshot_date {canon_date}")
    expected = claims.get("snapshot_sha256") if claims else None
    if expected is not None and match.group("sha") != expected:
        problems.append("derived_from snapshot_sha256 does not match claims.json")
    return problems


def repin_derived_from(arch_text: str, version: str, date: str, sha: str) -> Optional[str]:
    """``arch_text`` with its derived_from RESEARCH.md line pinned to version, date and hash.

    Only that line changes; its indent and trailing comment are kept. None when the file has no
    line of the full ``RESEARCH.md v<version> (<date>) snapshot_sha256:<hex>`` form.
    """
    match = DERIVED_LINE_PATTERN.search(arch_text)
    if not match:
        return None
    line = f"{match.group('prefix')}RESEARCH.md v{version} ({date}) snapshot_sha256:{sha}{match.group('suffix')}"
    return arch_text[: match.start()] + line + arch_text[match.end() :]


def read_lf(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def write_lf(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def design_doc_warnings(design_text: str, canon_ver: Optional[str], arch_ver: Optional[str]) -> List[str]:
    """Report a docs/AGENT_DESIGN.md derived_from line that lags RESEARCH.md or AGENT_ARCHITECTURE.md."""
    match = DESIGN_DERIVED_PATTERN.search(design_text)
    if not match:
        return ["AGENT_DESIGN.md has no `derived_from: RESEARCH.md vX · AGENT_ARCHITECTURE.md vY` line"]
    warnings = []
    if match.group("research") != canon_ver:
        warnings.append(
            f"AGENT_DESIGN.md derived_from is RESEARCH.md v{match.group('research')}, "
            f"but RESEARCH.md is v{canon_ver}"
        )
    if match.group("arch") != arch_ver:
        warnings.append(
            f"AGENT_DESIGN.md derived_from is AGENT_ARCHITECTURE.md v{match.group('arch')}, "
            f"but AGENT_ARCHITECTURE.md is v{arch_ver}"
        )
    return warnings


def parse_gate_summary(stdout: str) -> Optional[Tuple[int, int]]:
    match = GATE_SUMMARY_PATTERN.search(stdout)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def run_process(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", cwd=cwd)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def use_utf8_output() -> None:
    """Print § and · from check_rule_citations.py even where the console default is a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main() -> int:
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Marcus self-update and drift audit engine")
    parser.add_argument("--check", action="store_true", help="Check drift without modifying files (exit 1 if drift detected)")
    parser.add_argument("--apply", action="store_true", help="Synchronize references and verify gates")
    parser.add_argument("--repo-root", type=str, default=None, help="Explicit repository root path")
    args = parser.parse_args()

    mode = "check" if args.check or not args.apply else "apply"

    # Locate paths
    script_dir = Path(__file__).resolve().parent
    marcus_dir = script_dir.parent
    repo_root = Path(args.repo_root).resolve() if args.repo_root else marcus_dir.parent.parent

    canonical_research = repo_root / "research" / "RESEARCH.md"
    canonical_sources = repo_root / "research" / "sources.yaml"
    claims_file = marcus_dir / "references" / "claims.json"
    reference_research = marcus_dir / "references" / "RESEARCH.md"
    architecture_file = marcus_dir / "AGENT_ARCHITECTURE.md"
    gate_tests = marcus_dir / "evals" / "run_gate_tests.py"
    validator = marcus_dir / "scripts" / "validate_skill.py"
    citation_checker = repo_root / "scripts" / "research" / "check_rule_citations.py"
    design_doc = repo_root / "docs" / "AGENT_DESIGN.md"

    print("Marcus Self-Update & Architecture Audit Engine")
    print("------------------------------------------------------------------------")

    if not canonical_research.exists():
        print(f"ERROR: Canonical research file not found at {canonical_research}", file=sys.stderr)
        return 2

    canon_text = canonical_research.read_text(encoding="utf-8")
    canon_ver, canon_date = extract_metadata(canon_text)
    canon_counts = count_markers(canon_text)

    drift_detected = False
    arch_drift = False
    claims_drift = False
    citations_drift = False
    arch_text: Optional[str] = None

    # 1. Compare canonical research against Marcus's reference copy
    if not reference_research.exists():
        print(f"DRIFT: Reference {reference_research} is missing.")
        drift_detected = True
        if mode == "apply":
            reference_research.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(canonical_research, reference_research)
            print(f"APPLIED: Copied {canonical_research.name} to {reference_research}")
    else:
        ref_text = reference_research.read_text(encoding="utf-8")
        ref_ver, ref_date = extract_metadata(ref_text)
        ref_counts = count_markers(ref_text)

        if canon_text != ref_text:
            print(f"DRIFT: Canonical research ({canon_ver} @ {canon_date}) differs from reference copy ({ref_ver} @ {ref_date}).")
            drift_detected = True

            # Report marker differences
            for marker in MARKERS:
                c_val = canon_counts.get(marker, 0)
                r_val = ref_counts.get(marker, 0)
                if c_val != r_val:
                    print(f"       Marker shift: {marker} count {r_val} -> {c_val}")

            if mode == "apply":
                shutil.copy2(canonical_research, reference_research)
                print(f"APPLIED: Updated {reference_research.name} to v{canon_ver} ({canon_date}).")
        else:
            print(f"SYNCED: Reference copy matches research/RESEARCH.md v{canon_ver} ({canon_date}).")

    # 1b. --apply re-pins the derived_from RESEARCH.md line once claims.json matches research/.
    # The rules themselves are checked by check_rule_citations.py below and never edited here.
    if mode == "apply" and architecture_file.exists() and canon_ver and canon_date:
        fresh_claims, _ = load_claims(claims_file)
        if fresh_claims is not None and not claims_hash_drift(fresh_claims, canonical_research, canonical_sources):
            current = read_lf(architecture_file)
            pinned = repin_derived_from(current, canon_ver, canon_date, fresh_claims["snapshot_sha256"])
            if pinned is not None and pinned != current:
                write_lf(architecture_file, pinned)
                print(f"APPLIED: Pinned AGENT_ARCHITECTURE.md derived_from to RESEARCH.md v{canon_ver} ({canon_date}).")

    # 2. Check AGENT_ARCHITECTURE.md derived_from header
    if architecture_file.exists():
        arch_text = architecture_file.read_text(encoding="utf-8")
        arch_match = DERIVED_RESEARCH_PATTERN.search(arch_text)
        if arch_match:
            arch_ver = arch_match.group("version")
            if arch_ver != canon_ver:
                print(f"DRIFT: AGENT_ARCHITECTURE.md derived_from is v{arch_ver}, but RESEARCH.md is v{canon_ver}.")
                drift_detected = True
                arch_drift = True
            else:
                print(f"SYNCED: AGENT_ARCHITECTURE.md correctly derived from v{canon_ver}.")
        else:
            print("WARNING: Could not parse derived_from RESEARCH.md version in AGENT_ARCHITECTURE.md.")
            drift_detected = True
            arch_drift = True

    # 3. Grade counts and freshness of the compiled claims.json
    claims, claims_error = load_claims(claims_file)
    if claims is None:
        print(f"DRIFT: {claims_error}; {REGRADE_HINT}.")
        drift_detected = True
        claims_drift = True
    else:
        counts = claims_counts(claims)
        summary = ", ".join(f"{key} {counts[key]}" for key in GRADE_COUNT_KEYS)
        print(f"CLAIMS: {len(claims.get('claims') or [])} claims from {claims_file.name} ({summary}).")
        stale = claims_hash_drift(claims, canonical_research, canonical_sources)
        if stale:
            for reason in stale:
                print(f"DRIFT: {claims_file.name} {reason}; {REGRADE_HINT}.")
            drift_detected = True
            claims_drift = True
        else:
            print(f"SYNCED: {claims_file.name} hashes match RESEARCH.md and sources.yaml.")

    # 4. Snapshot date and hash in AGENT_ARCHITECTURE.md derived_from
    if arch_text is not None:
        problems = derived_snapshot_drift(arch_text, canon_date, claims)
        if problems:
            for problem in problems:
                print(f"DRIFT: AGENT_ARCHITECTURE.md {problem}.")
            expected_sha = (claims or {}).get("snapshot_sha256") or "<hex>"
            print(f"       Expected: RESEARCH.md v{canon_ver} ({canon_date}) snapshot_sha256:{expected_sha}")
            drift_detected = True
            arch_drift = True
        else:
            print(f"SYNCED: AGENT_ARCHITECTURE.md snapshot_sha256 matches {claims_file.name} ({canon_date}).")

    # 5. Rule citation tokens and the human companion's derived_from line
    if citation_checker.is_file() and arch_text is not None:
        checker_cmd = [
            sys.executable,
            str(citation_checker),
            "--repo",
            str(repo_root),
            "--arch",
            str(architecture_file),
            "--claims",
            str(claims_file),
        ]
        code, stdout, stderr = run_process(checker_cmd, cwd=repo_root)
        if code == 0:
            print(f"PASS: Rule citations ({stdout.splitlines()[-1] if stdout else 'no output'}).")
        else:
            print(f"DRIFT: check_rule_citations.py exited {code}:")
            for line in (stdout or stderr).splitlines():
                print(f"       {line}")
            drift_detected = True
            citations_drift = True

    if design_doc.is_file() and arch_text is not None:
        arch_ver, _ = extract_metadata(arch_text)
        for warning in design_doc_warnings(design_doc.read_text(encoding="utf-8"), canon_ver, arch_ver):
            print(f"WARNING: {warning}.")

    # 6. Deterministic regression suite (run_gate_tests.py)
    if gate_tests.exists():
        code, stdout, stderr = run_process([sys.executable, str(gate_tests)], cwd=marcus_dir)
        if code != 0:
            print(f"FAIL: Gate regression suite failed with exit code {code}:")
            print(stderr or stdout, file=sys.stderr)
            return 1
        summary = parse_gate_summary(stdout)
        if summary is None:
            print("FAIL: could not parse gate-test summary")
            return 1
        passed, total = summary
        print(f"PASS: Marcus gate regression suite ({passed}/{total} passing).")

    # 7. G4 validation check (validate_skill.py)
    if validator.exists():
        code, stdout, stderr = run_process([sys.executable, str(validator), str(marcus_dir)], cwd=marcus_dir)
        if "BLOCKING" in stdout or code > 1:
            print("FAIL: G4 validation detected blocking findings:")
            print(stdout, file=sys.stderr)
            return 1
        print("PASS: G4 validation passed (0 blocking findings).")

    print("------------------------------------------------------------------------")
    if mode == "check" and drift_detected:
        print("RESULT: Drift detected between research snapshot and Marcus reference. Run with --apply to update.")
        return 1
    if mode == "apply" and arch_drift:
        print(
            "RESULT: AGENT_ARCHITECTURE.md derived_from does not match research/RESEARCH.md and could not be "
            "re-pinned. Edit it by hand."
        )
        return 1
    if mode == "apply" and claims_drift:
        print(f"RESULT: {claims_file.name} is stale against research/. Regrade with grade_cap.py --write.")
        return 1
    if mode == "apply" and citations_drift:
        print("RESULT: AGENT_ARCHITECTURE.md rule citations fail check_rule_citations.py. Fix the tokens by hand.")
        return 1

    print("RESULT: Marcus is synchronized and all deterministic gates hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
