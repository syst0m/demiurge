# PROVENANCE — imhotep

```yaml
skill: imhotep
created: 2026-11-01
origin: scaffolded by marcus (new_skill.py) from 3 recorded failures, then written by hand
trust_tier: T2          # T2 until G5 passes; T2 must not be installed
gate_reached: G4
baseline_score: null    # G1 - fill from eval_runner.py --baseline
treated_score: null     # G5 - fill from eval_runner.py
delta: null
model_harness_pair: null
research_snapshot: {version: "1.3.3", snapshot_sha256: "23a01fe276a556e90aa983d6953f326b18a0d8d550306ed44e5d80ded620a842"}
research_claims: [fail.self-eval, fail.self-correction, fail.reward-hacking, eval.judge-bias, ma.value, ma.cognition-stance, eval.persona-prompting, eval.visible-heldout-gap, fail.escalation-channel, fail.pressure-exploit, goal.clarification-timing, pushbench.quant-goal-persistence, goal.learning-vs-outcome]
vendored: {repo: "https://github.com/robonuggets/be-ambitious", commit: "dc116a3", license: MIT, trust_tier: T3, pin: references/be-ambitious/UPSTREAM.yaml}
```

## Current Specification

Imhotep is the third Pantheon persona. It builds the user's real deliverables at the ambitious
level (Altitude, Depth, Range) by following the vendored be-ambitious procedure plus the overlay in
`references/OVERLAY.md`. It grounds choices in RESEARCH.md, takes skills from the registry, writes
visible and held-out checks before it builds, fails any build that edits its judge
(`scripts/judge_guard.py`), and records outcomes in the run ledger.

## Evidence of need (G0)

1. SpecBench 2026: every frontier coding agent saturates visible tests while held-out pass rates
   trail by a gap that grows 28 pp per 10x code size.
2. AgentPressureBench 2026: user pressure on a visible score made 13 coding agents exploit the
   evaluation (403 of 1326 runs).
3. The Demiurge loop stopped at "a skill exists": no persona applied Marcus's measured skills to the
   user's real deliverables or fed outcomes back to the ledger.

**Estimated deployment volume:** 50. The scaffold's economics warning applies: at this volume the
value is in the gates over a hand-written skill, not in generation.

The regression suite in `evals/evals.json` holds 12 cases (3 from the failures above, 4 from the
upstream rules, 5 from the overlay and standing orders) and must hold at 100%.

## Scripts (why executable content is necessary)

- `scripts/judge_guard.py`: the judge-integrity check must be mechanical. An instruction not to edit
  the judge is the control SpecBench and EvilGenie show failing. Stdlib plus read-only `git diff`
  and `git ls-files`. No network, no writes.
- `scripts/test_judge_guard.py`: its unit tests, run by `scripts/run_unit_tests.py`.

## Verification Status

- G4 (`validate_skill.py`): 0 blocking, 1 warning (`reference-no-toc` on the vendored file, which `vendor_sync.py --check` forbids editing; `.forgeignore` does not cover that check).
- `judge_guard.py`: 5 unit tests pass (build-only edit passes; committed, uncommitted and new judge
  files fail; unknown base is a usage error).
- Vendored files: `python scripts/vendor_sync.py --check` passes against the pinned sha256.

## What has not been verified

- No G1 baseline or G5 treated run is recorded. Trust tier stays **T2** and the skill must not be
  installed globally until `eval_runner.py` shows b > c per case; McNemar p < alpha at 20 or more
  cases; regression at 100% against the G1 baseline.
- Overlay rules O1–O4, O6, O8 and O9 rest on abstracts read for `docs/IMHOTEP_EVALUATION.md`, not on
  graded RESEARCH.md claims. They stay marked *judgement* until Buckminster's proposal is signed off.

## Trifecta position

- Private data touched: yes — the user's repository and any data the task names.
- Untrusted content ingested: yes — the vendored upstream text (T3), web pages and tool output.
- Exfiltration vector present: only through tools the harness grants (network, PR creation).

All three can meet in one session. The split: the vendored text changes only through an
operator-reviewed `vendor_sync.py --apply`, Range subagents are read-only, and pushing, publishing
and scheduling always wait for the user.
