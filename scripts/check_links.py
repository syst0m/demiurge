#!/usr/bin/env python3
"""Harness script to validate markdown links and references across Demiurge documentation."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_TARGETS = [
    "research/RESEARCH.md",
    "skills/marcus/references/RESEARCH.md",
    "skills/marcus/references/EVIDENCE.md",
    "skills/marcus/AGENT_ARCHITECTURE.md",
    "skills/buckminster/references/RESEARCH_METHODOLOGY.md",
    "docs/DOCUMENTATION.md",
    "docs/OPERATING_GUIDE.md",
    "docs/AGENT_DESIGN.md",
    "docs/INSTALLATION.md",
    "README.md",
    "skills/marcus/human-only/demiurge-brief.md",
    ".agents/rules/artifact-generation.md",
    ".agents/rules/release-management.md",
]

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def validate_file(
    file_path: Path, root_dir: Path, strict: bool = False
) -> tuple[int, int, list[str]]:
    if not file_path.exists():
        return 0, 1, [f"Missing file: {file_path}"]

    content = file_path.read_text(encoding="utf-8")
    links = MD_LINK_RE.findall(content)
    errors: list[str] = []
    valid_count = 0

    for text, dest in links:
        dest_clean = dest.strip()
        # Remote URL
        if dest_clean.startswith(("http://", "https://")):
            parsed = urlparse(dest_clean)
            if not parsed.netloc:
                errors.append(f"Invalid URL '{dest_clean}' for text '{text}'")
            else:
                valid_count += 1
            continue

        # Fragment-only link (#heading)
        if dest_clean.startswith("#"):
            valid_count += 1
            continue

        # Local filesystem path
        target_path_str = dest_clean.split("#")[0]
        if not target_path_str:
            valid_count += 1
            continue

        target = (file_path.parent / target_path_str).resolve()
        if not target.exists():
            # Check relative to root
            alt_target = (root_dir / target_path_str.lstrip("/\\")).resolve()
            if alt_target.exists():
                valid_count += 1
            else:
                errors.append(
                    f"Broken local link: [{text}]({dest}) -> path not found: {target}"
                )
        else:
            valid_count += 1

    return valid_count, len(errors), errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify markdown links and references."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_TARGETS,
        help="Files or directories to inspect.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status if any broken links or missing files are found.",
    )
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    total_valid = 0
    total_broken = 0
    all_errors: list[str] = []

    print(f"Demiurge Link Harness: checking {len(args.paths)} targets...")
    print("-" * 72)

    for p in args.paths:
        target = root_dir / p if not os.path.isabs(p) else Path(p)
        if target.is_dir():
            files = list(target.rglob("*.md"))
        else:
            files = [target]

        for f in files:
            valid, broken, errors = validate_file(f, root_dir, strict=args.strict)
            total_valid += valid
            total_broken += broken
            all_errors.extend(errors)
            rel_path = (
                f.relative_to(root_dir) if f.is_relative_to(root_dir) else f
            )
            status = "OK" if broken == 0 else f"FAIL ({broken} errors)"
            print(f"{str(rel_path):<50} {valid:>3} links  [{status}]")

    print("-" * 72)
    print(
        f"Summary: {total_valid} valid links, {total_broken} broken/missing references."
    )

    if all_errors:
        print("\nErrors identified:")
        for err in all_errors:
            print(f"  - {err}")
        if args.strict:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
