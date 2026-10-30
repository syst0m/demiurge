#!/usr/bin/env python3
"""Tests for gh_minutes_gate.py. gh is stubbed; no network."""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gh_minutes_gate as gate  # noqa: E402


def iso(offset_seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - offset_seconds))


def fake_gh(routes):
    """routes: list of (substring-of-args, response). First match wins; no match is None."""
    def run(args, timeout=0):
        joined = " ".join(args)
        for needle, response in routes:
            if needle in joined:
                return response
        return None
    return run


PRIVATE = ("repo view", {"nameWithOwner": "o/r", "isPrivate": True})
PUBLIC = ("repo view", {"nameWithOwner": "o/r", "isPrivate": False})


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"GH_MINUTES_CACHE_DIR": self.tmp.name}, clear=False)
        self.env.start()
        os.environ.pop("GH_MINUTES_MODE", None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def detect(self, routes, **kw):
        with mock.patch.object(gate, "run_gh", fake_gh(routes)):
            return gate.detect(**kw)

    def test_override_wins_without_calling_gh(self):
        with mock.patch.dict(os.environ, {"GH_MINUTES_MODE": "local"}):
            with mock.patch.object(gate, "run_gh", side_effect=AssertionError("gh called")):
                self.assertEqual(gate.detect()["mode"], "local")

    def test_gh_unavailable_fails_closed(self):
        self.assertEqual(self.detect([])["mode"], "local")

    def test_public_repo_is_github(self):
        self.assertEqual(self.detect([PUBLIC])["mode"], "github")

    def test_quota_endpoint_zero_left_is_local(self):
        r = self.detect([PRIVATE, ("settings/billing/actions", {"included_minutes": 2000, "total_minutes_used": 2000})])
        self.assertEqual(r["mode"], "local")

    def test_quota_endpoint_minutes_left_is_github(self):
        r = self.detect([PRIVATE, ("settings/billing/actions", {"included_minutes": 2000, "total_minutes_used": 5})])
        self.assertEqual(r["mode"], "github")

    def test_billing_annotation_is_local(self):
        r = self.detect([PRIVATE,
                         ("run list", [{"databaseId": 7, "conclusion": "failure", "createdAt": iso(60)}]),
                         ("actions/runs/7/jobs", {"jobs": [{"id": 99}]}),
                         ("check-runs/99/annotations",
                          [{"message": "The job was not started because recent account payments have failed"}])])
        self.assertEqual(r["mode"], "local")
        self.assertIn("billing", r["reason"])

    def test_recent_success_is_github(self):
        r = self.detect([PRIVATE, ("run list", [{"databaseId": 7, "conclusion": "success", "createdAt": iso(3600)}])])
        self.assertEqual(r["mode"], "github")

    def test_old_success_only_is_local(self):
        r = self.detect([PRIVATE, ("run list", [{"databaseId": 7, "conclusion": "success",
                                                 "createdAt": iso(10 * 86400)}])])
        self.assertEqual(r["mode"], "local")

    def test_ordinary_test_failure_is_not_billing(self):
        r = self.detect([PRIVATE,
                         ("run list", [{"databaseId": 7, "conclusion": "failure", "createdAt": iso(60)},
                                       {"databaseId": 6, "conclusion": "success", "createdAt": iso(7200)}]),
                         ("actions/runs/7/jobs", {"jobs": [{"id": 99}]}),
                         ("check-runs/99/annotations", [{"message": "Process completed with exit code 1."}])])
        self.assertEqual(r["mode"], "github")

    def test_cache_hit_then_expiry_then_refresh(self):
        now = 1_000_000.0
        first = self.detect([PRIVATE, ("run list", [{"databaseId": 1, "conclusion": "success",
                                                     "createdAt": iso(10)}])], now=now)
        self.assertEqual(first["source"], "live")
        hit = self.detect([PRIVATE], now=now + 60)
        self.assertEqual((hit["mode"], hit["source"]), ("github", "cache"))
        expired = self.detect([PRIVATE], now=now + gate.CACHE_TTL_SECONDS + 1)
        self.assertEqual((expired["mode"], expired["source"]), ("local", "live"))
        refreshed = self.detect([PRIVATE, ("run list", [{"databaseId": 1, "conclusion": "success",
                                                         "createdAt": iso(10)}])], now=now + 120, refresh=True)
        self.assertEqual(refreshed["source"], "live")

    def test_blocked_and_allowed_commands(self):
        for cmd in ("gh pr create --fill", "gh pr merge 3 --squash", "gh workflow run ci.yml",
                    "gh run watch 5", "git add . && gh pr create"):
            self.assertTrue(gate.blocked_command(cmd), cmd)
        for cmd in ("gh pr view 3", "gh pr list", "git push origin main", "git tag v1.0.0",
                    "gh release create v1", "npm test", "ls"):
            self.assertFalse(gate.blocked_command(cmd), cmd)

    def test_decide_blocks_in_local_and_allows_in_github(self):
        with mock.patch.dict(os.environ, {"GH_MINUTES_MODE": "local"}):
            code, msg = gate.decide("gh pr create")
            self.assertEqual(code, 2)
            self.assertIn("local flow", msg)
            self.assertEqual(gate.decide("npm test")[0], 0)
        with mock.patch.dict(os.environ, {"GH_MINUTES_MODE": "github"}):
            self.assertEqual(gate.decide("gh pr create")[0], 0)

    def test_unblocked_command_never_calls_gh(self):
        with mock.patch.object(gate, "run_gh", side_effect=AssertionError("gh called")):
            self.assertEqual(gate.decide("git status")[0], 0)

    def test_hook_payload_shapes(self):
        self.assertEqual(gate.command_from_hook({"tool_input": {"command": "gh pr create"}}), "gh pr create")
        self.assertEqual(gate.command_from_hook({"tool_input": {"CommandLine": "gh pr create"}}), "gh pr create")
        self.assertEqual(gate.command_from_hook({"toolCall": {"name": "run_command", "args": {"CommandLine": "gh pr create"}}}), "gh pr create")
        self.assertEqual(gate.command_from_hook({}), "")

    def test_blocked_command_matcher_coverage(self):
        self.assertTrue(gate.blocked_command("gh pr create"))
        self.assertTrue(gate.blocked_command("gh.exe pr create --fill"))
        self.assertTrue(gate.blocked_command("gh --repo o/r pr create"))
        self.assertTrue(gate.blocked_command("gh pr -R o/r merge 123 --auto --squash"))
        self.assertTrue(gate.blocked_command("gh workflow run ci.yml"))
        self.assertTrue(gate.blocked_command("gh run watch 456"))
        self.assertTrue(gate.blocked_command("gh run rerun 456"))
        self.assertFalse(gate.blocked_command("gh pr list"))
        self.assertFalse(gate.blocked_command("git status"))
        self.assertFalse(gate.blocked_command("gh pr list && echo create"))

    def test_hook_antigravity_protocol(self):
        payload = json.dumps({
            "toolCall": {"name": "run_command", "args": {"CommandLine": "gh pr create --fill"}},
            "conversationId": "test-conv-id"
        })
        with mock.patch.dict(os.environ, {"GH_MINUTES_MODE": "local"}):
            with mock.patch("sys.stdin", io.StringIO(payload)), redirect_stdout(io.StringIO()) as out:
                code = gate.main(["--hook"])
                self.assertEqual(code, 0)
                data = json.loads(out.getvalue())
                self.assertEqual(data["decision"], "deny")
                self.assertIn("Do not open PRs", data["reason"])
        with mock.patch.dict(os.environ, {"GH_MINUTES_MODE": "github"}):
            with mock.patch("sys.stdin", io.StringIO(payload)), redirect_stdout(io.StringIO()) as out:
                code = gate.main(["--hook"])
                self.assertEqual(code, 0)
                data = json.loads(out.getvalue())
                self.assertEqual(data["decision"], "allow")

    def test_hook_round_trip_exit_codes(self):
        payload = json.dumps({"tool_input": {"command": "gh pr create --fill"}})
        with mock.patch.dict(os.environ, {"GH_MINUTES_MODE": "local"}):
            with mock.patch("sys.stdin", io.StringIO(payload)), redirect_stderr(io.StringIO()) as err:
                self.assertEqual(gate.main(["--hook"]), 2)
            self.assertIn("Do not open PRs", err.getvalue())
        with mock.patch.dict(os.environ, {"GH_MINUTES_MODE": "github"}):
            with mock.patch("sys.stdin", io.StringIO(payload)):
                self.assertEqual(gate.main(["--hook"]), 0)
        with mock.patch("sys.stdin", io.StringIO("not json")):
            self.assertEqual(gate.main(["--hook"]), 0)

    def test_status_json(self):
        with mock.patch.dict(os.environ, {"GH_MINUTES_MODE": "local"}), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(gate.main(["--status", "--json"]), 0)
        self.assertEqual(json.loads(out.getvalue())["mode"], "local")


if __name__ == "__main__":
    unittest.main()
