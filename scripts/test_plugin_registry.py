#!/usr/bin/env python3
"""Tests for scripts/plugin_registry.py. Run: python scripts/test_plugin_registry.py"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plugin_registry as pr  # noqa: E402

REG = {
    "ponytail": {"provides_skills": ["ponytail"],
                 "harness": {"claude-code": "ponytail@ponytail", "hermes": "ponytail", "antigravity": "ponytail"}},
    "token-optimizer": {"provides_skills": ["token-optimizer", "resume-checkpoint"],
                        "harness": {"claude-code": "token-optimizer@alexgreensh-token-optimizer",
                                    "hermes": "token-optimizer", "antigravity": None}},
    "i-have-adhd": {"provides_skills": ["i-have-adhd"],
                    "harness": {"claude-code": None, "hermes": None, "antigravity": "i-have-adhd"}},
}


def probe_none(harness, plugin_id):
    return False


def probe_all(harness, plugin_id):
    return True


class PlanTests(unittest.TestCase):
    def test_installed_plugin_is_use_and_excludes_its_skills(self):
        rows = pr.plan("claude-code", ["ponytail"], REG, probe_all)
        self.assertEqual(rows[0]["status"], "use")
        self.assertEqual(pr.exclusions(rows, REG), {"ponytail"})

    def test_missing_plugin_is_fallback_with_hint_and_no_exclusion(self):
        rows = pr.plan("claude-code", ["ponytail"], REG, probe_none)
        self.assertEqual(rows[0]["status"], "fallback")
        self.assertIn("/plugin install ponytail@ponytail", rows[0]["hint"])
        self.assertEqual(pr.exclusions(rows, REG), set())

    def test_harness_without_build_is_unsupported(self):
        rows = pr.plan("antigravity", ["token-optimizer"], REG, probe_all)
        self.assertEqual(rows[0]["status"], "unsupported")
        self.assertEqual(pr.exclusions(rows, REG), set())

    def test_claude_only_plugin_is_unsupported_on_hermes(self):
        rows = pr.plan("hermes", ["i-have-adhd"], REG, probe_all)
        self.assertEqual(rows[0]["status"], "unsupported")

    def test_unknown_plugin_is_unsupported_not_an_error(self):
        rows = pr.plan("claude-code", ["nope"], REG, probe_all)
        self.assertEqual(rows[0]["status"], "unsupported")

    def test_exclusion_covers_every_skill_the_plugin_provides(self):
        rows = pr.plan("claude-code", ["token-optimizer"], REG, probe_all)
        self.assertEqual(pr.exclusions(rows, REG), {"token-optimizer", "resume-checkpoint"})


class ProbeTests(unittest.TestCase):
    def test_claude_probe_reads_installed_plugins_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            f = home / ".claude" / "plugins" / "installed_plugins.json"
            f.parent.mkdir(parents=True)
            f.write_text(json.dumps({"plugins": {"ponytail@ponytail": [{}]}}), encoding="utf-8")
            orig = pr._home
            pr._home = lambda: home
            try:
                self.assertTrue(pr.installed_probe("claude-code", "ponytail@ponytail"))
                self.assertFalse(pr.installed_probe("claude-code", "caveman@caveman"))
            finally:
                pr._home = orig

    def test_hermes_probe_needs_plugin_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hermes"
            (root / "plugins" / "ponytail").mkdir(parents=True)
            (root / "plugins" / "ponytail" / "plugin.yaml").write_text("name: ponytail\n", encoding="utf-8")
            orig = pr.hermes_root
            pr.hermes_root = lambda: root
            try:
                self.assertTrue(pr.installed_probe("hermes", "ponytail"))
                self.assertFalse(pr.installed_probe("hermes", "token-optimizer"))
            finally:
                pr.hermes_root = orig


if __name__ == "__main__":
    unittest.main()
