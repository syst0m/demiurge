# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Gates for Marcus.** Seven deterministic gates (G0-G6) now check the seven design steps, as
  rules G-1 to G-10 in a new `PART III - Enforcement` section of `AGENT_ARCHITECTURE.md`.
- **`skills/marcus/scripts/`** - four stdlib-only Python gates: `validate_skill.py` (format and
  line-level security scan), `eval_runner.py` (baseline vs treatment, `pass^k`, refuses to spend
  without `--yes`), `route_check.py` (description collision across the installed library) and
  `new_skill.py` (scaffold, refused below three recorded failures).
- **`skills/marcus/evals/run_gate_tests.py`** - deterministic regression suite for the gates
  themselves. 10 cases, no model calls, currently 10/10.
- **`skills/marcus/references/EVIDENCE.md`** - graded evidence on generating skills and harnesses,
  sibling to `RESEARCH.md`. Headline: no peer-reviewed work exists on generating Agent Skills, and
  the largest controlled study (7,560 runs) found generated skills no better than no skill.
- **`skills/marcus/references/SPEC.md`** - gate definitions, owners, failure actions, trust tiers
  and the rejection catalogue.
- **`skills/marcus/HARNESS.md`** - Marcus's own harness, declared across the six runtime
  responsibilities.
- **`skills/marcus/PROVENANCE.md`** - origin, trust tier, and what has not been verified.
- **`skills/sample-skill/`** - new skill that finds and vets events by place, date, interest and
  access needs, with `plan_queries.py` owning relative-date resolution.
- **`human-only/` convention** - rendered deliverables excluded from model context, enforced by a
  `permissions.deny` rule rather than by convention alone.

### Changed

- **Step 6 VERIFY is a script rather than a checklist.** Rule V-4 holds that invariants become
  hooks because models forget and hooks do not; the self-audit checklist was a prompt line. The
  mechanical items moved to `validate_skill.py`, and the items a script cannot see stayed as
  judgement, stated in the hand-off.
- `skills/buckminster/SKILL.md` - editorial improvements folded back from the deployment target,
  where they had been made directly.
- Absolute `~/`-prefixed paths throughout. Repo-relative paths resolved here and broke once
  deployed to `~/.claude/skills/`.

### Fixed

- `validate_skill.py` recall, found by running it against the installed library: the
  "tool content is data" check matched a single phrasing and reported two compliant skills as
  non-compliant; the eval reader understood one schema and reported a 16-case suite as empty.
  Both now accept the shapes in use, with regression cases covering them.
- Dangling and ambiguous paths in `skills/marcus`, `skills/buckminster` and the sample-skill skill.

### Known issues

- `scripts/gate-tropes.sh` and `styles/Humanize/NegativeParallelism.yml` contain a chat transcript
  describing the intended rule rather than the rule itself, so neither runs. The active Vale
  configuration is `.vale.ini` -> `.vale/styles/Foundry/`, which is unaffected.
- Gate G5 has never been run on Marcus. The harness enforces a rule its owner has not satisfied.

## [0.1.1] - 2026-08-30

### Added

- Added `release-management.md` agent rule to prompt for release sign-offs on major changes.
- Updated Pull Request templates to include mandatory release considerations.
- Integrated **Vale** prose linter locally and in CI (`prose-lint.yml`) with custom rules to ban GenAI writing styles and enforce brevity.

## [0.1.0] - 2026-08-30

### Added

- Initial open-source release of the Marcus and Buckminster agents.
- **Marcus**: Agent that designs and generates other agents as installable packages.
- **Buckminster**: Agent that researches agentic engineering to propose updates for Marcus.
- Setup GitHub Actions release workflow for automated deployments.
- Configured secret scanning workflow with `gitleaks`.
- Integrated pre-commit hooks for code quality, including markdown linting.
- Established repository standards with community health files (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates).
