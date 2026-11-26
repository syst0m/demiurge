# 0002: Global Stop-hook block cap set to 3

**Context.** `/goal` wraps a prompt-based Stop hook. When a goal needs the user, the hook blocks each stop and Claude repeats the same reply. Claude Code's default cap is 8 blocks, then it overrides the 9th. Local transcripts show 75 such loops, and 89% of the blocked replies made no tool call.

**Decision.** Set `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` to `3` in the `env` block of the user-level `~/.claude/settings.json`. It applies to every project. A cap of 2 cut 80 loops but caused 14 false stops, and a cap of 3 cut 79 loops with 11 false stops, so 3 is the lower-risk value.

**Considered and rejected.**

- A breaker Stop hook that returns `continue: false`. It ended the loop in a headless test, but it needs its own progress check and a script with a test.
- A goal-wording rule such as "or stop when only the user can act". It ended the loop in 1 of 3 runs.
- Reporting the loop upstream. No fix date is known, so it cannot stop the loops now.

**Consequences.** The cap applies to every Stop hook, including the trope and skill gates, so any gate that needs more than two retries stops early. A goal stays set after its loop ends, so the user runs `/goal clear`. The setting lives outside this repository, so this ADR is the only record of it.
