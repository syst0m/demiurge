<div align="center">
  <h1>Demiurge</h1>
  <p><b>Two autonomous agents in an empirical feedback loop. One researches; one designs.</b></p>
  <p>
    <a href="docs/DOCUMENTATION.md"><b>Master Documentation</b></a> •
    <a href="docs/INSTALLATION.md"><b>Installation Guide</b></a> •
    <a href="docs/OPERATING_GUIDE.md"><b>Operating Guide</b></a> •
    <a href="docs/AGENT_DESIGN.md"><b>Design Manual</b></a> •
    <a href="docs/BENCHMARKS.md"><b>Benchmarks</b></a>
  </p>
</div>

<div align="center">
  <img src="assets/demiurge_photo.jpg" width="400" alt="Demiurge Photo">
</div>

Demiurge isolates empirical research from agent synthesis. Self-contained, dependency-free, and anchored on deterministic quality gates.

| Agent | Responsibility | Core Principle |
|---|---|---|
| **Marcus** | Designs, scaffolds, audits, and proves agent skills. | Refuses to ship any agent without measured evidence. |
| **Buckminster** | Researches agentic engineering and standards. | Every claim requires 3 verified, hyperlinked sources. |

Named for Marcus Aurelius (wrote guidance, then followed it) and Buckminster Fuller (comprehensive anticipatory design science).

---

## Architecture

```
Buckminster ──proposes diff──> Operator Sign-Off ──merges──> research/RESEARCH.md
                                                                      │
                                                                   read by
                                                                      │
Agent Packages <──emits & proves── Marcus ──checks gates (G0-G6) <────┘
```

- **Strict One-Way Flow:** Buckminster researches; Marcus designs. Marcus never synthesizes an agent from claims absent from `research/RESEARCH.md`.
- **Human-in-the-Loop Governance:** Nothing merges into `research/RESEARCH.md` without operator approval.
- **Empirical Grounding:** Marcus ignores any claim absent from `research/RESEARCH.md`.
- **Deterministic Superiority over Prompts:** Invariants run as deterministic OS processes and automated gate harnesses:
  - **Negative Parallelism Defense:** Checked across pre-commit and Vale to eliminate rhetorical antithesis tropes across all documentation.
  - **Superfluous Comment Scanner:** `scripts/scan_superfluous.py` prevents chat transcripts, migration war stories, and session diaries from polluting code comments.
  - **Strict Reference Verification:** `scripts/check_links.py --strict` ensures all citations resolve to active markdown artifacts or external URIs.

For concrete LLD implementations (harnesses, gates, hooks, evals) and execution commands, see [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md).

---

## Core Documentation

Complete architectural details, Low-Level Design (LLD), and mechanical specifications are in [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md).

| Document | Audience | Scope |
|---|---|---|
| [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) | All | Top-Level Design (TLD), Low-Level Design (LLD), and full system specification. |
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Developer | Deployment to Claude Code, Antigravity, Gemini CLI, and custom harnesses. |
| [docs/OPERATING_GUIDE.md](docs/OPERATING_GUIDE.md) | Operator | Operational workflows, prompt examples, caveats, gotchas, and best practices. |
| [docs/AGENT_DESIGN.md](docs/AGENT_DESIGN.md) | Architect | Human companion guide: structural layers, decision trees, and checklists. |
| [skills/buckminster/references/RESEARCH_METHODOLOGY.md](skills/buckminster/references/RESEARCH_METHODOLOGY.md) | Researcher | Tri-source verification protocols, search disciplines, and evidence grading. |
| [research/RESEARCH.md](research/RESEARCH.md) | Both Agents | Canonical empirical knowledge base: benchmarks, failure modes, and standards. |
| [skills/marcus/AGENT_ARCHITECTURE.md](skills/marcus/AGENT_ARCHITECTURE.md) | Marcus | Machine specification for progressive disclosure and mechanical gate enforcement. |
| [docs/BENCHMARKS.md](docs/BENCHMARKS.md) | Evaluator | Independent industry benchmarking (SWE-bench, GAIA, Tau-bench) and metrics. |

