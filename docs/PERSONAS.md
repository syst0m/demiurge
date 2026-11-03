# The Four Personas

Demiurge is a Pantheon of four personas. Three of them are agents you call by name. The fourth, Demiurge, is the system that holds them together.

| Persona | Role | You call it with | Reads | Writes |
|---|---|---|---|---|
| [Demiurge](#demiurge) | The system: gates, release, ledger, benchmarks | Scripts and hooks (no slash command) | Everything | Nothing on its own |
| [Niccolo](#niccolo) | Researches agentic engineering | `/niccolo` | The web, scholarly connectors | Diff proposals to `research/` |
| [Marcus](#marcus) | Designs and proves agent skills | `/marcus` | `references/RESEARCH.md` | Installable skill packages |
| [Imhotep](#imhotep) | Builds your real deliverables | `/imhotep` | Marcus's registry, `RESEARCH.md` | Your deliverable and a judge report |

```text
Niccolo ──proposes diff──> You approve ──merges──> research/RESEARCH.md
                                                          │
Skill packages <──emits & proves── Marcus <──────────────┘
      │
   equips
      ▼
   Imhotep ──builds──> held-out judge ──outcomes──> run ledger ──> Niccolo & Marcus
```

Every command on this page runs from the root of the demiurge checkout. Set `DEMIURGE_REPO` to that path. A persona that finds the variable unset asks you for the path.

---

## Demiurge

![Demiurge](../assets/demiurge.jpg)

> "The world is a fabrication of an error."
>
> — *The Gospel of Philip* (Nag Hammadi)

Demiurge is the system around the three agents. It has no slash command and no `SKILL.md`. It is the set of scripts, hooks and rules that make the agents prove their work.

### What it does

- **Gates.** Pre-commit hooks scan for secrets and PII, rhetorical tropes, superfluous commentary and session transcripts. They also check Markdown, prose style, release integrity and vendored file pins.
- **Release.** One script tags, pushes the tag, creates the GitHub release and verifies it.
- **Run ledger.** Records which skill ran, in which harness, with which model, and whether you marked it good or bad. It holds metadata only and never scores a skill.
- **Benchmarks.** Compares the framework against the bare model. A framework change must show a positive resolution lift and a lower cost.
- **Self-harness `[EMERGING]`.** An opt-in loop that diagnoses failures and proposes harness changes. A human merge decides each one.
- **Standing orders.** Rules for every agent session in the repository, for example the GitHub minutes gate.

### Commands

| Task | Command |
|---|---|
| Can GitHub Actions run now? Run before any PR. | `python scripts/gh_minutes_gate.py --status` |
| Run all unit tests | `python scripts/run_unit_tests.py` |
| Check every Markdown link | `python scripts/check_links.py --strict` |
| Check skills across harnesses | `python scripts/check_harness_parity.py` |
| Check the skill copies in the repo | `bash scripts/sync-skills.sh --check --repo-only` |
| Deploy skills to Claude Code and Antigravity (you run this) | `bash scripts/sync-skills.sh` |
| Cut a release | `python scripts/verify_release.py --cut` |
| Label a run for failure intake | `python scripts/ledger/ledger.py verdict <run_id> --label ok\|bad` |
| Build the local skill registry | `python scripts/registry/build_registry.py` |
| Check vendored upstream files | `python scripts/vendor_sync.py --fetch` |
| Refresh the research brief gist | `python scripts/sync_brief_summary.py` |
| Install the portable pre-commit hook | `bash scripts/install-git-hook.sh` |
| Add the skills to Hermes as commands | `python scripts/sync-hermes-commands.py` |

### Read more

- [Standing Orders](STANDING_ORDERS.md), [Run Ledger](RUN_LEDGER.md), [Skill Registry](SKILL_REGISTRY.md)
- [Benchmarks](BENCHMARKS.md), [Self-Harness](SELF_HARNESS.md)
- [Master Documentation](DOCUMENTATION.md)

---

## Niccolo

> "For this can be said about men in general: that they are ungrateful, fickle, dissembling, hypocritical, cowardly, and greedy for gain."
>
> — *The Prince* (Chapter XVII)

Niccolo researches the current state of agentic engineering. It judges a claim by its evidence and trusts no claim on its own word. It proposes changes to `research/RESEARCH.md`, the only file Marcus treats as established fact.

### What it does

- **Verifies each claim with three sources.** A finding needs at least 3 independent, hyperlinked sources, and at most 1 may be a vendor.
- **Grades each claim.** `[SETTLED]`, `[CONTESTED]`, `[VENDOR]` or `[EMERGING]`. See [Evidence](EVIDENCE.md).
- **Proposes a diff and never a rewrite.** The diff lists new findings, reclassifications, contradictions, retractions and a statement of what was re-checked and still holds.
- **States the consequence for Marcus.** It names which generation rules a change would alter.
- **Never approves its own work.** You merge the pull request.

### Commands and prompts

| Task | How |
|---|---|
| Verify one claim | `/niccolo` then describe the claim. Ask for a graded finding. |
| Run a research pass on topics | `/niccolo /goal` then list the topics and ask for a diff proposal against `research/RESEARCH.md`. |
| Pay down source debt first | `python scripts/research/grade_cap.py --debt --limit 10` |
| Cap grades by their sources | `python scripts/research/grade_cap.py --write` |
| Confirm the ledger is consistent | `python scripts/research/grade_cap.py --check` |
| Run the scheduled sweep | Follow [`routines/research-sweep.md`](../routines/research-sweep.md). It works in its own git worktree and opens a pull request. |
| Verify an upgrade in a fresh context | Follow [`routines/research-verifier.md`](../routines/research-verifier.md). |

Example prompt:

```text
/niccolo
Verify whether storing conversation state in vector stores improves long-horizon
agent task completion compared to plain markdown files.
Cross-reference empirical benchmarks and return a graded finding.
```

### Integrations

Four scholarly connectors improve research quality. None is required. Without them Niccolo falls back to web search and open archives, and it says in the proposal that citation reception was not checked. A finding with no reception check cannot reach `[SETTLED]`.

| Connector | Use |
|---|---|
| [Undermind](https://undermind.ai) | Deep literature search and full-text PDFs |
| [scite](https://scite.ai/mcp) | Smart Citations and retraction notices |
| [Consensus](https://consensus.app) | Search across PubMed, Semantic Scholar and arXiv |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov) | Biomedical only. Niccolo does not use it for agentic engineering. |

### Read more

- [Research Methodology](../skills/niccolo/references/RESEARCH_METHODOLOGY.md), [Research Pipeline](RESEARCH_PIPELINE.md), [Claims Ledger](CLAIMS_LEDGER.md)
- [Skill file](../skills/niccolo/SKILL.md)

---

## Marcus

![Marcus](../assets/marcus.jpg)

> "Of each particular thing, ask: What is it in itself, in its own constitution? What is its substance and material?"
>
> — *Meditations* (Book 8.11)

Marcus designs, generates, audits and measures agent skills and harness configurations. Marcus refuses to ship anything not measured against a baseline.

### What it does

- **Runs a 7-step pipeline** (Elicit, Classify, Derive, Draft, Emit, Verify, Hand off) checked by 7 mechanical gates, G0 to G6.
- **Refuses ungrounded work.** G0 needs 3 real failure traces. G5 needs a measured improvement over a baseline that did not have the skill.
- **Emits packages** for Claude, Claude Code, Gemini, Gemini CLI, `AGENTS.md`, CLI harnesses and web chat.
- **Audits third-party skills.** An unread third-party skill is trust tier T4 and is not installed.
- **Works offline.** The scripts use the Python standard library only.

### Slash commands

| Command | What it does |
|---|---|
| `/marcus help` or `/marcus --help` | Prints the G0 checklist and command syntax. Changes nothing. |
| `/marcus generate <name>` or `/marcus create <name>` | Designs and scaffolds a new skill, from intake (G0) to the install-scope question (G6). |
| `/marcus modify <path-or-name>` or `/marcus edit <path-or-name>` | Adds a feature to an existing skill. Needs evidence of a gap and checks for regressions. |
| `/marcus audit <path-or-url>` or `/marcus review <path-or-url>` | Scans a skill for format and security flaws and assigns a trust tier. |
| `/marcus update` or `/marcus --update` | Syncs Marcus with the latest `RESEARCH.md` and reports which rules changed. |
| `/marcus --simulate <task>` or `/marcus --dry-run` | Walks G0 to G6 in memory with synthetic traces. Output is labeled `[SIMULATION — NOT MEASURED]`. |
| `/marcus interactive` or `/marcus ui` | Opens the intake dialog and the pipeline board. |

Example prompt:

```text
/marcus generate pg-migrations
Real failures:
1. Running DDL without a transaction.
2. Dropping a column before the application stopped using it.
3. Taking exclusive table locks during peak traffic.
Target platforms: Antigravity and Claude Code.
```

### Scripts

Run these from `skills/marcus/`. They need no network except `eval_runner.py`, which spends model calls and refuses to run without `--yes`.

| Gate | Command |
|---|---|
| G1 baseline | `python scripts/eval_runner.py <skill> --baseline` |
| G4 format and security | `python scripts/validate_skill.py <skill>` |
| G5 proof | `python scripts/eval_runner.py <skill>` |
| G6 route collision | `python scripts/route_check.py <skill> --library <skills-dir>` |
| G6 install scope | `python scripts/install_skill.py <skill> --describe` |
| Self-update | `python scripts/update_marcus.py --check` |
| Own regression suite | `python evals/run_gate_tests.py` |

### Integrations

At the end of G6 Marcus lists each hook in plain words and asks where the skill should live: **Project**, **Global** or **Staging**. Marcus never edits `~/.claude/settings.json` or `~/.gemini/config/hooks.json`. Antigravity has no skill-level hooks, so a hook that must run there needs a project install.

### Read more

- [Operating Guide](OPERATING_GUIDE.md), [Design Manual](AGENT_DESIGN.md)
- [Agent Architecture Spec](../skills/marcus/AGENT_ARCHITECTURE.md), [Gate Spec](../skills/marcus/references/SPEC.md)
- [Skill file](../skills/marcus/SKILL.md)

---

## Imhotep

![Imhotep](../assets/imhotep.jpg)

> "If you do not make yourself equal to God, you cannot understand God: for the like is not intelligible save to the like."
>
> — *Corpus Hermeticum* (Book XI)

Imhotep builds your real deliverables at the ambitious level. The governing rule: ambition on the target, conservatism on the judge. The goal can be unreasonable. The check that scores it cannot be soft.

### What it does

- **Raises the goal first.** It follows the vendored [be-ambitious](https://github.com/robonuggets/be-ambitious) procedure (Altitude, Depth, Range) plus an evidence overlay, and writes a one-screen Build Brief.
- **Grounds each choice.** Each brief line carries a `RESEARCH.md` claim id, or the label "my judgement".
- **Equips itself from Marcus's registry.** It prefers measured skills. When a method has no skill, it writes a build request for Marcus.
- **Writes the judge first.** It writes visible checks. A fresh-context subagent writes held-out checks under `.judge/heldout/`, and Imhotep never opens them.
- **Builds as the single writer,** then runs both suites and `judge_guard.py`.
- **Reports real numbers.** A missed target with real numbers passes. A gamed check fails.

### Commands and prompts

| Task | How |
|---|---|
| Build, fix, ship or analyse something properly | `/imhotep <task>` |
| Rewrite a prompt at a higher level | `/imhotep` with the prompt. It stops after the rewrite. |
| Natural-language triggers | "be ambitious", "aim higher", "go deeper", "what would a top expert do", "raise the bar" |
| Check the judge was not touched | `python skills/imhotep/scripts/judge_guard.py --base <commit> --paths <judge paths>` |
| Record the outcome | `python scripts/ledger/ledger.py verdict <run_id> --label ok\|bad` |
| Build the registry it reads | `python scripts/registry/build_registry.py` |

Example prompt:

```text
/imhotep the marcus PROVENANCE research snapshot is behind claims.json
```

### Integrations

- **Marcus's registry** at `~/.demiurge/registry.yaml` supplies the skills it equips.
- **The run ledger** records each verdict. A failure caused by a skill goes to Marcus through `ledger.py promote`.
- **Routines.** When the goal is durable, Imhotep writes a proposed `routines/<name>.md`. You approve it. It never schedules one itself.
- **Not for** research questions (Niccolo) or skill design (Marcus).

### Read more

- [Imhotep Evaluation](IMHOTEP_EVALUATION.md), [Overlay](../skills/imhotep/references/OVERLAY.md)
- [Skill file](../skills/imhotep/SKILL.md)

---

## Using the personas in each harness

| Harness | How to call a persona | Setup |
|---|---|---|
| Claude Code | `/marcus`, `/niccolo`, `/imhotep` | `bash scripts/sync-skills.sh` |
| Antigravity IDE | `@marcus`, `@niccolo`, `@imhotep` | Open the repository. It finds `skills/` and `.agents/`. |
| Antigravity CLI (`agy`) | Same as the IDE | `npx skills add path/to/demiurge/skills/<name>` |
| Hermes | Plugin commands | `python scripts/sync-hermes-commands.py` |
| Claude web | Name the persona in the prompt | Add the `SKILL.md` files and `research/RESEARCH.md` to a Project |
| Gemini (AI Studio, Gem) | Name the persona in the prompt | Paste the `SKILL.md` files and `research/RESEARCH.md` |
| ChatGPT | Name the persona in the prompt | Upload the same files to a Custom GPT |
| Cline, Copilot, Codex | Ask it to act as the persona | Point it at `skills/<name>/SKILL.md` |

Full steps: [Installation Guide](INSTALLATION.md). Typical workflows and gotchas: [Operating Guide](OPERATING_GUIDE.md).
