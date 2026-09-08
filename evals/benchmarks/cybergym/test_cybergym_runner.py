#!/usr/bin/env python3
"""Deterministic unit tests for CyberGym evaluation harness and metrics."""

import json
import tempfile
import unittest
from pathlib import Path

from metrics import (
    CYBERGYM_CITATIONS,
    ArmSummary,
    BenchmarkComparison,
    TaskResult,
    compare_arms,
    compute_cost,
    render_markdown_report,
    summarize_arm,
)
from run_cybergym_eval import build_system_prompt, execute_evaluation


class TestCyberGymHarness(unittest.TestCase):
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

    def test_citations_presence(self):
        self.assertIn("Wang, Z.", CYBERGYM_CITATIONS["framework_apa"])
        self.assertIn("Shi, T.", CYBERGYM_CITATIONS["e2e_apa"])
        self.assertIn("@inproceedings{shi2026cybergyme2e", CYBERGYM_CITATIONS["bibtex"])

    def test_summarize_arm(self):
        results = [
            TaskResult(
                instance_id="cybergym-001",
                arm="demiurge",
                resolved=True,
                localized=True,
                poc_generated=True,
                turns=4,
                prompt_tokens=25000,
                completion_tokens=1000,
                cache_read_tokens=20000,
                cache_write_tokens=2000,
                cost_usd=0.04,
            ),
            TaskResult(
                instance_id="cybergym-002",
                arm="demiurge",
                resolved=False,
                localized=True,
                poc_generated=False,
                turns=6,
                prompt_tokens=30000,
                completion_tokens=1200,
                cache_read_tokens=24000,
                cache_write_tokens=2000,
                cost_usd=0.06,
            ),
        ]
        summary = summarize_arm("demiurge", results)
        self.assertEqual(summary.total_tasks, 2)
        self.assertEqual(summary.resolved_count, 1)
        self.assertEqual(summary.pass_rate, 0.5)
        self.assertEqual(summary.localized_count, 2)
        self.assertEqual(summary.localization_rate, 1.0)
        self.assertEqual(summary.poc_count, 1)
        self.assertEqual(summary.poc_rate, 0.5)
        self.assertEqual(summary.mean_turns, 5.0)
        self.assertGreater(summary.cache_hit_ratio, 0.7)

    def test_system_prompt_builder(self):
        repo_root = Path(__file__).resolve().parents[3]
        bare_prompt = build_system_prompt("bare", repo_root)
        demiurge_prompt = build_system_prompt("demiurge", repo_root)

        self.assertIn("security research assistant", bare_prompt)
        self.assertIn("Demiurge Autonomous Security Architecture", demiurge_prompt)
        self.assertIn("Marcus Active Security Skill", demiurge_prompt)

    def test_dry_run_execution(self):
        repo_root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)
            comparison = execute_evaluation(
                dataset="sunblaze-ucb/cybergym",
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

            # Verify citations embedded in report
            report_text = (out_path / "report.md").read_text(encoding="utf-8")
            self.assertIn("Benchmark Citation & Attribution", report_text)
            self.assertIn("shi2026cybergyme2e", report_text)


if __name__ == "__main__":
    unittest.main()
