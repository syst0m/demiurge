<div align="center">
  <h1>Demiurge</h1>
  <p><b>Two autonomous agents in an empirical feedback loop. One researches; one designs.</b></p>
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

- **Strict One-Way Flow:** Buckminster researches; Marcus designs. Marcus ignores claims unlisted in `research/RESEARCH.md`.
- **Human Governance:** Knowledge base updates require explicit operator approval.
- **Deterministic Gates:** Invariants execute via OS processes: Vale for trope elimination, [scripts/scan_superfluous.py](scripts/scan_superfluous.py) for comment hygiene, and [scripts/check_links.py](scripts/check_links.py) for reference integrity.

---

## Documentation

| Guide | Scope & Focus |
|---|---|
| [Master Documentation](docs/DOCUMENTATION.md) | Top-Level Design (TLD), Low-Level Design (LLD), and full system specification. |
| [Installation Guide](docs/INSTALLATION.md) | Deployment to Claude Code, Antigravity, Gemini CLI, and custom harnesses. |
| [Operating Guide](docs/OPERATING_GUIDE.md) | Operational workflows, prompt templates, 7 gotchas, and best practices. |
| [Design Manual](docs/AGENT_DESIGN.md) | Human companion guide: structural layers, decision trees, and checklists. |
| [Benchmarks Guide](docs/BENCHMARKS.md) | Independent evaluation (SWE-bench, GAIA, Tau-bench) and metrics engine. |
| [Research Methodology](skills/buckminster/references/RESEARCH_METHODOLOGY.md) | Tri-source verification protocols, search disciplines, and evidence grading. |
| [Empirical Knowledge Base](research/RESEARCH.md) | Canonical empirical research: benchmarks, failure modes, and primitives. |
| [Agent Architecture Spec](skills/marcus/AGENT_ARCHITECTURE.md) | Progressive disclosure specifications and mechanical gate enforcement (G0–G6). |

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

Architectural decisions anchor exclusively in verifiable empirical data:

- **Tri-Source Verification (Rule K-6):** Findings require three independent citations; peer-reviewed research prioritized; vendor citations capped at one.
- **Strict Grounding Gates (G0 & G3):** Marcus blocks skill synthesis absent validated entries in `research/RESEARCH.md`.
- **Confidence Taxonomy:**

| Marker | Standard | Architectural Action |
|---|---|---|
| `[SETTLED]` | Replicated empirical data or open standards. | Mandatory default architecture; deterministic gate policy. |
| `[CONTESTED]` | Conflicting data or single un-replicated study. | Configurable operator trade-off; requires explicit selection. |
| `[VENDOR]` | Produced by commercial vendor. | Opt-in requirement; flagged commercial interest. |
| `[EMERGING]` | Mechanistically sound; unverified in production. | Documented in research notes; excluded from gating. |

---

## Independent Benchmarking & Validation

Demiurge validates framework utility against bare foundation models. Architectural overhead requires positive resolution lift ($\Delta > 0$) and reduced unit cost. Specifications reside in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

### Latest Benchmark: SWE-bench Lite (`v0.2.0-swebench-001`)

Evaluated on [SWE-bench Lite](https://www.swebench.com/) (Arm A: Bare Model vs. Arm B: Demiurge) using `claude-3-5-sonnet-20241022`:

| Metric | Bare Foundation Model | Demiurge Architecture | Delta ($\Delta$) |
|---|---|---|---|
| **Task Resolution Rate** | 40.00% (2 / 5) | **80.00% (4 / 5)** | **+40.00%** |
| **Prompt-Cache Hit Ratio** | 20.00% | **82.00%** | **+62.00%** |
| **Mean Turns to Solution** | 7.80 | **7.40** | **-0.40** |
| **Cost per Resolved Task** | $0.2050 | **$0.0533** | **-74.00%** |

Gate enforcement and test reproduction drove the 80% resolution rate (+40% lift). Anchoring static rules at `.agents/rules/` achieved an 82% cache hit ratio, cutting cost per fix by 74%. Telemetry details are in the [SWE-bench v0.2.0 Summary Report](docs/reports/swebench_v020_summary.md).
