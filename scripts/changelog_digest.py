#!/usr/bin/env python3
"""
changelog_digest.py - Weekly changelog digest generator.

Reads CHANGELOG.md (Keep a Changelog / SemVer) and prints a digest that groups
release entries into ISO weeks, so a week of merges shows up as a compact
summary instead of a long flat list.

Usage:
    python scripts/changelog_digest.py                 # current ISO week
    python scripts/changelog_digest.py --week 2026-44  # ISO week of a year
    python scripts/changelog_digest.py --from 2026-10-26 --to 2026-11-01
    python scripts/changelog_digest.py --out digest.md

Only the stdlib is used.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

# Keep a Changelog category order.
CATEGORY_ORDER = ("Added", "Changed", "Fixed", "Deprecated", "Removed", "Security")

# "## [0.15.0] - 2026-11-01"  -> version = "0.15.0", date = date(2026, 11, 1)
VERSION_RE = re.compile(r"^##\s+\[(?P<version>[^\]]+)\]\s+-\s+(?P<date>\d{4}-\d{2}-\d{2})$")
# "## [Unreleased]" -> no date (in-progress work).
UNRELEASED_RE = re.compile(r"^##\s+\[Unreleased\]$")
# "### Added" / "### Fixed"
CATEGORY_RE = re.compile(r"^###\s+(?P<category>[A-Za-z]+)$")
# "- **text**: rest of line"
LIST_ITEM_RE = re.compile(r"^-\s+(?P<text>.+)$")


def _parse_date(text: str) -> Optional[date]:
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _iso_week(d: date) -> tuple[int, int]:
    return d.isocalendar()[:2]


def parse_changelog(changelog_path: Path = CHANGELOG_PATH):
    """Return a list of blocks: {version, date, category: [items...]}."""
    blocks: list[dict] = []
    current: Optional[dict] = None
    current_category: Optional[str] = None

    for raw in changelog_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if UNRELEASED_RE.match(line):
            current = {"version": "Unreleased", "category": {}}
            blocks.append(current)
            current_category = None
            continue
        version_match = VERSION_RE.match(line)
        if version_match:
            current = {
                "version": version_match.group("version"),
                "date": _parse_date(version_match.group("date")),
                "category": {},
            }
            blocks.append(current)
            current_category = None
            continue
        if current is None:
            # A category or list item before any version heading (malformed).
            continue
        category_match = CATEGORY_RE.match(line)
        if category_match:
            current_category = category_match.group("category")
            current["category"].setdefault(current_category, [])
            continue
        item_match = LIST_ITEM_RE.match(line)
        if item_match and current is not None and current_category is not None:
            current["category"][current_category].append(item_match.group("text"))

    return blocks


def _item_preview(text: str, limit: int = 140) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _week_key(d: date) -> tuple[int, int]:
    return _iso_week(d)


def _groups_for(blocks, week: Optional[tuple[int, int]] = None):
    """Yield (iso_week, iso_year, block) for blocks in the requested week."""
    for block in blocks:
        if block.get("date") is None:
            continue
        group = _iso_week(block["date"])
        if week is None or group == week:
            yield group[0], group[1], block


def _week_range(iso_year: int, iso_week: int) -> tuple[date, date]:
    """Monday of the ISO week to Sunday of the same week."""
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    return monday, monday + timedelta(days=6)


def _build_digest(blocks, week: Optional[tuple[int, int]] = None, limit: int = 140):
    """Group blocks by ISO week; return markdown digest for the requested week."""
    if week is None:
        week = _iso_week(date.today())

    groups: dict[tuple[int, int], dict[str, list[str]]] = {}
    for iso_year, iso_week, block in _groups_for(blocks, week):
        groups.setdefault(
            (iso_year, iso_week),
            {cat: [] for cat in CATEGORY_ORDER},
        )
        for cat, items in block["category"].items():
            if cat in groups[(iso_year, iso_week)]:
                groups[(iso_year, iso_week)][cat].extend(items)

    if not groups:
        return None

    lines: list[str] = []
    lines.append("# Weekly Changelog Digest")
    lines.append("")
    lines.append(f"*ISO week {week[1]} of {week[0]} ({week[0]}-W{week[1]}).*")
    lines.append("")

    for (iso_year, iso_week), data in sorted(groups.items()):
        start, end = _week_range(iso_year, iso_week)
        lines.append(f"## {iso_year}-W{iso_week:02d} ({start.isoformat()} → {end.isoformat()})")
        lines.append("")

        headings = [c for c in CATEGORY_ORDER if c in data]
        if not headings:
            headings = sorted(data.keys())
            if not headings:
                lines.append("*No entries.*")
                lines.append("")
                continue
        for cat in headings:
            items = data[cat]
            if not items:
                continue
            lines.append(f"### {cat}")
            lines.append("")
            for item in items:
                lines.append(f"- {_item_preview(item, limit)}")
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def _build_digest_plain(blocks, week=None, limit=140):
    if week is None:
        week = _iso_week(date.today())
    groups = {}
    for iso_year, iso_week, block in _groups_for(blocks, week):
        g = groups.setdefault((iso_year, iso_week), {})
        for cat, items in block["category"].items():
            g.setdefault(cat, []).extend(items)
    if not groups:
        return None
    lines = [f"Weekly changelog digest, ISO {week[0]}-W{week[1]}", ""]
    for (iso_year, iso_week), data in sorted(groups.items(), key=lambda t: (t[0], t[1])):
        start, end = _week_range(iso_year, iso_week)
        lines.append(f"--- {start.isoformat()} to {end.isoformat()} ({iso_year}-W{iso_week:02d}) ---")
        for cat in CATEGORY_ORDER:
            items = data.get(cat)
            if items:
                lines.append(f"[{cat}]")
                for item in items:
                    lines.append(f"  - {_item_preview(item, limit)}")
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a weekly changelog digest from CHANGELOG.md.")
    parser.add_argument(
        "--week",
        metavar="YEAR-WEEK",
        help="ISO week of the form YYYY-Www (e.g. 2026-W44). Default: current week.",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        metavar="DATE",
        help="Inclusive start date (YYYY-MM-DD). With --to, overrides --week.",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        metavar="DATE",
        help="Inclusive end date (YYYY-MM-DD). With --from, overrides --week.",
    )
    parser.add_argument(
        "--format",
        choices=("md", "plain"),
        default="md",
        help="Output format (default: md).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=140,
        help="Maximum characters per changelog item (default: 140).",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        help="Write the digest to PATH instead of stdout.",
    )
    args = parser.parse_args(argv) if argv is not None else parser.parse_args()

    blocks = parse_changelog()
    if not blocks:
        print(f"changelog_digest: no version blocks found in {CHANGELOG_PATH}", file=sys.stderr)
        return 1

    week = None
    if args.from_date or args.to_date:
        from_date = _parse_date(args.from_date) if args.from_date else None
        to_date = _parse_date(args.to_date) if args.to_date else None
        if from_date is None or to_date is None:
            print("--from/--to must be YYYY-MM-DD.", file=sys.stderr)
            return 2
        week = _iso_week(from_date)
        if to_date is not None:
            week = (_iso_week(from_date)[0], _iso_week(to_date)[1])
    elif args.week:
        match = re.match(r"^(\d{4})-W(\d{2})$", args.week)
        if not match:
            print("--week must be YYYY-Www, e.g. 2026-W44.", file=sys.stderr)
            return 2
        week = (int(match.group(1)), int(match.group(2)))
    else:
        week = _iso_week(date.today())

    if args.format == "md":
        digest = _build_digest(blocks, week, args.limit)
    else:
        digest = _build_digest_plain(blocks, week, args.limit)

    if digest is None:
        print("No entries in the requested week.")
        return 0

    if args.out:
        Path(args.out).write_text(digest, encoding="utf-8")
    else:
        print(digest, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
