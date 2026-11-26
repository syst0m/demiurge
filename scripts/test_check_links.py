#!/usr/bin/env python3
"""Tests for check_links.py: a broken local link must fail, a good one must pass."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_links as cl  # noqa: E402


class ValidateFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "target.md").write_text("# Target\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def doc(self, body: str) -> Path:
        path = self.root / "doc.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_existing_local_link_has_no_errors(self):
        _valid, _invalid, errors = cl.validate_file(self.doc("[see](target.md)\n"), self.root, strict=True)
        self.assertEqual(errors, [])

    def test_missing_local_link_is_an_error(self):
        _valid, _invalid, errors = cl.validate_file(self.doc("[gone](missing.md)\n"), self.root, strict=True)
        self.assertTrue(errors, "a link to a missing file must be reported")

    def test_missing_file_is_an_error(self):
        _valid, invalid, errors = cl.validate_file(self.root / "nope.md", self.root)
        self.assertEqual(invalid, 1)
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
