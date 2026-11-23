# PII Gate Handoff for Marcus

Status: draft handoff, 2026-11-18.
Source design: [PII Control Redesign](PII_CONTROL_REDESIGN.md).

## Purpose

Marcus reviews the redesign, decides scope, and sets the acceptance numbers. Marcus does not
implement the gate in this handoff. Implementation follows the work order below.

## Decisions Marcus must make

1. Is D1 (public-tree allow-list) in scope for this release?
2. Where does the pattern list live? The draft proposes an Actions secret. The policy owner must confirm.
3. Do the D6 heuristics block or only warn? The draft proposes warn first.

## Facts checked on 2026-11-18

- The scanner fails open. `scripts/scan_security_and_pii.py` lines 47 to 51 replace a load error with an empty list.
- No remote branch tip holds the leaked profile files.
- Release commit `4d49256` on `origin/main` holds 12 profile files for the private skill.
- The private skill path was first added on 2026-09-06.
- The remote holds 54 `refs/pull/*` refs. Their contents are not checked.
- A message scan finds a personal first name in 140 of 1049 commits. This is a lower bound.

## Facts not checked

- Squash-merge default message behavior on GitHub.
- Whether GitHub Support can purge `refs/pull/*` objects.
- Whether fork pull requests receive Actions secrets. The draft assumes they do not.
- The entry path that let incident 5 through.
- The full count of history hits. `git log -G` gave unreliable results on Windows.

## Status of the design

Designs D1 to D7 are design choices. No file in `references/RESEARCH.md` settles them.

## Work order

1. User approves containment steps in the redesign, section 8.
2. Make the scanner fail closed (D2). Test with the pattern file removed. Exit code must be 2.
3. Write canary tests before any gate change (redesign, section 7, items 1, 3 and 5).
4. Add the server-side gate (D3). Confirm the secret and branch protection with the user first.
5. Add surfaces in leak order: commit messages and authors, then paths, then release notes.
6. Add the path allow-list (D1) last. It changes the sync and release scripts.
7. Report two numbers: surface canaries caught, and evasion catch rate per mutation.

## Acceptance numbers

| Measure | Required | Current |
|---|---|---|
| Surface canaries caught | 10 of 10 | 0 built |
| Fail-closed exit code with no pattern source | 2 | not run |
| Evasion catch rate | reported per mutation | not measured |

## Open questions

1. How did the profile files enter the tree? Name the script or agent run.
2. Which incidents does the user count? Five are recorded and the user counts four.
3. Do any of the 54 PR refs reach a leaked commit?
4. Does the owner policy allow the pattern list as an Actions secret?
5. Should the private skill move to a separate private repository?
