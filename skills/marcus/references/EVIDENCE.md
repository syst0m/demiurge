# EVIDENCE.md — what the literature actually supports about generating skills and harnesses

```yaml
version: 1.0.0
snapshot_date: 2026-09-04
scope: automatic generation of agent skills and agent harnesses
consumed_by: marcus
sibling: RESEARCH.md   # general agentic engineering; not duplicated here
next_review_due: 2026-10-04
```

**Load before:** designing the pipeline, changing a gate, or arguing that a gate can be skipped.

Grades match Marcus's vocabulary so the two files read together:

| Grade | Meaning | The factory may |
|---|---|---|
| `[SETTLED]` | Multiple independent sources, at least some empirical | Encode as a default |
| `[CONTESTED]` | Credible sources disagree, or a single study | Offer as an option, state the disagreement |
| `[VENDOR]` | Claim originates with a party selling the thing | Do not encode |
| `[EMERGING]` | Real but too new to have been replicated | Design notes only |

---

## 0. The peer-review finding — read this first

`[SETTLED]` **There is essentially no peer-reviewed literature on generating Agent Skills.**

A deliberate search for peer-reviewed work (Consensus with `exclude_preprints`, plus scite over 210M
records) returns almost nothing on this exact topic. What comes back at a reviewed venue is
*robotics and industrial automation* skill-library work, which shares the vocabulary but not the
artefact:

| Reviewed venue | Work | What it is actually about |
|---|---|---|
| ICRA 2024 | Tziafas et al., *Lifelong Robot Library Learning* | Growing a robot manipulation skill library; a skill abstractor distils experience into library entries |
| *Robotics and Autonomous Systems* | Zhao et al., *Agentic Skill Discovery* | LLM proposes tasks, RL learns policies, a separate VLM verifies — skill library from zero |
| IEEE ETFA 2025 | Silva et al., *Capability-Driven Skill Generation with LLMs* | Capability-as-contract, RAG over the user's own libraries, generates conforming implementations |
| IEEE ISBDAS 2026 | Meng et al., *Constraint-Consistent Skill Composition* | Skills carry preconditions/post-effects; retrieval scored on constraint consistency, not text similarity |
| *Information Fusion* 2025 | Sapkota et al. | Conceptual taxonomy separating AI Agents from Agentic AI |

Everything specific to `SKILL.md`-shaped skills — SkillCAT, Skill-Pro, MSCE, MIND-Skill, SkillOS,
Self-Harness, EvoAgentBench, Harness-Bench, the agent-skills survey (arXiv 2602.12430) — is
**arXiv-only**. Citation counts on 2026 preprints are months old and are not a quality signal.

**Consequences the factory encodes:**

1. Cite preprints as preprints. Never launder an arXiv number into "research shows".
2. Two transferable ideas *are* reviewed, and both come from the robotics side: a skill is a
   **contract** (preconditions, post-effects, interface) — ETFA/ISBDAS — and retrieval must score
   **constraint consistency**, not text similarity — ISBDAS. Both are in the spec.
3. The field's own evidence standard is low. Measure locally; do not import benchmark numbers.

---

## 1. The finding that constrains the whole design

`[CONTESTED]` **A single LLM-generated skill, dropped in front of a task, does not reliably help.**

Huang (2026), *Do LLM-Generated Skills Make Better AI Data Scientists?* — the largest controlled
ablation on this question:

- 56 tasks, 9 model configurations, 3 providers → **7,560 runs**, plus 1,512 more in a token-matched
  control.
- One generated skill per data-science lifecycle stage (preparation, extraction, analysis, reporting).
- **No variant beat No-Skill prompting.** All p ≥ 0.396. Total spread across every variant: **1.2 pp**.
- Component ablation found no single part carrying the value either.
- The token-matched control is the damning part: full generated skills performed **similarly to
  task-irrelevant content in skill format**. The gain was formatting, not knowledge.

Graded `[CONTESTED]` because it is one study, in one domain, on one-shot generation — but it is the
only large controlled test that exists, and it points one way.

**The factory's founding rule follows from it:** *generation is a proposal, never a delivery.* A
skill that has not measured better than no skill is not a skill; it is a draft. Gate **G5** exists
entirely because of this finding.

---

## 2. What makes generated skills work when they do work

`[CONTESTED]` — consistent across several preprints, no independent replication.

| Mechanism | Source | Reported |
|---|---|---|
| **Contrast success against failure** on the *same* task, several trajectories each, to isolate what explains the outcome difference | SkillCAT (arXiv 2606.13317) | up to **+49.69%** over the initial skill |
| **Replay each candidate patch** on clones of its source task; keep only patches that do not damage outcomes; merge hierarchically | SkillCAT | — |
| **Gate on verification, not plausibility** — a PPO-style gate over semantically generated candidates | Skill-Pro | superior reuse rates under heavy memory compression |
| **Attach applicability boundaries, verification rules and reliability estimates** to each skill; keep evidence links back to the trace | MSCE | outperforms skill- and memory-augmented baselines |
| **Route to task-relevant sub-skills** rather than loading the whole corpus | SkillCAT (TTE) | — |

