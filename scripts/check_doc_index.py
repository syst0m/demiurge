#!/usr/bin/env python3
"""Blocks any docs/ markdown file that is not indexed in docs/README.md (and docs/DOCUMENTATION.md when it belongs in the master TOC).

Exit codes: 0 all docs indexed, 1 unindexed doc found, 2 usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
DOCS_DIR_NAME = "docs"


def extract_links(path: Path) -> set[str]:
    """Return all doc-relative targets linked from one markdown file."""
    if not path.is_file():
        return set()
    content = path.read_text(encoding="utf-8")
    targets: set[str] = set()
    for _text, dest in MD_LINK_RE.findall(content):
        clean = dest.split("#")[0].strip()
        if not clean or clean.startswith(("http://", "https://", "#")):
            continue
        targets.add(clean)
    return targets


def index_docs(root: Path) -> set[Path]:
    """All docs/*.md reachable from docs/README.md (and docs/DOCUMENTATION.md)."""
    readme = root / "docs" / "README.md"
    master = root / "docs" / "DOCUMENTATION.md"
    linked: set[str] = set()
    for p in (readme, master):
        if p.is_file():
            linked |= extract_links(p)
    resolved: set[Path] = set()
    docs_dir = root / "docs"
    for target in linked:
        candidate = (docs_dir / target).resolve()
        if not candidate.exists():
            candidate = (root / target).resolve()
        if candidate.exists() and DOCS_DIR_NAME in candidate.parts:
            resolved.add(candidate)
    return resolved


def find_unindexed(root: Path) -> list[Path]:
    docs_dir = root / DOCS_DIR_NAME
    if not docs_dir.is_dir():
        return []
    indexed = index_docs(root)
    unindexed: list[Path] = []
    for md in sorted(docs_dir.rglob("*.md")):
        resolved = md.resolve()
        if resolved == (docs_dir / "README.md").resolve():
            continue  # the index itself is not required to link to itself
        if "reports" in resolved.relative_to(docs_dir).parts:
            continue  # docs/reports/ is the run registry, not part of the doc index
        if resolved not in indexed:
            unindexed.append(resolved)
    return unindexed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ensure every docs/ markdown file is linked from docs/README.md."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root (default: this script's parent's parent)",
    )
    args = parser.parse_args(argv)

    unindexed = find_unindexed(args.root)
    if unindexed:
        print("DRIFT  docs not indexed in docs/README.md (or docs/DOCUMENTATION.md):")
        for md in unindexed:
            print(f"  {md.relative_to(args.root)}")
        print("\nAdd a link to docs/README.md (and docs/DOCUMENTATION.md if it belongs in the master TOC), then re-run.")
        return 1
    print("OK  all docs/ markdown files are indexed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
