---
name: Artifact Generation Rules
description: Enforces brevity, conciseness, and human-like writing across all generated artifacts.
always_on: true
# Platform mapping:
# Antigravity: always_on: true | glob: "..." | model_decision: true
# Claude Code: alwaysApply: true | globs: [...]
# Cursor: alwaysApply: true | globs: [...]
# Codex: (inline in AGENTS.md — no frontmatter)
---

# Context & Trigger

When generating or rewriting artifacts, documentation, or any human-readable content in this repository.

## Rules & Directives

You **MUST** strictly adhere to the following guidelines:

1. **Apply the `writing-clearly-and-concisely` skill:** Ensure all writing is terse, readable, and relies on first principles reasoning. Eliminate fluff, buzzwords, and unnecessary exposition.
2. **Apply the `humanize` skill:** Systematically scan for and remove GenAI writing patterns (e.g., robotic transitions, overly complex SAT words where simple ones will do). Use natural, authentic, human-generated writing patterns.
3. **Brevity is Priority:** Keep sentences short. Use active voice. Get straight to the point.

## Enforcement & Verification

- These rules function as a permanent harness and must be applied automatically without requiring explicit prompting from the user.
- Pre-commit and CI prose linters (Vale) and the negative parallelism gate reject GenAI clichés and robotic transitions.
