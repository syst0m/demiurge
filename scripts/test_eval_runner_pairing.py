#!/usr/bin/env python3
"""
test_eval_runner_pairing.py - Unit tests for G5 per-case pairing in eval_runner.py.

G5 counts discordant cases by id, so a missing or repeated id would drop a case
or pair it with the wrong baseline row. These tests hold that it refuses both.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "marcus" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("eval_runner", SCRIPTS / "eval_runner.py")
er = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(er)


def row(case_id, passed: bool) -> dict:
    return {"id": case_id, "majority_pass": passed, "attempts": ["PASS" if passed else "FAIL"] * 3}


class TestCaseIds(unittest.TestCase):
    def test_unique_ids_pass(self):
        self.assertEqual(er.case_id_errors([{"id": "a"}, {"id": "b"}]), [])

    def test_missing_and_empty_ids_fail(self):
        errors = er.case_id_errors([{"id": "a"}, {}, {"id": " "}, {"id": 3}])
        self.assertEqual(errors, ["3 case(s) without a non-empty string id"])

    def test_repeated_id_across_suites_fails(self):
        cases = [{"suite": "regression", "id": "a"}, {"suite": "capability", "id": "a"}]
        self.assertEqual(er.case_id_errors(cases), ["repeated case id(s): a"])


class TestDiscordant(unittest.TestCase):
    def test_counts_flips_by_id(self):
        baseline = [row("a", False), row("b", True), row("c", True)]
        treated = [row("c", True), row("b", False), row("a", True)]
        self.assertEqual(er.discordant(baseline, treated), (1, 1))

    def test_repeated_ids_are_refused(self):
        baseline = [row("a", True), row("a", False)]
        with self.assertRaises(ValueError):
            er.discordant(baseline, list(baseline))

    def test_missing_ids_are_refused(self):
        with self.assertRaises(ValueError):
            er.discordant([row(None, False), row(None, True)], [row(None, True), row(None, True)])

    def test_different_case_sets_are_refused(self):
        with self.assertRaises(ValueError):
            er.discordant([row("a", False), row("b", False)], [row("a", True)])


class TestPairingErrors(unittest.TestCase):
    def pairing(self, ids):
        return {"case_ids": ids, "evals_sha256": "x", "k": 3, "runner_template": "r"}

    def test_repeated_baseline_ids_do_not_pair(self):
        errors = er.pairing_errors(self.pairing(["a", "a"]), self.pairing(["a", "a"]))
        self.assertIn("baseline case ids repeat", errors)

    def test_same_ids_pair(self):
        self.assertEqual(er.pairing_errors(self.pairing(["b", "a"]), self.pairing(["a", "b"])), [])


if __name__ == "__main__":
    unittest.main()
