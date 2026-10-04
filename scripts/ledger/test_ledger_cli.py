"""Tests for scripts/ledger/ledger.py."""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ledger  # noqa: E402
import ledger_lib  # noqa: E402

SESSION_ID = "0d9c1f2e-session-under-test"
# Built from pieces so the repository PII scanner does not flag this file.
WIN_PATH = "C:" + "\\" + "Us" + "ers\\alice\\notes\\plan.txt"
UNIX_PATH = "/ho" + "me/alice/project/main.py"
TOKEN = "gh" + "p_" + "a" * 36


def ts(days_ago: float, now: dt.datetime) -> str:
    return (now - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class CliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.dir = self.root / "ledger"
        self.transcripts = self.root / "projects"
        patcher = mock.patch.dict(os.environ, {
            ledger_lib.LEDGER_ENV: str(self.dir),
            ledger.TRANSCRIPTS_ENV: str(self.transcripts),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.now = dt.datetime.now(dt.timezone.utc)

    def run_cli(self, *argv: str) -> tuple:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ledger.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def invoke(self, run_id: str, skill: str = "demo", days_ago: float = 1, **extra) -> dict:
        row = {"run_id": run_id, "kind": "invoke", "origin": "organic", "skill": skill,
               "trigger": "model", "ts": ts(days_ago, self.now)}
        row.update(extra)
        return ledger_lib.append(row)

    def verdict(self, run_id: str, label: str, skill: str = "demo", days_ago: float = 1,
                source: str = "user", failure_class: str = "", **extra) -> dict:
        outcome = {"label": label, "source": source}
        if failure_class:
            outcome["failure_class"] = failure_class
        row = {"run_id": run_id, "kind": "verdict", "origin": "organic", "skill": skill,
               "outcome": outcome, "ts": ts(days_ago, self.now)}
        row.update(extra)
        return ledger_lib.append(row)


class TestVerdictAndFailures(CliTestCase):
    def test_verdict_then_failures(self) -> None:
        self.invoke("r1", harness="cc")
        self.invoke("r2")
        self.invoke("r3", skill="other")
        code, out, _ = self.run_cli("verdict", "r1", "--label", "bad", "--class", "misroute",
                                    "--note", "wrong skill")
        self.assertEqual(code, 0, out)
        self.run_cli("verdict", "r2", "--label", "ok")
        self.run_cli("verdict", "r3", "--label", "bad", "--class", "incomplete")
        code, out, _ = self.run_cli("failures", "demo", "--json")
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertEqual([r["run_id"] for r in rows], ["r1"])
        self.assertEqual(rows[0]["failure_class"], "misroute")
        self.assertEqual(rows[0]["harness"], "cc")
        code, out, _ = self.run_cli("failures", "demo")
        self.assertIn("r1", out)
        self.assertIn("wrong skill", out)

    def test_latest_verdict_wins_and_source_filter(self) -> None:
        self.invoke("r1")
        self.verdict("r1", "bad", failure_class="misroute")
        self.run_cli("dismiss", "r1", "--reason", "my mistake")
        self.invoke("r2")
        self.verdict("r2", "bad", source="judge", failure_class="wrong_output")
        _, out, _ = self.run_cli("failures", "demo", "--json")
        self.assertEqual(json.loads(out), [])
        _, out, _ = self.run_cli("failures", "demo", "--json", "--source", "judge")
        self.assertEqual([r["run_id"] for r in json.loads(out)], ["r2"])

    def test_last_limits_output(self) -> None:
        for i in range(5):
            self.invoke(f"r{i}", days_ago=5 - i)
            self.verdict(f"r{i}", "bad", days_ago=5 - i, failure_class="other")
        _, out, _ = self.run_cli("failures", "demo", "--json", "--last", "2")
        self.assertEqual([r["run_id"] for r in json.loads(out)], ["r3", "r4"])

    def test_verdict_guards(self) -> None:
        self.invoke("r1")
        code, _, err = self.run_cli("verdict", "r1", "--label", "bad")
        self.assertEqual(code, 2)
        self.assertIn("--class", err)
        code, _, err = self.run_cli("verdict", "missing", "--label", "ok")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", err)
        code, _, err = self.run_cli("verdict", "r1", "--label", "ok", "--note", "x" * 121)
        self.assertEqual(code, 2)
        self.assertEqual(len(list(ledger_lib.iter_rows())), 1)


class TestPromote(CliTestCase):
    def write_transcript(self, invoke_ts: dt.datetime, text: str) -> Path:
        folder = self.transcripts / "some-project"
        folder.mkdir(parents=True)
        path = folder / f"{SESSION_ID}.jsonl"

        def stamp(delta: float) -> str:
            return (invoke_ts + dt.timedelta(seconds=delta)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        entries = [
            {"type": "user", "timestamp": stamp(-120), "message": {"content": "earlier ask"}},
            {"type": "user", "timestamp": stamp(-60), "message": {"content": text}},
            {"type": "user", "timestamp": stamp(-30),
             "message": {"content": [{"type": "tool_result", "content": "tool output"}]}},
            {"type": "user", "isMeta": True, "timestamp": stamp(-20),
             "message": {"content": "meta text"}},
            {"type": "user", "timestamp": stamp(60), "message": {"content": "::bad misroute"}},
            {"type": "user", "timestamp": stamp(90), "message": {"content": "later ask"}},
        ]
        path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        return path

    def snapshot(self) -> dict:
        return {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_promote_stages_redacted_case_only(self) -> None:
        skill_dir = self.root / "skills" / "demo"
        (skill_dir / "evals").mkdir(parents=True)
        (skill_dir / "evals" / "evals.json").write_text('{"suites": {}}\n', encoding="utf-8")
        invoke_ts = self.now - dt.timedelta(hours=1)
        row = self.invoke("run-abc123", session=ledger_lib.hash_session(SESSION_ID),
                          ts=invoke_ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        self.verdict("run-abc123", "bad", days_ago=0, failure_class="misroute")
        message = (f"summarise {WIN_PATH} and {UNIX_PATH} then mail bob@corp.io "
                   f"with key {TOKEN} and ~/secrets/a.txt")
        self.write_transcript(ledger.parse_ts(row["ts"]), message)
        before = self.snapshot()

        code, out, err = self.run_cli("promote", "run-abc123", "--skill", "demo")
        self.assertEqual(code, 0, err)
        staging = self.dir / "promoted" / "demo"
        target = staging / "run-abc123.json"
        self.assertIn(str(target), out)
        self.assertIn("free-text personal content", out)

        after = self.snapshot()
        changed = {p for p in after if before.get(p) != after[p]}
        allowed_ledger = set(ledger_lib.month_files(self.dir)) | {self.dir / ledger_lib.LOCK_NAME}
        outside = {p for p in changed
                   if staging not in p.parents and p not in allowed_ledger}
        self.assertEqual(outside, set())
        self.assertEqual(changed & set(skill_dir.rglob("*")), set())

        case = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(set(case), {"id", "suite", "query", "expected_behavior",
                                     "needs_expected_behavior", "provenance"})
        self.assertEqual(case["suite"], "regression")
        self.assertEqual(case["expected_behavior"], "")
        self.assertIs(case["needs_expected_behavior"], True)
        self.assertEqual(case["provenance"], "ledger:run-abc123")
        self.assertTrue(case["query"].startswith("summarise "))
        for secret in ("alice", "bob@corp.io", TOKEN, "secrets/a.txt"):
            self.assertNotIn(secret, case["query"])
        self.assertIn("[REDACTED]", case["query"])

        promoted = [r for r in ledger_lib.find("run-abc123") if r.get("refs")]
        self.assertEqual(promoted[-1]["refs"]["promoted_to"], str(target))
        self.assertEqual(promoted[-1]["outcome"]["label"], "bad")

        code, _, err = self.run_cli("promote", "run-abc123", "--skill", "demo")
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)

    def test_promote_refusals(self) -> None:
        self.invoke("r1", skill="other", session=ledger_lib.hash_session(SESSION_ID))
        code, _, err = self.run_cli("promote", "r1", "--skill", "demo")
        self.assertEqual(code, 1)
        self.assertIn("belongs to", err)
        code, _, err = self.run_cli("promote", "r1", "--skill", "other")
        self.assertEqual(code, 1)
        self.assertIn("no transcript", err)
        code, _, _ = self.run_cli("promote", "r1", "--skill", "../escape")
        self.assertEqual(code, 2)
        self.assertFalse((self.dir / "promoted").exists())

    def test_redact_patterns(self) -> None:
        text = ledger.redact(f"see {WIN_PATH} or {UNIX_PATH}, write a@b.co, keep and/or /skill")
        self.assertNotIn("alice", text)
        self.assertNotIn("a@b.co", text)
        self.assertIn("and/or /skill", text)


class TestInventory(CliTestCase):
    def test_counts_only_below_min_n(self) -> None:
        for i in range(12):
            self.invoke(f"a{i}", harness="cc")
            self.verdict(f"a{i}", "bad" if i < 4 else "ok",
                         failure_class="misroute" if i < 4 else "")
        self.invoke("u1")
        code, out, _ = self.run_cli("inventory", "--by", "skill")
        self.assertEqual(code, 0)
        self.assertIn("demo: n=13 ok=8 bad=4 dismissed=0 unlabeled=1", out)
        self.assertNotIn("Wilson", out)
        self.assertNotIn("%", out.split("\n", 1)[1])
        self.assertIsNone(re.search(r"\b0\.\d", out))
        _, out, _ = self.run_cli("inventory", "--by", "failure_class")
        self.assertIn("misroute: failures=4", out)
        self.assertIsNone(re.search(r"\b0\.\d", out))

    def test_wilson_at_min_n_never_bare_rate(self) -> None:
        for i in range(20):
            self.invoke(f"a{i}", harness="cc")
            self.verdict(f"a{i}", "bad" if i < 7 else "ok",
                         failure_class="misroute" if i < 7 else "")
        _, out, _ = self.run_cli("inventory", "--by", "harness")
        low, high = ledger_lib.wilson(7, 20)
        self.assertIn("cc: n=20 ok=13 bad=7", out)
        self.assertIn(f"[{low:.2f}, {high:.2f}] over 20 labeled", out)
        self.assertNotIn("0.35", out)
        self.assertNotIn("35%", out)

    def test_days_and_origin_filter(self) -> None:
        self.invoke("old", days_ago=100)
        self.invoke("new", days_ago=1)
        ledger_lib.append({"run_id": "rep", "kind": "invoke", "origin": "replay",
                           "skill": "demo", "trigger": "eval"})
        _, out, _ = self.run_cli("inventory")
        self.assertIn("demo: n=1 ", out)


class TestPurge(CliTestCase):
    def test_purge_closed_old_months_keeps_unpromoted_fails(self) -> None:
        old = 400
        self.invoke("keep", days_ago=old)
        self.verdict("keep", "bad", days_ago=old, failure_class="misroute")
        self.invoke("drop-ok", days_ago=old)
        self.verdict("drop-ok", "ok", days_ago=old)
        self.invoke("drop-promoted", days_ago=old)
        self.verdict("drop-promoted", "bad", days_ago=old, failure_class="other",
                     refs={"promoted_to": "staged.json"})
        self.invoke("drop-unlabeled", days_ago=old)
        self.invoke("recent", days_ago=0)
        # a verdict in a later month still decides an old run's fate
        self.invoke("late-bad", days_ago=old)
        self.verdict("late-bad", "bad", days_ago=0, failure_class="incomplete")

        code, out, err = self.run_cli("purge", "--older-than", "180")
        self.assertEqual(code, 0, err)
        remaining = {(r["run_id"], r["kind"]) for r in ledger_lib.iter_rows(strict=True)}
        self.assertEqual(remaining, {("keep", "invoke"), ("keep", "verdict"),
                                     ("recent", "invoke"), ("late-bad", "invoke"),
                                     ("late-bad", "verdict")})
        self.assertEqual(list(self.dir.glob("*.tmp")), [])

    def test_current_month_untouched(self) -> None:
        self.invoke("recent", days_ago=0)
        self.run_cli("purge", "--older-than", "1")
        self.assertEqual([r["run_id"] for r in ledger_lib.iter_rows()], ["recent"])


class TestCheckKill(CliTestCase):
    def dates(self, installed_days_ago: int) -> list:
        installed = (self.now - dt.timedelta(days=installed_days_ago)).date()
        return ["--installed", installed.isoformat(), "--today", self.now.date().isoformat()]

    def test_empty_ledger_kills(self) -> None:
        code, out, _ = self.run_cli("check-kill", *self.dates(60))
        self.assertEqual(code, 1)
        self.assertTrue(out.rstrip().endswith("KILL"))

    def test_healthy_ledger_passes(self) -> None:
        for i in range(30):
            day = 58 - 2 * i
            self.invoke(f"r{i}", days_ago=day)
            if i < 12:
                self.verdict(f"r{i}", "bad", days_ago=day, failure_class="misroute")
        for i in range(3):
            self.verdict(f"r{i}", "bad", days_ago=1, failure_class="misroute",
                         refs={"promoted_to": f"p{i}.json"})
        code, out, _ = self.run_cli("check-kill", *self.dates(60))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.rstrip().splitlines()[-1], "PASS")
        self.assertIn("criterion 3: PASS  not applicable", out)

    def test_silence_and_unlabeled_kill(self) -> None:
        for i in range(20):
            self.invoke(f"r{i}", days_ago=59 - i / 2)
        for i in range(3):
            self.verdict(f"r{i}", "bad", days_ago=40, failure_class="other",
                         refs={"promoted_to": f"p{i}.json"})
        code, out, _ = self.run_cli("check-kill", *self.dates(60))
        self.assertEqual(code, 1)
        self.assertIn("criterion 1: PASS", out)
        self.assertIn("criterion 2: KILL", out)
        self.assertIn("criterion 4: KILL", out)

    def test_early_check_notes_review_date(self) -> None:
        _, out, _ = self.run_cli("check-kill", *self.dates(10))
        self.assertIn("early check", out)


class TestInstallHook(CliTestCase):
    def test_copies_files_and_prints_snippet(self) -> None:
        dest = self.root / "bin"
        hook = self.root / "ledger_hook.py"
        hook.write_text("# stub\n", encoding="utf-8")
        with mock.patch.object(ledger, "HOOK_SOURCE", hook):
            code, out, err = self.run_cli("install-hook", "--dest", str(dest))
        self.assertEqual(code, 0, err)
        self.assertTrue((dest / "ledger_hook.py").is_file())
        self.assertTrue((dest / "ledger_lib.py").is_file())
        snippet = json.loads(out[out.index("{"):])
        commands = [h["command"] for entries in snippet["hooks"].values()
                    for entry in entries for h in entry["hooks"]]
        self.assertTrue(all(c.endswith("|| true") for c in commands))

    def test_missing_hook_source(self) -> None:
        with mock.patch.object(ledger, "HOOK_SOURCE", self.root / "absent.py"):
            code, _, err = self.run_cli("install-hook", "--dest", str(self.root / "bin"))
        self.assertEqual(code, 2)
        self.assertFalse((self.root / "bin").exists())


if __name__ == "__main__":
    unittest.main()
