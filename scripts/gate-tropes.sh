#!/usr/bin/env bash
# Scan Markdown for negative parallelism - the "it is not X, it is Y" construction
# and its variants. Based on woerndl/unsloppify and tropes.fyi.
#
# Usage:
#   scripts/gate-tropes.sh                 scan every tracked .md file
#   scripts/gate-tropes.sh FILE [FILE...]  scan the named files (how pre-commit calls it)
#
# Exit 0 clean, 1 if any trope is found.
#
# This file previously held a chat transcript describing the scanner rather than
# the scanner. The working copy had been installed straight into .git/hooks/,
# where it was unversioned and would be displaced by `pre-commit install`. It now
# lives here and runs as a local hook, so it survives that and reaches CI.

set -euo pipefail

TROPE_REGEX="(it is|it's) not .+(,|;|—|-) it( is|'s) |not because .+, but because|(the question|the problem) is not .+\. (the question|the problem) is |isn't just .+(,|;|—|-) it( is|'s) |(is|are) not just .+(,|;|—|-) (it is|it's|they are|they're)"

echo "Scanning for AI tropes (negative parallelism)..."

if [ "$#" -gt 0 ]; then
    files=("$@")
else
    # Standalone or CI: every Markdown file Git knows about, so vendored and
    # ignored trees are skipped without needing a prune list.
    mapfile -t files < <(git ls-files '*.md')
fi

if [ "${#files[@]}" -eq 0 ]; then
    echo "No Markdown files to scan."
    exit 0
fi

if grep -HniE "$TROPE_REGEX" "${files[@]}"; then
    echo ""
    echo "Error: negative parallelism detected in the lines above."
    echo "Rewrite them with plain constructions. State the thing you mean and stop."
    exit 1
fi

echo "No AI tropes detected."
exit 0
