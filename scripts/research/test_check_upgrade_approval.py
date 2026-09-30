#!/usr/bin/env python3
"""
test_check_upgrade_approval.py - Unit tests for the owner approval gate.

Each test writes fixture comment JSON to a temp dir and runs
check_upgrade_approval.py in a subprocess with ``gh`` replaced by a Python
stub through DEMIURGE_GH. The stub prints the fixture pages and records its
arguments; it never touches the network.
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

import check_upgrade_approval as cua

SCRIPT = Path(__file__).resolve().parent / "check_upgrade_approval.py"
HEAD = "a" * 40
OLD = "b" * 40
OWNER = "octo-owner"
BOT = "research-bot"

GH_STUB = """\
import json, os, sys
with open(os.environ["GH_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
code = int(os.environ.get("GH_STUB_EXIT", "0"))
if code:
    sys.stderr.write("stub failure\\n")
    sys.exit(code)
with open(os.environ["GH_STUB_PAGES"], encoding="utf-8") as fh:
    sys.stdout.write(fh.read())
"""


def comment(login: str, body: str, user_type: str = "User", cid: int = 1) -> dict:
    return {"id": cid, "user": {"login": login, "type": user_type}, "body": body}


class TestCheckUpgradeApproval(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.log = self.tmp / "gh.log"
        self.pages = self.tmp / "pages.json"
        stub = self.tmp / "gh_stub.py"
        stub.write_text(GH_STUB, encoding="utf-8")
        self.env = {
            "PATH": os.environ.get("PATH", ""),
            "DEMIURGE_GH": shlex.join([sys.executable, str(stub)]),
            "GH_STUB_LOG": str(self.log),
            "GH_STUB_PAGES": str(self.pages),
            "GITHUB_REPOSITORY": "example/demo",
        }
        for key in ("SYSTEMROOT", "TEMP", "TMP", "COMSPEC"):
            if key in os.environ:
                self.env[key] = os.environ[key]

    def tearDown(self):
        self._tmp.cleanup()

    def write_pages(self, *pages: list) -> None:
        self.pages.write_text("".join(json.dumps(page) for page in pages), encoding="utf-8")

    def run_check(self, *extra: str, head: str = HEAD, deny: str = BOT) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--pr",
            "7",
            "--head-sha",
            head,
            "--owner",
            OWNER,
            "--deny-login",
            deny,
            *extra,
        ]
        return subprocess.run(cmd, env=self.env, capture_output=True, text=True, encoding="utf-8")

    def test_owner_with_correct_sha_passes(self):
        self.write_pages([comment(OWNER, f"Looks right.\n/approve-upgrade {HEAD}\n")])
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK:", proc.stdout)
        calls = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(calls, [["api", "repos/example/demo/issues/7/comments", "--paginate"]])

    def test_wrong_sha_fails(self):
        self.write_pages([comment(OWNER, f"/approve-upgrade {OLD}")])
        proc = self.run_check()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("FAIL:", proc.stdout)

    def test_non_owner_fails(self):
        self.write_pages([comment("someone-else", f"/approve-upgrade {HEAD}")])
        self.assertEqual(self.run_check().returncode, 1)

    def test_bot_login_fails_even_as_owner(self):
        self.write_pages([comment(OWNER, f"/approve-upgrade {HEAD}")])
        self.assertEqual(self.run_check(deny=OWNER).returncode, 1)

    def test_bot_comment_fails(self):
        self.write_pages([comment(BOT, f"/approve-upgrade {HEAD}", user_type="Bot")])
        self.assertEqual(self.run_check().returncode, 1)

    def test_owner_login_with_bot_type_fails(self):
        self.write_pages([comment(OWNER, f"/approve-upgrade {HEAD}", user_type="Bot")])
        self.assertEqual(self.run_check().returncode, 1)

    def test_approval_on_later_page_passes(self):
        first = [comment("someone-else", "hello", cid=1), comment(OWNER, f"/approve-upgrade {OLD}", cid=2)]
        second = [comment(OWNER, f"/approve-upgrade {HEAD}", cid=3)]
        self.write_pages(first, second)
        self.assertEqual(self.run_check().returncode, 0)

    def test_sha_inside_prose_does_not_count(self):
        self.write_pages([comment(OWNER, f"I will /approve-upgrade {HEAD} later")])
        self.assertEqual(self.run_check().returncode, 1)

    def test_uppercase_sha_does_not_count(self):
        self.write_pages([comment(OWNER, f"/approve-upgrade {HEAD.upper()}")])
        self.assertEqual(self.run_check().returncode, 1)

    def test_empty_deny_login_still_requires_owner(self):
        self.write_pages([comment(OWNER, f"/approve-upgrade {HEAD}")])
        self.assertEqual(self.run_check(deny="").returncode, 0)

    def test_no_comments_fails(self):
        self.write_pages([])
        self.assertEqual(self.run_check().returncode, 1)

    def test_bad_head_sha_is_usage_error(self):
        self.write_pages([])
        self.assertEqual(self.run_check(head="abc123").returncode, 2)
        self.assertFalse(self.log.exists())

    def test_gh_failure_is_error(self):
        self.write_pages([])
        self.env["GH_STUB_EXIT"] = "1"
        proc = self.run_check()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ERROR:", proc.stdout)

    def test_malformed_json_is_error(self):
        self.pages.write_text('{"message": "Not Found"}', encoding="utf-8")
        self.assertEqual(self.run_check().returncode, 2)

    def test_repository_flag_overrides_env(self):
        self.write_pages([comment(OWNER, f"/approve-upgrade {HEAD}")])
        proc = self.run_check("--repository", "other/repo")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        calls = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(calls[0][1], "repos/other/repo/issues/7/comments")


class TestHelpers(unittest.TestCase):
    def test_parse_pages_concatenated(self):
        text = '[{"id": 1}]\n[{"id": 2}, {"id": 3}]'
        self.assertEqual([c["id"] for c in cua.parse_pages(text)], [1, 2, 3])

    def test_parse_pages_empty(self):
        self.assertEqual(cua.parse_pages(""), [])

    def test_find_approval_skips_missing_user(self):
        comments = [{"body": f"/approve-upgrade {HEAD}"}, comment(OWNER, f"/approve-upgrade {HEAD}", cid=9)]
        found = cua.find_approval(comments, HEAD, OWNER, BOT)
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], 9)

    def test_crlf_body_line_counts(self):
        self.assertEqual(cua.approved_shas(f"ok\r\n/approve-upgrade {HEAD}\r\n"), [HEAD])


if __name__ == "__main__":
    unittest.main()
