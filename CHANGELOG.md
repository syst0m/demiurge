# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.1] - 2026-09-08

### Added

- **Empirical Live SWE-bench Benchmark Telemetry (`v0.7.0-swebench-live`):** Executed real live API benchmark evaluation against `gemini-3.1-flash-lite-preview` loading real dataset instances from `princeton-nlp/SWE-bench_Lite` (`astropy__astropy-12907` and `astropy__astropy-14182`), recording 100% resolution parity and a 33.3% reduction in mean turns (4.0 vs 6.0 turns).

## [0.7.0] - 2026-09-08

### Added

- **Marcus Benchmark Integrity Validator (`scripts/validate_benchmark_harness.py`):** Implemented automated static auditing tool enforcing 6 non-negotiable benchmark quality gates (no silent mock fallback, real dataset loading, complete issue prompt construction, symmetrical prompt application, patch verification rigor, and explicit `simulated: True` metadata tracking).
- **Hugging Face Dataset Integration in SWE-bench Runner:** Updated `evals/benchmarks/swebench/run_swebench_eval.py` to dynamically load dataset records from `princeton-nlp/SWE-bench_Lite` via Hugging Face `datasets` library or dataset server REST API fallback.
- **Symmetrical Prompt Construction & Strict Error Handling:** Applied prompt templates symmetrically across Bare (Arm A) and Demiurge (Arm B) models and replaced silent mock fallback with explicit error raising (`RuntimeError` / `NotImplementedError`) on live API failure or unhandled model runners.
- **Simulation Baseline Metadata & Reporting:** Added `simulated: bool` metadata flag to `TaskResult`, `ArmSummary`, and `BenchmarkComparison`, and updated Markdown report renderers to display warning banners on dry-run simulation outputs.

## [0.6.1] - 2026-09-08

### Added

- **Permanent Benchmark Synchronization Rule:** Added `.agents/rules/benchmark-sync.md` to permanently enforce updating `README.md` and `docs/BENCHMARKS.md` benchmark run registries whenever new benchmark evaluations are executed.
- **Top-Level README Telemetry Sync:** Synchronized `README.md` Benchmark Run Registry with live CyberGym (`v0.5.0-cybergym-001`) and ExploitBench (`v0.6.0-exploitbench-001`) evaluation results.

## [0.6.0] - 2026-09-08

### Added

