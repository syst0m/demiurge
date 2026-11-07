#!/usr/bin/env python3
"""Tests for the testing-matrix blocking gate (scripts/testing_matrix_gate.py)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parent / "testing_matrix_gate.py"


class GateCase(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="gate-test-"))
        subprocess.run(["git", "init", "-q", "."], cwd=self.repo, check=True)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def gate(self, *args):
        return subprocess.run([sys.executable, str(GATE), "--repo", str(self.repo), *args],
                              capture_output=True, text=True)

    def write(self, name: str, body: str = "x\n") -> None:
        p = self.repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


class TestBlocks(GateCase):
    def test_source_without_test_blocks(self):
        self.write("app.py")
        out = self.gate()
        self.assertEqual(out.returncode, 1)
        self.assertIn("BLOCKED", out.stdout)
        for heading in ("Impact Analysis", "Implementation/Update/Deletion Plan", "Execution Approach"):
            self.assertIn(heading, out.stdout)

    def test_staged_and_untracked_are_seen(self):
        self.write("a.py")
        subprocess.run(["git", "add", "a.py"], cwd=self.repo, check=True)
        self.assertEqual(self.gate().returncode, 1)
        self.write("b.py")  # untracked
        self.assertEqual(self.gate().returncode, 1)

    def test_test_change_alongs_source_passes(self):
        self.write("app.py")
        self.write("test_app.py")
        self.assertEqual(self.gate().returncode, 0)

    def test_test_directories_are_tests(self):
        self.write("app.py")
        self.write("tests/test_app.py")
        self.assertEqual(self.gate().returncode, 0)

    def test_gate_script_is_not_mistaken_for_a_test(self):
        """Regression: a substring match marked `testing_matrix_gate.py` as a test, so a
        source-only diff passed."""
        self.write("app.py")
        self.write("hooks/testing_matrix_gate.py")
        self.assertEqual(self.gate().returncode, 1)

    def test_latest_and_contest_are_not_tests(self):
        self.write("latest.py")
        self.assertEqual(self.gate().returncode, 1)

    def test_conftest_is_a_test(self):
        self.write("app.py")
        self.write("tests/conftest.py")
        self.assertEqual(self.gate().returncode, 0)

    def test_docs_only_passes(self):
        self.write("docs/NOTE.md")
        self.assertEqual(self.gate().returncode, 0)

    def test_json_mode_allows_the_hook_to_decide(self):
        self.write("app.py")
        out = self.gate("--json")
        self.assertEqual(out.returncode, 0)
        self.assertIn('"decision": "block"', out.stdout)

    def test_dialects_differ_per_harness(self):
        """Claude Code blocks a Stop with 'block'; Antigravity with 'continue'."""
        self.write("app.py")
        claude = json.loads(self.gate("--json", "--hook-format", "claude-code").stdout)
        anti = json.loads(self.gate("--json", "--hook-format", "antigravity").stdout)
        self.assertEqual(claude["decision"], "block")
        self.assertEqual(anti["decision"], "continue")
        self.assertNotEqual(claude["decision"], anti["decision"])

    def test_dialect_allows_stop_when_tests_present(self):
        self.write("app.py")
        self.write("test_app.py")
        claude = json.loads(self.gate("--json", "--hook-format", "claude-code").stdout)
        anti = json.loads(self.gate("--json", "--hook-format", "antigravity").stdout)
        self.assertEqual(claude, {})
        self.assertEqual(anti["decision"], "stop")

    def test_non_git_repository_passes(self):
        plain = self.repo / "plain"
        plain.mkdir()
        out = subprocess.run([sys.executable, str(GATE), "--repo", str(plain)],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
