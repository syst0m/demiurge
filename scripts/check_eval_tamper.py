#!/usr/bin/env python3
"""Blocking gate: a pull request must not edit a skill and its own existing evals together.

An agent that edits its own evaluator can pass any test. This gate fails a pull request that
modifies an existing `skills/<name>/evals/evals.json` and also changes any other file of the
same skill, unless a commit message carries a line `Evals: reviewed`. A new skill (evals.json
added, not modified) is not flagged. The skip is printed, never silent.

Usage: python scripts/check_eval_tamper.py --base origin/main
Exit codes: 0 pass or skipped, 1 gate failed, 2 usage error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

SKIP_LINE = re.compile(r"^\s*Evals:\s*reviewed\s*$", re.IGNORECASE | re.MULTILINE)
EVALS = re.compile(r"^skills/([^/]+)/evals/evals\.json$")
SKILL_FILE = re.compile(r"^skills/([^/]+)/(?!evals/)")


def check(changes: List[Tuple[str, str]], messages: str) -> Tuple[List[str], Optional[str]]:
    """changes is (git status letter, path) pairs. Returns (errors, note)."""
    if SKIP_LINE.search(messages):
        return [], "skipped: a commit message carries 'Evals: reviewed'"
    edited_evals = {m.group(1) for status, path in changes
                    if status.startswith("M") and (m := EVALS.match(path))}
    touched: Dict[str, List[str]] = {}
    for _, path in changes:
        if (m := SKILL_FILE.match(path)) and m.group(1) in edited_evals:
            touched.setdefault(m.group(1), []).append(path)
    errors = [f"skill '{name}' changes its evals.json and {len(files)} other file(s) "
              f"(for example {files[0]}). A person must review the evals change."
              for name, files in sorted(touched.items())]
    return errors, None


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Blocking skill-and-evals tamper gate")
    parser.add_argument("--base", required=True, help="base ref, for example origin/main")
    args = parser.parse_args()
    try:
        raw = _git("diff", "--name-status", f"{args.base}...HEAD")
        messages = _git("log", "--format=%B", f"{args.base}..HEAD")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    changes = [(parts[0], parts[-1]) for line in raw.splitlines()
               if len(parts := line.split("\t")) >= 2]
    errors, note = check(changes, messages)
    if note:
        print(f"NOTE: eval tamper gate {note}")
        return 0
    if errors:
        for err in errors:
            print(f"FAIL  {err}")
        print("Skip after review with a commit message line: Evals: reviewed")
        return 1
    print("OK    eval tamper gate: no skill edits its own existing evals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
