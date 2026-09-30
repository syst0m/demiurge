#!/usr/bin/env python3
"""
test_sweep_pr.py - Unit tests for sweep_pr.py prepare and publish guards.

Each test builds a temporary bare remote and a clone of it, runs sweep_pr.py in
a subprocess with HOME pointed at the temp dir, and replaces ``gh`` with a
Python stub through DEMIURGE_GH. The stub records its arguments and never
touches the network.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sweep_pr.py"
DATE = "2026-10-01"
BRANCH = f"research/sweep-{DATE}"

GH_STUB = """\
import json, os, sys
with open(os.environ["GH_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
print("https://example.invalid/pull/1")
"""


class TestSweepPr(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.remote = self.tmp / "remote.git"
        self.repo = self.tmp / "work"
        self.log = self.tmp / "gh.log"
        stub = self.tmp / "gh_stub.py"
        stub.write_text(GH_STUB, encoding="utf-8")
        self.env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", ""),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CEILING_DIRECTORIES": str(self.tmp),
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
            "DEMIURGE_GH": shlex.join([sys.executable, str(stub)]),
            "GH_STUB_LOG": str(self.log),
        }
        for key in ("SYSTEMROOT", "TEMP", "TMP", "COMSPEC", "USERPROFILE"):
            if key in os.environ:
                self.env[key] = os.environ[key]
        self.git(self.tmp, "init", "--quiet", "--bare", "--initial-branch=main", str(self.remote))
        self.git(self.tmp, "clone", "--quiet", str(self.remote), str(self.repo))
        self.git(self.repo, "checkout", "--quiet", "-B", "main")
        self.write(self.repo, ".gitignore", "scratch/\n")
        self.write(self.repo, "research/RESEARCH.md", "# Research\n")
        self.write(self.repo, "skills/marcus/references/claims.json", "{}\n")
        self.write(self.repo, "scripts/tool.py", "print('tool')\n")
        self.commit(self.repo, "initial")
        self.git(self.repo, "push", "--quiet", "origin", "main")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, cwd: Path, *args: str) -> str:
        proc = subprocess.run(["git", *args], cwd=str(cwd), env=self.env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def write(self, root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, root: Path, message: str) -> None:
        self.git(root, "add", "-A")
        self.git(root, "commit", "--quiet", "-m", message)

    def sweep(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(cwd),
            env=self.env,
            capture_output=True,
            text=True,
        )

    def prepared(self) -> Path:
        proc = self.sweep(self.repo, "prepare", "--date", DATE)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return self.repo / "scratch" / f"sweep-{DATE}"

    def gh_calls(self) -> list:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def remote_has_branch(self) -> bool:
        return bool(self.git(self.repo, "ls-remote", "--heads", "origin", BRANCH).strip())

    def test_prepare_creates_branch_and_worktree(self):
        worktree = self.prepared()
        self.assertTrue((worktree / "research" / "RESEARCH.md").is_file())
        head = self.git(worktree, "rev-parse", "--abbrev-ref", "HEAD").strip()
        self.assertEqual(head, BRANCH)

    def test_prepare_refuses_existing_branch(self):
        self.prepared()
        self.git(self.repo, "worktree", "remove", str(self.repo / "scratch" / f"sweep-{DATE}"))
        proc = self.sweep(self.repo, "prepare", "--date", DATE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("already exists locally", proc.stdout)

    def test_prepare_refuses_remote_branch(self):
        self.git(self.repo, "push", "--quiet", "origin", f"main:refs/heads/{BRANCH}")
        self.git(self.repo, "update-ref", "-d", f"refs/remotes/origin/{BRANCH}")
        proc = self.sweep(self.repo, "prepare", "--date", DATE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("already exists on origin", proc.stdout)

    def test_prepare_refuses_existing_worktree_path(self):
        (self.repo / "scratch" / f"sweep-{DATE}").mkdir(parents=True)
        proc = self.sweep(self.repo, "prepare", "--date", DATE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("worktree path", proc.stdout)
        self.assertFalse(self.git(self.repo, "branch", "--list", BRANCH).strip())

    def test_prepare_rejects_bad_date(self):
        proc = self.sweep(self.repo, "prepare", "--date", "tomorrow")
        self.assertEqual(proc.returncode, 2)

    def test_publish_refuses_main(self):
        proc = self.sweep(self.repo, "publish", "--yes")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("refusing to publish from main", proc.stdout)
        self.assertEqual(self.gh_calls(), [])

    def test_publish_refuses_other_branch_name(self):
        self.git(self.repo, "checkout", "--quiet", "-b", "feature/research-sweep")
        self.write(self.repo, "research/RESEARCH.md", "# Research\n\nNew.\n")
        self.commit(self.repo, "edit")
        proc = self.sweep(self.repo, "publish", "--yes")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("does not match", proc.stdout)
        self.assertEqual(self.gh_calls(), [])

    def test_publish_refuses_empty_research_diff(self):
        worktree = self.prepared()
        self.write(worktree, "skills/marcus/references/claims.json", '{"a": 1}\n')
        self.commit(worktree, "refs only")
        proc = self.sweep(worktree, "publish", "--yes")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("no research/ change", proc.stdout)
        self.assertFalse(self.remote_has_branch())

    def test_publish_refuses_no_commits(self):
        worktree = self.prepared()
        proc = self.sweep(worktree, "publish")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("no research/ change", proc.stdout)

    def test_publish_refuses_path_outside_allowed(self):
        worktree = self.prepared()
        self.write(worktree, "research/RESEARCH.md", "# Research\n\nNew.\n")
        self.write(worktree, ".github/workflows/x.yml", "name: x\n")
        self.commit(worktree, "sneak")
        proc = self.sweep(worktree, "publish", "--yes")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn(".github/workflows/x.yml", proc.stdout)
        self.assertFalse(self.remote_has_branch())
        self.assertEqual(self.gh_calls(), [])

    def test_publish_refuses_uncommitted_changes(self):
        worktree = self.prepared()
        self.write(worktree, "research/RESEARCH.md", "# Research\n\nNew.\n")
        self.commit(worktree, "edit")
        self.write(worktree, "scripts/tool.py", "print('changed')\n")
        proc = self.sweep(worktree, "publish")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("uncommitted", proc.stdout)

    def test_publish_dry_run_prints_commands(self):
        worktree = self.prepared()
        self.write(worktree, "research/RESEARCH.md", "# Research\n\nNew.\n")
        self.write(worktree, "skills/marcus/references/claims.json", '{"a": 1}\n')
        self.commit(worktree, "edit")
        proc = self.sweep(worktree, "publish")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(f"git push --set-upstream origin refs/heads/{BRANCH}:refs/heads/{BRANCH}", proc.stdout)
        self.assertIn(f"pr create --base main --head {BRANCH}", proc.stdout)
        self.assertFalse(self.remote_has_branch())
        self.assertEqual(self.gh_calls(), [])

    def test_publish_yes_pushes_and_opens_pr(self):
        worktree = self.prepared()
        self.write(worktree, "research/RESEARCH.md", "# Research\n\nNew.\n")
        self.commit(worktree, "edit")
        proc = self.sweep(worktree, "publish", "--yes", "--title", "research: sweep")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(self.remote_has_branch())
        main_sha = self.git(self.repo, "ls-remote", "origin", "refs/heads/main").split()[0]
        self.assertEqual(main_sha, self.git(self.repo, "rev-parse", "main").strip())
        calls = self.gh_calls()
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call[:6], ["pr", "create", "--base", "main", "--head", BRANCH])
        self.assertEqual(call[call.index("--title") + 1], "research: sweep")
        body = Path(call[call.index("--body-file") + 1]).read_text(encoding="utf-8")
        self.assertIn("research/RESEARCH.md", body)

    def test_publish_allows_verify_branch(self):
        self.git(self.repo, "checkout", "--quiet", "-b", "research/verify-pr-12")
        self.write(self.repo, "research/verifications/x/abc.yaml", "verdict: pass\n")
        self.commit(self.repo, "record")
        proc = self.sweep(self.repo, "publish")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("--head research/verify-pr-12", proc.stdout)


if __name__ == "__main__":
    unittest.main()
