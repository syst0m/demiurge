#!/usr/bin/env python3
"""Self-Harness Script Integrity Validator.

Audits scripts/self_harness/{diagnose_failures,propose_candidate,materialize_candidate,
acceptance_gate,run_self_harness_loop}.py against the rules docs/SELF_HARNESS.md §5
promises for validate_self_harness_scripts.py, in the shape of
scripts/validate_benchmark_harness.py:
- Rule S1: no mock/fabricated fallback data anywhere in these scripts.
- Rule S2: every stage script defines an explicit FORMAT version string.
- Rule S3: materialize_candidate.py refuses a dirty tree and a second active candidate.
- Rule S4: acceptance_gate.py's decision is the no-drop-plus-improvement rule.
- Rule S5: no script pushes, merges, or opens/merges a pull request. Merging stays human.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

TARGET_FILENAMES = (
    "diagnose_failures.py",
    "propose_candidate.py",
    "materialize_candidate.py",
    "acceptance_gate.py",
    "run_self_harness_loop.py",
)


def check_no_mock_fallback(content: str) -> List[str]:
    if "mock" in content.lower():
        return ["Rule S1: file references 'mock' data; these scripts must never fabricate results."]
    return []


def check_format_constant(content: str) -> List[str]:
    if "FORMAT = " not in content:
        return ["Rule S2: file does not define a FORMAT version string for its output payload."]
    return []


def check_materialize_guards(path: Path, content: str) -> List[str]:
    if path.name != "materialize_candidate.py":
        return []
    violations = []
    if "--porcelain" not in content:
        violations.append("Rule S3: missing a dirty-working-tree guard (expected a 'git status --porcelain' check).")
    if "self-harness/*" not in content:
        violations.append("Rule S3: missing a one-candidate-at-a-time guard over refs/heads/self-harness/*.")
    return violations


def check_acceptance_rule(path: Path, content: str) -> List[str]:
    if path.name != "acceptance_gate.py":
        return []
    violations = []
    if "dropped" not in content or "improved" not in content:
        violations.append("Rule S4: acceptance decision does not reference both 'dropped' and 'improved' status.")
    if "not dropped and bool(improved)" not in content:
        violations.append("Rule S4: acceptance decision is not the no-drop-plus-improvement rule (Gate G5).")
    return violations


def check_no_merge_authority(content: str) -> List[str]:
    forbidden = ("git push", "git merge", "gh pr merge")
    violations = []
    for phrase in forbidden:
        if phrase in content:
            violations.append(f"Rule S5: file contains {phrase!r}; merging must stay a human action.")
    return violations


def audit_file(path: Path) -> List[str]:
    content = path.read_text(encoding="utf-8", errors="replace")
    violations: List[str] = []
    violations.extend(check_no_mock_fallback(content))
    violations.extend(check_format_constant(content))
    violations.extend(check_materialize_guards(path, content))
    violations.extend(check_acceptance_rule(path, content))
    violations.extend(check_no_merge_authority(content))
    return violations


def main() -> int:
    self_dir = Path(__file__).resolve().parent
    target_files = [self_dir / name for name in TARGET_FILENAMES]
    missing = [f for f in target_files if not f.is_file()]
    if missing:
        print(f"Missing expected self-harness script(s): {missing}")
        return 1

    total_violations = 0
    print(f"Auditing {len(target_files)} self-harness script(s) with the Integrity Validator:\n")
    for target in target_files:
        rel_path = target.relative_to(self_dir.parents[1])
        print(f"Auditing [{rel_path}]...")
        violations = audit_file(target)
        if violations:
            total_violations += len(violations)
            for v in violations:
                print(f"  [FAIL] Violation: {v}")
        else:
            print("  [OK] All Self-Harness Integrity Rules PASSED.")
        print()

    if total_violations > 0:
        print(f"FAILED: Found {total_violations} self-harness integrity violation(s).")
        return 1

    print("PASSED: All audited self-harness scripts meet the integrity rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
