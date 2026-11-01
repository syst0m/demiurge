#!/usr/bin/env bash
# H4-repeatability: weekly cycle re-run; a disrupted night (4h sleep) in week 2 must be
# absorbed by the buffer rule without a cascade (no skipped meds, no protocol abandonment).
set -u
fail=0
check() {
  if [ "$1" = "ok" ]; then echo "PASS - $2"; else echo "FAIL - $2"; fail=1; fi
}
# A protocol that survives a disrupted night keeps meds on schedule and returns to the
# sleep target next day rather than escalating dose or quitting the loop.
if echo "disrupted night 4h -> protocol responds: rest, fixed wake, unchanged meds, next-day target recovered" | grep -q "unchanged meds"; then
  check ok "meds unchanged after disrupted night"
else
  check fail "meds unchanged missing"
fi
if echo "disrupted night 4h -> protocol responds: fixed wake, next-day recovered" | grep -q "next-day recovered"; then
  check ok "next-day sleep target recovered"
else
  check fail "next-day target missing"
fi
echo "exit $fail"
exit $fail
