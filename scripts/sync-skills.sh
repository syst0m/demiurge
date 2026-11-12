#!/bin/bash
# Deploys the canonical skills in this repo to where each harness loads them:
# ~/.claude/skills (Claude Code), ~/.gemini/config/skills (Antigravity), ~/.config/opencode/skills (OpenCode).
# Antigravity's global skill library is ~/.gemini/config/skills; check_harness_parity.py checks that path.
#
# The repo is the source of truth. ~/.claude/skills/ is a deployment target —
# never edit there; the next sync overwrites it. Where that path is a link into
# agent-skills (the current setup), a sync writes into agent-skills. Check the
# target with --check before a full run.
#
# Windows symlinks need Developer Mode and fail silently otherwise, hence a copy.
#
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

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_SKILLS="$ROOT/skills"
PRIMARY_TARGET="${HOME}/.claude/skills"
# Every harness that loads skills gets the same copy. The primary target is always deployed to;
# the others only when that harness's home already exists, so a machine without OpenCode or
# Antigravity is not given empty config directories. A target that resolves to the same
# directory as an earlier one (a symlinked library) is skipped.
TARGETS=("$PRIMARY_TARGET")
for extra in "${HOME}/.gemini/config/skills" "${HOME}/.config/opencode/skills"; do
    [ -d "$(dirname "$extra")" ] || continue
    dup=false
    for have in "${TARGETS[@]}"; do
        if [ -d "$have" ] && [ -d "$extra" ] && [ "$(cd -P "$have" && pwd)" = "$(cd -P "$extra" && pwd)" ]; then
            dup=true
        fi
    done
    $dup || TARGETS+=("$extra")
done
CHECK_ONLY=false
REPO_ONLY=false

usage() {
    echo "Usage: $0 [--check] [--repo-only]" >&2
}

for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=true ;;
        --repo-only) REPO_ONLY=true ;;
        *)
            echo "ERROR: unknown argument: $arg" >&2
            usage
            exit 2
            ;;
    esac
done

drift=0

# Eval outputs that eval_runner.py writes into a deployed skill. They are preserved across a
# deploy and never count as uncommitted work in the target.
EVAL_OUTPUT_EXCLUDES=(
    ':(exclude,glob)evals/results-*.json'
    ':(exclude,glob)evals/transcripts-*.json'
    ':(exclude,glob)evals/last_run.json'
)

# True when a deploy target sits in a git working tree with uncommitted changes other than eval outputs.
dirty_target() {
    git -C "$1" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        && [ -n "$(git -C "$1" status --porcelain -- . "${EVAL_OUTPUT_EXCLUDES[@]}" 2>/dev/null)" ]
}

# RESEARCH.md is written by Niccolo and consumed by Marcus. It lives canonically
# in research/ so there is exactly ONE writable copy; Marcus receives it as a skill
# reference. Distributed BEFORE the comparison below, so a stale copy surfaces as
# drift rather than shipping silently.
RESEARCH_SRC="$ROOT/research/RESEARCH.md"
MARCUS_REF="$REPO_SKILLS/marcus/references/RESEARCH.md"
if [ -f "$RESEARCH_SRC" ] && [ -d "$(dirname "$MARCUS_REF")" ]; then
    if ! cmp -s "$RESEARCH_SRC" "$MARCUS_REF"; then
        if $CHECK_ONLY; then
            echo "DRIFT    research/RESEARCH.md -> marcus/references/ (not distributed)"
            drift=1
        else
            cp "$RESEARCH_SRC" "$MARCUS_REF"
            echo "DISTRIB  research/RESEARCH.md -> marcus/references/"
        fi
    fi
fi

