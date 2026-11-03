#!/usr/bin/env python3
"""Fail when a benchmark registry row is not backed by a live results.json.

Reads the table under "## 4. Benchmark Run Registry" in docs/BENCHMARKS.md.
Each row must link a results.json that exists, records ``"simulated": false``,
and matches the row's task count and pass rates.

Usage:
    python scripts/check_benchmark_claims.py [--repo DIR]

Exit codes:
    0  every registry row is backed by a live results.json
    1  a row is unbacked, simulated or does not match its file
    2  the registry table is missing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

DOC = Path("docs") / "BENCHMARKS.md"
HEADING = "## 4. Benchmark Run Registry"
LINK = re.compile(r"\[[^\]]*\]\(([^)]+results\.json)\)")
PERCENT = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")


def registry_rows(text: str) -> Optional[List[List[str]]]:
    """Return the cells of each data row of the first table after HEADING, or None."""
    if HEADING not in text:
        return None
    section = text.split(HEADING, 1)[1].split("\n## ", 1)[0]
    rows: List[List[str]] = []
    for line in section.splitlines():
        if line.startswith("### "):
            break
        if line.startswith("|") and not set(line) <= set("|- "):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows[1:]  # first row is the header


def pct(cell: str) -> Optional[float]:
    m = PERCENT.search(cell)
    return float(m.group(1)) if m else None


def check_row(repo: Path, cells: List[str]) -> List[str]:
    run_id = cells[0].strip("`")
    link = LINK.search(" ".join(cells))
    if not link:
        return [f"{run_id}: no results.json link"]
    path = (repo / DOC).parent / link.group(1)
    if not path.is_file():
        return [f"{run_id}: {link.group(1)} does not exist"]
    comp = json.loads(path.read_text(encoding="utf-8")).get("comparison", {})
    if comp.get("simulated") is not False:
        return [f"{run_id}: results.json does not record simulated=false"]
    errors = []
    bare, dem = comp.get("bare", {}), comp.get("demiurge", {})
    if str(bare.get("total_tasks")) != cells[4]:
        errors.append(f"{run_id}: row says {cells[4]} tasks, file says {bare.get('total_tasks')}")
    for label, cell, arm in (("bare", cells[5], bare), ("demiurge", cells[6], dem)):
        want = round(arm.get("pass_rate", -1) * 100, 1)
        got = pct(cell)
        if got is None or abs(got - want) > 0.05:
            errors.append(f"{run_id}: {label} pass is {cell}, file says {want}%")
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    repo = Path(parser.parse_args(argv).repo)
    rows = registry_rows((repo / DOC).read_text(encoding="utf-8"))
    if rows is None:
        print(f"ERROR: '{HEADING}' not found in {DOC}", file=sys.stderr)
        return 2
    errors = [e for cells in rows for e in check_row(repo, cells)]
    for e in errors:
        print(f"FAIL  {e}")
    if errors:
        return 1
    print(f"OK    {len(rows)} registry row(s) backed by live results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
