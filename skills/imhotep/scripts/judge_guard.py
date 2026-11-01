#!/usr/bin/env python3
"""Fail a build that changed its own judge.

Imhotep commits its visible and held-out checks before it builds. This script
compares each judge path against that base commit and fails when any of them
was modified, deleted or is uncommitted, so a gamed check cannot pass silently.

Usage:
    python judge_guard.py --base <commit> --paths <path> [<path> ...] [--repo DIR]

Exit codes:
    0  no judge path changed since --base
    1  a judge path changed
    2  usage error, or --base is not a commit in --repo
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import List, Optional


def changed_judge_paths(repo: str, base: str, paths: List[str]) -> List[str]:
    # Working tree against base: catches committed, staged and unstaged edits alike.
    out = subprocess.run(
        ["git", "-C", repo, "diff", "--name-only", base, "--", *paths],
        check=True, capture_output=True, text=True,
    ).stdout
    untracked = subprocess.run(
        ["git", "-C", repo, "ls-files", "--others", "--exclude-standard", "--", *paths],
        check=True, capture_output=True, text=True,
    ).stdout
    return sorted(set(out.split()) | set(untracked.split()))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--paths", required=True, nargs="+")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    if subprocess.run(["git", "-C", args.repo, "cat-file", "-e", f"{args.base}^{{commit}}"],
                      capture_output=True).returncode:
        print(f"ERROR: {args.base} is not a commit in {args.repo}", file=sys.stderr)
        return 2
    changed = changed_judge_paths(args.repo, args.base, args.paths)
    for path in changed:
        print(f"CHANGED  {path}")
    if changed:
        print("The judge changed after it was committed. Restore it, and escalate if it was wrong.")
        return 1
    print(f"OK       {len(args.paths)} judge path(s) unchanged since {args.base[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
