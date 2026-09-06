#!/bin/bash
# Deploys the canonical skills in this repo to where Claude Code loads them.
#
# The repo is the source of truth. ~/.claude/skills/ is a deployment target —
# never edit there; the next sync overwrites it.
#
# Windows symlinks need Developer Mode and fail silently otherwise, hence a copy.
#
# Usage:  ./scripts/sync-skills.sh          apply
#         ./scripts/sync-skills.sh --check  report drift, write nothing (exit 1 if drift)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_SKILLS="$ROOT/skills"
TARGET="${HOME}/.claude/skills"
CHECK_ONLY=false
[ "${1:-}" = "--check" ] && CHECK_ONLY=true

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

for skill_dir in "$REPO_SKILLS"/*/; do
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
            find "$TARGET/$name/evals" -maxdepth 1 -type f                 \( -name 'results-*.json' -o -name 'transcripts-*.json' \)                 -exec cp {} "$preserved/" \; 2>/dev/null || true
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

if $CHECK_ONLY && [ "$drift" -ne 0 ]; then
    echo ""
    echo "Drift detected. Run ./scripts/sync-skills.sh to apply."
    exit 1
fi

exit 0