The shared shape: *many trajectories → contrastive extraction → replay validation → selective merge
→ conditional loading*. Every step these methods add over naive generation is a **rejection
mechanism**. That is the difference between them and the Huang result.

`[CONTESTED]` **Automation does not yet beat curation.** EvoAgentBench (528/267 split, 2 scaffolds,
3 backbones) reports that hand-curated ability content **transfers reliably across model families**,
while **"no current automatic method sustains positive gain in all settings."**

**Encoded as:** the factory is a human-in-the-loop assembly line with automated gates, not an
autonomous skill generator. It proposes; a person accepts.

---

## 3. Meta-agent economics and the context pathology

`[CONTESTED]` — El et al. (2025), *Inefficiencies of Meta Agents for Agent Design*, examining the
ADAS / Meta-Agent-Search family:

- **Growing the context with every previous design performs *worse* than ignoring prior designs
  entirely.** An evolutionary approach — a selected archive, not an accumulated transcript — beats both.
- Designed agents show **low behavioural diversity**, so the usual "generate many, then ensemble"
  escape is weaker than assumed.
- **Cost.** Design-plus-deploy beat human-designed agents on only **two datasets**, and only past
  ~15,000 deployed examples. Below that scale, automated design does not pay for itself.

For context, ADAS itself (Hu et al. 2024, arXiv) originated the meta-agent-in-code idea, and
SwarmAgentic reports +261.8% over ADAS on TravelPlanner — the authors' own method on their own
selection. `[VENDOR]`-adjacent; not encoded.

**Encoded as:** the factory keeps a *selected archive* of accepted skills with their measured deltas,
never a running transcript of everything it has generated. And it states the economics up front:
below roughly a few thousand uses, hand-writing the skill is cheaper than an automated design loop.

---

## 4. Harnesses

`[SETTLED]` **The harness is a first-class experimental variable, often dominating model choice.**

- *Stop Comparing LLM Agents Without Disclosing the Harness* (arXiv 2026) formalises the **Binding
  Constraint Thesis**: at comparable frontier capability, harness configuration governs more variance
  than model choice — including **model ranking reversals** — so current leaderboards systematically
  misattribute harness gains to models.
- **Harness-Bench** (106 sandboxed tasks, **5,194 trajectories**) finds substantial variation in
  completion, process quality, efficiency and failure behaviour across model×harness pairings, and
  concludes capability should be **reported at the model-harness configuration level**.
- **ClawsBench** decomposes scaffolding into two independent levers — *domain skills injected via
  progressive disclosure* and *a coordinating meta-prompt* — and varies both. With full scaffolding:
  39–64% task success but **7–33% unsafe action rates**; on one harness the top five models sit inside
  a 10-point band on success while unsafe-action rates span 7–23%, **with no consistent ordering
  between the two metrics**. Capability and safety are separate axes and must be reported separately.
- *Baselines Before Architecture* (XBOW, 104 tasks) finds plain coding CLIs already solve a large
  share, and repeated plain-agent runs can match published specialised-harness scores in union coverage.

`[SETTLED]` **The six runtime responsibilities.** Guo et al.'s survey decomposes any execution harness
into **observation, context, control, action, state, verification**. This is the most useful structural
result available and is the backbone of the harness line in the spec.

`[EMERGING]` **Harnesses can improve themselves under regression gating.** *Self-Harness* (arXiv 2026):
a three-stage loop — **Weakness Mining** from execution traces → **Harness Proposal** (diverse but
*minimal* edits tied to specific failures) → **Proposal Validation**, accepting only after regression
testing. Across 9 model×benchmark combinations (Terminal-Bench 2.0, SWE-bench Verified, AppWorld),
every final harness improved held-in *and* held-out pass rates, up to **+132% relative**.

Single paper, no replication, authors' own benchmark selection → `[EMERGING]`. But the loop is
structurally identical to the skill line's contrast → propose → replay-validate. **One pipeline, two
product lines** is an evidence-supported design, not a convenience.

`[EMERGING]` Harness choice changes the agent's *beliefs*, not only its score — blocked actions,
compressed repairs and selective verification can preserve terminal success while altering the beliefs
that drive later decisions (*Harness-Induced Belief Divergence*, 2026).

**Encoded as:** every emitted harness declares its configuration across the six responsibilities;
every measurement records the model-harness pair; a plain-agent baseline is mandatory before any
harness is credited with a gain.

---

## 5. Security and supply chain

`[SETTLED]` **A large minority of published skills carry security flaws.** Two independent scans
disagree on the number, which is itself informative:

