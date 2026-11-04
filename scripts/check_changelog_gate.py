#!/usr/bin/env python3
"""Blocking gate: every pull request to main must cut a release in CHANGELOG.md.

release.yml tags a release only when a merge adds a new version heading. Entries left under
[Unreleased] never tag. This gate fails a pull request unless:

1. it adds a new `## [x.y.z] - YYYY-MM-DD` heading,
2. the new top version is greater than the base's top version, and
3. [Unreleased] holds no entries after the change.

A pull request may skip the gate with a line `Changelog: none` in any of its commit messages.
The skip is printed, never silent.

Usage: python scripts/check_changelog_gate.py --base origin/main
Exit codes: 0 pass or skipped, 1 gate failed, 2 usage error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from verify_release import SEMVER_HEADING_PATTERN

SKIP_LINE = re.compile(r"^\s*Changelog:\s*none\s*$", re.IGNORECASE | re.MULTILINE)
UNRELEASED_HEADING = re.compile(r"^##\s+\[Unreleased\]\s*$", re.IGNORECASE | re.MULTILINE)
ANY_SECTION = re.compile(r"^##\s+\[", re.MULTILINE)


def _version_key(version: str) -> Tuple[int, int, int]:
    core = version.split("-", 1)[0]
    major, minor, patch = (int(part) for part in core.split("."))
    return major, minor, patch


def _versions(text: str) -> List[str]:
    return [m.group("version") for m in SEMVER_HEADING_PATTERN.finditer(text)]


def _unreleased_entries(text: str) -> List[str]:
    """Non-blank lines under [Unreleased], excluding the ### sub-headings."""
    start = UNRELEASED_HEADING.search(text)
    if not start:
        return []
    rest = text[start.end():]
    nxt = ANY_SECTION.search(rest)
    body = rest[: nxt.start()] if nxt else rest
    return [ln for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("###")]


def check(base_text: str, head_text: str, messages: str) -> Tuple[List[str], Optional[str]]:
    """Return (errors, note). A note means the gate was skipped on purpose."""
    if SKIP_LINE.search(messages):
        return [], "skipped: a commit message carries 'Changelog: none'"
    errors: List[str] = []
    base_versions = _versions(base_text)
    head_versions = _versions(head_text)
    added = [v for v in head_versions if v not in base_versions]
    if not added:
        errors.append("No new version heading. Add '## [x.y.z] - YYYY-MM-DD' so release.yml tags a release.")
    else:
        top_new = max(added, key=_version_key)
        if base_versions and _version_key(top_new) <= _version_key(max(base_versions, key=_version_key)):
            errors.append(f"New version {top_new} is not greater than the base's top version {max(base_versions, key=_version_key)}.")
        for match in SEMVER_HEADING_PATTERN.finditer(head_text):
            if match.group("version") in added and not match.group("date"):
                errors.append(f"Heading for {match.group('version')} has no date. Use '## [{match.group('version')}] - YYYY-MM-DD'.")
    leftovers = _unreleased_entries(head_text)
    if leftovers:
        errors.append(f"[Unreleased] still holds {len(leftovers)} line(s). Move them under the new version heading.")
    return errors, None


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Blocking changelog release gate")
    parser.add_argument("--base", required=True, help="base ref, for example origin/main")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    args = parser.parse_args()
    try:
        base_text = _git("show", f"{args.base}:{args.changelog}")
        messages = _git("log", "--format=%B", f"{args.base}..HEAD")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    head_text = Path(args.changelog).read_text(encoding="utf-8")
    errors, note = check(base_text, head_text, messages)
    if note:
        print(f"NOTE: changelog gate {note}")
        return 0
    if errors:
        for err in errors:
            print(f"FAIL  {err}")
        print("Skip on purpose with a commit message line: Changelog: none")
        return 1
    print("OK    changelog gate: new release heading, [Unreleased] empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
