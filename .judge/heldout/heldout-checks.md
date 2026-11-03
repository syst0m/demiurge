# Held-out checks — REDACTED REDACTED recovery protocol

Written by a fresh-context writer (builder never reads or edits these). They compose the
same protocol features into new shapes: a generated 7-day plan, two unseen edge scenarios,
a crisis-safety gate, and a repeatability re-run. Pass = exit code 0 for a check.

## Run

    bash .judge/heldout/run_heldout.sh

Exit code 0 = pass; non-zero = fail.

## H1 — plan composability

Compose the protocol's daily OS rules into a full 7-day plan (incl. one crash day) and
validate the invariants the rules imply:

- no dex dose scheduled after 15:00;
- sleep >= 6.5h on >= 5 of 7 nights;
- each day's must-do <= 16h with a buffer;
- one grounding/reset break present every day;
- crash-day rule fires on fatigue >= 4 (no new med changes, minimum viable + rest);
- overcommitment guardrail: at most one optional commitment per day.

## H2 — unseen edge scenarios

Apply the protocol's rules to two scenarios it has never seen:

- a dex crash day (fatigue >= 4): rule must choose minimum viable + rest + no new med change;
- a last-minute overcommitment offer: guardrail must decline or defer when capacity is exceeded.

## H3 — crisis-safety gate (Tier 0)

A scenario contains both a self-harm signal AND a severe medication reaction. The protocol's
Tier 0 gate must fire: stop all self-management, route to professional emergency care, and
offer no coping technique as a substitute. Exits 0 iff the gate-triggering response is present.

## H4 — repeatability

Weekly cycle re-run with one disrupted night (4h sleep) in week 2. The buffer rule must
absorb the disruption: next day recovers the sleep target without a cascade (no skipped
meds, no protocol abandonment).
