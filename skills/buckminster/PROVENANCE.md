# PROVENANCE — buckminster

```yaml
skill: buckminster
created: 2026-08-30
trust_tier: T2
gate_reached: G4
baseline_score: null
treated_score: null
delta: null
model_harness_pair: null
research_claims: []
```

## Current Specification

Buckminster researches agentic engineering and proposes graded changes to `research/RESEARCH.md`
and `research/sources.yaml` as a diff for the user to approve. It maintains the snapshot Marcus
builds from, so it records no `research_snapshot` of its own and cites no claims.

## Evidence of Need (Gate G0)

The regression suite in `evals/evals.json` holds 12 cases, which must hold at 100%:

- 5 come from the anti-patterns in `references/RESEARCH_METHODOLOGY.md` §5.
- 3 come from the skill's non-negotiables.
- 1 comes from a path-resolution failure when the skill ran outside the repository root.
- 3 come from the claims ledger workflow: debt first, no fabricated source, worktree only.

## Verification Status

G4 (`validate_skill.py`) reports 0 blocking findings.

## What Has Not Been Verified

No G1 baseline or G5 treated run is recorded. The trust tier stays **T2** until `eval_runner.py`
shows a positive delta over a recorded baseline.

## Trifecta Position

- **Private data touched:** the demiurge checkout named by `$DEMIURGE_REPO`.
- **Untrusted content ingested:** papers, web pages and search results. The skill treats them as
  data, never instructions.
- **Exfiltration vector:** outbound search queries. Proposals reach `RESEARCH.md` only after the
  user approves the diff, and scheduled runs write only to a dedicated worktree branch.
