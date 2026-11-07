#!/usr/bin/env python3
"""
test_changelog_digest.py - Tests for scripts/changelog_digest.py.

Run with: python scripts/run_unit_tests.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout

# Make scripts importable when run from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import changelog_digest as cd  # noqa: E402


class ChangelogDigestTest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = 2000

    def test_item_preview_short(self):
        self.assertEqual(cd._item_preview("Short item", 140), "Short item")

    def test_item_preview_truncates(self):
        text = "x" * 200
        preview = cd._item_preview(text, 140)
        self.assertEqual(len(preview), 140)
        self.assertTrue(preview.endswith("…"))

    def test_iso_week_today(self):
        year, week, _ = date.today().isocalendar()
        iso_year, iso_week = cd._iso_week(date.today())
        self.assertEqual(iso_year, year)
        self.assertEqual(iso_week, week)

    def test_parse_changelog_structures(self):
        blocks = cd.parse_changelog()
        self.assertGreaterEqual(len(blocks), 1)
        latest = next(b for b in blocks if b.get("date") is not None)
        self.assertIsNotNone(latest["date"])
        self.assertTrue(latest["category"])
        for block in blocks:
            if block["version"] == "Unreleased":
                self.assertIsNone(block.get("date"))

    def test_parse_changelog_cuts_off_unknown_category(self):
        path = Path(__file__).parent / "CHANGELOG_FAKE.md"
        path.write_text(
            "## [0.1.0] - 2026-01-01\n\n### Added\n- Real item\n- Also added\n\n### Fixed\n- Bug fix\n",
            encoding="utf-8",
        )
        try:
            blocks = cd.parse_changelog(changelog_path=path)
            self.assertEqual(len(blocks), 1)
            self.assertEqual(blocks[0]["category"]["Added"], ["Real item", "Also added"])
            self.assertEqual(blocks[0]["category"]["Fixed"], ["Bug fix"])
        finally:
            path.unlink()

    def test_build_digest_current_week(self):
        digest = cd._build_digest(cd.parse_changelog(), week=(2026, 44))
        self.assertIsNotNone(digest)
        self.assertIn("# Weekly Changelog Digest", digest)
        self.assertIn("ISO week", digest)
        self.assertIn("## 2026-W44", digest)

    def test_build_digest_plain_current_week(self):
        digest = cd._build_digest_plain(cd.parse_changelog(), week=(2026, 44))
        self.assertIsNotNone(digest)
        self.assertIn("Weekly changelog digest, ISO", digest)
        self.assertIn("2026-W44", digest)

    def test_build_digest_no_entries_for_past_week(self):
        fake = Path(__file__).parent / "CHANGELOG_FAKE.md"
        fake.write_text(
            "## [0.1.0] - 2026-01-01\n\n### Added\n- Item\n",
            encoding="utf-8",
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "digest.md")
                old_cwd = os.getcwd()
                os.chdir(Path(__file__).parent)
                try:
                    buf = StringIO()
                    with redirect_stdout(buf):
                        rc = cd.main(["--out", out, "--from", "2030-01-01", "--to", "2030-01-07"])
                    self.assertEqual(rc, 0)
                    self.assertIn("No entries in the requested week.", buf.getvalue())
                finally:
                    os.chdir(old_cwd)
        finally:
            fake.unlink()

    def test_main_writes_to_out_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "digest.md")
            old_cwd = os.getcwd()
            os.chdir(Path(__file__).parent)
            try:
                rc = cd.main(["--out", out, "--from", "2026-10-26", "--to", "2026-11-01"])
            finally:
                os.chdir(old_cwd)
            self.assertEqual(rc, 0)
            self.assertIn("Imhotep", Path(out).read_text(encoding="utf-8"))

    def test_week_arg(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "digest.md")
            old_cwd = os.getcwd()
            os.chdir(Path(__file__).parent)
            try:
                rc = cd.main(["--out", out, "--week", "2026-W44"])
            finally:
                os.chdir(old_cwd)
            self.assertEqual(rc, 0)
            self.assertIn("2026-W44", Path(out).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
