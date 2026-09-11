#!/usr/bin/env python3
"""Cluster demiurge-arm benchmark failures into a diagnosis brief for the proposer stage.

Reads one or more evals/benchmarks/*/results.json files (the existing schema each
runner already writes: a top-level demiurge_tasks list of {instance_id, resolved,
error, ...}). Only the demiurge arm is diagnosed; the bare arm is not a harness
candidate for this project. TaskResult (evals/benchmarks/*/metrics.py) carries no
gate, mechanism, or criticality field today, so clustering uses the one structured
signal that exists: the normalized error text. The brief says so explicitly rather
than inventing a taxonomy the data does not support.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FORMAT = "demiurge.self_harness.diagnosis.v0"
_WHITESPACE = re.compile(r"\s+")
_SIGNATURE_LENGTH = 80


def normalize_error(error: str) -> str:
    collapsed = _WHITESPACE.sub(" ", error).strip().lower()
    return collapsed[:_SIGNATURE_LENGTH]


def load_failing_tasks(results_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    if "demiurge_tasks" not in payload:
        raise ValueError(f"{results_path}: missing 'demiurge_tasks' (not a self-harness results.json)")
    tasks = payload["demiurge_tasks"]
    failing = []
    for task in tasks:
        if task.get("resolved") is False:
            failing.append({**task, "source": str(results_path)})
    return failing


def cluster_failures(failing_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for task in failing_tasks:
        raw_error = task.get("error") or "(no error message recorded)"
        signature = normalize_error(raw_error)
        cluster = grouped.setdefault(
            signature,
            {"signature": signature, "instance_ids": [], "raw_errors": [], "count": 0},
        )
        cluster["count"] += 1
        cluster["instance_ids"].append(task.get("instance_id", "unknown"))
        if len(cluster["raw_errors"]) < 3 and raw_error not in cluster["raw_errors"]:
            cluster["raw_errors"].append(raw_error)

    clusters = sorted(grouped.values(), key=lambda c: (-c["count"], c["signature"]))
    for index, cluster in enumerate(clusters, start=1):
        cluster["cluster_id"] = f"cluster-{index:02d}"
    return clusters


def render_brief(sources: list[str], total_tasks: int, clusters: list[dict[str, Any]]) -> str:
    lines = [
        "# Self-Harness Diagnosis Brief",
        "",
        "Clusters below group demiurge-arm failures by normalized error text. Demiurge's "
        "TaskResult schema does not yet carry a gate, mechanism, or criticality field, so no "
        "such taxonomy is claimed here.",
        "",
        f"- Sources: {', '.join(sources)}",
        f"- Demiurge-arm tasks inspected: `{total_tasks}`",
        f"- Failing tasks: `{sum(c['count'] for c in clusters)}`",
        f"- Cluster count: `{len(clusters)}`",
        "",
    ]

    if not clusters:
        lines.append("No failing demiurge-arm tasks in the given results. No-op: propose nothing.")
        return "\n".join(lines) + "\n"

    for cluster in clusters:
        lines.append(f"## {cluster['cluster_id']}")
        lines.append("")
        lines.append(f"- Count: `{cluster['count']}`")
        lines.append(f"- Error signature: `{cluster['signature']}`")
        lines.append(f"- Representative instances: {', '.join(cluster['instance_ids'][:5])}")
        lines.append("- Example errors:")
        for raw_error in cluster["raw_errors"]:
            lines.append(f"  - {raw_error}")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose demiurge-arm benchmark failures.")
    parser.add_argument("--results", action="append", required=True, type=Path, help="Path to a results.json. Repeatable.")
    parser.add_argument("--output", required=True, type=Path, help="Path to write diagnosis_brief.md")
    parser.add_argument("--json", type=Path, help="Optional path to write diagnosis.json")
    args = parser.parse_args(argv)

    failing_tasks: list[dict[str, Any]] = []
    total_tasks = 0
    for results_path in args.results:
        if not results_path.is_file():
            raise FileNotFoundError(f"results file not found: {results_path}")
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        total_tasks += len(payload.get("demiurge_tasks", []))
        failing_tasks.extend(load_failing_tasks(results_path))

    clusters = cluster_failures(failing_tasks)
    sources = [str(p) for p in args.results]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_brief(sources, total_tasks, clusters), encoding="utf-8")
    print(f"Diagnosis brief written to: {args.output}")

    if args.json:
        diagnosis_payload = {
            "format": FORMAT,
            "sources": sources,
            "total_demiurge_tasks": total_tasks,
            "failing_demiurge_tasks": sum(c["count"] for c in clusters),
            "clusters": clusters,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(diagnosis_payload, indent=2) + "\n", encoding="utf-8")
        print(f"Diagnosis JSON written to: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
