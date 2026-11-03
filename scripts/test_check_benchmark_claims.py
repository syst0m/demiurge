#!/usr/bin/env python3
"""Tests for check_benchmark_claims.py against a temporary repo."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_benchmark_claims as chk  # noqa: E402

TABLE = """## 4. Benchmark Run Registry

| Run ID | Date | Model | Suite | Tasks | Bare Pass | Demiurge Pass | Delta | Mode | Results |
|---|---|---|---|---|---|---|---|---|---|
| `r1` | d | m | s | 2 | 50.0% | 100.0% | +50.00% | LIVE | [results.json](../eval_results/x/results.json) |

### Unverified and withdrawn runs

| `old` | not a registry row |

## 5. Next
"""


def results(simulated, tasks=2):
    return {"comparison": {"simulated": simulated,
                           "bare": {"total_tasks": tasks, "pass_rate": 0.5},
                           "demiurge": {"total_tasks": tasks, "pass_rate": 1.0}}}


class ClaimsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "BENCHMARKS.md").write_text(TABLE, encoding="utf-8")
        (self.repo / "eval_results" / "x").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        (self.repo / "eval_results" / "x" / "results.json").write_text(json.dumps(data), encoding="utf-8")

    def run_check(self):
        return chk.main(["--repo", str(self.repo)])

    def test_live_matching_row_passes(self):
        self.write(results(False))
        self.assertEqual(self.run_check(), 0)

    def test_simulated_row_fails(self):
        self.write(results(True))
        self.assertEqual(self.run_check(), 1)

    def test_missing_simulated_flag_fails(self):
        data = results(False)
        del data["comparison"]["simulated"]
        self.write(data)
        self.assertEqual(self.run_check(), 1)

    def test_missing_file_fails(self):
        self.assertEqual(self.run_check(), 1)

    def test_pass_rate_mismatch_fails(self):
        data = results(False)
        data["comparison"]["demiurge"]["pass_rate"] = 0.6
        self.write(data)
        self.assertEqual(self.run_check(), 1)

    def test_missing_table_exits_2(self):
        (self.repo / "docs" / "BENCHMARKS.md").write_text("# none\n", encoding="utf-8")
        self.assertEqual(self.run_check(), 2)


if __name__ == "__main__":
    unittest.main()
