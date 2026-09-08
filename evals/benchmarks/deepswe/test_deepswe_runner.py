#!/usr/bin/env python3
"""Deterministic tests for the DeepSWE evaluation harness and metrics."""

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
from run_deepswe_eval import (
    build_system_prompt,
    load_deepswe_dataset,
    run_mock_task,
)


class TestDeepSWEHarness(unittest.TestCase):
    def test_cost_calculation(self):
        cost = compute_cost(
            model="gemini-3.0-flash",
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
                instance_id="deepswe-task-001",
                arm="demiurge",
                resolved=True,
                turns=4,
                prompt_tokens=20000,
                completion_tokens=1000,
                cache_read_tokens=16000,
                cache_write_tokens=2000,
                cost_usd=0.05,
                simulated=True,
            ),
            TaskResult(
                instance_id="deepswe-task-002",
                arm="demiurge",
                resolved=False,
                turns=8,
                prompt_tokens=25000,
                completion_tokens=1200,
                cache_read_tokens=20000,
                cache_write_tokens=2000,
                cost_usd=0.07,
                simulated=True,
            ),
        ]
        summary = summarize_arm("demiurge", results)
        self.assertEqual(summary.total_tasks, 2)
        self.assertEqual(summary.resolved_count, 1)
        self.assertEqual(summary.pass_rate, 0.5)
        self.assertEqual(summary.mean_turns, 6.0)
        self.assertGreater(summary.cache_hit_ratio, 0.7)
        self.assertTrue(summary.simulated)

    def test_system_prompt_builder(self):
        repo_root = Path(__file__).resolve().parents[3]
        bare_prompt = build_system_prompt("bare", repo_root)
        demiurge_prompt = build_system_prompt("demiurge", repo_root)

        self.assertIn("autonomous coding assistant", bare_prompt)
        self.assertIn("Demiurge Autonomous Architecture", demiurge_prompt)
        self.assertIn("Marcus Active Skill", demiurge_prompt)

    def test_dataset_loader_and_sampling(self):
        # Test full dataset index loading
        full_tasks = load_deepswe_dataset()
        self.assertEqual(len(full_tasks), 113)
        self.assertEqual(full_tasks[0]["instance_id"], "deepswe-task-001")

        # Test deterministic sampling with seed
        sampled_tasks = load_deepswe_dataset(n_tasks=10, sample_seed=0)
        self.assertEqual(len(sampled_tasks), 10)

        # Test slice option
        sliced_tasks = load_deepswe_dataset(slice_str="0:5")
        self.assertEqual(len(sliced_tasks), 5)

    def test_mock_task_execution(self):
        task = {
            "instance_id": "deepswe-task-001",
            "repo": "datacurve-ai/task-repo-001",
            "problem_statement": "DeepSWE long-horizon task issue #001",
            "base_commit": "commit_001_hash",
        }
        res_bare = run_mock_task(task, "bare", "gemini-3.0-flash")
        res_dem = run_mock_task(task, "demiurge", "gemini-3.0-flash")

        self.assertTrue(res_bare.simulated)
        self.assertTrue(res_dem.simulated)
        self.assertTrue(res_dem.resolved)
        self.assertFalse(res_bare.resolved)

    def test_markdown_report_rendering(self):
        bare_results = [run_mock_task({"instance_id": "t1"}, "bare", "gemini-3.0-flash")]
        demiurge_results = [run_mock_task({"instance_id": "t1"}, "demiurge", "gemini-3.0-flash")]

        comp = compare_arms("gemini-3.0-flash", "datacurve-ai/deep-swe", bare_results, demiurge_results)
        report = render_markdown_report(comp)

        self.assertIn("# DeepSWE Comparative Evaluation Report", report)
        self.assertIn("SIMULATION BASELINE", report)
        self.assertIn("gemini-3.0-flash", report)


if __name__ == "__main__":
    unittest.main()
