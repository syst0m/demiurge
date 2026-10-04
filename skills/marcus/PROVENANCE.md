# PROVENANCE — marcus

```yaml
skill: marcus
created: 2026-08-30
merged: 2026-09-04
trust_tier: T1-conditional
gate_reached: G4 (G0 partial, G1/G5 pending isolated runner)
baseline_score: null
treated_score: null
delta: null
model_harness_pair: null
supersedes: skill-forge@1.0.0
research_snapshot: {version: "1.3.1", snapshot_sha256: "f36d8fcaa26813a5c6f25aa11fcf82d79e08be9002a469971e8fe90efe609477"}
research_claims: []
```

## Current Specification

Marcus pairs design guidance with mechanical harness enforcement. Seven design steps map directly to seven machine-checkable validation gates.

The self-audit checklist previously in `AGENT_ARCHITECTURE.md` §6 executes as a deterministic hook via `scripts/validate_skill.py`. Per **Rule V-4**, invariants execute as automated hooks to ensure consistent enforcement across sessions.

## Evidence of Need (Gate G0)

Marcus incorporates failure cases identified during skill evaluation:

1. **Injection-Shaped Fixtures in Templates:**
   `templates/agent-skill/evals/evals.json:16` contains `IGNORE PREVIOUS INSTRUCTIONS` as an injection-resistance fixture. The validator requires recorded, reason-bearing suppressions for intentional test fixtures.
2. **Scanner Self-Inspection Integrity:**
   Pattern definitions within validators must be auditable. The validator requires explicit suppressions for intentional regex test patterns.
3. **`SKILL.md` Inclusion in Security Scanning:**
   `SKILL.md` is scanned directly during security checks alongside all executable scripts.
4. **Baseline Eval Suites:**
   Every skill in the library requires an evaluation suite at the root directory to verify performance against unassisted baselines.

## Script Architecture

The five scripts implement the quality gates and self-update loop: G4 (`validate_skill.py`), G5 (`eval_runner.py`), G6 (`route_check.py`), the G0–G3 scaffold (`new_skill.py`), and self-update/drift audit (`update_marcus.py`), alongside `evals/run_gate_tests.py` for Marcus's regression suite. Each performs a deterministic check independent of model judgment.

All scripts use standard-library Python 3: zero network access, zero package installation, and zero writes outside target directories, with one opt-in exception: `eval_runner.py --ledger` (or `ledger_enabled: true` in the config) appends metadata-only replay rows to the run ledger at `$DEMIURGE_LEDGER_DIR` or `~/.demiurge/ledger/`. `modify_skill.py --evidence ledger:<run_id>` reads that ledger and never writes to it: it accepts only a run of the target skill whose latest label is `bad`, and copies the run id, failure class, label source and origin into `PROVENANCE.md` and the new regression case, never the verdict note. `eval_runner.py` requires `--yes` and `--runner-model` prior to API execution.

## 2026-09-11 — Fast Commands & Self-Update Subcommand

Added explicit fast commands and self-update mechanism:

- Subcommand `/marcus update`: Automates rule drift checks, snapshot diffing, and reference sync via `scripts/update_marcus.py`.
- Interactive slash subcommands: `/marcus generate`, `/marcus audit`, `/marcus update`, `/marcus --simulate`, and `/marcus --help`.
- Gate G4 re-validated (0 blocking, 0 warnings); gate regression suite maintained at 14/14 passing.

## 2026-09-14 — Modify / Add-Feature Pipeline (Rule G-12)

Added a measured revision cycle for editing existing skills, closing the gap where prior gates covered only creation (G0–G6 for new skills) and left in-place edits unmeasured:

- Subcommand `/marcus modify` (alias `/marcus edit`): Scaffolds a revision via `scripts/modify_skill.py`, which refuses without recorded gap evidence (G0) and refuses when the target skill does not exist.
- Rule G-12: Requires a pre-revision baseline (G1), a minimal draft (G2–G3), format/security validation (G4), 100% non-regression plus positive lift on new cases (G5), and an appended `PROVENANCE.md` entry (G6) — codified in `AGENT_ARCHITECTURE.md` and `references/SPEC.md`.
- Gate regression suite extended to 17/17 passing (`regression-13` through `regression-15`), covering refusal without evidence, refusal on a missing target, and a successful revision that appends both a provenance entry and a new eval case.

## 2026-09-17 — Fix: `modify_skill.py` crash on a bare-list `suites` value

**Evidence of need (G0):** `TypeError: list indices must be integers or slices, not str`,
thrown by `scripts/modify_skill.py:108` when run against another installed skill's real
`evals/evals.json`. Reproduced directly with
`python scripts/modify_skill.py <skill-dir> --feature x --evidence y`.

**Root cause:** the suite-update branch assumed `evals_data["suites"][name]` is always a
dict shaped `{"cases": [...]}`. That skill's real `evals/evals.json` keys
`suites["regression"]` and `suites["capability"]` to bare lists of case objects.
`setdefault("regression", {})` returned the existing list unchanged, so `"cases" in reg`
tested list membership (false), and `reg["cases"] = new_cases` then assigned a string key
on a list and crashed.

**Fix:** the branch now checks the type of `suites["regression"]` before writing to it —
a list is extended directly, a dict appends to (or creates) its `.cases`, and a missing
key is created as `{"cases": new_cases}` to preserve prior behaviour.

**Verification:** `evals/run_gate_tests.py` regression-16 reproduces the bare-list
shape (`suites` keyed to bare lists) as a fixture, runs `modify_skill.py` against it, and
asserts exit 0 with the new case appended to the list in place. Full deterministic suite:
18/18 passing. G4 (`validate_skill.py`) re-run clean: 0 blocking, 9 suppressed with a
stated reason. No model-based G5 run: this is a script bug fix with no change to agent
instructions, so the deterministic regression case is the applicable proof, matching the
precedent set by regression-13/14/15 for this same script.

