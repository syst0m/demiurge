# Eradicating Negative Parallelism

I have completed the implementation plan to eliminate AI tropes and negative parallelism from the Demiurge project and its associated agents.

## What was changed?

1. **Automated Gating with Vale and Bash**
   - Created `.vale.ini` configuring a new `Humanize` style for Markdown files.
   - Created `styles/Humanize/NegativeParallelism.yml`, a strict Vale rule detecting variations of the "It's not X, it's Y" trope.
   - Created `scripts/gate-tropes.sh`, a bash scanner that uses `grep` to fail any pipeline if negative parallelism is detected in Markdown files.

2. **Marcus & Buckminster Instructions**
   - Updated `skills/marcus/SKILL.md` to explicitly forbid negative parallelism, filler transitions, and manufactured drama under its "Non-negotiables".
   - Updated `skills/buckminster/SKILL.md` to enforce direct framing and plain English in its "Core discipline".

3. **Demiurge Agent Architecture Docs**
   - Added a new `Tone and Prose (Anti-Sloppiness)` section to `docs/AGENT_DESIGN.md` explicitly detailing the failure modes highlighted by the research (e.g. `unsloppify` and `tropes.fyi`) to serve as an ongoing manual and philosophical standard.

## Next Steps

- If you have CI/CD running, add `bash scripts/gate-tropes.sh` to your pipeline.
- Or, you can add it as a Git pre-commit hook by copying it to `.git/hooks/pre-commit`.
- Agents generating text using Marcus and Buckminster will now avoid this construction naturally, and your tests will enforce it if they slip!