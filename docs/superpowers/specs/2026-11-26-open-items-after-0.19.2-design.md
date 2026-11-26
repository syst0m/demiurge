# Open Items After 0.19.2: Design

**Status:** Items C1 to C8 are done. Items O1 to O7 stay open.
**Date:** 2026-11-26
**Repos:** `demiurge`, `agent-skills`

## 1. Goal

Close every item that was left open after release 0.19.2. State each item that cannot close today, with its trigger and its acceptance test.

## 2. How the decisions were made

The user asked for this spec with the words "Spec out not done and you do all yourself". The agent therefore took each recommended answer without a question round. Section 4 lists each decision and how to reverse it.

## 3. Closed items

| ID | Item | Result on 2026-11-26 |
|---|---|---|
| C1 | Release 0.19.2 | [Pull request 60](https://github.com/syst0m/demiurge/pull/60) merged as `9d8f26e`. `verify_release.py --remote` passes for `v0.19.2`. |
| C2 | Skill parity | `sync-skills.sh` deployed `marcus`. `check_harness_parity.py` reports `OK` for all three skills. |
| C3 | Old Antigravity plugin | `agy plugin uninstall i-have-adhd` removed it. A backup is in `~/.gemini/backups/i-have-adhd-plugin-20261126`. |
| C4 | Live output count | Pass in all three harnesses. Section 5 has the method and limits. |
| C5 | Antigravity hit log | The Stop hook ran and logged nothing. `agent-skills` 1.69.2 reads the Antigravity transcript. A live run then wrote a hit. |
| C6 | Dangling links in `agent-skills` | Eight tracked links had no tracked target, and the link test failed on a fresh checkout. 1.69.2 removes them from the index. |
| C7 | Contracted trope forms | The three negative parallelism gates in `demiurge` now match `isn't` and the curly apostrophe. A scan of all tracked Markdown files finds no hit. |
| C8 | `GH_MINUTES_MODE` override | The variable is unset after the app restart. The gate reports `GITHUB` for `demiurge`. |

## 4. Decisions taken for the user

| ID | Decision | How to reverse |
|---|---|---|
| D1 | Merge pull request 60 with a merge commit, as earlier pull requests did. | Revert the merge commit with `git revert -m 1 9d8f26e`. |
| D2 | Run the skill deploy that `AGENTS.md` gives to the user, because the request delegated it. | The deploy added four test files to the deployed `marcus` folder. Delete them. |
| D3 | Remove the old plugin after a backup. | Copy the backup into `~/.gemini/config/plugins/`, then restore `config.json` from the same backup. |
| D4 | Release `agent-skills` 1.69.2 through a local merge, because its gate reports `LOCAL`. | Revert merge `bba7d77` with `git revert -m 1` and delete tag `v1.69.2`. |
| D5 | Create only the `v1.69.2` tag by hand. `tag_changelog_versions.py --apply` also creates two older tags and pushes a Google Doc. | Run the script when you want those effects. |
| D6 | Widen the three negative parallelism gates. | Revert the commit that changes them. |
| D7 | Leave the running Hermes gateway up. It answered both test turns with the current behaviour. | Run `hermes gateway restart`. |

## 5. Live output count

Each harness ran one plain-facts prompt and one prompt that asked for a flagged line. The pass count is one reply for each turn.

| Harness | Command form | Replies per turn | Flagged line logged |
|---|---|---|---|
| Claude Code | `claude -p` | 1 and 1 | Yes |
| Antigravity | `agy -p` | 1 and 1 | No on the first run. Yes on the rerun after 1.69.2. |
| Hermes | `hermes chat -q --oneshot` | 1 and 1 | Yes, in the Hermes home log |

Limits:

- All runs were headless command line runs. No desktop app turn was tested.
- The running gateway served the Hermes runs as local turns. No Telegram turn was tested.
- The test runs added entries to the Claude Code hit log, the Hermes hit log and the Antigravity run ledger.

## 6. Open items

| ID | Item | Owner and trigger | Done when |
|---|---|---|---|
| O1 | Respec the goal loop (ADR 0002). | Agent. Run on or after 2026-12-10, so that sessions with the block cap exist. | The user accepts a spec in this folder. |
| O2 | Interactive output count. | User. Send one prompt in each desktop app and one in Telegram. | Each turn shows one reply. |
| O3 | 126 uncommitted paths in `agent-skills`, in `token-optimizer`, `gemini-api` and `code-review-and-quality`. Most carry the date 2026-11-26. | User. This work did not make them. | The paths are committed or discarded. |
| O4 | Tags `v1.67.0` and `v1.68.1` are missing in `agent-skills`. | User. The tag script also pushes a Google Doc. | Both tags exist, or the user rejects them. |
| O5 | Local tags `v0.17.9` to `v0.18.2` point to other commits than the `origin` tags in this clone. | User. `git fetch --tags` refuses to overwrite them. | The user picks the correct set. |
| O6 | `bundles/writing/bundle.json` and `scripts/upstream_skills.txt` still name the removed skill `writing-clearly-and-concisely`. | Agent, in the next `agent-skills` change. | Neither file names the skill, or the user restores it. |
| O7 | Git cannot delete stale worktree entries `wt` to `wt9` in `agent-skills` (permission denied). | User. | `git worktree prune` runs with no error. |

### O1 method

1. Read the session transcripts that start after 2026-11-26.
2. Count each run of repeated Stop-hook blocks under a `/goal` command as one loop.
3. Record the number of loops and the length of each loop.
4. Compare the result with the ADR 0002 figures of 75 loops and 89% blocked replies with no tool call.
5. Run `/grill-with-docs` on the problem that remains, then write the spec.

ADR 0002 treats its four decisions as settled. The new spec leaves ADR 0002 unchanged and drops the stop rule in the `grill-with-docs` skill text. The user accepted these three points on 2026-11-26.

## 7. Closed with no change

The user accepted these on 2026-11-26:

- The two `write_json` helpers stay separate.
- A commit message that quotes a blocked `gh` command stays blocked in `LOCAL` mode.
- The minutes gate cache keeps its small write race.
- The `agent-skills` tag workflow stays as it is.

## 8. Outside this spec

[PII Control Redesign](../../PII_CONTROL_REDESIGN.md) and its handoff are drafts from 2026-11-18. [Self-Harness](../../SELF_HARNESS.md) is opt-in. This work did not touch either one.
