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

When executing a release:

1. **Never suppress CI:** NEVER include `[skip ci]`, `[ci skip]`, `[skip actions]`, or `[no ci]` in a release commit message. This silences GitHub Actions `release.yml` on tag push.
2. **Tag and release follow the changelog:** A release is a new `## [x.y.z]` heading in `CHANGELOG.md`.
   - `GITHUB` mode: merging it to `main` runs `.github/workflows/release.yml`, which creates the tag
     `v<version>` and the GitHub Release. Do not tag by hand.
   - `LOCAL` mode: run `python scripts/verify_release.py --cut`. It tags `HEAD`, pushes the tag,
     creates the release from the changelog section, and skips any step already done.
3. **Pass the Release Gate:** Run the mechanical verification script before marking release complete:

   ```bash
   python scripts/verify_release.py --remote
   ```

## Enforcement & Verification

- Changes that alter public interfaces, security gates, or knowledge bases require documented version bumps.
- Releases must be recorded in `CHANGELOG.md` adhering to Keep a Changelog and Semantic Versioning specifications before tagging.
- The `gate-release` pre-commit hook rejects commits that violate release conventions.
- Final release sign-off requires `python scripts/verify_release.py --remote` to return exit code 0.
