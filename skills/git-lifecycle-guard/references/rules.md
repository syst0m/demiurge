# Rules — git-lifecycle-guard

These are the operator's seven lifecycle rules. Each has a check and a pass line. Day limits are
proposed defaults — the operator sets the real values.

This file is append-only: add entries, never rewrite or condense existing ones. (Rule K-2,
accumulated knowledge is append-only.)

**Load before:** running `git-lifecycle-guard check` or `cleanup`, or writing any hook/CI wiring
for this workflow. (Rule K-1.)

| # | Rule | Check | Pass line |
|---|------|-------|-----------|
| 1 | Delete a merged branch within N days. | `git branch --merged main --format='%(refname:short) %(committerdate:short)'` | No branch is older than N days. |
| 2 | Remove a worktree when its branch is merged. | `git worktree list`, then `git merge-base --is-ancestor <branch> main` | No worktree holds a branch that is an ancestor of main. |
| 3 | Every worktree has an owner and a tracking item. | `gh pr list --head <branch>`, or a task ID in the branch name | An open PR exists, or the name carries an ID. |
| 4 | Flag an unmerged branch with no commit for N days. | `git for-each-ref --no-merged main --format='%(committerdate:short) %(refname:short)'` | No unmerged branch is older than N days without a note. |
| 5 | A merge keeps all branch work. | Before: `git diff --name-only $(git merge-base HEAD main) HEAD`. After: `git diff <branch-tip> HEAD -- <file>` per file. | No branch-added line is missing unless the merge message lists it. |
| 6 | The branch does not duplicate a revision or version on main; no stray files. | Search PROVENANCE and CHANGELOG for duplicate headings; scan tree for `plugin/tmp/` and `Screenshot *.png`. | Zero duplicates and zero stray files. |
| 7 | A deployed copy has no one-sided entries. | Diff entries both ways between the repo file and the `~/.claude/skills/` copy. | Both differences are empty. |

Notes from the operator's attachment:

- Rule 5 (case 01) is a per-merge test; it cannot run on a snapshot. It runs at merge time.
- Rule 5 merge date vs tip date: rule 1 uses tip commit date; use the merge commit date if exactness is wanted.
- Case "name versus content": `fix/habit-click-latency` has a tip about the Portal bulk delete. No git check catches that; it needs a human look.
- Rule 3's PR lookup failed earlier because the GitHub connector failed; fall back to task ID in branch name, else manual review.
- Git does not record deleted worktrees. History counts are floors rather than exact numbers.

Proposed defaults: merged_days = 7, unmerged_days = 14 (per the operator's attachment).
