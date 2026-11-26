#!/usr/bin/env python3
"""Tests for modify_skill.py: a change with too little evidence, or a missing skill, must be refused."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "modify_skill.py"


class ModifySkillRefusalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.skill = Path(self.tmp.name) / "skill"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text("---\nname: skill\ndescription: x\n---\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_no_evidence_is_refused(self):
        proc = self.run_script(str(self.skill), "--feature", "add a step")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("REFUSED", proc.stderr)

    def test_missing_skill_is_refused(self):
        proc = self.run_script(str(Path(self.tmp.name) / "nope"), "--feature", "add a step", "--evidence", "a")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("skill directory not found", proc.stderr)


if __name__ == "__main__":
    unittest.main()