---

## Repository Layout

| Path | Contents |
|---|---|
| `.agents/` | Canonical workspace configuration and path-scoped rules (`.agents/rules/`). |
| `assets/` | Project diagrams, media, and visual assets. |
| `docs/` | System documentation: Master Documentation, Installation, Operations, and Design. |
| `evals/` | Deterministic gate regression tests and independent industry benchmark adapters. |
| `research/` | Master empirical knowledge base (`RESEARCH.md`) maintained via reviewed proposals. |
| `scripts/` | Deterministic verification harnesses, security linters, link checkers, and sync tools. |
| `skills/` | Source definitions for Marcus (`skills/marcus/`) and Buckminster (`skills/buckminster/`). |

*Note: Edit files in `skills/` directly. Never edit deployed skill directories manually.*

---

## Evidence & Empirical Discipline

Demiurge rejects prompt folklore, marketing claims, and unmeasured assumptions. Every architectural decision, rule, and skill generation pipeline is grounded in verifiable empirical data:

1. **Tri-Source Verification (Rule K-6):** Every finding proposed for `research/RESEARCH.md` requires a minimum of three independent, hyperlinked citations. Peer-reviewed scientific literature is prioritized over open specifications; vendor reports are capped at one of the three.
2. **Strict Grounding Gate (G0 & G3):** Marcus mechanically rejects any design proposal or skill synthesis whose claims lack verified entries in `research/RESEARCH.md`.
3. **Evidence Confidence Taxonomy:** Claims in `research/RESEARCH.md` carry explicit confidence markers that dictate how Marcus acts upon them:

| Marker | Empirical Standard | Marcus Action & Architectural Enforcement |
|---|---|---|
| `[SETTLED]` | Replicated empirical data or adopted open standards. | Enforce as mandatory default architecture and deterministic gate policy. |
| `[CONTESTED]` | Conflicting empirical results or single un-replicated study. | Expose to operator as an explicit configurable trade-off; no silent defaults. |
| `[VENDOR]` | Originates from an entity commercially selling the solution. | Exclude from defaults; declare commercial conflict and require operator opt-in. |
| `[EMERGING]` | Mechanistically sound; lacks longitudinal production testing. | Document in architectural research notes; exclude from gating enforcement. |

---

## Independent Benchmarking & Validation

Demiurge measures its architectural efficacy against bare foundation models using standard industry benchmarks. Framework overhead is justified only when delivering a positive resolution lift ($\Delta > 0$) alongside lower net execution cost.

Complete benchmarking architecture, multi-benchmark roadmaps, telemetry formulas, and execution guides are documented in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

### Latest Benchmark Performance (`v0.2.0-swebench-001`)

Evaluated on [SWE-bench Lite](https://www.swebench.com/) comparing **Arm A (Bare Model)** against **Arm B (Demiurge Architecture)** using `claude-3-5-sonnet-20241022`:

| Metric | Bare Foundation Model | Demiurge Architecture | Net Lift / Delta |
|---|---|---|---|
| **Task Resolution Rate** | 40.00% (2 / 5) | **80.00% (4 / 5)** | **+40.00% ($\Delta$)** |
| **Prompt-Cache Hit Ratio** | 20.00% | **82.00%** | **+62.00%** |
| **Mean Turns to Solution** | 7.80 turns | **7.40 turns** | **-0.40 turns** |
| **Cost per Resolved Task** | $0.2050 | **$0.0533** | **-74.00%** |

- **Summary of Findings:** Demiurge achieved an 80% pass rate (+40% lift) by enforcing Marcus's local failure reproduction and pre-submission write gating. Anchoring static rules at `.agents/rules/` yielded an 82% prompt-cache hit ratio, cutting the cost per resolved task by 74%.
- **Detailed Reports:** See the [SWE-bench v0.2.0 Summary Report](docs/reports/swebench_v020_summary.md) for full telemetry breakdowns.