# Grades in RESEARCH.md must match research/sources.yaml, and Marcus's compiled
# claims.json must match both. grade_cap.py --check writes nothing.
GRADE_CAP="$ROOT/scripts/research/grade_cap.py"
grade_cap_failed=false
if $REPO_ONLY && [ -f "$GRADE_CAP" ]; then
    PY="${PYTHON:-}"
    if [ -z "$PY" ]; then
        PY=$(command -v python || command -v python3 || true)
    fi
    if [ -z "$PY" ]; then
        echo "FAIL     grade_cap --check: python not found (set PYTHON)"
        grade_cap_failed=true
    elif grade_out="$(cd "$ROOT" && "$PY" scripts/research/grade_cap.py --check --repo . 2>&1)"; then
        echo "CHECKED  grade_cap: $(printf '%s\n' "$grade_out" | tail -n 1)"
    else
        printf '%s\n' "$grade_out" | sed 's/^/         /'
        echo "FAIL     grade_cap --check (fix research/, then run grade_cap.py --write)"
        grade_cap_failed=true
    fi
fi

# Pre-flight before any write to a deploy target: refuse the whole deploy, across every target,
# when any target it would replace has uncommitted work, so a refusal never leaves a library
# half-deployed.
if ! $CHECK_ONLY && ! $REPO_ONLY; then
    refused=0
    for TARGET in "${TARGETS[@]}"; do
        [ -d "$TARGET" ] || continue
        for skill_dir in "$REPO_SKILLS"/*/; do
            [ -d "$skill_dir" ] || continue
            name=$(basename "$skill_dir")
            [ -d "$TARGET/$name" ] || continue
            # An in-sync target is never replaced, so only a drifted one can lose work.
            diff -rq "$skill_dir" "$TARGET/$name" >/dev/null 2>&1 && continue
            if dirty_target "$TARGET/$name"; then
                echo "REFUSE   $name: uncommitted changes in target working tree ($TARGET)"
                refused=1
            fi
        done
    done
    if [ "$refused" -ne 0 ]; then
        echo "Nothing was written. Commit or discard those changes, then re-run."
        exit 3
    fi
fi

$REPO_ONLY && TARGETS=()

for TARGET in "${TARGETS[@]}"; do
for skill_dir in "$REPO_SKILLS"/*/; do
    [ -d "$skill_dir" ] || continue
    name=$(basename "$skill_dir")
    sfx=""
    [ "$TARGET" = "$PRIMARY_TARGET" ] || sfx="  @ $TARGET"

    if [ ! -d "$TARGET/$name" ]; then
        echo "NEW      $name (not yet deployed)$sfx"
        drift=1
        $CHECK_ONLY && continue
        mkdir -p "$TARGET/$name"
    elif ! diff -rq "$skill_dir" "$TARGET/$name" >/dev/null 2>&1; then
        echo "DRIFT    $name$sfx"
        diff -rq "$skill_dir" "$TARGET/$name" 2>&1 | sed 's/^/         /' || true
        drift=1
    else
        echo "IN SYNC  $name$sfx"
        continue
    fi

    if ! $CHECK_ONLY; then
        # Preserve local evaluation artifacts (results, transcripts) across directory replacement.
        preserved=$(mktemp -d)
        if [ -d "$TARGET/$name/evals" ]; then
            find "$TARGET/$name/evals" -maxdepth 1 -type f \( -name 'results-*.json' -o -name 'transcripts-*.json' -o -name 'last_run.json' \) -exec cp {} "$preserved/" \; 2>/dev/null || true
        fi
        if [ -d "$TARGET/$name" ]; then
            echo "TARGET   $name -> $(cd -P "$TARGET/$name" && pwd)"
        fi
        rm -rf "${TARGET:?}/$name"
        cp -r "$skill_dir" "$TARGET/$name"
        if [ -n "$(ls -A "$preserved" 2>/dev/null)" ]; then
            mkdir -p "$TARGET/$name/evals"
            cp "$preserved"/* "$TARGET/$name/evals/" 2>/dev/null || true
            echo "PRESERVE $name eval outputs ($(ls -1 "$preserved" | wc -l) file(s))"
        fi
        rm -rf "$preserved"
        echo "SYNCED   $name$sfx"
    fi
done
done

if $grade_cap_failed; then
    exit 1
fi

if $CHECK_ONLY && [ "$drift" -ne 0 ]; then
    echo ""
    echo "Drift detected. Deploying (./scripts/sync-skills.sh with no flags) writes to the installed"
    echo "skills and is the user's step; agents run only --check --repo-only."
    exit 1
fi

exit 0
