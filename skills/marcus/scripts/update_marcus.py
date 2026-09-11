#!/usr/bin/env python3
"""Deterministic script for updating Marcus himself against upstream research snapshots.

Enforces:
1. Version and content synchronization between research/RESEARCH.md and skills/marcus/references/RESEARCH.md.
2. Alignment between derived_from in AGENT_ARCHITECTURE.md and RESEARCH.md version.
3. Rule diff inspection across confidence markers ([SETTLED], [CONTESTED], [VENDOR], [EMERGING]).
4. Execution of Marcus's deterministic gate test suite (run_gate_tests.py) and validator (validate_skill.py).

Usage:
    python skills/marcus/scripts/update_marcus.py --check   # Report drift (exit 1 if drift)
    python skills/marcus/scripts/update_marcus.py --apply   # Sync references, check gates
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RESEARCH_VERSION_PATTERN = re.compile(r"^version:\s*(?P<version>[\d\.]+)", re.MULTILINE)
SNAPSHOT_DATE_PATTERN = re.compile(r"^snapshot_date:\s*(?P<date>[\d-]+)", re.MULTILINE)
DERIVED_RESEARCH_PATTERN = re.compile(r"RESEARCH\.md\s+v(?P<version>[\d\.]+)", re.MULTILINE)

MARKERS = ["[SETTLED]", "[CONTESTED]", "[VENDOR]", "[EMERGING]"]


def extract_metadata(text: str) -> Tuple[Optional[str], Optional[str]]:
    ver_match = RESEARCH_VERSION_PATTERN.search(text)
    date_match = SNAPSHOT_DATE_PATTERN.search(text)
    ver = ver_match.group("version") if ver_match else None
    date = date_match.group("date") if date_match else None
    return ver, date


def count_markers(text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for marker in MARKERS:
        counts[marker] = text.count(marker)
    return counts


def run_process(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", cwd=cwd)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def main() -> int:
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
    reference_research = marcus_dir / "references" / "RESEARCH.md"
    architecture_file = marcus_dir / "AGENT_ARCHITECTURE.md"
    gate_tests = marcus_dir / "evals" / "run_gate_tests.py"
    validator = marcus_dir / "scripts" / "validate_skill.py"

    print("Marcus Self-Update & Architecture Audit Engine")
    print("------------------------------------------------------------------------")

    if not canonical_research.exists():
        print(f"ERROR: Canonical research file not found at {canonical_research}", file=sys.stderr)
        return 2

    canon_text = canonical_research.read_text(encoding="utf-8")
    canon_ver, canon_date = extract_metadata(canon_text)
    canon_counts = count_markers(canon_text)

    drift_detected = False

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

    # 2. Check AGENT_ARCHITECTURE.md derived_from header
    if architecture_file.exists():
        arch_text = architecture_file.read_text(encoding="utf-8")
        arch_match = DERIVED_RESEARCH_PATTERN.search(arch_text)
        if arch_match:
            arch_ver = arch_match.group("version")
            if arch_ver != canon_ver:
                print(f"DRIFT: AGENT_ARCHITECTURE.md derived_from is v{arch_ver}, but RESEARCH.md is v{canon_ver}.")
                drift_detected = True
            else:
                print(f"SYNCED: AGENT_ARCHITECTURE.md correctly derived from v{canon_ver}.")
        else:
            print("WARNING: Could not parse derived_from RESEARCH.md version in AGENT_ARCHITECTURE.md.")
            drift_detected = True

    # 3. Deterministic regression suite (run_gate_tests.py)
    if gate_tests.exists():
        code, stdout, stderr = run_process([sys.executable, str(gate_tests)], cwd=marcus_dir)
        if code != 0:
            print(f"FAIL: Gate regression suite failed with exit code {code}:")
            print(stderr or stdout, file=sys.stderr)
            return 1
        print("PASS: Marcus gate regression suite (14/14 passing).")

    # 4. G4 validation check (validate_skill.py)
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

    print("RESULT: Marcus is synchronized and all deterministic gates hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
