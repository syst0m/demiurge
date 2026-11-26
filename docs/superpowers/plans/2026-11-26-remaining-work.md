# Remaining Work After 0.19.0: Plan

**Date:** 2026-11-26
**Status:** Closed on 2026-11-26. Phases 1 to 4 are done. Phase 6 passed as a headless check. Decisions A to D are done. Phase 5 and the interactive check moved to the [open items spec](../specs/2026-11-26-open-items-after-0.19.2-design.md).
**Repos:** `demiurge`, `agent-skills`

## 1. Measured state

| Item | State on 2026-11-26 |
|---|---|
| demiurge | `main` equals `origin/main` at `7120ab6`. The tree was clean before this plan. |
| Release | `v0.19.0` is out. Its tag points to `e0a760d`. |
| CI | The 4 workflows on `7120ab6` passed. |
| agent-skills | `main` equals `origin/main`. 138 paths are uncommitted. |
| Parity | `check_harness_parity.py`: `claude-code` is `OK`. The other harnesses are `SKIPPED` (same directory). |
| Hermes plugin | `sync-hermes-commands.py --check` reports `In sync`. |
| Claude Code Stop hook | The hit log has `stop` entries dated 2026-11-26. |
| Block cap | `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` is `3` in the user settings. |

## 2. The shared skill folders

`demiurge/skills/imhotep`, `marcus` and `niccolo` are links into `agent-skills/skills`. Git in `demiurge` tracks the same paths as normal files (`core.symlinks=false`). One working file therefore has two histories. Both repos track the same file names.

The two histories differ in 12 files. The live skills match the `demiurge` copy.

| Content | Newer copy |
|---|---|
| `RESEARCH.md` v1.3.5, `claims.json`, the `derived_from` line | demiurge |
| "Never say fixed without observed verification" in `marcus/SKILL.md` | demiurge |
| "Pitfalls: running the pipeline" in `marcus/SKILL.md` | agent-skills |
| UTF-8 `encoding` and `errors` arguments in `marcus/scripts/eval_runner.py` | agent-skills |
| Rule 11 wording cleanup in the other prose files | agent-skills |

The live skills lack the Pitfalls section and the encoding fix. Without the fix, `eval_runner.py` can return an empty transcript on Windows. The merge on 2026-11-26 rewrote one of the 12 files, `marcus/SKILL.md`. The other differences are older.

**Hazards.**

- `git checkout`, `git stash`, `git reset` and a branch switch write through the link. Do not run them on these paths before Phase 2 is done.
- `git commit -a` in `agent-skills` would commit the removal of the newer content.

## 3. Open decisions

| ID | Question | Recommendation |
|---|---|---|
| A | Does `demiurge` own `imhotep`, `marcus` and `niccolo`? | Yes. `release.yml` reads these files on a CI checkout that has no `agent-skills`, so `demiurge` must track them. `agent-skills` stops tracking them and keeps the files on disk. |
| B | Remove the `GH_MINUTES_MODE=local` override? | Yes, if Actions minutes are available. **Done 2026-11-26:** the user restarted the app. The variable is unset, and the gate reports `GITHUB`. |
| C | Accept the three goal loop answers below? | **Accepted 2026-11-26:** C1 yes, C2 yes, C3 yes. The `grill-with-docs` and `grilling` skill text holds no stop rule, so there is nothing to drop. |
| D | Delete the merged local branches `feat/hermes-trope-rewrite-impl`, `feat/trope-gate-open-items` and `fix/gh-gate-quoted-text`? | **Done 2026-11-26** with `git branch -d`, which refuses unmerged branches. The remote branches `origin/feat/hermes-trope-rewrite-impl` and `origin/feat/trope-gate-open-items` are untouched. |

Decision C holds these three questions. The user accepted all three on 2026-11-26.

1. Write the respec as a new file in `docs/superpowers/specs/` and leave ADR 0002 unchanged?
2. Treat the four decisions in ADR 0002 as settled?
3. Drop the proposed stop rule in the `grill-with-docs` skill text?

The reason for question 3: the `grilling` skill already tells the model to wait for answers. The `/goal` hook then blocks the stop. ADR 0002 tested a related wording rule, and it ended the loop in 1 of 3 runs.

## 4. Phases

### Phase 1: Reconcile the shared content (`/implement`, about 45 minutes)

