#!/usr/bin/env python3
"""Tests for route_check.py: a near-copy description must score as a revision, a distinct one as distinct."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_check as rc  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "route_check.py"


def skill(root: Path, name: str, description: str) -> Path:
    path = root / name
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n", encoding="utf-8")
    return path


class VectorTest(unittest.TestCase):
    def test_identical_descriptions_score_one(self):
        v = rc.vectorise("Format invoices for export. Use when the user asks for invoice formatting.")
        self.assertAlmostEqual(rc.cosine(v, v), 1.0)

    def test_disjoint_descriptions_score_zero(self):
        self.assertEqual(rc.cosine(rc.vectorise("kittens"), rc.vectorise("quarterly tax filing")), 0.0)


class CliTest(unittest.TestCase):
    def check(self, candidate: str, other: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cand = skill(root, "candidate", candidate)
            skill(root, "other", other)
            return subprocess.run([sys.executable, str(SCRIPT), str(cand), "--library", str(root)],
                                  capture_output=True, text=True).returncode

    def test_near_copy_is_a_revision(self):
        text = "Format quarterly invoices for export. Use when the user asks for invoice formatting."
        self.assertEqual(self.check(text, text), 2)

    def test_distinct_skill_passes(self):
        self.assertEqual(self.check("Format quarterly invoices for export. Use when the user asks for invoice formatting.",
                                    "Plan a hiking route with elevation data. Use when the user asks about trails."), 0)


if __name__ == "__main__":
    unittest.main()
