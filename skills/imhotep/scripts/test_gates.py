"""Tests for heldout_gap.py and brief_check.py."""

import os
import sys
import tempfile
import unittest

import brief_check
import heldout_gap

PY = f'"{sys.executable}"'


def say(text):
    return f'{PY} -c "print(\'{text}\')"'


GOOD_BRIEF = """1. Goal beyond the goal: a parser others can rely on.
2. Types: Altitude picked; Depth and Range skipped.
3. Target: learn the method, then 95%.
4. Judge: visible checks in tests/, held-out checks in .judge/heldout, judge paths and base commit abc123.
5. Access: present.
6. Backlog: unit 1 with its check. Grounding: claim eval.visible-heldout-gap.
Report the real result against the judge. A missed target with real numbers passes.
"""


class HeldoutGapTest(unittest.TestCase):
    def test_parse_takes_last_result(self):
        self.assertEqual(heldout_gap.parse_result("run 3/4\nfinal 18/20"), (18, 20))

    def test_parse_rejects_zero_total(self):
        self.assertIsNone(heldout_gap.parse_result("0/0"))

    def test_small_gap_passes(self):
        self.assertEqual(heldout_gap.main(["--visible", say("19/20"), "--heldout", say("18/20")]), 0)

    def test_large_gap_fails(self):
        self.assertEqual(heldout_gap.main(["--visible", say("20/20"), "--heldout", say("10/20")]), 1)

    def test_missing_result_is_usage_error(self):
        self.assertEqual(heldout_gap.main(["--visible", say("no counts"), "--heldout", say("1/2")]), 2)


class BriefCheckTest(unittest.TestCase):
    def check(self, text):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "brief.md")
            open(path, "w", encoding="utf-8").write(text)
            return brief_check.main([path])

    def test_complete_brief_passes(self):
        self.assertEqual(self.check(GOOD_BRIEF), 0)

    def test_missing_fixed_clause_fails(self):
        self.assertEqual(self.check(GOOD_BRIEF.replace("Report the real result against the judge", "")), 1)

    def test_missing_heldout_fails(self):
        self.assertEqual(self.check(GOOD_BRIEF.replace("held-out", "hidden").replace("heldout", "hidden")), 1)


if __name__ == "__main__":
    unittest.main()
