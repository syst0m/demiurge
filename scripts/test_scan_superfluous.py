#!/usr/bin/env python3
"""Tests for scan_superfluous.py: a chat-style comment must be flagged, plain code must not."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan_superfluous as ss  # noqa: E402


class ScanFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self, name: str, body: str):
        path = self.root / name
        path.write_text(body, encoding="utf-8")
        return ss.scan_file(path, self.root)

    def test_plain_code_is_clean(self):
        self.assertEqual(self.scan("clean.py", "# Sort by date, newest first.\nx = sorted(items)\n"), [])

    def test_chat_transcript_comment_is_flagged(self):
        findings = self.scan("chatty.py", "# In our previous chat we chose a dict.\nx = {}\n")
        self.assertTrue(findings, "a comment that quotes the chat must be flagged")


if __name__ == "__main__":
    unittest.main()
