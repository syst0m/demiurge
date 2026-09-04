# PROVENANCE — finding-events

```yaml
skill: finding-events
created: 2026-09-04
generated_by: marcus@2.0.0
trust_tier: T2                # T2 until G5 passes; T2 is not installed on merit
gate_reached: G4 (G0 waived by the user, G1/G5 not run)
baseline_score: null
treated_score: null
delta: null
model_harness_pair: null
```

## G0 — evidence of need, stated honestly

**This build would be refused by G0 as written.** The user specified the skill directly, with
example inputs — *London, this weekend, film-making, neurodivergent, dating* — rather than three
recorded failures. A direct instruction from the user is a legitimate reason to build; it is not
the same thing as evidence the skill will help, and the two should not be blurred.

What stands in for the missing failures: the regression cases encode the **documented failure modes
of this task class** rather than imagined ones — stale listings presented as current, directory
pages presented as events, venue accessibility copy repeated as confirmed, relative dates resolved
wrongly, and injected instructions inside listings. These are real failure modes; they are not this
user's observed failures.

**Replace them as real failures occur.** A regression case drawn from something that actually went
wrong is worth more than all six of these, and the suite only becomes load-bearing once it contains
some.

## Why a script is bundled

One script, justified against the finding that script-bundling skills are 2.12× more likely to
carry a vulnerability.

`scripts/plan_queries.py` owns relative-date resolution and query construction. Date arithmetic is
the fragile step: "this weekend" asked on a Sunday, "next weekend" asked on a Friday, and "this
week" asked on a Saturday all have answers people disagree about, and a wrong window sends the
entire search at the wrong dates with nothing downstream noticing. Low degrees of freedom is the
correct setting for that, so it is a script that prints its reasoning and flags phrases it does not
understand.

Stdlib only. No network, no writes, no reads outside its own arguments.

## Verification run

- `validate_skill.py` (G4): passing — see below for the current count
- Date-resolution edge cases checked by hand across a Wednesday, a Saturday and a Sunday, plus an
  unparseable phrase, which correctly refuses rather than guessing
- `eval_runner.py` (G1/G5): **not run.** Requires paid model calls

## What has not been verified

- **No measured delta.** Trust tier stays **T2**. The skill has not been shown to beat a plain agent
  with web search, and that comparison is the point of G5.
- **The claim worth testing is precision after vetting, not recall.** A plain agent finds plenty of
  events. Whether the vetting step makes the presented shortlist meaningfully more reliable is
  unmeasured.
- **`references/sources.md` is a map, not a verified directory.** Platform names are starting points
  for queries. They were not individually checked, and the file says so.
- The neurodivergent-suitability heuristics — capped numbers, stated end time, seated, activity-led,
  somewhere to withdraw to — are reasoning about what makes an event tolerable, not findings from
  a study. Treat them as the author's judgement, which is what they are.

## Trifecta position

- **Private data:** low — location, interests and access needs, in-session only, never persisted
- **Untrusted content:** **yes** — every search result and event page
- **Exfiltration vector:** **none** — no writes, sends, form submissions or bookings

Two of three. The read-only action surface is what keeps the third leg absent, and it is the whole
safety argument for this skill. **Adding booking, messaging or calendar-write capability completes
the trifecta.** If that is ever wanted, split the session per `HARNESS.md` rather than adding the
capability in place.
