#!/usr/bin/env python3
"""Check that a Build Brief has the parts Imhotep's SKILL.md requires.

Usage:
    python brief_check.py BRIEF.md

Exit codes:
    0  every required part is present
    1  a part is missing
"""

from __future__ import annotations

import re
import sys
from typing import List, Optional

FIXED_CLAUSE = "Report the real result against the judge"
# (label, pattern) for each numbered part of the brief in SKILL.md step 2.
PARTS = [
    ("goal beyond the goal", r"goal beyond the goal"),
    ("types picked and skipped", r"types?\b.*(altitude|depth|range)|(altitude|depth|range).*skipp"),
    ("target", r"\btarget\b"),
    ("judge: visible checks", r"visible"),
    ("judge: held-out checks", r"held-out|heldout"),
    ("judge paths and base commit", r"base commit|judge paths?"),
    ("access", r"\baccess\b"),
    ("backlog", r"\bbacklog\b"),
]
GROUNDING = re.compile(r"claim[: ]+[a-z]+\.[a-z0-9-]+|my judgement", re.IGNORECASE)


def missing_parts(text: str) -> List[str]:
    low = text.lower()
    out = [label for label, pat in PARTS if not re.search(pat, low)]
    if FIXED_CLAUSE.lower() not in low:
        out.append("fixed clause")
    if not GROUNDING.search(text):
        out.append("grounding (a claim id or 'my judgement')")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    missing = missing_parts(open(args[0], encoding="utf-8").read())
    for m in missing:
        print(f"MISSING  {m}")
    if missing:
        return 1
    print("OK       brief has every required part")
    return 0


if __name__ == "__main__":
    sys.exit(main())
