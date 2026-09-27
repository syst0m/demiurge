#!/usr/bin/env python3
"""Run every repository unit-test file, each in its own interpreter.

Usage:
    python scripts/run_unit_tests.py [filters...] [--list] [--verbose]

Discovers ``test_*.py`` under ``scripts/``, ``evals/`` and ``skills/`` and runs
each file with ``python -m unittest discover`` from the repository root. The
file's own directory becomes the top-level import directory, so a test can
import a sibling module by name or a repo module as ``scripts.<name>``.
A filter keeps only files whose repo-relative path contains that substring.

Exit codes:
    0  every selected test file passed
    1  at least one test file failed
    2  usage error, or no test file matched
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
SEARCH_ROOTS = ("scripts", "evals", "skills")
SKIP_DIRS = {"__pycache__", "node_modules", "venv", "scratch", "eval_results"}
TEST_GLOB = "test_*.py"


def _skipped(rel_parts: Sequence[str]) -> bool:
    return any(part in SKIP_DIRS or part.startswith(".") for part in rel_parts[:-1])


def discover(repo_root: Path = REPO_ROOT) -> List[Path]:
    """Return repo-relative test files, sorted, without following symlinks."""
    found: dict[Path, Path] = {}
    for root_name in SEARCH_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for path in root.rglob(TEST_GLOB):
            rel = path.relative_to(repo_root)
            if _skipped(rel.parts) or path.is_symlink() or not path.is_file():
                continue
            found.setdefault(path.resolve(), rel)
    return sorted(found.values(), key=lambda p: p.as_posix())


def build_command(rel: Path) -> List[str]:
    test_dir = rel.parent.as_posix()
    return [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        test_dir,
        "-p",
        rel.name,
        "-t",
        test_dir,
    ]


def run_file(rel: Path, repo_root: Path, verbose: bool) -> tuple[int, str, float]:
    cmd = build_command(rel)
    if verbose:
        cmd.append("-v")
    started = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr, time.monotonic() - started


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("filters", nargs="*", help="substring of a repo-relative test path")
    parser.add_argument("--list", action="store_true", help="print the selected files and exit")
    parser.add_argument("--verbose", action="store_true", help="print output of passing files too")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    files = discover(repo_root)
    if args.filters:
        files = [f for f in files if any(flt in f.as_posix() for flt in args.filters)]
    if not files:
        print("ERROR: no test files matched", file=sys.stderr)
        return 2

    if args.list:
        for rel in files:
            print(rel.as_posix())
        return 0

    failed: List[Path] = []
    for rel in files:
        code, output, elapsed = run_file(rel, repo_root, args.verbose)
        status = "PASS" if code == 0 else "FAIL"
        print(f"{status}  {rel.as_posix()}  ({elapsed:.1f}s)")
        if code != 0 or args.verbose:
            print(output.rstrip())
        if code != 0:
            failed.append(rel)

    print(f"\n{len(files) - len(failed)}/{len(files)} test files passed")
    for rel in failed:
        print(f"FAILED   {rel.as_posix()}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
