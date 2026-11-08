#!/usr/bin/env python3
"""Tests for check_doc_index.py against a temporary repo."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_doc_index as doc_index  # noqa: E402


class DocIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.docs = self.root / "docs"
        self.docs.mkdir()
        (self.docs / "README.md").write_text(
            "# Index\n| [Guide](GUIDE.md) | guide |\n| [Master Documentation](DOCUMENTATION.md) | master |\n", encoding="utf-8"
        )
        (self.docs / "DOCUMENTATION.md").write_text(
            "# Master\n- [Guide](GUIDE.md)\n", encoding="utf-8"
        )
        (self.docs / "GUIDE.md").write_text("# guide\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, *extra_args):
        return doc_index.main(["--root", str(self.root), *extra_args])

    def test_all_docs_indexed_passes(self):
        self.assertEqual(self.invoke(), 0)

    def test_unindexed_doc_fails(self):
        (self.docs / "ORPHAN.md").write_text("# orphan\n", encoding="utf-8")
        self.assertEqual(self.invoke(), 1)

    def test_reports_dir_not_required(self):
        reports = self.docs / "reports"
        reports.mkdir()
        (reports / "README.md").write_text("# reports registry\n", encoding="utf-8")
        self.assertEqual(self.invoke(), 0)


if __name__ == "__main__":
    unittest.main()
