#!/usr/bin/env python3
"""Tests for check_harness_parity.py against a temporary repo and home."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_harness_parity as parity  # noqa: E402


class ParityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo, self.home = base / "repo", base / "home"
        (self.repo / "skills" / "demo").mkdir(parents=True)
        (self.repo / "skills" / "demo" / "SKILL.md").write_text("v1\n", encoding="utf-8")
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def deploy(self, harness_home: str, content: str = "v1\n"):
        skill = self.home / harness_home / "skills" / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(content, encoding="utf-8")

    def states(self):
        return {(f["harness"], f["state"]) for f in parity.check(self.repo, self.home)}

    def test_all_installed_harnesses_current_passes(self):
        for h in (".claude", ".agents", ".config/opencode"):
            self.deploy(h)
        self.assertEqual(self.states(), {("claude-code", "ok"), ("antigravity", "ok"), ("opencode", "ok")})
        self.assertEqual(parity.main(["--repo", str(self.repo), "--home", str(self.home)]), 0)

    def test_opencode_missing_copy_fails(self):
        self.deploy(".claude")
        (self.home / ".config" / "opencode").mkdir(parents=True)
        self.assertIn(("opencode", "missing"), self.states())
        self.assertEqual(parity.main(["--repo", str(self.repo), "--home", str(self.home)]), 1)

    def test_stale_copy_fails(self):
        self.deploy(".claude", "v0\n")
        self.assertIn(("claude-code", "stale"), self.states())

    def test_uninstalled_harness_is_skipped_not_failed(self):
        self.deploy(".claude")
        self.assertIn(("opencode", "skipped"), self.states())
        self.assertEqual(parity.main(["--repo", str(self.repo), "--home", str(self.home)]), 0)

    def test_eval_outputs_and_pycache_do_not_count_as_drift(self):
        self.deploy(".claude")
        d = self.home / ".claude" / "skills" / "demo"
        (d / "evals").mkdir()
        (d / "evals" / "results-x.json").write_text("{}", encoding="utf-8")
        (d / "__pycache__").mkdir()
        (d / "__pycache__" / "a.pyc").write_bytes(b"x")
        self.assertIn(("claude-code", "ok"), self.states())

    def test_symlinked_duplicate_library_checked_once(self):
        self.deploy(".claude")
        (self.home / ".agents").mkdir()
        try:
            os.symlink(self.home / ".claude" / "skills", self.home / ".agents" / "skills", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        found = [f for f in parity.check(self.repo, self.home) if f["harness"] == "antigravity"]
        self.assertEqual(found[0]["state"], "skipped")


if __name__ == "__main__":
    unittest.main()
