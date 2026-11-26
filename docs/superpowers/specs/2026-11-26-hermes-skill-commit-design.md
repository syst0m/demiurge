# Hermes Skill Changes: Commit and Merge Flow Design

**Status:** Draft. Round 1 accepted on 2026-11-26. Round 2 values are rulings, marked R2 below, and wait for the user.
**Date:** 2026-11-26
**Repos:** `agent-skills` (owns the skills), `demiurge` (owns this spec and the Hermes locks for its own skills)

## 1. Goal

Stop skill edits from piling up as uncommitted files. Two flows commit and merge them:

- **Flow A, upstream sync:** the daily `npx skills update` changes skills that come from outside. The sync script puts them on `main`.
- **Flow B, Hermes lessons:** Hermes edits skills in its own background review. A batch job commits those edits to a branch, and opens or merges a pull request after a significant set of changes.

## 2. Facts that drive the design

| Fact | Evidence |
|---|---|
| Flow A writes into the checkout through folder links. Three upstream skills are links into `~/.agents/skills`. | `token-optimizer`, `gemini-api`, `code-review-and-quality` in `agent-skills/skills/`. |
| Hermes writes skills at once. It has no approval step by default. | `agent/background_review.py`; `skills.write_approval` unset. |
| Hermes writes a ledger entry for each change. The entry holds the skill, path, hashes and actor. | `hermes\skills\.curator_ledger.jsonl`, 934 entries from 10-30 to 11-25. |
| Most Hermes edits land in folders with no Git repository. | 190 of 235 changes since 11-12. |
| Hermes edits to demiurge-owned skills land in gitignored deployed copies. A deploy overwrites them. | `marcus`, `imhotep`, `niccolo` in `agent-skills`. |
| The sync script opens pull requests without the minutes gate. | `scripts/open_sync_pr.py` calls `gh pr create` with no gate check. |
| PR 67 has been stuck since 11-14, and the daily job rebuilds it each day. | Six findings: three scope findings, one code finding, one scope finding and one false secret hit. |

## 3. Decisions taken (Round 1)

| ID | Decision | Reversal |
|---|---|---|
| Q1 | One spec, two flows. | Split the spec. |
| Q2 | A ledger-driven batch job commits Hermes edits in batches. It runs as a Hermes `no_agent` script job. It stages named paths only, commits on a branch in a temporary worktree off `origin/main`, and reports other dirty paths. A commit per change is rejected: it makes hundreds of commits, and a Git lock blocks parallel writes. | Run the job per change through a hook. |
| Q3 | Git-less Hermes folders stay out of scope. The ledger keeps rollback copies, up to 5 MB (`skills.ledger_max_bytes`). | Add a Git step per folder. |
| Q4 | Lock `marcus`, `imhotep` and `niccolo` in Hermes with `hermes curator lock`. Hermes then stops its updates to these three. | `hermes curator unlock <skill>`. |
| Q5 | The automation follows the minutes gate. In `GITHUB` mode it opens a pull request. In `LOCAL` mode it opens no pull request. It runs the local checks, merges with `git merge --no-ff`, and pushes `main`, with no person present. | Set the gate to `GITHUB`, or stop the job. |
| Q6 | Repair PR 67: add `code-review-and-quality` to `scripts/upstream_skills.txt`, waive the false secret hit in `token-optimizer/scripts/benchmark.py`, rebuild the branch, and send one task per pull request. | Revert the list and waiver lines. |
| Q7 | This spec lives in `docs/superpowers/specs/`, with a row in `docs/README.md`. | Move the file. |

## 4. Round 2 rulings (R2)

The user has not answered Round 2. These values apply until the user changes them.

| ID | Ruling | Why | Cost if wrong |
|---|---|---|---|
| R2-1 | A change is significant when one of these holds: 10 or more files, 200 or more changed lines, or the oldest uncommitted change is 24 hours old. | The numbers match the ledger volume. A daily cadence fits the upstream sync. | A batch is too small or too late. The job only runs more often, so the cost is small. |
| R2-2 | Markdown text merges without a person. A person reviews a batch that touches scripts, executables, new skills, deletions, or text that a flag gate marks. | Text is live on disk at write time, so the merge gate protects only history and the remote. Scripts and deletions do more damage. | A bad text edit reaches `main`. The ledger and `git revert` undo it. |
| R2-3 | The commit message names the skills, the ledger entry ids, and the Hermes session ids. It ends with the Co-Authored-By line from the session rules. | Provenance lets a reviewer trace each edit. | Harder to trace, with no loss of data. |
| R2-4 | `skills.write_approval` stays unset. The merge gate handles review. | Turning it on stops every Hermes skill write until a person approves it, which blocks the curator. | Lessons take longer to go live. |

## 5. Flow A: upstream sync repair

