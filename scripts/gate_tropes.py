#!/usr/bin/env python3
"""Scan Markdown for negative parallelism - the "it is not X, it is Y" construction
and its variants. Based on woerndl/unsloppify and tropes.fyi.
Cross-platform python version that runs on Linux, macOS, and Windows.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TROPE_PATTERN = re.compile(
    r"(?:it is|it's) not .+(?:,|;|—|-) it(?: is|'s) "
    r"|not because .+, but because"
    r"|(?:the question|the problem) is not .+\. (?:the question|the problem) is "
    r"|isn't just .+(?:,|;|—|-) it(?: is|'s) "
    r"|(?:is|are) not just .+(?:,|;|—|-) (?:it is|it's|they are|they're)",
    re.IGNORECASE,
)


def get_markdown_files() -> list[str]:
    res = subprocess.run(
        ["git", "ls-files", "*.md"], capture_output=True, text=True, check=True
    )
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def main() -> int:
    print("Scanning for AI tropes (negative parallelism)...")
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = get_markdown_files()

    if not files:
        print("No Markdown files to scan.")
        return 0

    violations = []
    for fpath in files:
        p = Path(fpath)
        if not p.is_file():
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            for idx, line in enumerate(content.splitlines(), 1):
                if TROPE_PATTERN.search(line):
                    violations.append(f"{fpath}:{idx}:{line}")
        except Exception as e:
            print(f"Warning: could not read {fpath}: {e}", file=sys.stderr)

    if violations:
        print("\n".join(violations))
        print("\nError: negative parallelism detected in the lines above.")
        print(
            "Rewrite them with plain constructions. State the thing you mean and stop."
        )
        return 1

    print("No AI tropes detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
