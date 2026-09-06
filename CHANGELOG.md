# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] - 2026-09-06

### Added

- **Cross-Platform Anti-Trope Scanner:** Added `scripts/gate_tropes.py` as a cross-platform Python implementation of the negative parallelism gate, resolving Windows execution barriers in pre-commit and CI.
- **Tri-Source Verification Discipline:** Enforced mandatory tri-source verification in Buckminster (`skills/buckminster/SKILL.md` and `references/RESEARCH_METHODOLOGY.md`) requiring all findings proposed for `RESEARCH.md` to be supported by ≥3 independent verified resources, with peer-reviewed literature prioritized and vendor sources capped at 1 of 3.
- **Mandatory Concrete Hyperlinks:** Required all research findings to carry explicit clickable markdown URLs, DOIs, or arXiv links; prohibited vague domain-level mentions.
- **Ungrounded Claim Gate (G0 & G3):** Updated Marcus's gate definitions (`skills/marcus/references/SPEC.md` and `skills/marcus/AGENT_ARCHITECTURE.md`) with mechanical rejection for any research finding imported into knowledge tiers lacking 3 hyperlinked verified sources (Rule K-6, Rule G-11).

### Changed

- **Standardized `.agents/rules/` Primitives:** Aligned `artifact-generation.md` and `release-management.md` with Section 10 Primitive Specification, including standardized YAML frontmatter (`always_on: true`, cross-platform mappings) and hierarchical headings (`# Context & Trigger`, `## Rules & Directives`, `## Enforcement & Verification`).
- **Grounded `RESEARCH.md v1.2.0`:** Updated findings across Section 1 (Binding Constraint Thesis), Section 2 (Context Length Degradation), Section 4 (SWE-bench Solution Leakage & Test Quality), Section 6 (Skill Security Flaws & 2.12× Multiplier), and Section 9 (The Productivity-Reliability Paradox & 91% Review Bottleneck) with concrete DOIs and peer-reviewed citations. Synchronized to `skills/marcus/references/RESEARCH.md`.

## [0.1.3] - 2026-09-06

### Added

- **Multi-layer security scanning scaffolding:**
  - Local pre-commit hook (`scripts/scan_security_and_pii.py`) enforcing zero-dependency secret detection, PII/user-path scrubbing, and agent safety rules.
  - Semgrep SAST & Agent Policy suite (`.semgrep/agent-security.yml`) checking for unconstrained shell calls, safety gate overrides, and environment leaks.
  - Integrated Semgrep into GitHub Actions CI pipeline (`.github/workflows/security.yml`).
  - Automated Promptfoo adversarial red-teaming configuration (`promptfooconfig.yaml`) and scheduled CI workflow (`.github/workflows/agent-redteam.yml`) testing against OWASP LLM Top 10 vulnerabilities (prompt injection, excessive agency, goal hijacking, and RBAC).

## [0.1.2] - 2026-09-06

### Added

- **`research/RESEARCH.md`** - bumped to v1.2.0 (snapshot date: 2026-09-06). Added Section 10
  Primitive Taxonomy covering Rules, Skills, Harnesses, Lifecycle Hooks, Plugins, Subagents,
  and Custom Agents. Added benchmark updates (FrontierCode, SWE-CI, benchmark integrity crisis),
  worktree safety failure modes & deletion prevention, STORM state management, Agent Plugins 1.0,
  and MCP stateless spec update. Synchronised to `skills/marcus/references/RESEARCH.md`.
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
- **`human-only/` convention** - rendered deliverables excluded from model context, enforced by a
  `permissions.deny` rule rather than by convention alone.
- **`skills/buckminster/evals/evals.json`** - 12 cases. The nine regression cases are drawn from the
  anti-patterns in `references/RESEARCH_METHODOLOGY.md` §5, which that file records as observed and
  corrected in practice, so they satisfy G0 as real failures rather than invented ones.

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
- Dangling and ambiguous paths in `skills/marcus`, `skills/buckminster` and the Alfred skill.

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
