#!/usr/bin/env python3
"""Deterministic tests for the SWE-bench evaluation harness and metrics."""

import json
import tempfile
import unittest
from pathlib import Path

from metrics import (
    ArmSummary,
    BenchmarkComparison,
    TaskResult,
    compare_arms,
    compute_cost,
    render_markdown_report,
    summarize_arm,
)
from run_swebench_eval import build_system_prompt, execute_evaluation


class TestSWEBenchHarness(unittest.TestCase):
    def test_cost_calculation(self):
        cost = compute_cost(
            model="claude-3-5-sonnet-20241022",
            prompt_tokens=100000,
            completion_tokens=2000,
            cache_read_tokens=80000,
            cache_write_tokens=10000,
        )
        self.assertGreater(cost, 0.0)
        self.assertLess(cost, 1.0)

    def test_summarize_arm(self):
        results = [
            TaskResult(
                instance_id="task-1",
                arm="demiurge",
                resolved=True,
                turns=5,
                prompt_tokens=20000,
                completion_tokens=1000,
                cache_read_tokens=16000,
                cache_write_tokens=2000,
                cost_usd=0.05,
            ),
            TaskResult(
                instance_id="task-2",
                arm="demiurge",
                resolved=False,
                turns=8,
                prompt_tokens=25000,
                completion_tokens=1200,
                cache_read_tokens=20000,
                cache_write_tokens=2000,
                cost_usd=0.07,
            ),
        ]
        summary = summarize_arm("demiurge", results)
        self.assertEqual(summary.total_tasks, 2)
        self.assertEqual(summary.resolved_count, 1)
        self.assertEqual(summary.pass_rate, 0.5)
        self.assertEqual(summary.mean_turns, 6.5)
        self.assertGreater(summary.cache_hit_ratio, 0.7)

    def test_system_prompt_builder(self):
        repo_root = Path(__file__).resolve().parents[3]
        bare_prompt = build_system_prompt("bare", repo_root)
        demiurge_prompt = build_system_prompt("demiurge", repo_root)

        self.assertIn("autonomous coding assistant", bare_prompt)
        self.assertIn("Demiurge Autonomous Architecture", demiurge_prompt)
        self.assertIn("Marcus Active Skill", demiurge_prompt)

    def test_dry_run_execution(self):
        repo_root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)
            comparison = execute_evaluation(
                dataset="princeton-nlp/SWE-bench_Lite",
                task_slice="0:3",
                model="claude-3-5-sonnet-20241022",
                output_dir=out_path,
                dry_run=True,
                spend_confirmed=False,
                repo_root=repo_root,
            )
            self.assertEqual(comparison.bare.total_tasks, 3)
            self.assertEqual(comparison.demiurge.total_tasks, 3)
            self.assertTrue((out_path / "results.json").is_file())
            self.assertTrue((out_path / "report.md").is_file())
            self.assertTrue((out_path / "predictions_bare.json").is_file())
            self.assertTrue((out_path / "predictions_demiurge.json").is_file())


if __name__ == "__main__":
    unittest.main()
