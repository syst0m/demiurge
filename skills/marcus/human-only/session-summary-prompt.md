# Session Summary — Failures and Fixes

**Prompt for Marcus:** Review the following session log and extract the key failures, their root causes, and the corrective actions taken. Format as a structured report suitable for the run ledger.

## Failures

1. **Skill invocation drift — `/buckminster` and `/marcus` became unresponsive**
   - *Root cause:* Installed skill versions in Hermes drifted from the repo checkout. `check_harness_parity.py` reported `STALE` for both skills across `claude-code`, `antigravity`, and `.agents` harnesses.
   - *Corrective action:* Ran `bash scripts/sync-skills.sh` to sync repo → installed locations. Removed duplicate `claude-code-imports/{buckminster,marcus}` that conflicted with `agent-skills/{buckminster,marcus}` from the demiurge repo. Harness parity now reports `OK` for all skills.

2. **Failed to enforce release gate on repo changes**
   - *Root cause:* Per standing order #1, the GitHub minutes gate must be checked before any release action. The gate logic is: if GitHub Actions minutes are **exhausted** on the free tier, switch to `LOCAL` mode and run `python scripts/verify_release.py --cut` to tag, push, and verify the release; otherwise (minutes are still available on the free tier), open the PR and let Actions run. No release verification (`verify_release.py --cut`) was performed after modifying `research/sources.yaml`, `research/RESEARCH.md`, or skill files.
   - *Corrective action:* Acknowledge the gate was skipped. Next release should determine mode: if minutes exhausted → run `verify_release.py --cut` in LOCAL mode; if minutes available → open PR and let Actions run.

3. **Duplicate skill collision in Hermes**
   - *Root cause:* Two skills named `marcus` and two named `buckminster` existed at the same tier across Hermes' skill directories (`agent-skills/` vs `claude-code-imports/`). Both pairs had `name: <skill>` and overlapping descriptor text, causing Hermes to refuse to guess which to activate on `/<skill>`.
   - *Corrective action:* Removed `claude-code-imports/{buckminster,marcus}`. Retained the demiurge repo versions at `agent-skills/{buckminster,marcus}`. Verified `check_harness_parity.py` now reports `OK` for all skills under both `claude-code` and `antigravity` harnesses.

4. **GitHub gate logic not properly implemented**
   - *Root cause:* The gate check `python scripts/gh_minutes_gate.py --status` returned `GITHUB: public repo: Actions minutes are free [live]`, but the standing order specifies the gate should switch to `LOCAL` mode when minutes are **exhausted**, not when they're merely "free". If minutes are exhausted, the LOCAL release workflow (`verify_release.py --cut`) should fire, but it did not execute in this session.
   - *Corrective action:* Marcus should verify the gate logic: run `python scripts/gh_minutes_gate.py --status` and confirm the mode selection. If minutes are exhausted, ensure `verify_release.py --cut` is run in LOCAL mode. If minutes are available, PR-based release via Actions is the correct path.

5. **Local release workflow didn't fire when GitHub minutes were exhausted**
   - *Root cause:* When GitHub Actions minutes are exhausted on the free tier, the system should automatically switch to LOCAL mode and execute `python scripts/verify_release.py --cut` to tag, push, and verify the release. This local workflow did not fire in this session, possibly because the gate check returned `GITHUB` mode (minutes are free) rather than `LOCAL` mode (minutes exhausted), or because the standing order enforcement hook was not triggered.
   - *Corrective action:* Marcus should investigate the gate output and mode selection: if `gh_minutes_gate.py --status` indicates minutes are exhausted, the correct path is `LOCAL` mode with `verify_release.py --cut`; if minutes are free, the PR-based release via Actions is correct. Verify the conditional logic in the standing orders and ensure the appropriate mode is selected for the release workflow.

## Changes Made

| File | Change |
|------|--------|
| `research/sources.yaml` | Added claim `disc.felix-rieseberg` (Section 12) with 5 sources from felixrieseberg.com |
| `research/RESEARCH.md` | Added claim anchor `<!-- claim:disc.felix-rieseberg -->` before `goal.learning-vs-outcome` |
| `skills/buckminster/SKILL.md` | Updated via `sync-skills.sh` (no content change) |
| `skills/marcus/SKILL.md` | Updated via `sync-skills.sh` (no content change) |
| `research/sources.yaml` | Felix Rieseberg sources graded `[EMERGING]` with 4 debt reasons (lt3_independent, lt2_primary, independence_unset, unretrieved_source) |

## Verification

- `check_harness_parity.py`: `OK` for `buckminster`, `imhotep`, `marcus` under `claude-code` and `antigravity`
- `grade_cap.py --check`: `OK: 72 claims, 75 grades, caps current (enforced=false)`
- `python scripts/gh_minutes_gate.py --status`: `GITHUB: public repo: Actions minutes are free [live]`