| Scan | Corpus | Finding |
|---|---|---|
| Liu et al., via arXiv 2602.12430 | 42,447 community skills | **26.1%** contain ≥1 vulnerability; skills bundling executable scripts are **2.12×** more likely to be vulnerable; one actor group accounts for **54.1%** of confirmed malicious cases |
| Scan in Marcus's RESEARCH.md §6 | 3,984 published skills | **36.8%** with ≥1 flaw, **13.4%** critical, 76 confirmed malicious payloads, **91%** using prompt injection |

`[SETTLED]` that the rate is high and that script-bundling raises it; `[CONTESTED]` on the exact
figure. Both agree the barrier to publishing is a `SKILL.md` and a new account.

`[SETTLED]` **Runtime enforcement works where prompt-level guardrails do not.**

- **AgentSpec** (arXiv): a small DSL of trigger/predicate/enforcement rules prevents **>90%** of unsafe
  code-agent executions, **all** hazardous embodied actions, and **100%** AV legal compliance, at
  millisecond overhead. LLM-generated rules reached 95.56% precision / 70.96% recall — **generated
  rules are usable but under-recall; they supplement hand-written rules, never replace them.**
- **VeriGuard**: offline synthesise-and-verify a policy, then cheap online per-action monitoring — the
  split that makes formal methods affordable at runtime.
- **SEVerA** (2026): self-evolving agents under first-order-logic output contracts with verified
  fallback — **zero constraint violations** while still improving the soft objective. Direct evidence
  that gating a generative loop on contracts need not cost quality.
- **Vera / Vera-Bench** (1,600 executable safety cases, 124 risk categories) reports **93.9% average
  attack success under multi-channel attacks** against production agent frameworks. Assume the
  generated artefact is attackable.

`[SETTLED]` The four-tier provenance → verification-gate → permission model proposed in the
agent-skills survey is the only governance scheme on offer. Adopted, with its origin stated.

**Encoded as:** the validator refuses to pass a skill that bundles scripts without an explicit,
acknowledged justification; every emitted skill carries a provenance record and a trust tier; no
generated skill inherits write permissions by default.

---

## 6. Selection and routing degrade with library size

`[SETTLED]` **Writing a good description is necessary and not sufficient.**

- The survey reports **phase transitions in skill selection accuracy** as the library grows — quality
  does not decay smoothly, it falls off a cliff.
- **SkillResolve-Bench** (arXiv 2606.10388) exists specifically because of *same-capability
  ambiguity*: two skills that both plausibly cover a request.
- *Skill Is Not Document* (arXiv 2606.03565): retrieval must model **query-conditioned compatibility**,
  not document similarity — the preprint echo of the reviewed ISBDAS constraint-consistency result.
- **Skill Drift Is Contract Violation** (arXiv 2605.10990): skills rot as their environment moves;
  maintenance must be proactive.

**Encoded as:** gate **G6** checks a new description for collision against the installed library and
fails on excessive overlap. A skill that cannot be distinguished from an existing one is a *revision*
of that skill, not a new skill.

---

## 7. Format constraints (the platform, not the literature)

`[SETTLED]` from the Claude platform docs; these are validator rules, not opinions.

- `name`: ≤64 chars, lowercase/digits/hyphens only, no XML tags, must not contain `anthropic` or `claude`.
- `description`: non-empty, ≤1024 chars, no XML tags, **third person**, states *what* and *when*.
- Body: **under 500 lines**; metadata ~100 tokens per skill always loaded; body ideally under 5k tokens.
- References **one level deep from SKILL.md** — nested references get partially read (`head -100`).
- Reference files over 100 lines need a **table of contents**.
- **Forward slashes always**, even on Windows.
- Loading is three-tier: discovery (name + description) → activation (SKILL.md) → execution (bundled files).
- MCP tools referenced as `ServerName:tool_name`.
- Degrees of freedom matched to fragility: high (prose) / medium (parameterised script) / low (exact command).
- Scripts are executed, not read — their source never enters context, only their output.

`[SETTLED]` **Eval-driven development is the documented method**: identify gaps by running *without*
the skill, build ≥3 evaluations, establish a baseline, write minimal instructions, iterate. Test
across model tiers — what suits Opus may under-specify for Haiku.

---

## 8. What this evidence does not support

State these when asked, rather than implying the factory is more than it is:

- That an automatically generated skill will improve anything. §1.
- That an automated design loop pays for itself at small scale. §3.
- That any benchmark number here predicts your deployment. §4, and Marcus's RESEARCH.md §4.
- That prompt-level instructions mitigate prompt injection. §5.
- That the factory's own output is exempt from §1. It is not. It measures itself.

---

## Change log

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-09-04 | Initial extraction. Consensus (peer-review-filtered and unfiltered), scite, Claude platform docs, agent-skills survey arXiv 2602.12430. Sibling to Marcus's RESEARCH.md 1.0.0 — general agentic findings live there and are not repeated. |
