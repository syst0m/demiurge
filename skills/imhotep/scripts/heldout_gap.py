#!/usr/bin/env python3
"""Report the gap between visible and held-out pass rates, and fail a large gap.

Each command must print a final result as ``passed/total`` (for example ``18/20``).
The gap is visible pass rate minus held-out pass rate, in percentage points.

Usage:
    python heldout_gap.py --visible "<cmd>" --heldout "<cmd>" [--max-gap 10] [--cwd DIR]

Exit codes:
    0  the gap is at most --max-gap
    1  the gap is larger than --max-gap
    2  a command printed no ``passed/total``, or a total is zero
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from typing import List, Optional, Tuple

RESULT = re.compile(r"(\d+)\s*/\s*(\d+)")


def parse_result(output: str) -> Optional[Tuple[int, int]]:
    matches = RESULT.findall(output)
    if not matches:
        return None
    passed, total = (int(x) for x in matches[-1])
    return (passed, total) if total > 0 and passed <= total else None


def run(cmd: str, cwd: Optional[str]) -> Optional[Tuple[int, int]]:
    # A failing exit code is expected when tests fail; the printed counts decide.
    done = subprocess.run(shlex.split(cmd), cwd=cwd, capture_output=True, text=True)
    return parse_result(done.stdout + "\n" + done.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--visible", required=True)
    parser.add_argument("--heldout", required=True)
    parser.add_argument("--max-gap", type=float, default=10.0)
    parser.add_argument("--cwd")
    args = parser.parse_args(argv)
    vis, held = run(args.visible, args.cwd), run(args.heldout, args.cwd)
    if vis is None or held is None:
        print("ERROR: a suite printed no valid passed/total result", file=sys.stderr)
        return 2
    vis_pct, held_pct = vis[0] / vis[1] * 100, held[0] / held[1] * 100
    gap = vis_pct - held_pct
    print(f"visible   {vis[0]}/{vis[1]} = {vis_pct:.1f}%")
    print(f"held-out  {held[0]}/{held[1]} = {held_pct:.1f}%")
    print(f"gap       {gap:+.1f} pp (limit {args.max_gap:.1f})")
    return 1 if gap > args.max_gap else 0


if __name__ == "__main__":
    sys.exit(main())
