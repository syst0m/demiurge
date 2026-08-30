# agent-foundry

Two agents that build and maintain other agents. Self-contained — no dependency on any other
project.

| | Role |
|---|---|
| **Marcus** | Designs and generates agents, and emits them as installable packages for Claude, Claude Code, Gemini, Gemini CLI, AGENTS.md, CLI harnesses or web chat |
| **Buckminster** | Researches the current state of agentic engineering and proposes graded updates to the evidence Marcus builds from |

Named for Marcus Aurelius — who wrote his guidance to himself and then followed it — and
Buckminster Fuller, for comprehensive anticipatory design science.

## How they relate

```
Buckminster ──writes──> research/RESEARCH.md ──read by──> Marcus ──generates──> agent packages
     ▲                                                        │
     └──────────── user signs off on every change ────────────┘
```

**They are deliberately one-directional.** Buckminster researches and never designs. Marcus designs
and never researches — if it needs a fact that is not in `RESEARCH.md`, it says so and asks for a
Buckminster pass rather than going to find it. An ungraded fact would bypass the whole method.

## Layout

| Path | What |
|---|---|
| `research/RESEARCH.md` | **The shared snapshot.** One writable copy. Buckminster maintains it |
| `skills/marcus/` | `SKILL.md`, `AGENT_ARCHITECTURE.md` (HLD+LLD), `AGENT_DESIGN.md` (human guide), `templates/` |
| `skills/buckminster/` | `SKILL.md` + `references/RESEARCH_METHODOLOGY.md` |
| `scripts/sync-skills.sh` | Deploys to `~/.claude/skills/`; distributes `RESEARCH.md` into Marcus's references |

```bash
./scripts/sync-skills.sh --check    # report drift, write nothing
./scripts/sync-skills.sh            # apply
```

**Edit `skills/` here, never `~/.claude/skills/`** — that is a deployment target and gets
overwritten.

## The documents Marcus maintains

| File | Audience | Regenerated when |
|---|---|---|
| `AGENT_ARCHITECTURE.md` | Machine — Marcus generates against it | `RESEARCH.md` version changes |
| `AGENT_DESIGN.md` + `.pdf` | Human — flowchart, concrete steps, checklist | Same |

Both carry a `derived_from` header naming the `RESEARCH.md` version they were built against. When
those diverge, Marcus regenerates and reports what moved — including **which already-generated
agents were built against superseded rules.** It does not silently regenerate them; an agent in
production was built against a snapshot, and changing the snapshot does not change the agent.

## Evidence grading

Every claim in `RESEARCH.md` carries a marker, and the marker determines what Marcus may do with it:

| | Meaning | Marcus may |
|---|---|---|
| `[SETTLED]` | Multiple independent sources, at least some empirical | Encode as a default |
| `[CONTESTED]` | Credible sources disagree, or one study | Offer as an option, stating the disagreement |
| `[VENDOR]` | Originates with a party selling the thing | Not encode; cite only with the conflict named |
| `[EMERGING]` | Real but untested in practice | Mention in design notes only |

This is the mechanism that keeps generated agents anchored to evidence rather than to whatever was
fashionable when they were made.

## Scheduled research

The `agentic-research-sweep` routine runs Buckminster on a schedule. It produces a **diff proposal**
— new findings, reclassifications, contradictions, retractions, and an explicit statement of what
was re-checked and still holds — for sign-off. Nothing is written to `RESEARCH.md` without approval,
because a change there propagates into every agent generated afterwards.

Manage it with `/schedule`, or via the scheduled-tasks tooling.