1. Save a backup: write `git -C ../agent-skills diff -- skills/imhotep skills/marcus skills/niccolo` to a patch file outside both repos.
2. Edit each file hunk by hunk. Take the newer copy for each row in section 2.
3. Update the symlink pitfall text. `design_gate` now passes `--repo-root`.
4. Run `python skills/marcus/scripts/update_marcus.py --check --strict-design --repo-root .`.
5. Run `python skills/marcus/evals/run_gate_tests.py`.
6. Run `python -m pytest -q`.
7. Commit the named paths in `demiurge`.
8. Commit the same paths in `agent-skills`.

**Done when:** `git status` shows no change under the three folders in either repo.

### Phase 2: Give each file one owner (needs A and Phase 1, about 30 minutes)

1. Search the `agent-skills` tests and workflows for reads of the three folders.
2. For each folder, remove only the link in `demiurge`, for example `rm skills/marcus`. Use no trailing slash and no recursive flag.
3. Confirm that `../agent-skills/skills/marcus` still holds its files.
4. Run `git restore skills/marcus` in `demiurge`. Repeat steps 2 to 4 for the other folders.
5. In `agent-skills`, run `git rm -r --cached` on the three folders and add them to `.gitignore`.
6. Run `bash scripts/sync-skills.sh --check`. Confirm that it compares these folders with the deploy target.

A fresh clone of `agent-skills` then lacks the three folders until a sync runs.

**Done when:** only `demiurge` tracks the files, and parity passes.

### Phase 3: Release demiurge 0.19.1 (`/tdd` for the test, about 20 minutes)

1. Add one test in `scripts/test_verify_release.py`. The seam is `design_gate`: its command passes `--repo-root`.
2. Add a CHANGELOG entry for `7120ab6`, Phase 1 and Phase 2.
3. Correct the 0.19.0 line "Standing orders: a fix is not claimed". The rule is in `marcus/SKILL.md`.
4. Ask the user to approve `gh release edit v0.19.0`. The release text holds the same wrong line.
5. Run `python scripts/gh_minutes_gate.py --status`. Follow the mode it reports.

**Done when:** `python scripts/verify_release.py --remote` passes for `v0.19.1`.

### Phase 4: Close the trope gate documents (`/implement`, about 15 minutes)

1. In `agent-skills`, add double-quoted text to the exempt list in `i-have-adhd/SKILL.md` and `references/trope-gate-mechanism.md`. `QUOTE_RE` in `trope_gate.py` exempts it. The Claude Code, Antigravity and OpenCode skill libraries link to this copy.
2. Release `agent-skills` 1.69.1 with this change and the Phase 1 and 2 commits. Stage named paths only.
3. In the single-output spec, remove the `git-lifecycle-guard` `MISSING` note and the old branch name.
4. In ADR 0001, note that the two Hermes `config.yaml` files hold no `trope_rewrite` entry.

A separate, older plugin copy is in `~/.gemini/config/plugins/i-have-adhd`. It has no exemption list. This plan does not change it.

**Done when:** both documents list the same exemptions as the code, and parity passes.

### Phase 5: Respec the goal loop (needs C, about 30 minutes plus waiting time)

Status 2026-11-26: unblocked by C. Step 1 needs sessions that start after today, so it cannot finish in this session.

1. Repeat the ADR 0002 transcript count on sessions that start after 2026-11-26. Record the number of loops and their length.
2. Run `/grill-with-docs` with that result. Settle the problem that remains and the test plan.
3. Write the spec file from the answers and link it from `docs/README.md`. `/to-spec` publishes to an issue tracker, and decision C1 asks for a file.
4. Stop for the user's approval.

**Done when:** the user accepts the spec.

### Phase 6: Checks only the user can run (about 10 minutes)

1. Restart Hermes.
2. Send one plain-facts prompt in Hermes, Claude Code and Antigravity.
3. Count the replies for each turn. The pass count is one.
4. Record the result in the single-output spec status line.

## 5. Order

1. Run Phase 1.
2. Answer decision A.
3. Run Phase 2, then Phase 3, then Phase 4.
4. Run Phases 5 and 6 at any time.

## 6. Out of scope

- The other uncommitted paths in `agent-skills`, mainly `skills/token-optimizer` (113 paths). This work did not touch them.
- The quoted-text exemption and the two copies of the scanner. The spec accepts both as known limits.
