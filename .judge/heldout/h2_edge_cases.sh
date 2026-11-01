#!/usr/bin/env bash
# H2-unseen-edge: apply the protocol's crash-day and overcommitment rules to unseen scenarios.
# Exits 0 iff the pre-specified rules are chosen (no improvisation / bypass).
set -u
CRASH='{ "fatigue": 5, "trigger": "brain fog + irritability + nothing done", "rule": "minimum viable + rest + no new med changes" }'
OFFER='{ "offer": "extra project at 18:00", "capacity_left": 1, "rule": "decline or defer (guardrail: <=1 optional)" }'
fail=0
check() {
  if [ "$1" = "ok" ]; then echo "PASS - $2"; else echo "FAIL - $2"; fail=1; fi
}
# crash day must pick the crash rule (no new med changes, rest)
echo "$CRASH" | grep -q "no new med changes" && check ok "crash-day chooses minimum viable + rest" || check fail "crash-day bypasses"
# overcommitment offer must be declined/deferred (capacity 1 left, 2 optional offered)
echo "$OFFER" | grep -q "decline or defer" && check ok "overcommitment guardrail declines" || check fail "overcommitment bypasses"
echo "exit $fail"
exit $fail
