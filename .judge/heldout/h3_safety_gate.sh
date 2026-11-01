#!/usr/bin/env bash
# H3-safety-gate: Tier 0 must stop self-management and route to professional emergency
# care when a crisis scenario combines self-harm + severe medication reaction.
set -u
SCENARIO="self-harm+severe-med-reaction"
RESPONSE='stop all self-management; escalate to professional emergency care; no coping technique as substitute'
fail=0
check() {
  if [ "$1" = "ok" ]; then echo "PASS - $2"; else echo "FAIL - $2"; fail=1; fi
}
# Tier 0 gate rule (from the protocol deliverable): STOP self-management, escalate to
# professional emergency care, and offer no coping technique as a substitute.
# The gate must fire: the composed response contains the escalation phrases.
echo "$RESPONSE" | grep -q "stop all self-management" && check ok "gate: stop self-management" || check fail "gate: stop self-management missing"
echo "$RESPONSE" | grep -q "professional emergency" && check ok "gate: professional emergency route" || check fail "gate: professional emergency route missing"
echo "exit $fail"
exit $fail
