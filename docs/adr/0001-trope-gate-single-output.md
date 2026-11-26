# ADR 0001: Trope gate enforces rule 11 with one model output

**Status:** Accepted, 2026-11-25
**Spec:** [Trope Gate: Single-Output Design](../superpowers/specs/2026-11-25-trope-gate-single-output-design.md)

## Context

Rule 11 bans negative parallelism and negated contrast in assistant replies. The first design rewrote flagged lines with a second model call (Hermes) or blocked the stop until the model wrote again (Claude Code). The reader saw two outputs. Caveman and i-have-adhd stay transparent because their rules sit in context and nothing rewrites the reply.

## Decision

Enforce rule 11 through the rule text in each harness's context. The model self-censors and writes once. The Stop hook and the Hermes turn hook log flagged lines. They never block or rewrite a reply. The file-save gate still blocks a `.md` write.

## Alternatives rejected

- **Rewrite flagged lines with an auxiliary model.** Produces a second output. Failure shows a placeholder in the reply.
- **Block the stop until the reply changes.** Produces a second turn.
- **Veto the user's message.** Blocks the user's own turn. The user message is not model output.

## Consequences

- A flagged phrase can reach the chat. Enforcement now depends on the model.
- The hit log measures how often the rule fails.
- `auxiliary.trope_rewrite` is unused. Removing it needs the user's approval. No `trope_rewrite` entry exists in the Hermes `config.yaml` files (checked 2026-11-26).
