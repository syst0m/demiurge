# Skill Bundles & Plugin Packaging

```yaml
version: 0.1.0
status: proposal
audience: operators, maintainers
canonical_path: docs/SKILL_BUNDLES.md
```

Demiurge today ships **three skills** (`imhotep`, `marcus`, `niccolo`) to every harness by
copying them into each harness's global skill directory. That model cannot express "a set of
skills for a usecase", and on this machine it has already produced two harnesses running two
different versions of `marcus`.

This document reviews the current sync per harness (§1), records what each harness supports
natively (§2), and proposes a bundle/plugin packaging model (§3) with a baseline coding bundle
and the bundles that follow from it (§4).

---

## 1. Current state

### 1.1 Two libraries, one physical directory

| Library | Path | Skills | Written by |
| --- | --- | --- | --- |
| demiurge | `~/Documents/code/demiurge/skills/` | 3 — `imhotep`, `marcus`, `niccolo` | hand-authored |
| agent-skills | `~/Documents/code/agent-skills/skills/` | 71 | upstream sync + hand edits |

Harness views of those libraries:

| Harness | Global path | Skills | Link type |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills` | 71 | symlink → `agent-skills/skills` |
| Antigravity | `~/.agents/skills` | 52 | real directory (Antigravity installer, `~/.agents/.skill-lock.json`) |
| OpenCode | `~/.config/opencode/skills` | 71 | symlink → `agent-skills/skills` |
| Hermes Agent | `%LOCALAPPDATA%/hermes/skills/agent-skills` | 71 | symlink → `agent-skills/skills` |

### 1.2 The defect: three writers, one directory

`scripts/sync-skills.sh` treats `~/.claude/skills`, `~/.config/opencode/skills` and
`%LOCALAPPDATA%/hermes/skills/agent-skills` as deploy targets and does `rm -rf` + `cp -r` into
each. All three are symlinks to `agent-skills/skills`. **A demiurge deploy therefore deletes and
re-copies files inside a different repository's working tree.**

`agent-skills/skills/` has three writers:

1. `demiurge/scripts/sync-skills.sh` — from `demiurge/skills/`
2. `agent-skills/scripts/sync_agent_skills.ps1` — copying *back* from `~/.agents/skills/`
3. direct edits — the working tree already carries uncommitted `M skills/marcus/SKILL.md`

Nothing orders them. The `dirty_target` pre-flight refuses a deploy when the target repository is
dirty, so the failure mode is a refused sync rather than a silent overwrite — but the refusal
fires on every run until the other writer's work is committed.

### 1.3 Measured divergence (2026-11-07)

Normalizing line endings (`diff --strip-trailing-cr`):

| Skill | File | demiurge | `agent-skills` | Direction |
| --- | --- | --- | --- | --- |
| `marcus` | `SKILL.md` | 291 lines | 312 lines | `agent-skills` **ahead** — carries the "Improving an existing skill" section |
| `marcus` | `scripts/ledger_lib.py` | 409 lines | 367 lines | demiurge **ahead** — carries `CLASS_HELP` + `cheatsheet()` |
| `marcus` | `human-only/README.md` | 76 lines | 75 lines | demiurge **ahead** — documents `session-summary-prompt.md` |
| `imhotep` | `SKILL.md` | — | +9/-1 | `agent-skills` **ahead** — carries the held-out-fixture pitfall |
| `niccolo` | — | — | — | identical |

`agent-skills/skills/marcus/SKILL.md` was CRLF; demiurge's was LF.

**Neither repository is a superset.** Each carries work the other lacks, so a one-way copy in
either direction destroys work. The two harnesses were also running different content: Claude Code,
OpenCode and Hermes load the `agent-skills` copy, Antigravity loaded demiurge's.

**Consequence:** `check_harness_parity.py` reports `stale` for the `agent-skills` copies but cannot
tell ahead from behind, so the gate fires on a difference it cannot resolve.

### 1.4 Reconciliation performed (2026-11-07)

Merged in both directions, then verified byte-identical after newline normalization across all
three skills:

| Change | Direction |
| --- | --- |
| `marcus/SKILL.md` (the section, including the uncommitted 4th check) | `agent-skills` → demiurge |
| `imhotep/SKILL.md` (the pitfall) | `agent-skills` → demiurge |
| `marcus/scripts/ledger_lib.py` (`CLASS_HELP`, `cheatsheet()`) | demiurge → `agent-skills` |
| `marcus/human-only/README.md` | demiurge → `agent-skills` |
| `marcus/human-only/session-summary-prompt.md` (trailing newline) | demiurge → `agent-skills` |

Verification: recursive normalized comparison of `marcus`, `imhotep`, `niccolo` reports `CLEAN`;
`validate_skill.py` passes G4 on all three; `skills/marcus/evals/run_gate_tests.py --library skills`
passes 35/35. Nothing was committed — `agent-skills` carries unrelated uncommitted 
work that must be committed separately.

### 1.5 Gate and scope mismatches

| Issue | Detail |
| --- | --- |
| Target set ≠ gate set | `sync-skills.sh` writes to 5 targets; `check_harness_parity.py` checks 3. Hermes is deployed to but never gated. |
| False drift | `sync-skills.sh` compares with `diff -rq`, which counts `__pycache__/*.pyc` as drift. `check_harness_parity.py` ignores them. Every run reports drift the gate does not see. |
| `--check` cannot fix what it reports | The dirty-target pre-flight runs only on a real deploy. `--check` reports drift; the deploy it points at then refuses. |
| No bundle concept | Every harness receives every repo skill. There is no way to install "coding only" or "research only". |
| Copy, not link | demiurge copies into `~/.agents/skills` (a real directory), so the copy drifts and the parity gate exists to catch it. The other three harnesses link and cannot drift. |

---

## 2. Native bundle support per harness

Prioritized by how much of the bundle model each harness expresses natively.

| Harness | Native unit | Global scope | Project/repo scope | Bundles skills? |
| --- | --- | --- | --- | --- |
| **Antigravity** (agy, IDE, App) | plugin: `plugin.json` + `skills/`, `agents/`, `rules/`, `hooks.json`, `mcp_config.json` | `~/.gemini/antigravity-cli/plugins/<name>/`, `~/.gemini/config/plugins/<name>/` | `<repo>/.agents/plugins/<name>/` | **yes** |
| **Claude Code** | plugin: `.claude-plugin/plugin.json` + `skills/`, `commands/`, `agents/`, `hooks/` | `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` + `enabledPlugins` | `<repo>/.claude/settings.json` → `enabledPlugins` | **yes** |
| **Hermes Agent** | plugin: `plugin.yaml` + `skills/`, `commands/`, `hooks/` | `%LOCALAPPDATA%/hermes/plugins/<name>/` + `plugins.enabled` | `<repo>/.hermes/plugins/<name>/` + `HERMES_ENABLE_PROJECT_PLUGINS=1` | **yes** |
| **OpenCode** | JS plugin only | `~/.config/opencode/opencode.json` → `plugins: []` | `<repo>/opencode.json` → `plugins: []` | **no** |

Two consequences:

- **`.agents/skills/` and `.agents/plugins/` are the cross-harness workspace standard.** Antigravity
  defines them; OpenCode reads `.agents/skills/` on its own. A repo-scoped bundle written there is
  visible to Antigravity and OpenCode without either having a plugin loader.
- **OpenCode has no native skill bundle.** Its plugins are JS modules; skills are plain directories.
  OpenCode gets a directory install rather than a plugin. Anything that needs an OpenCode-only behaviour
  goes in a JS plugin under `.opencode/plugins/`, which is a separate concern from skill bundling.

The `agent-skills` repository already implements the Claude Code half of this: a
`.claude-plugin/marketplace.json` at the root, one plugin at `plugins/agent-skills/` whose
`skills/` is a symlink to the top-level `skills/`. It is one bundle containing all 71 skills. The
proposal below generalizes that shape to N bundles.

---

## 3. Proposal

### 3.1 One library, one writer

`agent-skills/skills/` is the single distribution library; every harness already links to it.
Keep it that way and remove the second writer:

- **demiurge stops deploying to harness directories.** It publishes its three skills *into*
  `agent-skills/skills/` and stops there. The `agent-skills` repository is the only thing that
  touches harness global paths (through `setup_links.ps1`).
- **`sync_agent_skills.ps1` stops copying back.** `~/.agents/skills` is an Antigravity-managed
  install with its own lock file; it is not a source for the library.
- **Direct edits to `agent-skills/skills/marcus/` are reconciled once**, then forbidden by a check.

Three writers become one, and the direction is always demiurge → agent-skills → harness link.
The one exception is the catch-up merge in §1.4, which ran the other way because `agent-skills`
held newer content; it is done once and is not a recurring path.

### 3.2 A bundle is a manifest rather than a copy

```
bundles/
  baseline-coding/
    bundle.json          # name, description, skills[]
  agent-engineering/
    bundle.json
  ...
```

`bundle.json` lists skill names and nothing else. It is JSON, not YAML, because the materializer
must run on a machine without PyYAML. No skill content is duplicated: the materializer reads
`agent-skills/skills/<name>/` (or the Hermes library, one category level down) and emits symlinks.

A bundle is **not** a directory of skills. Copying skill bodies per bundle is what produced §1.3.

### 3.3 Materialization per harness

| Harness | Emitted artefact | Scope switch |
| --- | --- | --- |
| Antigravity | `.agents/plugins/<bundle>/` with `plugin.json` + `skills/` symlinks | `--scope project` |
| Claude Code | `<repo>/.claude/plugins/<bundle>/` with `.claude-plugin/plugin.json` + `skills/` symlinks, plus an `enabledPlugins` line | `--scope project` |
| Hermes | `<repo>/.hermes/plugins/<bundle>/` with `plugin.yaml` + `skills/` symlinks, plus `HERMES_ENABLE_PROJECT_PLUGINS=1` | `--scope project` |
| OpenCode | `<repo>/.agents/skills/<bundle>/` with symlinks only | always project |

Global scope uses the same manifest and writes to the harness's global plugin directory, plus the
`enabledPlugins` / `plugins.enabled` / `plugin.json` registration.

Symlinks keep one copy. Where a platform cannot resolve them (Windows without Developer Mode), the
materializer falls back to a copy and the parity gate reports it as `copy` rather than `link`.

### 3.4 Baseline versus plugins

- **Baseline** — the harness- and usecase-agnostic floor, installed everywhere. Proposed: the three
  demiurge skills (`imhotep`, `marcus`, `niccolo`) plus the cross-harness plumbing they need.
  Nothing else. A skill that only makes sense for one kind of work is not baseline.
- **Plugins** — usecase sets, installed per repo. A repo opts in by naming bundles in its own
  config; the sync reads that and materializes only those.

The rule: **if a skill is in the baseline, every harness gets it; if it is not, no harness gets it
unless a bundle names it.**

---

## 4. Proposed bundles

### 4.1 `baseline-coding` (first)

Harness-agnostic coding floor. Candidate skills, all present in `agent-skills/skills/`:

| Skill | Why it is baseline |
| --- | --- |
| `code-review-and-quality` | multi-axis review before merge |
| `concise-commit-gate` | bounded, imperative commit messages |
| `github-pr-workflow` | branch → commit → PR → CI → merge |
| `github-issue-to-pr` | issue → verified PR |
| `requesting-code-review` | pre-commit review gate |
| `test-driven-development` | RED-GREEN-REFACTOR |
| `systematic-debugging` | root cause before fixing |
| `simplify-code` | cleanup of recent changes |
| `dead-code-removal` | orphaned modules |
| `plan` | markdown plan, no execution |
| `spike` | throwaway validation |
| `setup-pre-commit` | hooks + lint-staged |
| `changelog-automation` | changelog from commits and PRs |
| `secret-scanning` | supply-chain scan |

Deliberately excluded: `marcus`, `niccolo`, `imhotep` (agent engineering, not coding),
`token-*` (cost tooling, one harness), `node-inspect-debugger` / `python-debugpy` (language-specific).

### 4.2 Other bundles

| Bundle | Usecase | Candidate skills |
| --- | --- | --- |
| `research-writing` | literature reviews, papers, citations | `arxiv`, `paper-lookup`, `literature-review`, `research-lookup`, `citation-management`, `grounded-citations`, `scientific-writing`, `venue-templates`, `markdown-mermaid-writing`, `baoyu-format-markdown` |
| `lifeos` | LifeOS task and idea workflow | `lifeos`, `lifeos-jeeves`, `lifeos-ideas-triage`, `lifeos-tasks-triage`, `alfred-butler`, `weekly-review-planning`, `meeting-action-items`, `document-to-action-items` |
| `agent-engineering` | building agents and skills | `marcus`, `niccolo`, `imhotep`, `skill-creator`, `agent-skills-release`, `autoskill`, `find-skills`, `arbor`, `rhadamanthus` |
| `infosec-governance` | Technology Risk & InfoSec work | `secret-scanning`, `github-auth`, `fleet-auditor`, `analytic-method-validation`, `experimental-design` |
| `personal-writing` | drafting in Tom's voice | `my-writing-style`, `humanize`, `unsloppify`, `writing-clearly-and-concisely`, `i-have-adhd` |
| `` | strategy sessions | `` |

### 4.3 Blocking gate for `baseline-coding`

The testing-matrix mandate is `scripts/testing_matrix_gate.py`. It reads the working tree's
staged, unstaged and untracked changes, separates source from test files, and blocks when source
changed with no test change — emitting the Impact Analysis / Implementation-Update-Deletion Plan /
Execution Approach triple. A repository that is not a git worktree passes, because the gate judges
changes rather than their absence.

`baseline-coding` declares `"hooks": true`, so the materializer registers it with every harness:

| Harness | Wiring | Verified by |
| --- | --- | --- |
| Antigravity | `<bundle>/hooks.json` — a named hook group with a flat `Stop` handler list, returning `{"decision":"continue"}` to block | `agy plugin validate` → `skills 14 · hooks 1 · ✔ Validation passed` |
| Claude Code | `<project>/.claude/skills/<skill>` links + `hooks.Stop` in `.claude/settings.json`, returning `{"decision":"block"}` | settings.json parses; hook command resolves |
| Hermes | user plugin dir `%LOCALAPPDATA%/hermes/plugins/<bundle>/` + `plugins.enabled`; `pre_llm_call` returns `{"action":"block","message":...}` | `hermes plugins list` → enabled; `plugins validate` → `register() ran in isolation`, `declared hooks — matches registrations`; live probe returns the block object |

Three findings from verification, each of which changed the wiring:

1. **Hermes' desktop gateway never loads `./.hermes/plugins`.** `gateway/session_local.py`
   (`project_plugins_warning`) only warns that the env var has no effect there; that path is
   CLI-only. The bundle therefore targets the **user** plugin dir and enables itself in
   `config.yaml`. `--scope project` prints a note and still targets the user dir.
2. **Claude Code does not auto-load `.claude/plugins/<name>/`.** Without a marketplace install
   record it reports "enabled in project settings but isn't installed here". Skills go to the
   documented project scope `.claude/skills/` instead, and the gate is a `settings.json` hook.
3. **The block dialects differ.** Claude Code stops on `{"decision":"block"}`; Antigravity stops
   on `{"decision":"continue"}` (any other value lets the stop through). The gate takes
   `--hook-format {internal,claude-code,antigravity}`; `internal` is what the Hermes plugin
   consumes.

Not verified: the *running* gateway has not reloaded, so the Hermes hook is not live in the
current session until a gateway reload.

---

## 5. Migration

1. ~~Reconcile `agent-skills/skills/{marcus,imhotep}`~~ — **done**, see §1.4. Both directions were
   needed; a one-way copy would have lost work.
2. ~~Add `bundles/` and the materializer~~ — **done**. `bundles/` holds seven manifests;
   `scripts/sync_bundles.py` materializes them.
3. Rework `scripts/sync-skills.sh` into the bundle materializer; keep `--check` / `--repo-only`.
4. Extend `check_harness_parity.py` to cover Hermes and to ignore `__pycache__`, matching the
   materializer's comparison.
5. Remove the copy-back path from `sync_agent_skills.ps1`.
6. ~~Cut the baseline to `baseline-coding`~~ — **done** for the demiurge repo; the three demiurge
   skills now belong to `agent-engineering`.
7. ~~Add functional and non-functional tests~~ — **done**. `scripts/test_sync_bundles.py`, 15 cases,
   wired into `run_unit_tests.py`, `.agents/local-ci.json` and a `bundle-parity` pre-commit hook.

### 5.1 As built

- **Guard is per-path, not project-wide.** The materializer only ever writes paths it owns (the
  plugin dir, its manifest, its `skills/<name>` links). A real file or a directory with different
  content at one of those paths is refused, never overwritten. A repo with uncommitted work can
  still install a bundle.
- **The library is never written to.** The regression test asserts the library tree is byte-identical
  before and after. This is the defect in §1.2, fixed by construction.
- **Scope is a flag.** `--scope project` (default) writes `<project>/.agents|claude|hermes/plugins/<b>/`;
  `--scope global` writes the harness home. `--project` selects the repo.
- **State is the plugin directories.** They are committable and self-describing, so `--check` is a
  pure read and needs no separate lock file.

---

## 6. Decisions taken (2026-11-07)

1. **Bundle manifests and the materializer live in demiurge.** agent-skills keeps only skill
   bodies. Demiurge owns the sync scripts, gates and tests.
2. **The baseline is the coding floor only** (§4.1). The three demiurge skills move to an
   `agent-engineering` bundle.
3. **OpenCode is out of scope for bundles.** Bundles target Antigravity, Claude Code and Hermes.
4. **Implement §5 end to end**, in phases, stopping at each gate.