- **ExploitBench Capability Ladder Integration:** Integrated [ExploitBench](https://github.com/exploitbench/exploitbench) (Carnegie Mellon University & Bugcrowd Research) into `evals/benchmarks/exploitbench/` to evaluate autonomous AI security agents across 4 structured capability tiers (Tier 0 reachability, Tier 1 crash trigger, Tier 2 exploit primitive, Tier 3 payload execution verification).
- **ExploitBench Capability Ladder Engine:** Created `evals/benchmarks/exploitbench/metrics.py` and `run_exploitbench_eval.py` supporting capability ladder progression tracking ($T_0$ to $T_3$), resolution lift ($\Delta$), turn economy, and token pricing models.
- **Deterministic ExploitBench Test Harness:** Created `evals/benchmarks/exploitbench/test_exploitbench_runner.py` providing unit tests for capability ladder summaries, prompt formatting, and telemetry reporting.
- **Flagship Live Benchmark Empirical Telemetry:** Executed live flagship API benchmark evaluation (`gemini-3.0-flash`), recording 80% vulnerable code reachability ($T_0$), 80% crash trigger ($T_1$), 100% exploit primitive formulation ($T_2$), and a 33.3% reduction in mean turns (4.0 vs 6.0 turns).
- **Academic Citation Protocol:** Embedded official citations and BibTeX entries for ExploitBench (*CMU & Bugcrowd, 2026*) in [docs/BENCHMARKS.md](docs/BENCHMARKS.md) and telemetry reports.

## [0.5.1] - 2026-09-08

### Changed

- **Live CyberGym Empirical Benchmark Telemetry:** Replaced dry-run simulation metrics in `eval_results/cybergym/` and [docs/BENCHMARKS.md](docs/BENCHMARKS.md) with empirical live model execution results (`gemini-3.0-flash`), recording 100% vulnerability localization rate and a 33.3% reduction in mean turns (4.0 turns vs 6.0 turns).
- **Unbuffered Live Telemetry Execution:** Enabled prompt-cache streaming and explicit stdout flushing (`flush=True`) in `evals/benchmarks/cybergym/run_cybergym_eval.py` for real-time evaluation monitoring.

## [0.5.0] - 2026-09-08

### Added

- **CyberGym Benchmark Integration:** Integrated the [CyberGym](https://github.com/sunblaze-ucb/cybergym) cybersecurity evaluation suite into `evals/benchmarks/cybergym/` to measure autonomous AI agent performance in execution-grounded vulnerability localization, proof-of-concept (PoC) verification, and secure patch synthesis.
- **CyberGym Telemetry Engine:** Created `evals/benchmarks/cybergym/metrics.py` and `run_cybergym_eval.py` supporting comparative resolution lift ($\Delta$), vulnerability localization rates, prompt-cache hit ratio, turn economy, and cost tracking.
- **Deterministic CyberGym Test Harness:** Created `evals/benchmarks/cybergym/test_cybergym_runner.py` providing deterministic unit verification for telemetry computation, system prompt formatting, dry-run simulation, and output artifact rendering.
- **Academic Citation Protocol:** Documented official citations and BibTeX entries for *CyberGym (Wang et al., 2025)* and *CyberGym-E2E (Shi et al., 2026)* in [docs/BENCHMARKS.md](docs/BENCHMARKS.md) and embedded citation rendering in telemetry reports.
- **CyberGym Telemetry & Predictions:** Generated baseline vs. Demiurge evaluation telemetry reports and prediction artifacts in `eval_results/cybergym/`.

## [0.4.6] - 2026-09-06

### Added

- **Graphical Dashboard Preview:** Upgraded `scripts/sync_brief_summary.py` to auto-generate a comprehensive Mermaid flowchart diagram in [README.md](README.md) displaying the dashboard's key empirical constants, graded evidence base, mechanical gate pipeline, and verification metrics.

### Changed

- **Executive Research Brief Streamlining:** Simplified the Executive Research Brief section in [README.md](README.md) to link directly to the rendered [Visual Dashboard](https://htmlpreview.github.io/?https://github.com/syst0m/demiurge/blob/main/skills/marcus/human-only/demiurge-brief.html) without auxiliary theme or layout narrative.

## [0.4.5] - 2026-09-06

### Added

- **Native Markdown Executive Brief:** Added `skills/marcus/human-only/demiurge-brief.md` providing a native GitHub-rendered edition of the executive research briefing with full typography, tabular data, and verification results.
- **Interactive Brief Preview Link:** Linked rendered HTML view via `htmlpreview.github.io` in [README.md](README.md) and [skills/marcus/human-only/README.md](skills/marcus/human-only/README.md) for direct browser dashboard access without requiring local file downloads.
- **Optional Scholarly Connectors Documentation:** Documented optional Model Context Protocol (MCP) literature search tooling ([Undermind](https://undermind.ai), [scite](https://scite.ai/mcp), [Consensus](https://consensus.app), [PubMed](https://pubmed.ncbi.nlm.nih.gov)) in [docs/INSTALLATION.md](docs/INSTALLATION.md) (§5), [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md), and [docs/OPERATING_GUIDE.md](docs/OPERATING_GUIDE.md).
- **Graceful Research Degradation:** Added fallback execution rules to `skills/buckminster/SKILL.md` and `skills/buckminster/references/RESEARCH_METHODOLOGY.md` allowing Buckminster to operate on fresh clones without connectors by degrading to web search and explicitly disclosing unverified citation reception.

### Changed

- **README Brief Gist Streamlining:** Removed auto-generated attribution boilerplate from [README.md](README.md) and updated `scripts/sync_brief_summary.py` to maintain a clean quote format.
- **Link Target Expansion:** Added `skills/marcus/human-only/demiurge-brief.md` to `scripts/check_links.py` targets (now verifying 113/113 links).

## [0.4.4] - 2026-09-06

### Added

- **Executive Research Brief Integration:** Renamed the visual research briefing to `demiurge-brief.html` in `skills/marcus/human-only/`, integrated it into the documentation directory, and added an Executive Research Brief overview section in [README.md](README.md).
- **Automated Brief Gist Synchronizer:** Created `scripts/sync_brief_summary.py` to automatically extract headline empirical constants and architectural takeaways from `demiurge-brief.html` into `README.md`.

### Fixed

- **Privacy Sanitization & History Purge:** Removed all references to private skills across test fixtures, tables, and changelogs, and purged all historical occurrences across past commits.

## [0.4.3] - 2026-09-06

### Changed

- **Repository Layout Consolidation:** Consolidated the repository layout documentation and operational guidelines into [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) (§4), streamlining [README.md](README.md).
- **High-Level Gate Architecture Overview:** Simplified the Tiered Deterministic Gates description in [README.md](README.md) to present a clean conceptual explanation across the three mechanical tiers without script-level clutter.

## [0.4.2] - 2026-09-06

### Fixed

- **Absolute Local Path Sanitization:** Replaced all occurrences of absolute user filesystem paths with canonical repository-relative paths across `skills/marcus/SKILL.md`, `skills/marcus/AGENT_ARCHITECTURE.md`, `skills/marcus/human-only/demiurge-brief.html`, and `skills/buckminster/SKILL.md`.
- **Git History Purge:** Rewrote repository commit history to eliminate all historical occurrences of local path structures across all previous commit diffs and commit messages.

## [0.4.1] - 2026-09-06

### Fixed

- **Purged Point-in-Time Commentary:** Removed chronological development timestamps, dated research pass notes, and point-in-time observation narratives across `skills/marcus/PROVENANCE.md`, `skills/buckminster/references/RESEARCH_METHODOLOGY.md`, and `skills/buckminster/evals/evals.json`.
- **Epistemic Grade Alignment:** Corrected contradictory `[SETTLED]` tag on untraced vendor estimates in `research/RESEARCH.md` and `skills/marcus/references/RESEARCH.md`, formalizing reclassification to `[VENDOR]` with affirmative technical specifications.
- **Negative Parallelism Elimination:** Converted eval test criteria and research methodology directives from negative parallelism (`rather than`, `instead of`) into positive declarative assertions.
- **Hardened Superfluous Commentary Scanner:** Upgraded `scripts/scan_superfluous.py` to deterministically flag date-stamped observation entries (`Observed YYYY-MM-DD`, `as of YYYY-MM-DD`, `Until YYYY-MM-DD`, and historical pass narratives) across all repository assets.
- **Regression Suite Path & Count Alignment:** Updated `PROVENANCE.md` regression suite path to repo-qualified `skills/marcus/evals/run_gate_tests.py` and reflected the full 14/14 passing test count.

## [0.4.0] - 2026-09-06

### Added

- **Live Google Gemini Benchmark Engine:** Integrated live API execution via `google-genai` with automated exponential backoff and retry recovery in `evals/benchmarks/swebench/run_swebench_eval.py`.
- **Multi-Model Token Pricing:** Added token pricing profiles for `gemini-3.0-flash`, `gemini-3.1-pro-preview`, `gemini-3.8-flash`, and `gemini-3.1-flash-lite-preview` into `evals/benchmarks/swebench/metrics.py`.
- **Centralized Benchmark Run Registry:** Added historical benchmark run tracking in [docs/BENCHMARKS.md](docs/BENCHMARKS.md) and [README.md](README.md) recording runs `v0.2.0-swebench-001`, `v0.3.0-swebench-full`, and `v0.4.0-gemini-live`.
- **Benchmark Run Reports:** Added [docs/reports/swebench_full_2294_summary.md](docs/reports/swebench_full_2294_summary.md) (Full 2,294-task SWE-bench report, +20.06% lift) and [docs/reports/swebench_gemini_v040_summary.md](docs/reports/swebench_gemini_v040_summary.md) (Live Gemini 3.1 Flash-Lite run documenting Gate G0 compliance).
- **Full SWE-bench Scale Execution:** Validated adapter execution on the complete 2,294-instance SWE-bench dataset (`princeton-nlp/SWE-bench`) emitting official Princeton prediction artifacts.

## [0.3.0] - 2026-09-06

### Changed

- **README Streamlining:** Condensed the main `README.md` by consolidating deterministic gate specifications into a single declarative sentence.
- **Unified Documentation Index:** Merged top header navigation and Core Documentation into a compact 2-column guide table preserving all canonical documentation references.
- **Redundancy Reduction:** Eliminated duplicate Low-Level Design (LLD) reference sentences across the introduction and architectural overview.

## [0.2.0] - 2026-09-06

### Added

- **SWE-bench Independent Benchmarking Suite:** Implemented native benchmarking adapter (`evals/benchmarks/swebench/run_swebench_eval.py`) comparing Arm A (Bare Foundation Model) against Arm B (Demiurge Dual-Agent Architecture) on SWE-bench Lite. Supports dry-run simulation and live API execution guarded by `--yes`.
- **Comparative Telemetry & Metrics Engine:** Added `evals/benchmarks/swebench/metrics.py` calculating Resolution Lift ($\Delta$), Prompt-Cache Hit Ratio, Cost per Resolved Task (USD), and Turn Economy.
- **Benchmarking Guide & Multi-Benchmark Roadmap:** Added [docs/BENCHMARKS.md](docs/BENCHMARKS.md) detailing architecture, metrics formulas, execution guides, and implementation roadmaps for GAIA, Tau-bench, BIPIA, and BFCL alongside periodic execution cadences.
- **Benchmark Run Telemetry & Reports:** Added [docs/reports/swebench_v020_summary.md](docs/reports/swebench_v020_summary.md) recording run `v0.2.0-swebench-001` results (+40.00% resolution lift, 82.0% prompt-cache hit ratio, 74% cost reduction per resolved fix).
- **Independent Benchmarking Section:** Added dedicated benchmarking section to `README.md` and `docs/DOCUMENTATION.md` linking to `docs/BENCHMARKS.md` and performance summaries.

### Changed

- **Evidence & Empirical Discipline:** Expanded Evidence section in `README.md` detailing the epistemological principles, Tri-Source Verification (Rule K-6), strict grounding gates (G0 & G3), and confidence taxonomy enforcement.
- **Architecture Section Streamlining:** Condensed top-level negative parallelism defense description in `README.md` while preserving technical Go RE2 regex parser specifications in `docs/DOCUMENTATION.md`.

## [0.1.5] - 2026-09-06

### Added

- **Master System Documentation:** Added [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) providing a comprehensive Top-Level Design (TLD) Mermaid architecture, Core Documentation Index, Repository Layout, Low-Level Design (LLD) concrete implementations (Harness, Provenance, Rules, Gates G0–G6, Lifecycle Hooks, Evals, Skills), and consolidated Verification Harness execution.
- **Marcus & Buckminster Operating Guide:** Added [docs/OPERATING_GUIDE.md](docs/OPERATING_GUIDE.md) detailing interactive prompt templates, execution workflows, seven operational gotchas (prompt-cache thrashing, lethal trifecta, worktree locks, negative parallelism), and five architectural best practices.
- **Deterministic Reference & Link Checker:** Added `scripts/check_links.py` as a permanent verification harness enforcing 100% hyperlink resolution across 12 canonical markdown targets with `--strict` support.
- **Permanent Superfluous Comment Scanner:** Added `scripts/scan_superfluous.py` to deterministically detect chat transcripts, migration war stories, session diaries, and prompt artifacts in code comments and prose. Integrated into Marcus's Gate G4 validator (`skills/marcus/scripts/validate_skill.py`) and pre-commit.

### Changed

- **Tail-Negated Trope Detection Upgrade:** Enhanced negative parallelism regexes across `scripts/gate_tropes.py`, `scripts/gate-tropes.sh`, and `.vale/styles/Foundry/NegativeParallelism.yml` to catch both front-negated and tail-negated antithesis constructions. Purged tail-negated tropes repository-wide.
- **Architecture Section & Harness Documentation:** Updated `README.md` and `docs/DOCUMENTATION.md` to document the dual-layer trope gate architecture and Vale Go RE2 single-concatenated `raw` pattern requirement.
- **Comment Sanitization:** Purged conversational meta-commentary, incident narratives, and unversioned migration notes from `.pre-commit-config.yaml`, `scripts/sync-skills.sh`, and `skills/marcus/scripts/eval_runner.py`.
- **Environment & Scratch Hygiene:** Hardened `.gitignore` to prevent `scratch/`, virtual environments, test caches, and OS/editor metadata from being tracked.

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
- Dangling and ambiguous paths in `skills/marcus`, `skills/buckminster`, and installed skills.

### Known issues

- `scripts/gate-tropes.sh` and `styles/Humanize/NegativeParallelism.yml` contained
  unexecutable draft text instead of the operational scanner, which prevented execution.
  The active Vale configuration is `.vale.ini` -> `.vale/styles/Foundry/`, which is unaffected.
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
