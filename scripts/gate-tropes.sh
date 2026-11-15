#!/usr/bin/env bash
# Scan Markdown for negative parallelism and the compressed contrast "X, not Y".
# Delegates to gate_tropes.py, which delegates to the i-have-adhd trope_gate.py.
#
# Usage:
#   scripts/gate-tropes.sh                 scan every tracked .md file
#   scripts/gate-tropes.sh FILE [FILE...]  scan the named files (how pre-commit calls it)
#
# Exit 0 clean, 1 if any trope is found.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python "$HERE/gate_tropes.py" "$@"
