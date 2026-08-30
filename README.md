<div align="center">
  <h1>Demiurge</h1>
</div>

<div align="center">
  <img src="assets/demiurge_photo.jpg" width="400" alt="Demiurge Photo">
</div>

Two agents that build and maintain other agents. Self-contained, with zero external dependencies.

> **[Installation & Setup Guide](docs/INSTALLATION.md)**
> Inject Marcus and Buckminster into Claude, Gemini, OpenAI, or your local IDE.

| Agent | Role |
|---|---|
| **Marcus** | Designs and generates agents. Emits them as installable packages (Claude, Gemini, CLI, web chat). |
| **Buckminster** | Researches agentic engineering. Proposes graded updates to Marcus's knowledge base. |

Named for Marcus Aurelius (wrote guidance, then followed it) and Buckminster Fuller (comprehensive anticipatory design science).

## Architecture

```
Buckminster ──writes──> research/RESEARCH.md ──read by──> Marcus ──generates──> agent packages
     ▲                                                        │
     └──────────── user signs off on every change ────────────┘
```

**One-directional flow:** Buckminster researches, Marcus designs. If Marcus lacks a fact, it halts and requests a Buckminster research pass. Ungraded facts cannot bypass this loop.

## Directory Layout

| Path | Purpose |
|---|---|
| `research/RESEARCH.md` | **The shared snapshot.** Writable only by Buckminster. |
| `skills/marcus/` | Marcus's source files (`SKILL.md`, `AGENT_ARCHITECTURE.md`, templates). |
| `skills/buckminster/` | Buckminster's source files (`SKILL.md`, `RESEARCH_METHODOLOGY.md`). |
| `scripts/sync-skills.sh` | Deploys to `~/.claude/skills/` and distributes `RESEARCH.md`. |

**Rule:** Edit `skills/` directly. Never edit `~/.claude/skills/` (it will be overwritten).

## Maintained Documents

| File | Audience | Trigger |
|---|---|---|
| `AGENT_ARCHITECTURE.md` | Machine (Marcus's generation spec) | `RESEARCH.md` version bump |
| `docs/AGENT_DESIGN.md` | Human (Flowcharts, checklists) | `RESEARCH.md` version bump |

Marcus tags generated files with a `derived_from` header pointing to the `RESEARCH.md` version. If `RESEARCH.md` changes, Marcus reports the drift but does not silently regenerate old agents. Production agents remain pinned to their snapshot.

## Evidence Grading

Every claim in `RESEARCH.md` requires a marker. This dictates Marcus's behavior:

| Marker | Criteria | Marcus Action |
|---|---|---|
| `[SETTLED]` | Multiple independent/empirical sources | Encode as default behavior. |
| `[CONTESTED]` | Conflicting credible sources, or single study | Offer as an option. State the disagreement. |
| `[VENDOR]` | Source sells the solution | Do not encode. Cite conflict if mentioned. |
| `[EMERGING]` | Real, but untested in production | Add to design notes only. |

This forces agents to anchor on verifiable evidence.

## Scheduled Research

The `agentic-research-sweep` routine runs Buckminster on a schedule. It generates a **diff proposal** containing new findings, retractions, and verifications.

Nothing merges into `RESEARCH.md` without explicit user sign-off, as changes propagate to all subsequently generated agents.

Manage via `/schedule` or scheduled-tasks tooling.
