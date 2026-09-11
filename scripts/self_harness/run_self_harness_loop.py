#!/usr/bin/env python3
"""Resumable orchestrator for the self-harness loop: diagnose, propose, materialize, gate.

This is a state machine, not a fully automatic loop. The proposal step needs a human
or Marcus turn inside a supervised session (docs/INSTALLATION.md §5: Marcus stays
fully offline and deterministic, so this script never calls a model API on its own).
Each invocation inspects which stage artifacts already exist under --work-dir and
either performs the next deterministic step itself, or prints the exact next manual
command to run. No stage in this script merges, pushes, or opens a pull request.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acceptance_gate import run_acceptance_gate
from diagnose_failures import cluster_failures, load_failing_tasks, render_brief
from materialize_candidate import materialize, slugify
from propose_candidate import build_prompt, parse_surface_args, validate_and_build_bundle

FORMAT = "demiurge.self_harness.loop_state.v0"
REPO_ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def stage_diagnose(work_dir: Path, baseline_results: list[Path]) -> None:
    failing_tasks = []
    total_tasks = 0
    for results_path in baseline_results:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        total_tasks += len(payload.get("demiurge_tasks", []))
        failing_tasks.extend(load_failing_tasks(results_path))

    clusters = cluster_failures(failing_tasks)
    sources = [str(p) for p in baseline_results]
    (work_dir / "diagnosis_brief.md").write_text(render_brief(sources, total_tasks, clusters), encoding="utf-8")
    write_json(
        work_dir / "diagnosis.json",
        {
            "format": "demiurge.self_harness.diagnosis.v0",
            "sources": sources,
            "total_demiurge_tasks": total_tasks,
            "failing_demiurge_tasks": sum(c["count"] for c in clusters),
            "clusters": clusters,
        },
    )
    print(f"[diagnose] wrote {work_dir / 'diagnosis_brief.md'}")
    if not clusters:
        print("[diagnose] no failing demiurge-arm tasks. No-op: stop here.")


def stage_propose_build(work_dir: Path, surfaces: dict[str, Path]) -> None:
    diagnosis = json.loads((work_dir / "diagnosis.json").read_text(encoding="utf-8"))
    prompt = build_prompt(diagnosis, surfaces)
    (work_dir / "proposer_prompt.md").write_text(prompt, encoding="utf-8")
    print(f"[propose] wrote {work_dir / 'proposer_prompt.md'}")
    print(
        "[propose] next: run this prompt inside a supervised Marcus/Claude Code session, save "
        f"its JSON reply to {work_dir / 'proposer_response.json'}, then re-run this command."
    )


def stage_propose_parse(work_dir: Path, surfaces: dict[str, Path]) -> None:
    response = json.loads((work_dir / "proposer_response.json").read_text(encoding="utf-8"))
    bundle = validate_and_build_bundle(response, surfaces)
    write_json(work_dir / "proposal_bundle.json", bundle)
    print(f"[propose] wrote {work_dir / 'proposal_bundle.json'}")


def stage_materialize(work_dir: Path, suite: str) -> None:
    proposal = json.loads((work_dir / "proposal_bundle.json").read_text(encoding="utf-8"))
    candidate_id = slugify(f"{suite}-{proposal['proposal_id']}")
    manifest = materialize(proposal=proposal, repo_root=REPO_ROOT, candidate_id=candidate_id, checkout=True)
    write_json(work_dir / "candidate_manifest.json", manifest)
    print(f"[materialize] candidate branch: {manifest['branch']}")
    print(
        "[materialize] next: run the "
        f"{suite} benchmark suite against this checked-out branch, then save its results.json to "
        f"{work_dir / 'candidate_results.json'}"
    )


def stage_gate(work_dir: Path, baseline_results: list[Path], seed: int) -> None:
    result = run_acceptance_gate(
        baseline_paths=baseline_results,
        candidate_paths=[work_dir / "candidate_results.json"],
        seed=seed,
        splits_cache=work_dir / "splits.json",
    )
    write_json(work_dir / "gate_result.json", result)
    print(f"[gate] {result['decision']}: {result['reason']}")
    if result["accepted"]:
        manifest = json.loads((work_dir / "candidate_manifest.json").read_text(encoding="utf-8"))
        print(f"[gate] next: open a pull request from branch {manifest['branch']} for operator sign-off.")
    else:
        print("[gate] candidate rejected. It stays archived; no branch was merged.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one step of the self-harness loop.")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--surface", action="append", required=True, help="name=path, repeatable.")
    parser.add_argument("--baseline-results", action="append", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    surfaces = parse_surface_args(args.surface)

    write_json(
        work_dir / "loop_state.json",
        {
            "format": FORMAT,
            "suite": args.suite,
            "surfaces": {name: path.as_posix() for name, path in surfaces.items()},
            "baseline_results": [str(p) for p in args.baseline_results],
            "seed": args.seed,
        },
    )

    if not (work_dir / "diagnosis.json").is_file():
        stage_diagnose(work_dir, args.baseline_results)
        return 0
    if not (work_dir / "proposer_prompt.md").is_file():
        stage_propose_build(work_dir, surfaces)
        return 0
    if not (work_dir / "proposer_response.json").is_file():
        print(f"[propose] waiting for {work_dir / 'proposer_response.json'}")
        return 0
    if not (work_dir / "proposal_bundle.json").is_file():
        stage_propose_parse(work_dir, surfaces)
        return 0
    if not (work_dir / "candidate_manifest.json").is_file():
        stage_materialize(work_dir, args.suite)
        return 0
    if not (work_dir / "candidate_results.json").is_file():
        print(f"[materialize] waiting for {work_dir / 'candidate_results.json'}")
        return 0
    if not (work_dir / "gate_result.json").is_file():
        stage_gate(work_dir, args.baseline_results, args.seed)
        return 0

    print("[loop] complete for this candidate. See gate_result.json for the decision.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
