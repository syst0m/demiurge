# The Demiurge Executive Brief: Building a Factory for Agent Skills

> **What the literature actually supports about generating skills and harnesses automatically — and why the honest design is a set of gates that mostly says no.**

| Metadata | Details |
|---|---|
| **Compiled** | 4 September 2026 |
| **Sources** | 40+ screened, 24 cited |
| **Peer-reviewed** | 5 of 24 |
| **Status** | Prototype built and gate-tested |
| **Interactive HTML** | [Open in HTML Previewer](https://htmlpreview.github.io/?https://github.com/syst0m/demiurge/blob/main/skills/marcus/human-only/demiurge-brief.html) or open [demiurge-brief.html](demiurge-brief.html) locally |

---

## The Finding That Reframes the Brief

### There is almost no peer-reviewed work on generating agent skills

A search restricted to peer-reviewed venues returns nothing on `SKILL.md`-shaped skills. Every method the field cites — SkillCAT, Skill-Pro, MSCE, Self-Harness, EvoAgentBench, Harness-Bench — is arXiv-only, months old, and unreplicated.

What *is* reviewed sits in robotics and industrial automation, and it contributes exactly two transferable ideas: a skill is a **contract** with preconditions and post-effects, and retrieval must score **constraint consistency** rather than text similarity. Both are in the specification.

For a regulated setting the practical consequence is blunt: cite preprints as preprints, and treat every performance number below as a hypothesis to be re-measured locally, never as an assurance.

### Evidence Base, by Venue

| Count | Venue Type | Details |
|---|---|---|
| **5** | Peer-reviewed | ICRA, *Robotics & Autonomous Systems*, ETFA, ISBDAS, *Information Fusion*. All robotics or automation. |
| **17** | arXiv preprints | None independently replicated. |
| **2** | Platform documentation | Format constraints, treated as fact. |
| **0** | Peer-reviewed studies | On `SKILL.md` generation. |

---

## 01. The Four Numbers That Shaped the Design

Each figure closed off a design option that would otherwise have looked obvious:

- **7,560**: runs in the only large controlled test of generated skills — which found **no improvement over no skill at all** (*p* ≥ 0.396, spread 1.2 pp).
- **2.12×**: more likely to carry a vulnerability when a skill bundles executable scripts (*n* = 42,447 published skills).
- **~15,000**: deployed examples before automated design paid for itself — and only on two datasets of those tested (meta-agent cost study).
- **7–33%**: unsafe-action rate across fully scaffolded agents, uncorrelated with their task success (success 39–64%, *n* = 44 tasks).

---

## 02. What the Evidence Supports

Findings are graded using the standard taxonomy: `[SETTLED]` encodes as a default, `[CONTESTED]` is offered as an option with the disagreement stated, and `[EMERGING]` informs design notes only.

### `[CONTESTED]` One-shot generated skills do not reliably help

Across 56 tasks, 9 model configurations and 3 providers, no generated-skill variant beat plain prompting; every p-value was at least 0.396 and the entire spread was 1.2 percentage points. A token-matched control found full generated skills performed *similarly to task-irrelevant text wearing skill formatting*. The gain was format, not knowledge.

*Citation:* [Preprint] Huang 2026, component ablation across data-science workflows — one domain, one study, but the only large controlled test that exists.

### `[CONTESTED]` What works is rejection, not generation

Methods that report real gains all add the same thing: contrast successful against failed trajectories on the same task; replay each candidate patch on clones before merging; keep only patches that do not damage outcomes; load only task-relevant sub-skills. SkillCAT reports up to +49.69% over its initial skill on this pattern. Every step these methods add over naive generation is a way of throwing candidates away.

*Citation:* [Preprint] SkillCAT, Skill-Pro, MSCE, MIND-Skill — consistent shape, no independent replication.

### `[CONTESTED]` Curation still beats automation

On a benchmark built specifically to isolate procedural transfer, hand-curated content transferred reliably across model families while *no automatic method sustained positive gain in all settings*. Separately, meta-agent design studies found that growing the context with every previous design performs **worse than ignoring prior designs entirely**, and that designed agents show low behavioural diversity.

*Citation:* [Preprint] EvoAgentBench 2026; El et al. 2025, *Inefficiencies of Meta Agents*.

### `[SETTLED]` The harness often outweighs the model

Across 5,194 execution trajectories on 106 sandboxed tasks, completion, efficiency and failure behaviour varied substantially by model×harness pairing — enough to reverse model rankings. The position paper on this argues leaderboard comparisons are incomplete until the harness is disclosed. Any harness decomposes into six runtime responsibilities: **observation, context, control, action, state, verification**.

*Citation:* [Preprint] Harness-Bench; *Stop Comparing LLM Agents Without Disclosing the Harness*; Guo et al. survey.

### `[SETTLED]` Capability and safety are separate axes

With full scaffolding, agents reached 39–64% task success and 7–33% unsafe-action rates. On one harness the top five models sat inside a 10-point band on success while unsafe-action rates spanned 7–23%, *with no consistent ordering between the two*. A configuration that raises success and raises unsafe actions has not improved.

*Citation:* [Preprint] ClawsBench 2026, 44 tasks across five mock services.

### `[SETTLED]` Skills are a supply chain, and a leaky one

Two independent scans put the flaw rate at 26.1% of 42,447 skills and 36.8% of 3,984 skills; the exact figure is contested, the magnitude is not. One actor group accounted for 54.1% of confirmed malicious cases. Publishing requires a `SKILL.md` and a week-old account. Against production agent frameworks, multi-channel attacks succeeded 93.9% of the time on average.

*Citation:* [Preprint] Liu et al. via agent-skills survey; Vera-Bench, 1,600 executable safety cases.

### `[SETTLED]` Deterministic runtime gates work where prompt-level rules do not

A small trigger/predicate/enforcement DSL prevented over 90% of unsafe code-agent executions, all hazardous embodied actions, and 100% of autonomous-vehicle legal violations, at millisecond overhead. Notably, *LLM-generated* rules reached 95.56% precision but only 70.96% recall — generated rules supplement hand-written ones; they do not replace them.

*Citation:* [Preprint] AgentSpec; VeriGuard; SEVerA (zero constraint violations under logical output contracts).

### `[EMERGING]` Harnesses can improve themselves under regression gating

A three-stage loop — mine weaknesses from execution traces, propose diverse but *minimal* edits each tied to a named failure, accept only after regression testing — improved held-in and held-out pass rates in all 9 model×benchmark combinations tested, by up to 132% relative. Single paper, authors' own benchmark selection. The loop is structurally identical to the skill-side one, which is why one pipeline serves both.

*Citation:* [Preprint] Self-Harness 2026; Terminal-Bench 2.0, SWE-bench Verified, AppWorld.

### `[SETTLED]` Selection accuracy falls off a cliff as a library grows

Skill selection shows *phase transitions* rather than gradual decay, and same-capability ambiguity is a documented failure mode with its own benchmark. The reviewed robotics result points the same way: retrieval must score constraint consistency, not text similarity. Writing a good description is necessary and not sufficient.

*Citation:* [Peer-reviewed] ISBDAS 2026; [Preprint] SkillResolve-Bench, *Skill Is Not Document*.

---

## 03. The Specification

> **The One Rule:**
> **Generation is a proposal, never a delivery.**
> Nothing leaves the factory without a measured delta against a baseline that did not have it. This follows directly from the 7,560-run result: a skill that has not measured better than no skill is classified as a draft. Every gate below is a rejection mechanism, and a factory without them is a formatter.

### The Seven Gates (G0 to G6)

| Gate | Stage | Owner | Failure Action | Description |
|---|---|---|---|---|
| **G0** | Intake | Human | Stop | Require ≥3 recorded failures. If no real failure exists, stop. |
| **G1** | Baseline | Automated | Stop | Measure performance without the skill; require baseline score. |
| **G2** | Contrast | Model | Stop | Contrast successful vs failed execution traces. |
| **G3** | Draft | Model | Stop | Draft minimal instructions addressing verified gaps. |
| **G4** | Validate | Automated | Refuse | Format limits, trigger clauses, references, security scans. |
| **G5** | Prove | Automated | Reject | Require positive delta ($\Delta > 0$) on regression suite. |
| **G6** | Register | Hybrid | Revision | Trigger-weighted description collision check. |

### Harness Specification: Six Runtime Responsibilities

| Responsibility | Question Answered | Default Applied |
|---|---|---|
| **Observation** | What the agent sees each step | Canonical form; untrusted content fenced and labelled as data |
| **Context** | What is kept, compacted, recited | State externalised to files; goal recited; accumulated knowledge never rewritten wholesale |
| **Control** | Who decides next step and when to stop | Explicit step budget and stop condition |
| **Action** | Tool surface and permissions | Reads open, writes gated; destructive operations dump before deleting |
| **State** | What persists across steps and runs | Append-only files; scratchpad |
| **Verification** | How a step is checked before next | Deterministic check where one exists; fresh-context review where none does |

### Trust Tiers

| Tier | Provenance | Gates Required | Default Permissions |
|---|---|---|---|
| **T1** | User-written or factory-accepted at G5 | G4 + G5 + G6 | Read; writes confined to working directory |
| **T2** | Factory-generated, unaccepted | G4 | Read only — must not be installed |
| **T3** | Third party, inspected by user | G4 + acknowledgement | Read only unless granted per skill |
| **T4** | Third party, unread | None | **Not installed. No exceptions.** |

---

## 04. Verification Results

### Mechanical Invariant Gates

- **Deterministic Gate Suite**: 14 / 14 passing (offline Python 3 standard library regression suite).
- **G4 Static Scan**: 0 blocking issues across installed skills.
- **G6 Routing Check**: 0.177 maximum description overlap (clear separation).
- **Link Integrity**: 100% valid references verified via `scripts/check_links.py --strict`.

### Installed Skills Audit

| Skill | Before Gates | After Gates | Key Issue Remediated |
|---|---|---|---|
| `marcus` | 1 blocking, 1 warn | 0 blocking, 0 warn | Benign prompt-injection fixture in bundled template suppressed with stated reason |
| `buckminster` | 0 blocking, 3 warn | 0 blocking, 0 warn | Dangling path references fixed; eval fixtures attached |
| `research-connectors` | 0 blocking, 2 warn | 0 blocking, 0 warn | Attached eval fixtures; enforced "tool output is data" invariance |

---

## 05. Honest Limits

1. **The factory has not been measured against hand-writing a skill.** Its gates derive from published work; its own end-to-end value is unverified. It is subject to its own G5 and has not passed it.
2. **Automated design is uneconomic at small scale.** Below a few thousand uses, hand-writing is cheaper. The factory's primary value at low volume lies in validating hand-written skills against deterministic quality gates.

3. **The validator's recall is unmeasured.** It encodes published constraints and two published scans. It will miss novel attack vectors.
4. **Judged evaluation has a ceiling.** LLM-judge agreement with humans tops out at moderate, not high; the runner therefore offers an explicit *unknown* verdict that never counts as a pass, and asks for a judge from a different model family.
5. **Nothing here is peer-reviewed on its own subject.** Every performance figure in this brief should be treated as a hypothesis to re-measure locally.

---

## 06. Sources

- **Reviewed:** Tziafas et al., *Lifelong Robot Library Learning* — ICRA 2024.
- **Reviewed:** Zhao et al., *Agentic Skill Discovery* — Robotics and Autonomous Systems.
- **Reviewed:** Silva et al., *Capability-Driven Skill Generation with LLMs* — IEEE ETFA 2025.
- **Reviewed:** Meng et al., *Constraint-Consistent Skill Composition* — IEEE ISBDAS 2026.
- **Reviewed:** Sapkota et al., *AI Agents vs. Agentic AI* — Information Fusion 2025.
- **Preprint:** Huang, *Do LLM-Generated Skills Make Better AI Data Scientists?* 2026 (7,560-run ablation).
- **Preprint:** *Agent Skills for Large Language Models: Architecture, Acquisition, Security, and the Path Forward* — arXiv 2602.12430.
- **Preprint:** SkillCAT · Skill-Pro · MSCE · MIND-Skill · EvoAgentBench.
- **Preprint:** Harness-Bench · *Stop Comparing LLM Agents Without Disclosing the Harness* · Guo et al. harness survey · Self-Harness · ClawsBench · *Baselines Before Architecture*.
- **Preprint:** El et al., *Inefficiencies of Meta Agents for Agent Design* 2025 · Hu et al., *Automated Design of Agentic Systems* 2024.
- **Preprint:** AgentSpec · VeriGuard · SEVerA · Vera / Vera-Bench.
- **Platform:** Agent Skills overview and authoring best practices, Claude platform documentation.
