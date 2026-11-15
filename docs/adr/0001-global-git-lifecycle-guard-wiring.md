# ADR-0001: Wire git-lifecycle-guard globally into Hermes, Claude Code, Antigravity

## Context

The `git-lifecycle-guard` skill (T2) provides `check` (read-only audit) and `cleanup` (sign-off-gated deletion) for git branches and worktrees. G0–G4 complete; G5 pending operator `--yes`; G6 passed.

Marcus Rule G-13 recommends **Staging** for T2 skills and **refuses Global** below T1. Staging means the canonical source is the only copy — nothing is written to any harness. The operator has asked to wire `check` globally into all three harnesses (Hermes, Claude Code, Antigravity) so the audit blocks git changes everywhere, not just in repos where it's manually added.

## Decision

Wire `git-lifecycle-guard check` globally into Hermes, Claude Code, and Antigravity, overriding Rule G-13's Staging recommendation for T2. The skill itself remains at Staging (no install); the wiring adds `check` to each harness's pre-commit / pre-push / CI equivalent so stale branches and worktrees surface before work proceeds.

## Alternatives considered

**Staging only (per G-13).** Operator copies the script into each repo and wires `check` manually. Safe, compliant, but requires per-repo action across 25+ repos. High drift risk.

**Per-repo opt-in.** `check` added to each repo's pre-commit individually. Same drift risk as Staging; no global guarantee.

**Global with `--i-know`.** `install_skill.py --scope global --i-know` would write hooks globally. Refused for T2 by Rule G-13; skill has no `settings.fragment.json` hooks anyway, so global install adds nothing.

## Consequences

### Positive

- `check` runs in every harness session; stale branches/worktrees surface consistently across all 25+ repos.
- Single script source; harness configs call the same `scripts/git-lifecycle-guard.py`.

### Negative

- **Blocks git changes when rules fail.** A false positive halts work until sign-off or exclusion is added.
- **Bot merges.** 41 bot merges/week (week 44) can't give written `yes`. Cleanup must either skip bot-merged branches or require a bot sign-off policy.
- **Exclusions needed.** `.worktrees/ds-audit` (demiurge) is a live session's worktree and must never be deleted. Global wiring needs an exclusion mechanism.
- **20+ uncounted repos.** Opt-in vs opt-out decision pending (grill question 5).

### Open (needs grill answer)

- Trigger event: pre-commit, pre-push, CI, or manual?
- Escape hatch for false positives?
- Sign-off authority for unmerged branches?
- Opt-in or opt-out for the 20+ uncounted repos?
