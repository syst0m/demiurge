# PII Control Redesign: Draft for Marcus

Status: DRAFT. Marcus evaluates, amends and implements. Nothing here is measured yet.

This draft names no person, medication or private skill. Private values stay in the local pattern
file and in a CI secret.

## 1. Summary

Personal data reached the public remote repeatedly. The existing scanner has three structural
faults. Each fault lets a leak pass without any error.

1. It fails open. A missing pattern file becomes an empty pattern list.
2. It reads file content only. Commit messages, file paths, authors, PR text and branch names are never scanned.
3. It runs where the secret patterns exist: one machine. CI and every other clone scan with the generic patterns only.

Each earlier incident was closed with a content fix and a history purge. No incident added a canary
test for the surface that failed. A canary is a fake PII token planted to prove a gate fires.

## 2. Incident record

Source: `SECURE.md`, `CHANGELOG.md` lines 48, 456 and 470, and commits `ef9e7bf`, `5bc31f0`, `76afb6a`.
Count is at least five recorded clean-ups. The user counts four. Marcus must reconcile the list.

| # | Surface that leaked | Fix applied | Control added for that surface |
|---|---|---|---|
| 1 | File content (health protocols) | Untracked, `.gitignore` | Content scan, personal markers |
| 2 | Private skill references in fixtures and docs | Removed, history purge | None |
| 3 | Local paths in diffs and commit messages | History purge | Path regex on file content only |
| 4 | Name, medication, crisis keywords | `git filter-repo`, force push | Local pattern file (gitignored) |
| 5 | Private skill profiles in release `1.65.0` (squash of PR 50, 2026-11-11) | Removed from tips | None found |

Incident 5 returned a skill that `CHANGELOG.md` records as removed three days earlier. The removal
did not hold because nothing denied the path.

## 3. Current state, measured 2026-11-18

| Check | Result |
|---|---|
| Leaked profile files at the tip of any remote branch | 0 |
| Commits on all refs that touch the private skill path | 136 |
| Release commit `4d49256` on `origin/main` | Contains 12 profile files |
| First add of the private skill path | 2026-09-06 |
| `refs/pull/*` on the remote | 54 refs. Per-ref contents not verified. |
| Commits on all refs with a personal first name in message or author | 140 of 1049 |
| Commits on all refs with a health or neurodivergence marker in message | about 30 |
| Tracked files at HEAD matching a local pattern | 6 (some are false positives) |
| Tracked files at HEAD naming the private skill | 2: `CHANGELOG.md`, `docs/SKILL_BUNDLES.md` |
| Local pattern file | 26 patterns, last modified 2026-11-16, after incident 5 |

The history diff counts from `git log -G` came out near zero for names. The cause is probably POSIX
regex differences on Windows. Treat those counts as a lower bound. Marcus must measure with a
Python scan over `git log -p`.

## 4. Root causes

| ID | Cause | Evidence |
|---|---|---|
| RC1 | Fail-open pattern load | `scan_security_and_pii.py` lines 47-51: `except Exception: LOCAL_PII_PATTERNS = []` |
| RC2 | Personal patterns exist on one machine only | `.gitignore` line 59. CI `pre-commit` job has no pattern source. |
| RC3 | Surfaces unscanned | `check_file()` reads file bodies only. `main()` takes file paths only. |
| RC4 | Blocklist model | A new name passes until someone adds it. Pattern file post-dates incident 5. |
| RC5 | Self-exemption and loose allow-list | Lines 100, 108, 119, 131 skip any file whose path contains the scanner name. Line 111 and others skip a whole line when it holds any allow-list substring. |
| RC6 | No path deny-list | Incident 5 re-added a removed skill path. |
| RC7 | Entry paths skip the local hook | Squash merge on GitHub, web edits, agent worktrees, `--no-verify`, bot PRs from `research-pr.yml`. |
| RC8 | History and PR refs survive tip fixes | 54 `refs/pull/*` refs. A force push to `main` does not remove them. |
| RC9 | No measurement | No canary suite. No coverage number. |

Unconfirmed inference: the profiles entered through a bulk sync of `skills/` from a private source.
Release 1.65.0 also changed other skills in one commit, with author `Agent Workspace`. Marcus must
find the real entry path before the design is final.

## 5. What "100%" can mean

100% detection of unknown PII is unprovable for any pattern scanner. The scanner header already says so.

Two targets are provable:

1. **Surface coverage 100%.** Every place data can enter the public remote has a gate. A canary proves each gate.
2. **Containment by construction.** Private material cannot enter the public tree. A path allow-list enforces it. Pattern scanning is the second layer.

Marcus should report both numbers and refuse any claim of "all PII caught".

## 6. Proposed design

### D1. Public-tree allow-list (closes RC6, RC7)

