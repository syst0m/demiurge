---
name: Release Management
description: Instructions for when to prompt the user about cutting a new release.
---

# Release Prompting

Whenever you have completed a task that involves:

- Merging a significant feature or fix
- Conducting a major refactor
- Making changes that affect the external API or user-facing documentation

You **MUST** explicitly ask the user if they would like to cut a new release (e.g., bump the version, update `CHANGELOG.md`, and push a new git tag).

Do not assume a release is needed for minor typographical fixes or internal tool configurations, but when in doubt, ask the user.
