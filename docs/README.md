# Documentation Index

| Guide | Scope & Focus |
|---|---|
| [Installation Guide](INSTALLATION.md) | Deployment across harnesses, offline execution model, and optional research connectors. |
| [Personas](PERSONAS.md) | What each persona does, with slash commands, prompts, and integrations. |
| [Operating Guide](OPERATING_GUIDE.md) | Operational workflows, prompt templates, 8 gotchas, and best practices. |
| [Master Documentation](DOCUMENTATION.md) | Top-Level Design (TLD), Low-Level Design (LLD), and full system specification. |
| [Design Manual](AGENT_DESIGN.md) | Human companion guide: structural layers, decision trees, and checklists. |
| [Benchmarks Guide](BENCHMARKS.md) | Independent evaluation (SWE-bench, GAIA, Tau-bench), metrics engine, and the Benchmark Run Registry. |
| [Self-Harness Spec](SELF_HARNESS.md) | `[EMERGING]` opt-in loop for diagnosing, proposing, and gating harness-surface candidates. |
| [Imhotep Evaluation](IMHOTEP_EVALUATION.md) | Evidence review of the ambition tenets and the vendored be-ambitious procedure behind Imhotep. |
| [Evidence & Confidence Taxonomy](EVIDENCE.md) | Tri-source rule, grounding gates, and the `[SETTLED]` / `[CONTESTED]` / `[VENDOR]` / `[EMERGING]` markers. |
| [Executive Research Brief](BRIEF.md) | Four empirical constants, graded evidence base, and the gate pipeline. |
|| [Research Pipeline](RESEARCH_PIPELINE.md) | Sweep, verify, approve, merge: how a research finding reaches `RESEARCH.md`. |
|| [Scholarly Connectors on CI — Design](superpowers/specs/2026-11-23-scholarly-connectors-ci-design.md) | Full MCP (scite, Undermind, Consensus) in GitHub Actions for citation-reception verification; degrades gracefully when secrets are absent. |
| [Hermes Trope Gate Rewrite — Plan](superpowers/plans/2026-11-24-hermes-trope-gate-rewrite.md) | Rewrite flagged assistant-reply lines (3 tries) instead of withholding the reply; keep and flag lines that stay flagged. |
| [Trope Gate Rewrite Hardening — Plan](superpowers/plans/2026-11-24-trope-gate-rewrite-hardening.md) | Keep list markers, indent and line endings in rewrites; strict reply parsing and a per-call timeout; finish steps for the branch. |
| [Trope Gate Open Items — Plan](superpowers/plans/2026-11-24-trope-gate-open-items.md) | Close the parked trope gate items: regex escapes, line endings, fence retries, budget floor, and list and number pins. |
| [Trope Gate Single-Output — Design](superpowers/specs/2026-11-25-trope-gate-single-output-design.md) | Accepted: enforce rule 11 through the model's own output in Hermes, Claude Code and Antigravity, with no second reply. D1 to D4 decided; live check and parity still open. |
| [ADR index](adr/README.md) | Architecture decision records, including [0001: single-output trope gate](adr/0001-trope-gate-single-output.md) and [0002: global Stop-hook block cap](adr/0002-global-stop-hook-block-cap.md). |
|| [Claims Ledger](CLAIMS_LEDGER.md) | Claim anchors, sources, and the `grade_cap` rule. |
| [Run Ledger](RUN_LEDGER.md) | Failure intake from real skill runs. |
| [Skill Registry](SKILL_REGISTRY.md) | Local inventory of skills. |
| [Standing Orders](STANDING_ORDERS.md) | Rules for every agent session in this repository. |
| [Skill Bundles](SKILL_BUNDLES.md) | Bundle format and per-harness wiring for the skill bundle materializer. |
| [Research Methodology](../skills/niccolo/references/RESEARCH_METHODOLOGY.md) | Tri-source verification protocols, search disciplines, and evidence grading. |
| [Empirical Knowledge Base](../research/RESEARCH.md) | Canonical empirical research: benchmarks, failure modes, and primitives. |
| [Agent Architecture Spec](../skills/marcus/AGENT_ARCHITECTURE.md) | Progressive disclosure specifications and mechanical gate enforcement (G0–G6). |
