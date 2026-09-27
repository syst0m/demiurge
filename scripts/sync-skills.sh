#!/bin/bash
# Deploys the canonical skills in this repo to where Claude Code loads them.
#
# The repo is the source of truth. ~/.claude/skills/ is a deployment target —
# never edit there; the next sync overwrites it.
#
# Windows symlinks need Developer Mode and fail silently otherwise, hence a copy.
#
# Usage:  ./scripts/sync-skills.sh [--check] [--repo-only]
#   (no flags)   apply: distribute RESEARCH.md, then deploy every skill
#   --check      report drift, write nothing (exit 1 if drift)
#   --repo-only  touch only the in-repo RESEARCH.md distribution, never the deploy target,
#                and run scripts/research/grade_cap.py --check (a failure exits 1)
# Exit codes: 0 ok, 1 drift (--check) or grade_cap failure, 2 usage error, 3 refused (dirty target)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_SKILLS="$ROOT/skills"
TARGET="${HOME}/.claude/skills"
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

# RESEARCH.md is written by Buckminster and consumed by Marcus. It lives canonically
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
    elif grade_out=$("$PY" "$GRADE_CAP" --check --repo "$ROOT" 2>&1); then
        echo "CHECKED  grade_cap: $(printf '%s\n' "$grade_out" | tail -n 1)"
    else
        printf '%s\n' "$grade_out" | sed 's/^/         /'
        echo "FAIL     grade_cap --check (fix research/, then run grade_cap.py --write)"
        grade_cap_failed=true
    fi
fi

for skill_dir in "$REPO_SKILLS"/*/; do
    $REPO_ONLY && break
    [ -d "$skill_dir" ] || continue
    name=$(basename "$skill_dir")

    if [ ! -d "$TARGET/$name" ]; then
        echo "NEW      $name (not yet deployed)"
        drift=1
        $CHECK_ONLY && continue
        mkdir -p "$TARGET/$name"
    elif ! diff -rq "$skill_dir" "$TARGET/$name" >/dev/null 2>&1; then
        echo "DRIFT    $name"
        diff -rq "$skill_dir" "$TARGET/$name" 2>&1 | sed 's/^/         /' || true
        drift=1
    else
        echo "IN SYNC  $name"
        continue
    fi

    if ! $CHECK_ONLY; then
        # Preserve local evaluation artifacts (results, transcripts) across directory replacement.
        preserved=$(mktemp -d)
        if [ -d "$TARGET/$name/evals" ]; then
            find "$TARGET/$name/evals" -maxdepth 1 -type f                 \( -name 'results-*.json' -o -name 'transcripts-*.json' -o -name 'last_run.json' \)                 -exec cp {} "$preserved/" \; 2>/dev/null || true
        fi
        if [ -d "$TARGET/$name" ]; then
            if git -C "$TARGET/$name" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
                && [ -n "$(git -C "$TARGET/$name" status --porcelain -- . 2>/dev/null)" ]; then
                rm -rf "$preserved"
                echo "REFUSE   $name: uncommitted changes in target working tree"
                exit 3
            fi
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
        echo "SYNCED   $name"
    fi
done

if $grade_cap_failed; then
    exit 1
fi

if $CHECK_ONLY && [ "$drift" -ne 0 ]; then
    echo ""
    echo "Drift detected. Run ./scripts/sync-skills.sh to apply."
    exit 1
fi

exit 0
