<div align="center">
  <h1>Demiurge</h1>
  <p><b>Two autonomous agents in an empirical feedback loop. One researches; one designs.</b></p>
  <p>
    <a href="docs/DOCUMENTATION.md"><b>Master Documentation</b></a> •
    <a href="docs/INSTALLATION.md"><b>Installation Guide</b></a> •
    <a href="docs/OPERATING_GUIDE.md"><b>Operating Guide</b></a> •
    <a href="docs/AGENT_DESIGN.md"><b>Design Manual</b></a>
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
  - **Negative Parallelism & Trope Defense:** Checked across pre-commit (`scripts/gate_tropes.py`, `scripts/gate-tropes.sh`) and Vale (`.vale/styles/Foundry/NegativeParallelism.yml`). Vale uses Go RE2 without lookaround or backreferences; it concatenates `raw` entries sequentially, requiring all alternate forms in a single unified regex. Catches front-negated and tail-negated patterns across markdown.
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

---

## Repository Layout

| Path | Contents |
|---|---|
| `.agents/` | Canonical workspace configuration and path-scoped rules (`.agents/rules/`). |
| `assets/` | Project diagrams, media, and visual assets. |
| `docs/` | System documentation: Master Documentation, Installation, Operations, and Design. |
| `research/` | Master empirical knowledge base (`RESEARCH.md`) maintained via reviewed proposals. |
| `scripts/` | Deterministic verification harnesses, security linters, link checkers, and sync tools. |
| `skills/` | Source definitions for Marcus (`skills/marcus/`) and Buckminster (`skills/buckminster/`). |

*Note: Edit files in `skills/` directly. Never edit deployed skill directories manually.*

---

## Evidence Grading

Claims in `research/RESEARCH.md` require explicit confidence markers:

| Marker | Standard | Marcus Action |
|---|---|---|
| `[SETTLED]` | Replicated empirical data or adopted open standards. | Enforce as default architecture and gate policy. |
| `[CONTESTED]` | Conflicting empirical results or single un-replicated study. | Expose to operator as a configurable option. |
| `[VENDOR]` | Originates from an entity commercially selling the solution. | Exclude from defaults; declare commercial conflict. |
| `[EMERGING]` | Mechanistically sound; lacks longitudinal production testing. | Document in design notes only; exclude from gates. |
