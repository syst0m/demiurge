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
from run_swebench_eval import (
    build_system_prompt,
    build_task_user_prompt,
    eval_patch_resolution,
    execute_evaluation,
    load_swebench_dataset,
)


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
                simulated=True,
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
                simulated=True,
            ),
        ]
        summary = summarize_arm("demiurge", results)
        self.assertEqual(summary.total_tasks, 2)
        self.assertEqual(summary.resolved_count, 1)
        self.assertEqual(summary.pass_rate, 0.5)
        self.assertEqual(summary.mean_turns, 6.5)
        self.assertGreater(summary.cache_hit_ratio, 0.7)
        self.assertTrue(summary.simulated)

    def test_system_prompt_builder(self):
        repo_root = Path(__file__).resolve().parents[3]
        bare_prompt = build_system_prompt("bare", repo_root)
        demiurge_prompt = build_system_prompt("demiurge", repo_root)

        self.assertIn("autonomous coding assistant", bare_prompt)
        self.assertIn("Demiurge Autonomous Architecture", demiurge_prompt)
        self.assertIn("Marcus Active Skill", demiurge_prompt)

    def test_build_task_user_prompt(self):
        instance = {
            "instance_id": "django__django-11099",
            "repo": "django/django",
            "base_commit": "abc12345",
            "problem_statement": "ASCIIUsernameValidator allows trailing newline",
        }
        prompt = build_task_user_prompt(instance)
        self.assertIn("django__django-11099", prompt)
        self.assertIn("django/django", prompt)
        self.assertIn("ASCIIUsernameValidator allows trailing newline", prompt)

    def test_eval_patch_resolution(self):
        repo_root = Path(__file__).resolve().parents[3]
        instance = {"FAIL_TO_PASS": ["tests.test_validator"]}

        valid_patch = (
            "diff --git a/django/contrib/auth/validators.py b/django/contrib/auth/validators.py\n"
            "--- a/django/contrib/auth/validators.py\n"
            "+++ b/django/contrib/auth/validators.py\n"
            "@@ -17,3 +17,3 @@\n"
            "-    regex = r'^[\\w.@+-]+\\Z'\n"
            "+    regex = r'^[\\w.@+-]+$'\n"
        )
        resolved, err = eval_patch_resolution(instance, valid_patch, repo_root)
        self.assertTrue(resolved)
        self.assertIsNone(err)

        invalid_patch = "No diff here."
        resolved, err = eval_patch_resolution(instance, invalid_patch, repo_root)
        self.assertFalse(resolved)
        self.assertIsNotNone(err)

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
            self.assertTrue(comparison.simulated)
            self.assertTrue((out_path / "results.json").is_file())
            self.assertTrue((out_path / "report.md").is_file())
            self.assertTrue((out_path / "predictions_bare.json").is_file())
            self.assertTrue((out_path / "predictions_demiurge.json").is_file())

            report_text = (out_path / "report.md").read_text()
            self.assertIn("SIMULATION BASELINE", report_text)

    def test_unsupported_live_model_raises_error(self):
        repo_root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(NotImplementedError):
                execute_evaluation(
                    dataset="princeton-nlp/SWE-bench_Lite",
                    task_slice="0:1",
                    model="unsupported-model-id",
                    output_dir=Path(tmp_dir),
                    dry_run=False,
                    spend_confirmed=True,
                    repo_root=repo_root,
                )


if __name__ == "__main__":
    unittest.main()
