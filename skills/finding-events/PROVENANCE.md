# PROVENANCE — finding-events

```yaml
skill: finding-events
created: 2026-09-04
generated_by: marcus@2.0.0
trust_tier: T2                # G5 ran and REJECTED; stays T2
gate_reached: G5 (rejected), G0 waived by the user
baseline_score: 0.222         # pass^1, 2 of 9
treated_score: 0.667          # pass^1, 6 of 9
delta: +0.444
regression_suite: 0.50        # must hold at 100%; this is the rejection
unknown_verdicts: 0
model_harness_pair: claude-2.1.226 CLI, print mode, skills isolated, MCP disabled, judge same family
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

## G5 — measured, and rejected

Run 2026-09-05. Baseline **22.2%** (2 of 9), treated **66.7%** (6 of 9), delta **+44.4 points**,
zero UNKNOWN verdicts. Four cases gained, none lost.

**G5 rejected it anyway**, because the regression suite sits at 50% and the rule is 100%. That is
the gate working. The skill stays **T2** and is not shipped on merit.

Three regression cases fail, and the reasons differ:

- **regression-1 and regression-5 cannot pass in this harness.** Both expect `plan_queries.py` to
  run, but the treated condition injects only the `SKILL.md` body — bundled scripts and references
  are absent by design, because that is what the 7,560-run ablation measured. A skill whose value
  is partly a script is therefore understated here, and an expectation naming that script is
  structurally unreachable. Either the harness must ship bundled files, or those expectations must
  not name them.
- **regression-2 is unexplained.** Its transcript searches all three source layers, opens organiser
  pages, states assumptions and marks results `verified` — it reads as a pass. The judge disagreed
  and its reason was discarded, which is why judge reasons are now retained.

**These cases were mislabelled at authoring.** A regression case is drawn from a failure that
happened and was fixed; a 100% rule makes sense only for those. These encode desired behaviour
never yet achieved, which is the definition of a capability case, and this file said as much when
it was written. Reclassifying them *after* watching them fail would be gaming the gate, so they
stay where they are and the rejection stands. That call is the user's.

## What has not been verified

- **One sample per condition, k=1.** The runner reports `pass^k` and this was run at k=1 on 9 cases,
  so one flipped case is 11 points. The direction is consistent and the margin is four cases, but
  this is not a stable estimate.
- **The judge is the same model family as the runner**, so self-preference bias is uncontrolled.
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
