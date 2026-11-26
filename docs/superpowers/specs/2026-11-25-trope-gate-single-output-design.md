# Trope Gate: Single-Output Design

**Status:** Accepted. Decisions D1 to D4 taken as recommended (section 7). Implemented in demiurge and agent-skills. Open: the live output-count check (section 6), and deployment by the user via `scripts/sync-skills.sh`. Until that deploy runs, `check_harness_parity.py` reports one `STALE` line for `claude-code` `marcus`.
**Date:** 2026-11-25
**Branch:** main (merged from fix/gh-gate-quoted-text, 2026-11-26)

## 1. Goal

The user reads one reply per turn. A flagged line causes no second model output. Each harness still enforces the rule. Enforcement works through the model's own writing. No rewrite is used.

## 2. Current state

| Harness | Mechanism | Second output? |
|---|---|---|
| Hermes | `transform_llm_output` with `hold_stream=True`. An auxiliary model rewrites flagged lines. | Yes. The rewrite replaces the first draft. On failure, the reply carries `[trope gate: could not rewrite]`. |
| Hermes | `pre_llm_call` gate `trope_gate_pre_llm_call`. It vetoes a user message that contains a trope. | No. It blocks the user's own turn. |
| Claude Code | Stop hook `i-have-adhd/scripts/stop-hook-trope-gate.sh`. It blocks the stop until the reply changes. | Yes. The user sees the first reply, then a second turn. |
| Claude Code | `PreToolUse` hook `trope_gate.py --pretool` on Write and Edit for `.md` files. | No. It blocks a file write. |
| Antigravity | Rule 11 text is in the global `GEMINI.md` (line 26). No hook. | No. The model applies the text. |

## 3. How caveman and i-have-adhd stay transparent

1. Both load their rules into context before the first reply. Claude Code uses a `SessionStart` hook. Antigravity reads its global instruction file.
2. The model applies the rules while it writes. It self-censors. The reader sees one output.
3. Nothing rewrites the reply. Nothing re-runs the model after the reply is written.
4. i-have-adhd states this model in its own rule 11. The scanner exists only as a deterministic backstop for files.

Caveman uses an always-on activation rule, dropped into each repository by its `caveman-init` skill. This pass did not open caveman's hook files. The mechanism is therefore only partly verified.

## 4. Proposed design

### 4.1 One rule text, delivered to every harness

- Claude Code: the existing `SessionStart` context already carries the rule 11 text.
- Hermes: `pre_llm_call` returns the rule as context. It does not veto. Hermes appends that context to the turn, as `plugin_user_context` in `agent/turn_context.py`.
- Antigravity: add the rule 11 text to the global `GEMINI.md`. Deploy it through the existing sync path.

### 4.2 Remove the second output

- Hermes: delete the `transform_llm_output` rewrite, the `hold_stream` flag, and the `trope_rewrite` call.
- Hermes: delete the `pre_llm_call` veto. A user message is not model output. A trope check must not block the user's own turn.
- Claude Code: change the Stop hook from block to log. It records each hit. It does not block the stop.

### 4.3 Keep the scanner as a signal

- The scanner (`trope_gate.py`) runs on the Stop hook in log-only mode.
- Fenced code, inline code, block quotes and double-quoted text are exempt before matching.
- Each hit appends one line to a local ledger file.
- The hit rate per 100 replies measures how often the prompt rule fails.
- The file-save gate keeps its block.

### 4.4 Parity

`scripts/check_harness_parity.py` checks all three harnesses. A `MISSING` or `STALE` line counts as a failure.

## 5. Costs

- A flagged phrase can reach the chat. The prompt rule depends on the model.
- Hermes loses its automatic cleanup of replies.
- `auxiliary.trope_rewrite` becomes unused. Changing any `auxiliary.*` setting needs the user's approval.
- A blocked file write shows as a tool error. It does not show as a second reply.

## 6. Test plan

- Hermes unit tests: `trope_gate_log_llm_output` never rewrites a reply. `trope_gate_pre_llm_call` returns context and never vetoes a turn. Each flagged line writes one ledger line. The `::help` block hook on `pre_llm_call` is a separate hook and keeps its own behaviour.
- Claude Code: the Stop hook exits 0 on a hit and writes one ledger line.
- Parity: `scripts/check_harness_parity.py` passes.
- Live: send a plain-facts prompt in Hermes, Claude Code and Antigravity. Count the output messages per turn. The count must be one.

## 7. Open decisions

- **D1.** Remove the Hermes rewrite and the Hermes veto? Decided: yes.
- **D2.** Change the chat Stop hook to log-only? Decided: yes.
- **D3.** Keep the file-save block? Decided: yes.
- **D4.** Add rule 11 to the Antigravity global file, with no hook? Decided: yes. The rule text is already in the global `GEMINI.md`.

If D1 and D2 pass, record the decision as an ADR. The alternatives were a rewrite hook and a stop block. Both produce a second output.

## 8. Known limits

- The scanner exempts double-quoted text. Spec sections 2 and 3 name only fenced code, inline code and block quotes. A flagged phrase in quotes is not logged. Accepted by decision Q1.
- Two copies of the scanner logic exist: `scripts/sync-hermes-commands.py` and agent-skills `trope_gate.py`. They write the same hit log in different formats. The rule 11 text appears in three places. A shared module would couple the two repos, so these stay until a need appears. Accepted by decision Q2.
