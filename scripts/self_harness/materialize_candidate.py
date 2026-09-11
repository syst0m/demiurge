#!/usr/bin/env python3
"""Materialize a proposal_bundle.json as a single git branch, never a merge.

Enforces one self-harness candidate branch at a time. docs/OPERATING_GUIDE.md
Gotcha 6 documents why: concurrent worktrees risk .git/config.lock contention and
can destroy the primary .git directory. This script never creates a worktree; it
checks out one branch, commits, and (optionally) returns to the branch it started
from. It never pushes, merges, or opens a pull request — that stays a human action.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

FORMAT = "demiurge.self_harness.candidate_manifest.v0"
_SLUG_DISALLOWED = re.compile(r"[^a-z0-9-]+")


def slugify(value: str) -> str:
    slug = _SLUG_DISALLOWED.sub("-", value.strip().lower()).strip("-")
    return slug or "candidate"


def run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def existing_self_harness_branches(repo_root: Path) -> list[str]:
    output = run_git(repo_root, "for-each-ref", "--format=%(refname:short)", "refs/heads/self-harness/*")
    return [line for line in output.splitlines() if line]


def materialize(
    *,
    proposal: dict[str, Any],
    repo_root: Path,
    candidate_id: str,
    checkout: bool,
) -> dict[str, Any]:
    dirty = run_git(repo_root, "status", "--porcelain")
    if dirty:
        raise RuntimeError(
            "refusing to materialize a candidate onto a dirty working tree; commit or stash "
            "existing changes first"
        )

    active_branches = existing_self_harness_branches(repo_root)
    if active_branches:
        raise RuntimeError(
            "refusing to materialize a second candidate while one is already active: "
            f"{active_branches}. Merge or delete it first (one candidate at a time)."
        )

    original_branch = run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    base_commit = run_git(repo_root, "rev-parse", "HEAD")
    branch_name = f"self-harness/{candidate_id}"

    run_git(repo_root, "checkout", "-b", branch_name)
    try:
        surface_path = repo_root / proposal["surface_path"]
        surface_path.parent.mkdir(parents=True, exist_ok=True)
        surface_path.write_text(proposal["value"], encoding="utf-8")

        run_git(repo_root, "add", "--", proposal["surface_path"])
        commit_message = (
            f"self-harness: {proposal['title']}\n\n"
            f"{proposal['summary']}\n\n"
            f"proposal_id: {proposal['proposal_id']}\n"
            f"candidate_id: {candidate_id}\n"
            f"regression_guard: {proposal['regression_guard']}"
        )
        run_git(repo_root, "commit", "-m", commit_message)
        candidate_commit = run_git(repo_root, "rev-parse", "HEAD")
    finally:
        if not checkout:
            run_git(repo_root, "checkout", original_branch)

    manifest = {
        "format": FORMAT,
        "candidate_id": candidate_id,
        "proposal_id": proposal["proposal_id"],
        "branch": branch_name,
        "base_commit": base_commit,
        "candidate_commit": candidate_commit,
        "changed_surface": proposal["surface"],
        "changed_surface_path": proposal["surface_path"],
        "checked_out": checkout,
    }

    manifest_dir = repo_root / "eval_results" / "self_harness" / candidate_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "candidate_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize a self-harness proposal as a git branch.")
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--candidate-id", help="Defaults to a slug of proposal_id.")
    parser.add_argument(
        "--no-checkout",
        action="store_true",
        help="Return to the starting branch after committing, instead of leaving the candidate checked out.",
    )
    args = parser.parse_args(argv)

    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    candidate_id = slugify(args.candidate_id or proposal["proposal_id"])
    repo_root = args.repo_root.resolve()

    manifest = materialize(
        proposal=proposal,
        repo_root=repo_root,
        candidate_id=candidate_id,
        checkout=not args.no_checkout,
    )
    print(f"Candidate materialized on branch: {manifest['branch']}")
    print(f"Manifest: eval_results/self_harness/{candidate_id}/candidate_manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
