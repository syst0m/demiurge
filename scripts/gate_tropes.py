#!/usr/bin/env python3
"""Scan Markdown for negative parallelism and the compressed contrast "X, not Y".

Thin delegate. The patterns and scanner live in one place, the i-have-adhd
skill's trope_gate.py, so this repo and the Stop/pre-save hooks cannot drift.
Set TROPE_GATE to point at a different copy; the default is the user-level
skill link.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DEFAULT = Path.home() / ".claude" / "skills" / "i-have-adhd" / "scripts" / "trope_gate.py"


EXCLUDE = Path(__file__).resolve().parent / "trope_exclude.txt"


def excluded() -> set[str]:
    """Paths the gate skips. Each line is PATH<TAB>REASON; a reason is required."""
    out = set()
    for raw in EXCLUDE.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        path, _, reason = raw.partition("\t")
        if not reason.strip():
            raise SystemExit(f"Error: exclusion without a reason: {path!r}")
        out.add(path.strip().replace("\\", "/"))
    return out


def main() -> int:
    gate = Path(os.environ.get("TROPE_GATE", DEFAULT))
    if not gate.is_file():
        print(f"Error: trope gate not found at {gate}. Set TROPE_GATE.", file=sys.stderr)
        return 2
    skip = excluded()
    args = sys.argv[1:]
    if not args:
        listing = subprocess.run(["git", "ls-files", "*.md"], capture_output=True, text=True)
        args = [f for f in listing.stdout.splitlines() if f.strip()]
    files = [f for f in args if f.replace("\\", "/") not in skip]
    print("Scanning for AI tropes (negative parallelism, compressed contrast)...")
    if not files:
        print("No Markdown files to scan.")
        return 0
    return subprocess.run([sys.executable, "-I", str(gate), *files]).returncode


if __name__ == "__main__":
    sys.exit(main())
