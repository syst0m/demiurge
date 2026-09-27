#!/usr/bin/env python3
"""
test_sync_skills.py - Unit tests for the sync-skills.sh argument parsing and deploy guards.

Every test runs a copy of the script inside a temporary repo tree with HOME
pointed at a temporary directory, so no real deploy target is touched.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sync-skills.sh"
WSL_REFUSED = "bash not found (WSL bash refused)"


def _refuse_wsl(candidate: str | None) -> str | None:
    if not candidate:
        return None
    if "system32" in str(Path(candidate)).lower():
        return None
    return candidate


def resolve_bash() -> str | None:
    """Resolve bash: DEMIURGE_BASH, then Git for Windows bash next to git, then PATH."""
    override = os.environ.get("DEMIURGE_BASH")
    if override:
        return _refuse_wsl(override)
    git = shutil.which("git")
    if git:
        git_dir = Path(git).resolve().parent
        for candidate in (
            git_dir / "bash.exe",
            git_dir.parent / "bin" / "bash.exe",
            git_dir.parent.parent / "bin" / "bash.exe",
        ):
            if candidate.is_file():
                return _refuse_wsl(str(candidate))
    return _refuse_wsl(shutil.which("bash"))


BASH = resolve_bash()


@unittest.skipUnless(BASH, WSL_REFUSED)
class TestSyncSkills(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "repo"
        self.home = self.tmp / "home"
        self.home.mkdir()
        (self.root / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT, self.root / "scripts" / "sync-skills.sh")
        (self.root / "research").mkdir()
        (self.root / "research" / "RESEARCH.md").write_text("# Research\n", encoding="utf-8")
        refs = self.root / "skills" / "marcus" / "references"
        refs.mkdir(parents=True)
        (refs / "RESEARCH.md").write_text("# Research\n", encoding="utf-8")
        self.target = self.home / ".claude" / "skills"

    def tearDown(self):
        self._tmp.cleanup()

    def run_sync(self, *args: str) -> subprocess.CompletedProcess:
        env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", ""),
            "GIT_CEILING_DIRECTORIES": str(self.tmp),
            "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHON": sys.executable,
        }
        for key in ("SYSTEMROOT", "TEMP", "TMP", "COMSPEC"):
            if key in os.environ:
                env[key] = os.environ[key]
        return subprocess.run(
            [BASH, str(self.root / "scripts" / "sync-skills.sh"), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

    def deploy_identical(self):
        self.target.mkdir(parents=True)
        shutil.copytree(self.root / "skills" / "marcus", self.target / "marcus")

    def test_identical_copy_exits_0(self):
        result = self.run_sync("--check", "--repo-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("DRIFT", result.stdout)

    def test_mutated_copy_exits_1_with_drift(self):
        (self.root / "skills" / "marcus" / "references" / "RESEARCH.md").write_text(
            "# Stale\n", encoding="utf-8"
        )
        result = self.run_sync("--repo-only", "--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("DRIFT    research/RESEARCH.md", result.stdout)

    def test_repo_only_never_creates_home_claude(self):
        (self.root / "skills" / "marcus" / "references" / "RESEARCH.md").write_text(
            "# Stale\n", encoding="utf-8"
        )
        (self.root / "skills" / "demo").mkdir()
        (self.root / "skills" / "demo" / "SKILL.md").write_text("demo\n", encoding="utf-8")
        check = self.run_sync("--check", "--repo-only")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        self.assertFalse((self.home / ".claude").exists())
        apply = self.run_sync("--repo-only")
        self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
        self.assertIn("DISTRIB", apply.stdout)
        self.assertFalse((self.home / ".claude").exists())
        self.assertEqual(
            (self.root / "skills" / "marcus" / "references" / "RESEARCH.md").read_text(encoding="utf-8"),
            "# Research\n",
        )

    def stub_grade_cap(self, exit_code: int) -> Path:
        """A grade_cap.py stand-in that records its arguments and exits with exit_code."""
        research_scripts = self.root / "scripts" / "research"
        research_scripts.mkdir()
        record = self.tmp / "grade_cap_args.txt"
        (research_scripts / "grade_cap.py").write_text(
            "import sys\n"
            f"open({str(record)!r}, 'w', encoding='utf-8').write(' '.join(sys.argv[1:]))\n"
            "print('grade_cap stub says', sys.argv[1])\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )
        return record

    def test_repo_only_runs_grade_cap_check(self):
        record = self.stub_grade_cap(0)
        result = self.run_sync("--check", "--repo-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CHECKED  grade_cap: grade_cap stub says --check", result.stdout)
        self.assertTrue(record.read_text(encoding="utf-8").startswith("--check --repo "))

    def test_grade_cap_failure_exits_1(self):
        self.stub_grade_cap(1)
        for args in (("--check", "--repo-only"), ("--repo-only",)):
            with self.subTest(args=args):
                result = self.run_sync(*args)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("FAIL     grade_cap --check", result.stdout)
                self.assertFalse((self.home / ".claude").exists())

    def test_unknown_argument_exits_2(self):
        for args in (("--chek",), ("--check", "--bogus"), ("apply",)):
            with self.subTest(args=args):
                result = self.run_sync(*args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("Usage:", result.stderr)
                self.assertFalse((self.home / ".claude").exists())

    def test_dirty_git_target_refused_with_exit_3(self):
        self.deploy_identical()
        deployed = self.target / "marcus"
        init = subprocess.run(
            ["git", "init", "-q", str(deployed)],
            capture_output=True,
            text=True,
            env={"HOME": str(self.home), "PATH": os.environ.get("PATH", ""), "GIT_CONFIG_NOSYSTEM": "1"},
            timeout=60,
        )
        self.assertEqual(init.returncode, 0, init.stderr)
        (deployed / "local-edit.md").write_text("uncommitted\n", encoding="utf-8")
        (self.root / "skills" / "marcus" / "SKILL.md").write_text("changed\n", encoding="utf-8")
        result = self.run_sync()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("REFUSE   marcus: uncommitted changes in target working tree", result.stdout)
        self.assertTrue((deployed / "local-edit.md").is_file())

    def test_last_run_json_preserved(self):
        self.deploy_identical()
        evals = self.target / "marcus" / "evals"
        evals.mkdir()
        (evals / "last_run.json").write_text('{"ok": true}\n', encoding="utf-8")
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("TARGET   marcus -> ", result.stdout)
        self.assertIn("SYNCED   marcus", result.stdout)
        self.assertEqual((evals / "last_run.json").read_text(encoding="utf-8"), '{"ok": true}\n')


if __name__ == "__main__":
    unittest.main()