1. Add `code-review-and-quality` to `scripts/upstream_skills.txt`.
2. Add a waiver for `token-optimizer/scripts/benchmark.py`. A waiver is one line in `scripts/upstream_text_waivers.txt`: the path and the finding kind (`secret`). The gate keys each waiver by path and kind. A reviewer adds the line.
3. Change `notify_once` in `scripts/open_sync_pr.py` so its key uses the pull request URL. One pull request then sends one task.
4. Run the minutes gate before any `gh pr create` call in the script. In `LOCAL` mode the script merges locally and does not open a pull request.
5. Rebuild the branch. The rebuild drops the stale `marcus` and `niccolo` files from the sync.

**Acceptance:** `scripts/test_open_sync_pr.py` and the `check_sync_pr` tests pass. PR 67 closes or merges. One task appears per pull request.

## 6. Flow B: Hermes batch commit

### 6.1 Trigger

A Hermes `no_agent` cron job runs a script once a day. The script exits early when no change is significant (R2-1).

### 6.2 Steps

1. Read the ledger lines added since the last run. The run state lives in a file beside the script.
2. Keep the lines whose path sits in an agent-skills folder. Git-less folders are skipped (Q3).
3. Classify each queued path. Hold a path, and keep it queued, when it is not a markdown file in a skill that `origin/main` tracks, its mode changed, its text has a risky match, or its disk bytes differ from the newest ledger hash (a person changed it by hand). Held paths do not stop the other paths.
4. Create a temporary worktree from `origin/main`, on branch `auto/hermes-lessons`.
5. Copy the safe paths in. Stage named paths only. Never run `git add -A`.
6. Commit with the R2-3 message.
7. Run the local checks, `scripts/ci_local.py`, on the commit.
8. Apply the R2-2 rule. Merge to `main` with `git merge --no-ff` only when the batch is significant (R2-1), no path is held, and the minutes mode is `LOCAL`. Otherwise push the branch only and leave the queue as it is. In `GITHUB` mode the job never merges: a pull request takes the branch.
9. Remove the worktree. Write the run state only after a push or a merge succeeds.

### 6.3 Failure handling

| Failure | Action |
|---|---|
| Local checks fail | Keep the branch. Send one task. Do not merge. |
| Merge conflict | Keep the branch. Send one task. |
| Ledger unreadable | Exit 1. Send one task. |
| Minutes gate unreadable | Treat the state as `LOCAL`. |

### 6.4 Locks

Lock the demiurge-owned skills (Q4). Re-check the locks in each batch run, because a deploy can reset them.

## 7. Acceptance tests

| Test | Pass when |
|---|---|
| Ledger reader | Reads only new lines. Skips Git-less folders. |
| Stage names | The commit holds only the named paths. |
| Gate | `LOCAL` mode opens no pull request. |
| Notify | One task per pull request URL. |
| Lock check | `hermes curator status` lists `imhotep`, `marcus` and `niccolo`. |
| Parity | `python scripts/check_harness_parity.py` reports no `MISSING` or `STALE` line. |

### 6.5 Build status (2026-11-26)

- Built: `scripts/hermes_lesson_commit.py` and `scripts/test_hermes_lesson_commit.py` in `agent-skills`. 13 tests pass. `ci_local.py` passes.
- Dry run on the real ledger: 10 queued files. 1 safe. 9 held: 6 in `marcus`, 1 in `imhotep` (both gitignored in `agent-skills`, so they count as new skills), 1 Python script in `dark-strategist-efficacy-audit`, and 1 in `marcus` that is not markdown. Nothing was written.
- Registered: Hermes cron job `hermes-lesson-commit` (id `ecd8717f76dd`), daily at 08:30, `--no-agent`, through `~/.hermes/scripts/hermes_lesson_commit_run.py`. It runs with `--apply`.
- Live run 2026-11-26: queued 10 files. 1 safe file already matched `origin/main`, so nothing was committed. 9 held files stay queued.
- Fixed on 2026-11-26 (agent-skills `d5e2c64`): held files stay queued when nothing is committed.
- Not built: the GITHUB pull-request step. Merge in `GITHUB` mode stays with a person.
- Ruling: R2-1 uses 24 hours. An earlier draft of the job used 7 days. The job follows this spec.

## 8. Out of scope

- Git-less Hermes folders (Q3).
- Per-change commits (Q2).
- `skills.write_approval` (R2-4).
- The `hermes_skill_inventory.py --check` failure. It has a separate cause, and I did not trace it.

## 9. Open items

- Round 2 answers from the user. R2-1 to R2-4 stay in force until then.
- Where Hermes edits to demiurge-owned skills (`marcus`, `imhotep`, `niccolo`) should go. They are gitignored in `agent-skills`, so the job holds them. Options: a demiurge branch, or drop them. The user decides.
- Enable the cron job: register the `no_agent` script in Hermes after the user approves the job's first live run.
- Run the O1 goal-loop respec on or after 2026-12-10 (see [open items spec](2026-11-26-open-items-after-0.19.2-design.md)).
