#!/usr/bin/env python3
"""Gate: every skill in this repo is deployed, and current, in every installed harness.

Harness libraries checked (a harness whose home directory does not exist is skipped, as
scripts/sync-skills.sh skips it):

  claude-code   ~/.claude/skills
  antigravity   ~/.agents/skills
  opencode      ~/.config/opencode/skills

Exit codes: 0 every installed harness holds a current copy of every skill, 1 a copy is missing or
stale. A library that resolves to the same directory as an earlier one is reported once.
The fix for a failure is the user's step: scripts/sync-skills.sh with no flags.

Usage: check_harness_parity.py [--repo <dir>] [--json]
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

HARNESS_LIBRARIES = {
    "claude-code": (".claude", "skills"),
    "antigravity": (".agents", "skills"),
    "opencode": (".config/opencode", "skills"),
}
IGNORED = ("__pycache__", "*.pyc", "results-*.json", "transcripts-*.json", "last_run.json")


def tree(root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or any(fnmatch.fnmatch(part, pat) for part in rel.parts for pat in IGNORED):
            continue
        out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def check(repo: Path, home: Path) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    seen: Dict[Path, str] = {}
    skills = sorted(p for p in (repo / "skills").iterdir() if p.is_dir())
    for harness, (harness_home, sub) in HARNESS_LIBRARIES.items():
        if not (home / harness_home).is_dir():
            findings.append({"harness": harness, "skill": "*", "state": "skipped", "detail": "harness not installed"})
            continue
        library = home / harness_home / sub
        real = library.resolve()
        if real in seen:
            findings.append({"harness": harness, "skill": "*", "state": "skipped",
                             "detail": f"same directory as {seen[real]}"})
            continue
        seen[real] = harness
        for skill in skills:
            deployed = library / skill.name
            if not deployed.is_dir():
                findings.append({"harness": harness, "skill": skill.name, "state": "missing", "detail": str(deployed)})
            elif tree(skill) != tree(deployed):
                findings.append({"harness": harness, "skill": skill.name, "state": "stale", "detail": str(deployed)})
            else:
                findings.append({"harness": harness, "skill": skill.name, "state": "ok", "detail": str(deployed)})
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    findings = check(args.repo.resolve(), args.home)
    failed = [f for f in findings if f["state"] in ("missing", "stale")]
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"{f['state'].upper():8} {f['harness']:12} {f['skill']}  {f['detail'] if f['state'] != 'ok' else ''}".rstrip())
        if failed:
            print("\nHarness parity failed. Deploy with: bash scripts/sync-skills.sh (the user's step; "
                  "agents run only --check --repo-only).", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