## 2026-09-25 — Interactive UI & Demiurge Controls Integration

Added native Antigravity interactive UI modalities (`ask_question` and Markdown Artifact boards) tailored specifically for Demiurge repository controls:

- `skills/marcus/config.default.yaml`: Configurable defaults for Demiurge controls, including research drift checks against `research/RESEARCH.md`, pre-commit mechanical linters (`gate_tropes.py`, `scan_security_and_pii.py`, `scan_superfluous.py`), benchmark registry tracking, and release management prompts.
- `skills/marcus/scripts/resolve_config.py`: Deterministic config resolution supporting project-level overrides in `.agents/skills.config.yaml` or `.agents/config.yaml` without forks.
- Subcommand `/marcus interactive` (alias `/marcus ui`): Launches an interactive intake modal and emits a visual pipeline board artifact (`demiurge_build_board.md`).
- Gate G4 re-validated (0 blocking, 0 warnings); gate regression suite maintained at 17/17 passing.

## 2026-10-04 — Install Scope (Rule G-13)

**Evidence of need (G0), recorded for the modify pipeline:**

1. **A send guard designed for a global install.** Networker's outbound guard
   (`hooks/deny_outbound.py`, wired by its `settings.fragment.json`) is a `PreToolUse` hook whose
   matcher covers `mcp__.*`, Bash and PowerShell. It was designed for a global `PreToolUse`
   install, where it would have blocked Gmail and Calendar tools in every session, including
   sessions that never load networker.
2. **A T2 skill loadable everywhere.** Networker is recorded at T2 ("must not be installed"), yet
   it became loadable in every Claude Code session because `~/.claude/skills` is a symlink into
   the agent-skills repo's `skills/` directory. Nothing between "written to the canonical source"
   and "loaded in every session" asked where the skill should live.
3. **Antigravity has no skill-level hooks.** Its hooks are global, workspace (`.agents/hooks.json`)
   or plugin hooks. A skill whose hooks must run under Antigravity can only be scoped to a
   workspace, so "global or nothing" leaves no safe place for a hook that blocks a tool class.

**Change:** new `scripts/install_skill.py` installs a skill at project, global or staging scope,
dry run until `--yes`. Project scope links the skill into `<dir>/.claude/skills/` and/or
`<dir>/.agents/skills/` and appends the skill's fragment hooks and deny entries to the project's
settings as new array entries, after a backup. Global scope links into a library and writes no
hooks: they reach a global install only through `SKILL.md` frontmatter. The script refuses global
below T1, global with a tool-class-blocking `PreToolUse` hook unless `--i-know`, project for T4,
any write outside the target, and a link path that already exists and is not ours. `--remove`
takes out exactly what the install recorded. Every applied install appends an `install:` block
here, in the installed skill's `PROVENANCE.md`, and a line to `~/.demiurge/installs.jsonl`. Rule
G-13 in `AGENT_ARCHITECTURE.md`; detail in `references/SPEC.md` §6.1. G6 and `/marcus
interactive` ask *"Where should `<skill>` and its hooks live?"* after listing each hook in plain
words.

**Script justification (G4):** linking and settings merges are fragile file operations across
two harness schemas and two platforms (symlink, or a directory junction on Windows without
Developer Mode). A script makes the refusal rules and the exact undo deterministic, where a prompt
line would not.

**Verification:** `scripts/test_install_skill.py` (29 unit tests, temp directories with HOME,
USERPROFILE and the sidecar redirected) and `regression-25` to `regression-28` in
`evals/run_gate_tests.py` (29/29 passing). G4 re-run: 0 blocking. No model-based G5 run: the
change adds a script and a G6 question, and the deterministic cases are the applicable proof, as
for regression-13 to regression-16.

## Open Validation Scope

- **Self-Referential Gate G5 Evaluation:** End-to-end G5 execution on Marcus's full skill factory workflow requires isolated execution environments to prevent nested agents from inheriting the installed skill library.
- **Comparative Baseline Definition:** Designing an agent lacks an automated benchmark baseline; empirical validation is tracked via task-specific evaluation suites.
- **Validator Recall Boundaries:** The validator enforces published structural constraints and static scans; edge cases outside current rules require manual review.
- **Route Collision Bounds:** `route_check.py` evaluates bag-of-words cosine similarity with a weighted trigger clause.
- **Evaluation Grading Variance:** `eval_runner.py` incorporates deterministic test assertions alongside model grading.

## Deterministic Suite

Execute local regression tests: `python skills/marcus/evals/run_gate_tests.py` (29/29 passing). Regression test cases are derived from the findings above and maintain 100% pass rates.

## Trifecta Position

- **Private data touched:** Local skills directory, the install sidecar at `~/.demiurge/installs.jsonl` (absolute project paths; written by `install_skill.py --yes`), plus the run ledger at `~/.demiurge/ledger/` when `eval_runner.py --ledger` writes to it (opt-in) or `modify_skill.py --evidence ledger:<run_id>` reads it (read-only).
- **Untrusted content ingested:** Third-party `SKILL.md` and reference files during audit.
- **Exfiltration vector:** Zero in scripts. Zero network calls. Writes outside the target skill are the opt-in ledger append, which holds metadata and no prompt, transcript or judge text, and `install_skill.py --yes`, which writes only the chosen project or library, the installed skill's `PROVENANCE.md` and the local install sidecar.

The scripts remain network-free to prevent audit path exploitation.
