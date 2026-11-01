#!/usr/bin/env bash
# HELD-OUT RUNNER - runs the fresh-context held-out checks.
# Exit 0 = all checks pass; non-zero = at least one fails.
set -u
cd "$(dirname "$0")"
overall=0
for f in h1_plan.py h2_edge_cases.sh h3_safety_gate.sh h4_repeatability.sh; do
  echo "===== $f ====="
  if [[ "$f" == *.py ]]; then python3 "$f"; else bash "$f"; fi
  if [ $? -ne 0 ]; then overall=1; fi
done
echo "held-out overall exit: $overall"
exit $overall
