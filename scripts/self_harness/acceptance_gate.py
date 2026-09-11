#!/usr/bin/env python3
"""Self-harness acceptance gate: this is Gate G5, applied to a harness-surface candidate.

skills/marcus/AGENT_ARCHITECTURE.md's Gate G5 already reads: "Delta <= 0, or any
regression drop -> reject." This script is that rule, computed per train/heldout
split, averaged across repeats, and applied to a demiurge-arm results.json pair
(baseline vs. candidate) instead of a generated skill's eval score.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from splits import load_or_create_splits

FORMAT = "demiurge.self_harness.acceptance_gate.v0"
DEFAULT_SEED = 0
DEFAULT_SPLITS_CACHE = Path("eval_results/self_harness/splits.json")


def load_task_outcomes(results_path: Path) -> dict[str, bool]:
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    if "demiurge_tasks" not in payload:
        raise ValueError(f"{results_path}: missing 'demiurge_tasks' (not a self-harness results.json)")
    outcomes: dict[str, bool] = {}
    for task in payload["demiurge_tasks"]:
        instance_id = task.get("instance_id")
        if instance_id is None:
            raise ValueError(f"{results_path}: a demiurge_tasks entry is missing 'instance_id'")
        resolved = task.get("resolved")
        if not isinstance(resolved, bool):
            raise ValueError(f"{results_path}: instance {instance_id!r} has a non-boolean 'resolved'")
        outcomes[instance_id] = resolved
    return outcomes


def load_repeats(paths: list[Path]) -> list[dict[str, bool]]:
    return [load_task_outcomes(path) for path in paths]


def assert_symmetrical(baseline_repeats: list[dict[str, bool]], candidate_repeats: list[dict[str, bool]]) -> set[str]:
    all_repeats = baseline_repeats + candidate_repeats
    task_id_sets = [frozenset(repeat.keys()) for repeat in all_repeats]
    first = task_id_sets[0]
    for other in task_id_sets[1:]:
        if other != first:
            raise ValueError(
                "baseline and candidate results do not cover the same task set; the acceptance "
                "gate requires symmetrical evaluation across every repeat"
            )
    return set(first)


def split_pass_rate(repeat: dict[str, bool], split_ids: list[str]) -> dict[str, Any]:
    relevant = [repeat[task_id] for task_id in split_ids]
    total = len(relevant)
    passed = sum(1 for outcome in relevant if outcome)
    return {"passed": passed, "total": total, "pass_rate": (passed / total) if total else 0.0}


def average_pass_rate(per_repeat: list[dict[str, Any]]) -> float:
    if not per_repeat:
        return 0.0
    return sum(item["pass_rate"] for item in per_repeat) / len(per_repeat)


def compare_split(
    split_name: str,
    split_ids: list[str],
    baseline_repeats: list[dict[str, bool]],
    candidate_repeats: list[dict[str, bool]],
) -> dict[str, Any]:
    baseline_metrics = [split_pass_rate(repeat, split_ids) for repeat in baseline_repeats]
    candidate_metrics = [split_pass_rate(repeat, split_ids) for repeat in candidate_repeats]
    baseline_avg = average_pass_rate(baseline_metrics)
    candidate_avg = average_pass_rate(candidate_metrics)
    delta = candidate_avg - baseline_avg

    if delta > 0:
        status = "improved"
    elif delta < 0:
        status = "dropped"
    else:
        status = "unchanged"

    return {
        "split": split_name,
        "task_count": len(split_ids),
        "baseline_average_pass_rate": round(baseline_avg, 4),
        "candidate_average_pass_rate": round(candidate_avg, 4),
        "delta": round(delta, 4),
        "status": status,
        "baseline_repeats": baseline_metrics,
        "candidate_repeats": candidate_metrics,
    }


def run_acceptance_gate(
    *,
    baseline_paths: list[Path],
    candidate_paths: list[Path],
    seed: int,
    splits_cache: Path,
) -> dict[str, Any]:
    baseline_repeats = load_repeats(baseline_paths)
    candidate_repeats = load_repeats(candidate_paths)
    task_ids = assert_symmetrical(baseline_repeats, candidate_repeats)

    splits = load_or_create_splits(splits_cache, sorted(task_ids), seed)

    comparisons = [
        compare_split(name, splits[name], baseline_repeats, candidate_repeats)
        for name in ("train", "heldout")
        if splits[name]
    ]
    if not comparisons:
        raise ValueError("no non-empty train/heldout split produced from the given task set")

    dropped = [c["split"] for c in comparisons if c["status"] == "dropped"]
    improved = [c["split"] for c in comparisons if c["status"] == "improved"]
    accepted = not dropped and bool(improved)

    if accepted:
        reason = f"accepted: improved on {improved}, dropped on none"
    elif dropped:
        reason = f"rejected: dropped on {dropped}"
    else:
        reason = "rejected: no split improved"

    return {
        "format": FORMAT,
        "accepted": accepted,
        "decision": "accepted" if accepted else "rejected",
        "reason": reason,
        "rule": "no split drops and at least one split improves (Gate G5)",
        "seed": seed,
        "baseline_results": [str(p) for p in baseline_paths],
        "candidate_results": [str(p) for p in candidate_paths],
        "splits": {c["split"]: c for c in comparisons},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply the self-harness acceptance gate (Gate G5).")
    parser.add_argument("--baseline-results", action="append", required=True, type=Path)
    parser.add_argument("--candidate-results", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--splits-cache", type=Path, default=DEFAULT_SPLITS_CACHE)
    args = parser.parse_args(argv)

    result = run_acceptance_gate(
        baseline_paths=args.baseline_results,
        candidate_paths=args.candidate_results,
        seed=args.seed,
        splits_cache=args.splits_cache,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['decision']}: {result['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