- A manifest lists every top-level path and skill allowed in the public repo.
- Any tracked path outside the manifest fails the gate.
- `sync-skills.sh`, `sync_bundles.py` and the release cut read the manifest. They refuse to copy a skill not on it.
- Private skill names are held in a secret deny-list. The tracked manifest lists allowed names only.

### D2. Fail-closed patterns (closes RC1)

- Add `--strict`. In strict mode, an absent pattern source exits 2.
- Pattern sources in order: `DEMIURGE_PII_PATTERNS` env var, CI secret, `scripts/local_pii_patterns.py`.
- CI, pre-push, `verify_release.py --cut` and `--pre-commit` in agent worktrees all run strict.
- A load error prints one line and exits 2. It never degrades.

### D3. Server-side gate (closes RC2, RC7)

- New CI job `pii-gate`. It runs on `pull_request` and on `push` to `main`.
- The pattern list is an Actions secret. The owner is the only committer, so fork-secret limits do not apply. Marcus confirms.
- Branch protection requires `pii-gate`. Admin bypass is off.
- Squash-merge default message is the PR title. The gate scans the title and body before merge.

### D4. Every surface (closes RC3)

| Surface | Gate |
|---|---|
| File content | Existing scan, with patterns from D2 |
| File and directory names | New: scan `git ls-files` output |
| Commit messages | New: `commit-msg` hook and CI scan of `base..head` |
| Author and committer fields | New: CI scan of `%an %ae %cn %ce` |
| Branch and tag names | New: CI scan of ref names |
| Tag annotations and release notes | New: scan in `verify_release.py --cut` |
| PR title and body | New: `pull_request` event payload scan |
| Binary and container files (docx, pdf, zip, image metadata) | New: extract text and scan, or block the type |
| Full history | New: weekly scheduled scan of all refs |
| Outgoing commits | New: `pre-push` hook scans `@{u}..HEAD` |

### D5. Remove blind spots (closes RC5)

- Delete the path-based self-exemption. Keep the pattern definitions in a file outside scan scope, loaded from the secret.
- Make each allow-list entry exact: file path plus matched string. Drop the whole-line substring rule.
- Move personal examples out of the tracked scanner header and example file.

### D6. Structural heuristics for unknown names (partial answer to RC4)

- Flag directories and files shaped like per-person records: `profiles/`, `diagnoses/`, `outcomes`, `*_ledger.json`.
- Flag a capitalised name in a path segment under a skill `profiles/` or `people/` directory.
- Report as warnings that block in strict mode. Expect false positives. Marcus measures the rate.

### D7. Incident rule (closes RC9)

An incident closes only when all three exist:

1. A canary for the surface that failed.
2. A control that fails on that canary.
3. A row in the incident table in section 2.

## 7. Acceptance tests for Marcus

Place under `evals/pii_gate/`. Use fake tokens only. A real value never appears in a fixture.

1. **Surface canaries.** One fake name planted at each surface in D4. Every gate must fail. Required: 10 of 10.
2. **Entry-path canaries.** Plant the token, then commit via hook, `--no-verify`, a fresh clone, a worktree, a GitHub web edit and a squash merge. Required: the push or merge is blocked at every entry path.
3. **Fail-closed test.** Remove the pattern source. Strict mode must exit 2.
4. **Evasion mutations.** Case change, Unicode look-alike letters, token split across a line break, base64, JSON escape, token inside a filename, token inside a symlink target. Report the catch rate per mutation. List every failure as a known gap.
5. **Allow-list test.** A line holding an allow-listed substring plus a canary must still fail.
6. **Path test.** A new `skills/<name>/profiles/` directory outside the manifest must fail.
7. **False-positive budget.** Run on the clean tip. Required: 0 findings after reviewed exact allow-list entries.

## 8. Containment steps for the current leak

These are separate from the design. The user decides each one.

| Step | Detail | Decision owner |
|---|---|---|
| 1 | Remove the private skill name from `CHANGELOG.md` line 52 and `docs/SKILL_BUNDLES.md` lines 82 and 91. These are the current code-search hits. | User |
| 2 | Run `git filter-repo` to drop the private skill path and rewrite matching commit messages on all refs. | User |
| 3 | Force-push all branches. Delete stale remote branches. | User |
| 4 | Ask GitHub Support to purge cached views and `refs/pull/*` objects. Without this, the objects stay reachable by SHA. | User |
| 5 | Delete or rewrite GitHub Releases and tags that carry affected assets or notes. | User |
| 6 | Record that a named third party's personal data was disclosed. Decide whether governance rules require a formal record. | User |

## 9. Open questions

1. How did the profiles enter the tree? Name the script or agent run.
2. Which five or four incidents does the user count?
3. Are the 54 PR refs affected? List each ref that reaches a leaked commit.
4. Can the owner hold the pattern list as an Actions secret, or does policy forbid it?
5. Should the private skill move to a separate private repository, with the public repo holding no reference to it?
