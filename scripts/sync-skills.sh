#!/usr/bin/env bash
# Deploys the canonical skills in this repo to where each harness loads them:
# ~/.claude/skills (Claude Code), ~/.agents/skills (Antigravity), ~/.config/opencode/skills (OpenCode).

# The repo is the source of truth. ~/.claude/skills/ is a deployment target —
# never edit there; the next sync overwrites it.

# Usage:  ./scripts/sync-skills.sh [--check] [--repo-only]
#   (no flags)   apply: distribute RESEARCH.md, then deploy every skill
#   --check      report drift, write nothing (exit 1 if drift)
#   --repo-only  touch only the in-repo RESEARCH.md distribution, never the deploy target,
#                and run scripts/research/grade_cap.py --check (a failure exits 1)
# Exit codes: 0 ok, 1 drift (--check) or grade_cap failure, 2 usage error, 3 refused (dirty target)
#
# NOTE: this script no longer writes into agent-skills/skills. That directory is a
# symlinked copy of agent-skills repo skills. Cross-repo writes were the defect in §1.2;
# the new materializer (python scripts/sync_bundles.py) targets each harness's native shape
# instead. Run `./scripts/sync-skills.sh --check` to report drift only; use the Python
# materializer for bundle materialization.
