"""Tests for judge_guard.py against a throwaway git repository."""

import subprocess
import tempfile
import unittest
from pathlib import Path

import judge_guard


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout.strip()


class JudgeGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.invalid")
        git(self.repo, "config", "user.name", "t")
        (Path(self.repo) / "tests").mkdir()
        (Path(self.repo) / "tests" / "test_x.py").write_text("assert True\n")
        (Path(self.repo) / "src.py").write_text("x = 1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "judge")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def run_guard(self):
        return judge_guard.main(["--repo", self.repo, "--base", self.base, "--paths", "tests"])

    def test_build_edits_only_pass(self):
        (Path(self.repo) / "src.py").write_text("x = 2\n")
        self.assertEqual(self.run_guard(), 0)

    def test_uncommitted_judge_edit_fails(self):
        (Path(self.repo) / "tests" / "test_x.py").write_text("pass\n")
        self.assertEqual(self.run_guard(), 1)

    def test_committed_judge_edit_fails(self):
        (Path(self.repo) / "tests" / "test_x.py").write_text("pass\n")
        git(self.repo, "commit", "-qam", "soften")
        self.assertEqual(self.run_guard(), 1)

    def test_new_file_in_judge_path_fails(self):
        (Path(self.repo) / "tests" / "conftest.py").write_text("skip = True\n")
        self.assertEqual(self.run_guard(), 1)

    def test_unknown_base_is_usage_error(self):
        self.assertEqual(judge_guard.main(["--repo", self.repo, "--base", "deadbeef", "--paths", "tests"]), 2)


if __name__ == "__main__":
    unittest.main()
