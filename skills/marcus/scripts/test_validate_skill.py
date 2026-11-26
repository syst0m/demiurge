#!/usr/bin/env python3
"""Tests for validate_skill.py: a skill with no SKILL.md or no frontmatter must fail."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_skill as vs  # noqa: E402

GOOD = """---
name: sample-skill
description: Use when the user asks for a sample skill check.
---

# Sample skill

Do the sample task in three steps.
"""


class ValidateSkillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "sample-skill"
        self.dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_skill_md_is_blocking(self):
        findings = vs.validate(self.dir)
        self.assertEqual([f.code for f in findings], ["skill-md-missing"])
        self.assertEqual(findings[0].level, vs.BLOCKING)

    def test_missing_frontmatter_is_blocking(self):
        (self.dir / "SKILL.md").write_text("# No frontmatter here\n", encoding="utf-8")
        codes = [f.code for f in vs.validate(self.dir)]
        self.assertIn("frontmatter-missing", codes)

    def test_well_formed_skill_has_no_blocking_findings(self):
        (self.dir / "SKILL.md").write_text(GOOD, encoding="utf-8")
        blocking = [f for f in vs.validate(self.dir) if f.level == vs.BLOCKING]
        self.assertEqual(blocking, [])


if __name__ == "__main__":
    unittest.main()
