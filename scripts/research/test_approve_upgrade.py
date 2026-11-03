#!/usr/bin/env python3
"""
test_approve_upgrade.py - Unit tests for approve_upgrade.py.

``gh`` is replaced by a Python function that records its calls and returns
canned output, so no test touches the network.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import approve_upgrade  # noqa: E402

SHA = "a" * 40
OTHER_SHA = "b" * 40


class FakeGh:
    def __init__(self, *, state="OPEN", login="owner", head=SHA, later_head=None, checks=None):
        self.calls = []
        self.state = state
        self.login = login
        self.heads = [head, later_head or head]
        self.checks = checks if checks is not None else [
            {"name": "research-approval", "bucket": "fail", "link": "https://github.com/o/r/actions/runs/777/job/1"}
        ]

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["pr", "view"] and "headRefOid" in args[-1] and "files" not in args[-1]:
            return 0, json.dumps({"headRefOid": self.heads[1]})
        if args[:2] == ["pr", "view"]:
            return 0, json.dumps(
                {
                    "state": self.state,
                    "title": "Upgrade",
                    "url": "https://github.com/o/r/pull/24",
                    "headRefOid": self.heads[0],
                    "files": [{"path": "scripts/research/x.py"}],
                }
            )
        if args[:2] == ["api", "user"]:
            return 0, json.dumps({"login": self.login})
        if args[:2] == ["repo", "view"]:
            return 0, json.dumps({"owner": {"login": "owner"}})
        if args[:2] == ["pr", "checks"]:
            return 1, json.dumps(self.checks)
        return 0, ""

    def commands(self):
        return [c[:2] for c in self.calls]


def run(gh, *, answer="y", interactive=True, approver=""):
    lines = []
    code = approve_upgrade.run(
        "24", approver, gh=gh, ask=lambda _p: answer, interactive=interactive, out=lines.append
    )
    return code, "\n".join(lines)


class ApproveUpgradeTest(unittest.TestCase):
    def test_no_terminal_refuses_without_calling_gh(self):
        gh = FakeGh()
        code, _ = run(gh, interactive=False)
        self.assertEqual(code, 2)
        self.assertEqual(gh.calls, [])

    def test_wrong_user_refuses_without_commenting(self):
        gh = FakeGh(login="someone-else")
        code, text = run(gh)
        self.assertEqual(code, 2)
        self.assertIn("someone-else", text)
        self.assertNotIn(["pr", "comment"], gh.commands())

    def test_explicit_approver_overrides_owner(self):
        gh = FakeGh(login="reviewer")
        code, _ = run(gh, approver="reviewer")
        self.assertEqual(code, 0)

    def test_closed_pr_refuses(self):
        gh = FakeGh(state="MERGED")
        code, _ = run(gh)
        self.assertEqual(code, 2)
        self.assertNotIn(["pr", "comment"], gh.commands())

    def test_decline_posts_nothing(self):
        for answer in ("", "n", "yes please"):
            gh = FakeGh()
            code, _ = run(gh, answer=answer)
            self.assertEqual(code, 1, answer)
            self.assertNotIn(["pr", "comment"], gh.commands())

    def test_head_moved_cancels(self):
        gh = FakeGh(later_head=OTHER_SHA)
        code, text = run(gh)
        self.assertEqual(code, 1)
        self.assertIn("head changed", text)
        self.assertNotIn(["pr", "comment"], gh.commands())

    def test_approval_posts_full_sha_and_reruns_failed_job(self):
        gh = FakeGh()
        code, _ = run(gh)
        self.assertEqual(code, 0)
        self.assertIn(["pr", "comment", "24", "--body", f"/approve-upgrade {SHA}"], gh.calls)
        self.assertIn(["run", "rerun", "777", "--failed"], gh.calls)

    def test_no_failed_job_skips_rerun(self):
        gh = FakeGh(checks=[{"name": "research-approval", "bucket": "pass", "link": ""}])
        code, text = run(gh)
        self.assertEqual(code, 0)
        self.assertNotIn(["run", "rerun"], gh.commands())
        self.assertIn("No failed", text)


if __name__ == "__main__":
    unittest.main()
