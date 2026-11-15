# PROVENANCE — git-lifecycle-guard

```yaml
skill: git-lifecycle-guard
created: 2026-11-15
trust_tier: T2
gate_reached: G6 (G4 passed, G5 pending operator --yes to spend model calls, G6 passed)
baseline_score: null
treated_score: null
delta: null
model_harness_pair: null
```

## Gate results

| Gate | Result | Notes |
|------|--------|-------|
| G0 Intake | pass | 3 real failures captured; 7 correctness rules defined; volume measured |
| G1 Baseline | pass | Measured with git alone on all 24 repos under ~/Documents/code; failures: alfred R1+R4, demiurge R2, lifeos R2+R4, sans-indexes R4 (6 rule failures total; 20 repos pass) |
| G2 Contrast | pass | Each rule traces to a named outcome difference (cases 01-03) |
| G3 Draft | pass | Minimal script + SKILL.md applying rules by grade |
| G4 Validate | pass | `validate_skill.py` clean: 0 blocking, 0 warnings |
| G5 Prove | pending | `eval_runner.py` is model-based; requires `--yes` + `--runner-model` + `--judge-model` to spend. Not executed — no model tokens spent. Dry-run showed 4 cases x k=3. |
| G6 Register | pass | `route_check.py` distinct vs 3 installed skills (max sim 0.084). Install scope: see below. |

## Evidence of need (Gate G0)

Three real failures (operator attachment, 2026-11-15):

1. **demiurge — stale upstream merge dropped work (case 01).** Branch `fix/audit-findings` merged
   into main in f4e3303 from a stale base; commit 05a18c1 restored work the merge would have lost
   (skills/imhotep/SKILL.md 105 lines, skills/marcus/scripts/eval_runner.py 119 lines,
   skills/marcus/SKILL.md 9 lines). PR 35 conflict fix commit 5af7ef0 touched 5 files
   (781 insertions, 281 deletions); ~2h40m elapsed between restore and conflict fix.
2. **agent-skills — two sessions landed the same UI layer (case 02).** Branch `ds-ui-panel`;
   reconcile commit dcdd02f touched 54 files (1,755 insertions, 2,448 deletions), merged two
   CHANGELOG entries, collapsed a duplicate "Revision 6" in PROVENANCE, left stray screenshots and
   build folders.
3. **alfred — stale deployed copy nearly overwrote lessons (case 03).** Same shape as a stale
   worktree but in ~/.claude/skills/. Commit d56a2e4 rebuilt lessons.md as a union (11 -> 18
   entries); dump-before-delete guard made recovery possible.

Volume (git, ISO weeks 44-46): 15-85 merges to main/week (peak 86 in week 45), 100-130 release
tags/week peak (mostly lifeos), >=20 branches/week (week 46 floor). Five repos counted; 20 more in
Documents/code uncounted.

## Correctness (operator's seven rules)

See `references/rules.md`. Rules 1, 2, 3, 4 are implemented as git-native read-only checks in
`scripts/git-lifecycle-guard.py check`. Rules 5, 6, 7 are documented as advisory / manual-review
checks. Rule 5 runs at merge time; it does not run on a snapshot.

## Baseline (Gate G1) — measured with git alone, nothing changed

| Repo | R1 merged<=7d | R2 worktree clean | R4 unmerged<=14d |
|------|---------------|-------------------|------------------|
| agent-skills | pass | pass | pass |
| alfred | FAIL: 6 merged branches, oldest 2026-06-14 | pass | FAIL: lifeos-v2, research/lookup-fix |
| antigravity-awesome-skills | pass | pass | pass |
| antigravity-sdk-python | pass | pass | pass |
| awesome-mcp-servers | pass | pass | pass |
| capsule-sourcing-db | pass | pass | pass |
| CyberdropBunkrDownloader | pass | pass | pass |
| demiurge | pass | FAIL: scratch/sweep-2026-11-14 no diff from main | pass |
| go-dcpp | pass | pass | pass |
| hermes-agent-tools | pass | pass | pass |
| hermes-browser-extension | pass | pass | pass |
| honcho | pass | pass | pass |
| Hublist | pass | pass | pass |
| jobhunt-cyber-mgr | pass | pass | pass |
| lifeos | pass | FAIL: worktree gamified-kiosk-audhd-8fde34 holds merged branch fix/habit-click-latency | FAIL: claude/global-cleanup-workflow-231905 |
| lifeos-v2 | pass | pass | pass |
| lotophage | pass | pass | pass |
| mangadex-extension | pass | pass | pass |
| pyWars | pass | pass | pass |
| sans-index-creator | pass | pass | pass |
| sans-indexes | pass | pass | FAIL: pr-9 (last commit 2024-05-26) |
| sec573_book_indexer | pass | pass | pass |
| skills | pass | pass | pass |
| tex-course-index-template | pass | pass | pass |

## Trifecta position

- Private data touched: local git repositories (branches, worktrees, refs).
- Untrusted content ingested: branch names and refs from remotes (treated as data; never instructions).
- Exfiltration vector: none — no network calls; writes only to the cleanup log and an opt-in dump dir.
- Two legs present; exfiltration absent → no session split required.

## Write discipline

- `check` is read-only; `cleanup` is a dry-run unless `--apply`, and always requires `--sign-off`.
- Destructive deletes dump first: branch tip SHAs are logged (restorable via `git branch <name> <sha>`);
  worktree removals with uncommitted changes dump dirty status to `--dump-dir` before `--force`.

## Gate status

- G4 `validate_skill.py`: passed — clean, 0 blocking, 0 warnings.
- G5 `eval_runner.py`: pending — model-based; requires operator `--yes` + `--runner-model` + `--judge-model` to spend. No model tokens spent.
- G6 `route_check.py`: passed — description distinct vs 3 installed skills (max sim 0.084).

## Install scope (Gate G6)

Rule G-13: trust tier gates install scope; Marcus never installs a tool-class-blocking hook globally. Operator **overrode** the Staging recommendation to **Global** across all three harnesses.

- Trust tier: **T2** (generated by the factory, not yet G5-accepted).
- Scope: **Global** (operator override; G-13 default Staging overridden explicitly).
- Wiring applied:
  - **pre-push + pre-commit**: `.pre-commit-config.yaml` local hook `git-lifecycle-guard-check` runs `check --repos .` on every push/commit in demiurge (hard block on non-zero exit).
  - **Claude Code**: `.claude/settings.json` `PreToolUse` hook on `Bash|PowerShell|Write` runs `check --repos .` (hard block, no `|| true`).
  - **Antigravity**: `.agents/hooks.json` `PreToolUse` hook on `run_command|write_to_file` runs `check --repos .` (hard block).
  - **Hermes**: `skills/git-lifecycle-guard/hermes-plugin/plugin.yaml` registers `git-lifecycle-guard-check` command; documented in `docs/OPERATING_GUIDE.md` Gotcha 9 (Hermes has no native git hook; manual invocation).
- Scope coverage: all 24 repos under `~/Documents/code` (baseline measured on all; 4 repos with 6 rule failures).
- Escape hatch: `GIT_LIFECYCLE_SKIP=1` bypasses all rules and exits 0.
- Exclusions: `skills/git-lifecycle-guard/exclusions.json` lists `ds-audit` worktree (never deleted by cleanup; `check` still reports it).

G5 `eval_runner.py`: pending — model-based; requires operator `--yes` + `--runner-model` + `--judge-model` to spend. No model tokens spent.
