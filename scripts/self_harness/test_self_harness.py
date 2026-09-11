#!/usr/bin/env python3
"""Deterministic tests for the self-harness subsystem (scripts/self_harness/)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acceptance_gate
import diagnose_failures
import materialize_candidate
import propose_candidate
import splits
import validate_self_harness_scripts

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_results(path: Path, demiurge_tasks: list[dict]) -> None:
    path.write_text(json.dumps({"demiurge_tasks": demiurge_tasks}, indent=2), encoding="utf-8")


class TestSplits(unittest.TestCase):
    def test_split_is_order_independent(self):
        ids = [f"task-{i}" for i in range(20)]
        forward = splits.compute_split(ids, seed=7)
        backward = splits.compute_split(list(reversed(ids)), seed=7)
        self.assertEqual(forward, backward)

    def test_split_is_a_partition(self):
        ids = [f"task-{i}" for i in range(20)]
        result = splits.compute_split(ids, seed=1)
        self.assertEqual(set(result["train"]) | set(result["heldout"]), set(ids))
        self.assertEqual(set(result["train"]) & set(result["heldout"]), set())
        self.assertGreater(len(result["heldout"]), 0)

    def test_load_or_create_splits_extends_without_moving_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "splits.json"
            first = splits.load_or_create_splits(cache_path, ["a", "b", "c"], seed=3)
            second = splits.load_or_create_splits(cache_path, ["a", "b", "c", "d"], seed=3)
            self.assertEqual(set(first["train"]) | set(first["heldout"]), {"a", "b", "c"})
            self.assertTrue(set(first["train"]).issubset(set(second["train"])) or set(first["heldout"]).issubset(set(second["heldout"])))
            self.assertIn("d", set(second["train"]) | set(second["heldout"]))
            for task_id in ("a", "b", "c"):
                self.assertEqual(task_id in first["train"], task_id in second["train"])


class TestDiagnoseFailures(unittest.TestCase):
    def test_clusters_by_normalized_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            results_path = Path(tmp) / "results.json"
            _write_results(
                results_path,
                [
                    {"instance_id": "t1", "resolved": False, "error": "Timeout waiting for patch."},
                    {"instance_id": "t2", "resolved": False, "error": "  timeout waiting for patch.  "},
                    {"instance_id": "t3", "resolved": False, "error": "Invalid diff format."},
                    {"instance_id": "t4", "resolved": True, "error": None},
                ],
            )
            failing = diagnose_failures.load_failing_tasks(results_path)
            self.assertEqual(len(failing), 3)
            clusters = diagnose_failures.cluster_failures(failing)
            self.assertEqual(len(clusters), 2)
            self.assertEqual(clusters[0]["count"], 2)

    def test_no_failures_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            results_path = Path(tmp) / "results.json"
            _write_results(results_path, [{"instance_id": "t1", "resolved": True, "error": None}])
            failing = diagnose_failures.load_failing_tasks(results_path)
            clusters = diagnose_failures.cluster_failures(failing)
            self.assertEqual(clusters, [])
            brief = diagnose_failures.render_brief([str(results_path)], 1, clusters)
            self.assertIn("No-op", brief)


class TestProposeCandidate(unittest.TestCase):
    def _surfaces(self, tmp: str) -> dict[str, Path]:
        surface_path = Path(tmp) / "rule.md"
        surface_path.write_text("original content\n", encoding="utf-8")
        return {"rule": surface_path}

    def _valid_response(self) -> dict:
        return {
            "proposal_id": "tighten-rule",
            "title": "Tighten the rule",
            "surface": "rule",
            "value": "new content\n",
            "summary": "Adds a missing constraint.",
            "why_distinct": "Only candidate touching this surface.",
            "net_gain_hypothesis": "Fewer timeout failures.",
            "regression_guard": "Must not remove existing constraints.",
        }

    def test_accepts_a_valid_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            surfaces = self._surfaces(tmp)
            bundle = propose_candidate.validate_and_build_bundle(self._valid_response(), surfaces)
            self.assertEqual(bundle["surface"], "rule")
            self.assertEqual(bundle["value"], "new content\n")

    def test_rejects_undeclared_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            surfaces = self._surfaces(tmp)
            response = self._valid_response()
            response["surface"] = "not-declared"
            with self.assertRaises(ValueError):
                propose_candidate.validate_and_build_bundle(response, surfaces)

    def test_rejects_unchanged_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            surfaces = self._surfaces(tmp)
            response = self._valid_response()
            response["value"] = "original content\n"
            with self.assertRaises(ValueError):
                propose_candidate.validate_and_build_bundle(response, surfaces)

    def test_rejects_empty_regression_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            surfaces = self._surfaces(tmp)
            response = self._valid_response()
            response["regression_guard"] = "   "
            with self.assertRaises(ValueError):
                propose_candidate.validate_and_build_bundle(response, surfaces)


class TestMaterializeCandidate(unittest.TestCase):
    def _init_repo(self, tmp: str) -> Path:
        repo_root = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)
        (repo_root / "rule.md").write_text("original content\n", encoding="utf-8")
        subprocess.run(["git", "add", "rule.md"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo_root, check=True)
        return repo_root

    def _proposal(self) -> dict:
        return {
            "proposal_id": "tighten-rule",
            "title": "Tighten the rule",
            "surface": "rule",
            "surface_path": "rule.md",
            "value": "new content\n",
            "summary": "Adds a missing constraint.",
            "regression_guard": "Must not remove existing constraints.",
        }

    def test_materializes_a_branch_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._init_repo(tmp)
            manifest = materialize_candidate.materialize(
                proposal=self._proposal(), repo_root=repo_root, candidate_id="tighten-rule", checkout=True
            )
            self.assertEqual(manifest["branch"], "self-harness/tighten-rule")
            self.assertEqual((repo_root / "rule.md").read_text(encoding="utf-8"), "new content\n")
            manifest_path = repo_root / "eval_results" / "self_harness" / "tighten-rule" / "candidate_manifest.json"
            self.assertTrue(manifest_path.is_file())

    def test_refuses_a_dirty_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._init_repo(tmp)
            (repo_root / "rule.md").write_text("uncommitted edit\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                materialize_candidate.materialize(
                    proposal=self._proposal(), repo_root=repo_root, candidate_id="tighten-rule", checkout=True
                )

    def test_refuses_a_second_active_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._init_repo(tmp)
            materialize_candidate.materialize(
                proposal=self._proposal(), repo_root=repo_root, candidate_id="first", checkout=True
            )
            with self.assertRaises(RuntimeError):
                materialize_candidate.materialize(
                    proposal=self._proposal(), repo_root=repo_root, candidate_id="second", checkout=True
                )


class TestAcceptanceGate(unittest.TestCase):
    def test_accepted_when_a_split_improves_and_none_drop(self):
        comparison = acceptance_gate.compare_split(
            "heldout", ["a", "b"], baseline_repeats=[{"a": False, "b": False}], candidate_repeats=[{"a": True, "b": False}]
        )
        self.assertEqual(comparison["status"], "improved")

    def test_dropped_when_candidate_regresses(self):
        comparison = acceptance_gate.compare_split(
            "heldout", ["a", "b"], baseline_repeats=[{"a": True, "b": True}], candidate_repeats=[{"a": True, "b": False}]
        )
        self.assertEqual(comparison["status"], "dropped")

    def test_unchanged_when_identical(self):
        comparison = acceptance_gate.compare_split(
            "heldout", ["a", "b"], baseline_repeats=[{"a": True, "b": False}], candidate_repeats=[{"a": True, "b": False}]
        )
        self.assertEqual(comparison["status"], "unchanged")

    def test_end_to_end_rejects_when_nothing_improves(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tasks = [{"instance_id": f"t{i}", "resolved": True, "error": None} for i in range(10)]
            baseline_path = tmp_path / "baseline.json"
            candidate_path = tmp_path / "candidate.json"
            _write_results(baseline_path, tasks)
            _write_results(candidate_path, tasks)
            result = acceptance_gate.run_acceptance_gate(
                baseline_paths=[baseline_path],
                candidate_paths=[candidate_path],
                seed=0,
                splits_cache=tmp_path / "splits.json",
            )
            self.assertFalse(result["accepted"])

    def test_end_to_end_requires_symmetrical_task_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline_path = tmp_path / "baseline.json"
            candidate_path = tmp_path / "candidate.json"
            _write_results(baseline_path, [{"instance_id": "t1", "resolved": True, "error": None}])
            _write_results(candidate_path, [{"instance_id": "t2", "resolved": True, "error": None}])
            with self.assertRaises(ValueError):
                acceptance_gate.run_acceptance_gate(
                    baseline_paths=[baseline_path],
                    candidate_paths=[candidate_path],
                    seed=0,
                    splits_cache=tmp_path / "splits.json",
                )


class TestValidateSelfHarnessScripts(unittest.TestCase):
    def test_audits_its_own_siblings_clean(self):
        for filename in validate_self_harness_scripts.TARGET_FILENAMES:
            path = REPO_ROOT / "scripts" / "self_harness" / filename
            violations = validate_self_harness_scripts.audit_file(path)
            self.assertEqual(violations, [], f"{filename}: {violations}")

    def test_main_passes(self):
        self.assertEqual(validate_self_harness_scripts.main(), 0)


if __name__ == "__main__":
    unittest.main()
