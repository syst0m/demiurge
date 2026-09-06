---
name: Release Management
description: Instructions for when to prompt the user about cutting a new release.
always_on: true
# Platform mapping:
# Antigravity: always_on: true | glob: "..." | model_decision: true
# Claude Code: alwaysApply: true | globs: [...]
# Cursor: alwaysApply: true | globs: [...]
# Codex: (inline in AGENTS.md — no frontmatter)
---

# Context & Trigger

Whenever you have completed a task that involves:

- Merging a significant feature or fix
- Conducting a major refactor
- Making changes that affect the external API or user-facing documentation

## Rules & Directives

You **MUST** explicitly ask the user if they would like to cut a new release (e.g., bump the version, update `CHANGELOG.md`, and push a new git tag).

Do not assume a release is needed for minor typographical fixes or internal tool configurations, but when in doubt, ask the user.

## Enforcement & Verification

- Changes that alter public interfaces, security gates, or knowledge bases require documented version bumps.
- Releases must be recorded in `CHANGELOG.md` adhering to Keep a Changelog and Semantic Versioning specifications before tagging.
