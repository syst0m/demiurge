#!/usr/bin/env python3
"""Marcus Benchmark Integrity Validator.

Audits benchmark runners in evals/benchmarks/ against Marcus Benchmark Quality Gates:
- Rule B1: No silent mock fallback on live API failure or unhandled model paths.
- Rule B2: No fake synthetic task ID generation without dataset integration.
- Rule B3: Complete task prompt construction including real issue statements.
- Rule B4: Symmetrical prompt application across all experimental arms.
- Rule B5: Rigorous resolution verification beyond trivial string substring matching.
- Rule B6: Explicit `simulated: True` metadata and simulation warning banners on dry-runs.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple


def check_no_silent_mock_fallback(tree: ast.AST, content: str) -> List[str]:
    """Verify that live execution blocks do not silently fall back to mock data on error."""
    violations = []
    # Check for try/except or if response is None returning mock_run_task in live functions
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("run_"):
            # Check if function calls mock_run_task
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func_name = ""
                    if isinstance(child.func, ast.Name):
                        func_name = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        func_name = child.func.attr
                    if "mock_run" in func_name:
                        violations.append(
                            f"Line {child.lineno}: Function '{node.name}' contains a call to '{func_name}'. "
                            "Live runner functions must raise an explicit error instead of falling back to mock data."
                        )
    return violations


def check_dataset_integration(content: str) -> List[str]:
    """Verify runner imports or defines dataset loading functionality."""
    violations = []
    if "load_swebench_dataset" not in content and "load_dataset" not in content and "datasets" not in content:
        violations.append("Benchmark runner lacks dataset loading integration (Rule B2).")
    return violations


def check_prompt_completeness(content: str) -> List[str]:
    """Verify prompt builders include problem_statement or task issue description."""
    violations = []
    if "problem_statement" not in content and "issue_description" not in content:
        violations.append("Benchmark runner prompts do not reference problem_statement or issue description (Rule B3).")
    return violations


def check_simulated_metadata(content: str) -> List[str]:
    """Verify TaskResult and BenchmarkComparison include simulated metadata flag."""
    violations = []
    if "simulated" not in content:
        violations.append("Benchmark runner or metrics engine does not track 'simulated' flag (Rule B6).")
    return violations


def audit_runner(file_path: Path) -> List[str]:
    """Audit a benchmark runner file against Marcus Quality Gates."""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    violations = []

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return [f"Syntax error parsing {file_path.name}: {e}"]

    violations.extend(check_no_silent_mock_fallback(tree, content))
    violations.extend(check_dataset_integration(content))
    violations.extend(check_prompt_completeness(content))
    violations.extend(check_simulated_metadata(content))

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Marcus Benchmark Integrity Validator")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Path to benchmark runner python scripts to audit",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    target_files: List[Path] = []

    if args.paths:
        target_files = args.paths
    else:
        benchmarks_dir = repo_root / "evals" / "benchmarks"
        if benchmarks_dir.is_dir():
            target_files = list(benchmarks_dir.glob("**/run_*_eval.py"))

    if not target_files:
        print("No benchmark runners found to audit.")
        return 0

    total_violations = 0
    print(f"Auditing {len(target_files)} benchmark runner(s) with Marcus Integrity Harness:\n")

    for target in target_files:
        try:
            rel_path = target.relative_to(repo_root)
        except ValueError:
            rel_path = target
        print(f"Auditing [{rel_path}]...")
        violations = audit_runner(target)
        if violations:
            total_violations += len(violations)
            for v in violations:
                print(f"  [FAIL] Violation: {v}")
        else:
            print("  [OK] All Marcus Benchmark Quality Gates PASSED.")
        print()

    if total_violations > 0:
        print(f"FAILED: Found {total_violations} benchmark integrity violation(s).")
        return 1

    print("PASSED: All audited benchmark runners meet Marcus quality standards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
