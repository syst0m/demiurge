#!/usr/bin/env python3
"""Tests for resolve_config.py: project overrides win over skill defaults, nested keys merge."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_config as rcfg  # noqa: E402


class DeepMergeTest(unittest.TestCase):
    def test_override_wins_and_nested_dicts_merge(self):
        base = {"a": 1, "nested": {"x": 1, "y": 2}}
        override = {"a": 9, "nested": {"y": 3}}
        self.assertEqual(rcfg.deep_merge(base, override), {"a": 9, "nested": {"x": 1, "y": 3}})


class ResolveTest(unittest.TestCase):
    def test_project_override_applies_over_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skill"
            skill_dir.mkdir()
            # JSON is valid YAML, so the fixtures parse with or without PyYAML.
            (skill_dir / "config.default.yaml").write_text('{"mode": "default", "limit": 3}', encoding="utf-8")
            project = root / "project"
            (project / ".agents").mkdir(parents=True)
            (project / ".agents" / "skills.config.yaml").write_text('{"marcus": {"mode": "project"}}', encoding="utf-8")
            result = rcfg.resolve("marcus", skill_dir, project)
            self.assertEqual(result, {"mode": "project", "limit": 3})


if __name__ == "__main__":
    unittest.main()
