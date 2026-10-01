"""Tests for skills/marcus/scripts/ledger_lib.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
MARCUS_SCRIPTS = REPO_ROOT / "skills" / "marcus" / "scripts"
sys.path.insert(0, str(MARCUS_SCRIPTS))

import ledger_lib  # noqa: E402


def invoke_row(**extra):
    row = {"run_id": ledger_lib.new_run_id(), "kind": "invoke", "origin": "organic",
           "skill": "demo", "trigger": "slash"}
    row.update(extra)
    return row


CONTENDER = """
import sys
sys.path.insert(0, sys.argv[1])
import ledger_lib
try:
    ledger_lib.append({"run_id": "r", "kind": "invoke", "origin": "organic", "skill": "s"},
                      timeout=0.2)
except ledger_lib.LedgerLockTimeout:
    sys.exit(3)
"""


class LedgerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "ledger"
        patcher = mock.patch.dict(os.environ, {ledger_lib.LEDGER_ENV: str(self.dir)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)


class TestAppendAndRead(LedgerTestCase):
    def test_ledger_dir_honours_env(self) -> None:
        self.assertEqual(ledger_lib.ledger_dir(), self.dir)

    def test_round_trip(self) -> None:
        session = ledger_lib.hash_session("raw-session-id")
        written = ledger_lib.append(invoke_row(session=session, model_id="stub", harness="cc"))
        verdict = ledger_lib.append({
            "run_id": written["run_id"], "kind": "verdict", "origin": "organic", "skill": "demo",
            "outcome": {"label": "bad", "source": "user", "failure_class": "misroute",
                        "note": "picked the wrong skill"},
        })
        rows = list(ledger_lib.iter_rows())
        self.assertEqual(rows, [written, verdict])
        self.assertEqual(ledger_lib.find(written["run_id"]), [written, verdict])
        self.assertEqual(ledger_lib.find("absent"), [])
        self.assertEqual(written["schema"], ledger_lib.SCHEMA_VERSION)
        files = ledger_lib.month_files()
        self.assertEqual([p.name for p in files], [f"runs-{written['ts'][:4]}-{written['ts'][5:7]}.jsonl"])
        self.assertNotIn("raw-session-id", files[0].read_text(encoding="utf-8"))

    def test_invalid_enum_rejected(self) -> None:
        with self.assertRaisesRegex(ledger_lib.LedgerError, "kind"):
            ledger_lib.append(invoke_row(kind="guess"))
        bad_class = {"run_id": "r1", "kind": "verdict", "origin": "organic", "skill": "demo",
                     "outcome": {"label": "bad", "source": "user", "failure_class": "vibes"}}
        with self.assertRaisesRegex(ledger_lib.LedgerError, "outcome.failure_class"):
            ledger_lib.append(bad_class)
        with self.assertRaisesRegex(ledger_lib.LedgerError, "outcome.source"):
            ledger_lib.append({**bad_class, "outcome": {"label": "ok", "source": "oracle"}})
        self.assertEqual(ledger_lib.month_files(), [])

    def test_unknown_key_rejected(self) -> None:
        with self.assertRaisesRegex(ledger_lib.LedgerError, "prompt: unknown key"):
            ledger_lib.append(invoke_row(prompt="text that must never be stored"))
        with self.assertRaisesRegex(ledger_lib.LedgerError, "refs.transcript: unknown key"):
            ledger_lib.append(invoke_row(refs={"transcript": "x"}))

    def test_long_note_rejected(self) -> None:
        row = {"run_id": "r1", "kind": "verdict", "origin": "organic", "skill": "demo",
               "outcome": {"label": "bad", "source": "user", "note": "x" * 121}}
        with self.assertRaisesRegex(ledger_lib.LedgerError, "outcome.note"):
            ledger_lib.append(row)
        row["outcome"]["note"] = "x" * 120
        ledger_lib.append(row)

    def test_raw_session_and_missing_fields_rejected(self) -> None:
        with self.assertRaisesRegex(ledger_lib.LedgerError, "session"):
            ledger_lib.append(invoke_row(session="abc-123-raw"))
        with self.assertRaisesRegex(ledger_lib.LedgerError, "skill: required"):
            ledger_lib.append({"run_id": "r1", "kind": "invoke", "origin": "organic"})
        with self.assertRaisesRegex(ledger_lib.LedgerError, "outcome: required"):
            ledger_lib.append({"run_id": "r1", "kind": "verdict", "origin": "organic", "skill": "s"})

    def test_malformed_lines_skipped_or_raised(self) -> None:
        good = ledger_lib.append(invoke_row())
        path = ledger_lib.month_files()[0]
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("not json\n{\"kind\": \"invoke\"}\n")
        self.assertEqual(list(ledger_lib.iter_rows()), [good])
        with self.assertRaises(ledger_lib.LedgerError):
            list(ledger_lib.iter_rows(strict=True))

    def test_lock_timeout(self) -> None:
        # The contender is a child process: an msvcrt byte lock does not block a second
        # handle opened by the same process.
        with ledger_lib.locked():
            result = subprocess.run([sys.executable, "-c", CONTENDER, str(MARCUS_SCRIPTS)],
                                    capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(list(ledger_lib.iter_rows()), [])


WORKER = """
import sys
sys.path.insert(0, sys.argv[1])
import ledger_lib
tag = sys.argv[2]
for i in range(500):
    ledger_lib.append({"run_id": f"{tag}-{i}", "kind": "invoke", "origin": "organic",
                       "skill": "demo", "trigger": "model"})
