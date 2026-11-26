#!/usr/bin/env python3
"""Tests for gate_tropes.py: a negative-parallelism line must fail the gate, plain text must pass."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_tropes as gt  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "gate_tropes.py"


class TropePatternTest(unittest.TestCase):
    def test_negative_parallelism_matches(self):
        self.assertTrue(gt.TROPE_PATTERN.search("It is not a bug, it is a design choice."))

    def test_contracted_forms_match(self):
        for line in (
            "It isn't a bug, it's a design choice.",
            "It isn’t a bug; it is a design choice.",
            "It’s not a bug, it’s a design choice.",
            "The problem isn't the disk. The problem is the network.",
        ):
            self.assertTrue(gt.TROPE_PATTERN.search(line), line)

    def test_plain_statement_does_not_match(self):
        self.assertFalse(gt.TROPE_PATTERN.search("This is a design choice."))
        self.assertFalse(gt.TROPE_PATTERN.search("It isn't ready."))


class GateRunTest(unittest.TestCase):
    def run_gate(self, body: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text(body, encoding="utf-8")
            return subprocess.run([sys.executable, str(SCRIPT), str(doc)],
                                  capture_output=True, text=True).returncode

    def test_trope_line_fails(self):
        self.assertEqual(self.run_gate("It is not a bug, it is a design choice.\n"), 1)

    def test_plain_file_passes(self):
        self.assertEqual(self.run_gate("This is a design choice.\n"), 0)


if __name__ == "__main__":
    unittest.main()
