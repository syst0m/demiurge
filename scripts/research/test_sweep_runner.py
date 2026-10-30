#!/usr/bin/env python3
"""
test_sweep_runner.py - Unit tests for the weekend sweep runner's notification gate.

The sweep emails went missing twice: on 2026-10-10 the gws token had no Gmail
send scope, and on 2026-10-18 gws had no token at all. Each failure went only
to runner.log. On 2026-10-17 the claude login had expired, and the runner
spent six attempts before it said so. These tests pin the gate: a failed email
stays in an outbox and is sent again at the next start, a failed email raises
its own toast, and a daily login check reports a broken claude or gws login
before a weekend attempt depends on it.

Each test points DEMIURGE_SWEEP_HOME at a temp dir and replaces
subprocess.run with a fake, so no test starts claude, gws or PowerShell.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "sweep_runner.py"
SAT = dt.datetime(2026, 10, 24, 9, 0)
MON = dt.datetime(2026, 10, 26, 8, 30)
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.modify"


class FakeTools:
    """Stands in for claude, gws and PowerShell; records every call."""

    def __init__(self):
        self.claude_logged_in = True
        self.gws_token_valid = True
        self.gws_scopes = ["email", SEND_SCOPE]
        self.send_rc = 0
        self.sweep_result = {"status": "no_change", "summary": "nothing new"}
        self.sent = []
        self.toasts = []
        self.sweeps = 0

    def run(self, cmd, **kwargs):
        if cmd[0] == "powershell":
            self.toasts.append(cmd[-1])
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[1:3] == ["auth", "status"] and "gws" in cmd[0]:
            out = json.dumps({"token_valid": self.gws_token_valid, "scopes": self.gws_scopes,
                              "user": "owner@example.invalid"})
            return subprocess.CompletedProcess(cmd, 0, out, "")
        if cmd[1:3] == ["gmail", "+send"]:
            if self.send_rc == 0:
                self.sent.append(cmd[cmd.index("--subject") + 1])
            return subprocess.CompletedProcess(cmd, self.send_rc, "",
                                               "" if self.send_rc == 0 else "error[auth]: Gmail auth failed")
        if cmd[1:3] == ["auth", "status"]:
            return subprocess.CompletedProcess(cmd, 0 if self.claude_logged_in else 1,
                                               json.dumps({"loggedIn": self.claude_logged_in}), "")
        if "-p" in cmd:
            self.sweeps += 1
            return subprocess.CompletedProcess(cmd, 0, f"SWEEP_RESULT {json.dumps(self.sweep_result)}\n", "")
        raise AssertionError(f"unexpected command: {cmd}")


class SweepRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "prompt.md").write_text("sweep", encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {"DEMIURGE_SWEEP_HOME": str(self.home),
                                                "DEMIURGE_REPO": str(self.home)})
        self.env.start()
        os.environ.pop("SWEEP_NOTIFY_EMAIL", None)
        spec = importlib.util.spec_from_file_location("sweep_runner", SCRIPT)
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)
        self.tools = FakeTools()
        self.patch = mock.patch.object(self.runner.subprocess, "run", side_effect=self.tools.run)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def weekend_done(self):
        """Mark the weekend before MON done, so a Monday start reports only the login check."""
        state = {"weekends": {"2026-10-24": {"attempts": [], "success": True, "notified": []}}}
        (self.home / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def start(self, now, *argv):
        with mock.patch.dict(os.environ, {"SWEEP_NOW": now.isoformat()}), \
                mock.patch.object(sys, "argv", ["sweep_runner.py", *argv]):
            return self.runner.main()

    def test_a_failed_email_is_kept_and_sent_at_the_next_start(self):
        self.tools.send_rc = 2
        self.start(SAT)
        self.assertEqual(self.tools.sent, [])
        self.tools.send_rc = 0
        self.start(MON)
        self.assertIn("[Research sweep] No changes this week", self.tools.sent)

    def test_a_failed_email_raises_a_toast_that_says_so(self):
        self.tools.send_rc = 2
        self.start(SAT)
        self.assertTrue(any("email failed" in t.lower() for t in self.tools.toasts), self.tools.toasts)

    def test_an_expired_claude_login_is_reported_before_the_attempt(self):
        self.tools.claude_logged_in = False
        self.start(SAT)
        self.assertTrue(any("claude" in s.lower() and "login" in s.lower() for s in self.tools.sent), self.tools.sent)

    def test_a_gws_token_without_gmail_send_is_reported_by_toast(self):
        self.weekend_done()
        self.tools.gws_scopes = ["email", "https://www.googleapis.com/auth/drive"]
        self.start(MON)
        self.assertTrue(any("gws" in t.lower() for t in self.tools.toasts), self.tools.toasts)

    def test_a_weekday_start_runs_the_login_check_once_a_day(self):
        self.weekend_done()
        self.tools.claude_logged_in = False
        self.start(MON)
        self.start(MON + dt.timedelta(hours=2))
        reports = [s for s in self.tools.sent if "login" in s.lower()]
        self.assertEqual(len(reports), 1, self.tools.sent)
        self.assertEqual(self.tools.sweeps, 0)

    def test_healthy_logins_send_no_login_report(self):
        self.weekend_done()
        self.start(MON)
        self.assertEqual(self.tools.sent, [])
        self.assertEqual(self.tools.toasts, [])

    def test_the_owner_address_comes_from_env_or_gws_not_the_source(self):
        self.assertIsNone(re.search(r"[\w.]+@gmail\.com", SCRIPT.read_text(encoding="utf-8")))
        self.assertEqual(self.runner.owner_email(), "owner@example.invalid")
        with mock.patch.dict(os.environ, {"SWEEP_NOTIFY_EMAIL": "set@example.invalid"}):
            self.assertEqual(self.runner.owner_email(), "set@example.invalid")


if __name__ == "__main__":
    unittest.main()