"""


class TestConcurrentAppend(LedgerTestCase):
    def test_two_processes_500_rows_each(self) -> None:
        procs = [subprocess.Popen([sys.executable, "-c", WORKER, str(MARCUS_SCRIPTS), tag],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True)
                 for tag in ("a", "b")]
        for proc in procs:
            _, err = proc.communicate(timeout=300)
            self.assertEqual(proc.returncode, 0, err)
        lines = [line for path in ledger_lib.month_files()
                 for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(lines), 1000)
        rows = [json.loads(line) for line in lines]
        self.assertTrue(all(ledger_lib.validate(row) == [] for row in rows))
        self.assertEqual(len({row["run_id"] for row in rows}), 1000)
        self.assertEqual(len(list(ledger_lib.iter_rows(strict=True))), 1000)


class TestSkillSha(unittest.TestCase):
    def _write(self, root: Path, files) -> None:
        for rel, text in files:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def test_stable_across_file_order(self) -> None:
        files = [("SKILL.md", "body"), ("scripts/a.py", "print(1)"), ("references/b.md", "ref")]
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self._write(Path(one), files)
            self._write(Path(two), list(reversed(files)))
            self._write(Path(two), [("scripts/__pycache__/a.pyc", "cache"), (".hidden", "x")])
            first = ledger_lib.skill_sha(Path(one))
            self.assertEqual(first, ledger_lib.skill_sha(Path(two)))
            self.assertRegex(first, r"^[0-9a-f]{64}$")
            self._write(Path(two), [("scripts/a.py", "print(2)")])
            self.assertNotEqual(first, ledger_lib.skill_sha(Path(two)))

    def test_eval_outputs_and_skipped_trees_do_not_change_hash(self) -> None:
        with tempfile.TemporaryDirectory() as one:
            root = Path(one)
            self._write(root, [("SKILL.md", "body"), ("evals/evals.json", "[]")])
            first = ledger_lib.skill_sha(root)
            self._write(root, [
                ("evals/results-baseline.json", "{}"),
                ("evals/transcripts-treated.json", "[]"),
                ("evals/last_run.json", "{}"),
                ("node_modules/pkg/index.js", "x"),
                (".git/HEAD", "ref"),
            ])
            self.assertEqual(first, ledger_lib.skill_sha(root))
            self._write(root, [("references/results-notes.json", "{}")])
            self.assertNotEqual(first, ledger_lib.skill_sha(root))

    def test_budget_raises(self) -> None:
        with tempfile.TemporaryDirectory() as one:
            root = Path(one)
            self._write(root, [("SKILL.md", "body"), ("a.md", "12345")])
            self.assertEqual(ledger_lib.skill_sha(root, max_files=2, max_bytes=9),
                             ledger_lib.skill_sha(root))
            with self.assertRaises(ledger_lib.SkillShaBudgetExceeded):
                ledger_lib.skill_sha(root, max_files=1)
            with self.assertRaises(ledger_lib.SkillShaBudgetExceeded):
                ledger_lib.skill_sha(root, max_bytes=8)

    def test_rename_changes_hash(self) -> None:
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self._write(Path(one), [("a.md", "same")])
            self._write(Path(two), [("b.md", "same")])
            self.assertNotEqual(ledger_lib.skill_sha(Path(one)), ledger_lib.skill_sha(Path(two)))


class TestStatistics(unittest.TestCase):
    def test_wilson(self) -> None:
        low, high = ledger_lib.wilson(7, 10)
        self.assertAlmostEqual(low, 0.397, places=3)
        self.assertAlmostEqual(high, 0.892, places=3)
        self.assertEqual(ledger_lib.wilson(0, 0), (0.0, 1.0))
        low, high = ledger_lib.wilson(0, 20)
        self.assertEqual(low, 0.0)
        self.assertLess(high, 0.2)
        with self.assertRaises(ValueError):
            ledger_lib.wilson(3, 2)

    def test_mcnemar_exact(self) -> None:
        self.assertAlmostEqual(ledger_lib.mcnemar_exact(6, 0), 0.03125)
        self.assertAlmostEqual(ledger_lib.mcnemar_exact(5, 0), 0.0625)
        self.assertAlmostEqual(ledger_lib.mcnemar_exact(0, 6), 0.03125)
        self.assertEqual(ledger_lib.mcnemar_exact(0, 0), 1.0)
        self.assertEqual(ledger_lib.mcnemar_exact(3, 3), 1.0)
        with self.assertRaises(ValueError):
            ledger_lib.mcnemar_exact(-1, 0)


if __name__ == "__main__":
    unittest.main()
