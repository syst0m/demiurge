# SELF_HARNESS.md — a self-improving harness loop for Demiurge

```yaml
version: 0.1.0
status: "[EMERGING] — opt-in, excluded from mandatory gating"
derived_from:
  - skills/marcus/references/EVIDENCE.md v1.0.0, lines 149-153 (Self-Harness citation)
  - skills/marcus/AGENT_ARCHITECTURE.md v2.0.0, Gate G5 "Prove"
  - docs/BENCHMARKS.md v1.0.0, §3.1 Resolution Lift formula
template: https://github.com/qzzqzzb/Self-Harness (arXiv 2606.09498)
audience: operators, framework maintainers
canonical_path: docs/SELF_HARNESS.md
```

> **Status banner.** This subsystem rests on a single, un-replicated preprint. Demiurge's own
> confidence taxonomy (`README.md`) marks `[EMERGING]` findings as "excluded from gating" until
> tri-source verification (Rule K-6). Every part of this spec follows from that constraint: the
> loop ships as an opt-in tool an operator runs by hand, never as a new mandatory gate, and every
> accepted candidate still waits for a human merge decision.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Why the Mapping Is Already Half-Built](#2-why-the-mapping-is-already-half-built)
3. [Stage Mapping](#3-stage-mapping)
4. [Train / Heldout Split Convention](#4-train--heldout-split-convention)
5. [Directory Layout & Script Responsibilities](#5-directory-layout--script-responsibilities)
6. [Cost & Cadence Guardrails](#6-cost--cadence-guardrails)
7. [Governance & Merge Flow](#7-governance--merge-flow)
8. [Non-Goals](#8-non-goals)
9. [Evidence Status & Attribution](#9-evidence-status--attribution)
10. [Phased Rollout](#10-phased-rollout)

---

## 1. Overview

Self-Harness (Terminal-Bench 2.0, SWE-bench Verified, AppWorld; arXiv 2606.09498) holds the model
and the evaluator fixed and improves only the scaffolding that surrounds them. The published loop
has four stages: mine weaknesses from execution traces, propose a bounded and mechanism-tagged edit
to a named "virtual hook," materialize the edit as a candidate, and gate acceptance on regression
testing across held-in and held-out task splits. Across nine model-benchmark pairs, every final
harness improved both splits, by up to 132% relative.

This document specifies the equivalent loop for Demiurge itself. The object under optimization is
Demiurge's own harness: the static rules in `.agents/rules/`, the instructions in
`skills/marcus/SKILL.md` and `skills/buckminster/SKILL.md`, the gate logic in `scripts/*.py`, and
the treated-arm scaffolding inside each `evals/benchmarks/*/run_*_eval.py`. The evaluator is the
existing benchmark suite set (`swebench`, `cybergym`, `exploitbench`, `deepswe`, with GAIA,
Tau-bench, BIPIA, and BFCL on the roadmap in `docs/BENCHMARKS.md` §5). The model backbone stays
fixed, exactly as upstream requires.

## 2. Why the Mapping Is Already Half-Built

Three pieces of this loop already exist in Demiurge, independently of this spec:

- **The acceptance rule.** Gate **G5** in `skills/marcus/AGENT_ARCHITECTURE.md` already reads:
  *"Delta ≤ 0, or any regression drop → reject."* `docs/OPERATING_GUIDE.md` Gotcha 2 restates it as
  a hard failure gate that leaves rejected drafts archived with their scores. This is the Self-Harness
  acceptance criterion, written into Demiurge's own gate table before this spec existed.
- **The comparison arms.** Every benchmark runner in `evals/benchmarks/` already produces a bare-model
  arm and a Demiurge arm, scored with the Resolution Lift formula in `docs/BENCHMARKS.md` §3.1
  ($\Delta = \text{Pass Rate}*{\text{Demiurge}} - \text{Pass Rate}*{\text{Bare}}$).
- **The evidence entry.** `skills/marcus/references/EVIDENCE.md:149-153` already cites the paper
  under `[EMERGING]`, with the same summary used above.

What Demiurge lacks is the automation connecting these three pieces: a diagnosis step that clusters
benchmark failures, a proposal step that turns a cluster into a bounded edit of a named harness
surface, and an orchestrator that runs the loop end to end with resumable state.

## 3. Stage Mapping

| Self-Harness stage           | Upstream reference                                             | Demiurge asset (existing)                                                                                                              | Demiurge asset (new)                             |
|----------------------------|----------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------|
| Fixed model + evaluator    | —                                                              | Fixed model backbone; `evals/benchmarks/*` suites                                                                                      | —                                                |
| Harness under optimization | `harnesses/qwen_tb2_final/`                                    | `.agents/rules/*.md`, `skills/marcus/SKILL.md`, `skills/buckminster/SKILL.md`, `scripts/*.py`, the Arm B code in each `run_*_eval.py` | —                                                |
| Weakness Mining            | `diagnosis/src/self_harness_diagnosis/integrated.py`           | `eval_results/<suite>/results.json`                                                                                                    | `scripts/self_harness/diagnose_failures.py`      |
| Harness Proposal           | `proposer/src/self_harness_proposer/{hooks,multi_proposer}.py` | Marcus (`skills/marcus/`), running inside a supervised session                                                                         | `scripts/self_harness/propose_candidate.py`      |
| Materialize                | `proposer/src/self_harness_proposer/materialize.py`            | Git (Demiurge is already a git repository with a PR flow)                                                                              | `scripts/self_harness/materialize_candidate.py`  |
| Acceptance Gate            | `acceptance/scripts/run_acceptance_gate.py`                    | Gate G5 rule text; each suite's `metrics.py` $\Delta$ formula                                                                          | `scripts/self_harness/acceptance_gate.py`        |
| Merge                      | mechanical accept (upstream)                                   | `.github/PULL_REQUEST_TEMPLATE.md`, operator review                                                                                    | mandatory human sign-off (see §7)                |

Two deliberate deviations from upstream, both traced to an existing Demiurge principle:

1. **Materialization uses a git branch.** Upstream writes a flat file copy. Demiurge already
   reviews changes through pull requests, and a git branch keeps candidates inside that review
   surface.
2. **Merge requires a human.** Upstream's acceptance gate is described as sufficient on its own.
   Demiurge's README states "Human Governance: Knowledge base updates require explicit operator
   approval," and the `[EMERGING]` status of the underlying paper raises the bar further: an
   automated merge would let a single un-replicated finding rewrite Demiurge's own harness
   unsupervised.

## 4. Train / Heldout Split Convention

Demiurge's benchmark runners load task instances live (dataset library, REST fallback, or a
generated fallback list — see `evals/benchmarks/swebench/run_swebench_eval.py`), so the task-ID
universe for a suite is not fixed ahead of a run. `scripts/self_harness/splits.py` computes a
deterministic, seeded partition of whatever instance-ID list a run actually produces, and caches it
the first time it is asked for a given task set:

```json
{
  "format": "demiurge.self_harness.splits.v0",
  "seed": 0,
  "heldout_fraction": 0.3,
  "train": ["task_id_1", "task_id_2", "..."],
  "heldout": ["task_id_9", "task_id_10", "..."]
}
```

This mirrors upstream's TB2 Clean64 split file (`eval/README.md`, 43 train / 21 heldout tasks)
without hand-authoring instance IDs no one has verified. The split is order-independent (the same
task-ID set always yields the same partition, regardless of the order those IDs arrive in), and
extends deterministically as new task IDs appear, without moving IDs already assigned. This gives
`acceptance_gate.py` a reproducible denominator across runs, so repeated evaluations of the same
candidate are comparable.

## 5. Directory Layout & Script Responsibilities

> **Implementation status.** Built and tested. `scripts/self_harness/` exists with the seven files
> below; `python scripts/self_harness/test_self_harness.py` (19 cases) and
> `python scripts/self_harness/validate_self_harness_scripts.py` both pass.

```
scripts/self_harness/
├── splits.py
├── diagnose_failures.py
├── propose_candidate.py
├── materialize_candidate.py
├── acceptance_gate.py
├── run_self_harness_loop.py
├── validate_self_harness_scripts.py
└── test_self_harness.py
```

- **`splits.py`** — the train/heldout partitioning described in §4. Not itself a pipeline stage; the
  other scripts import it.
- **`diagnose_failures.py`** — reads `eval_results/<suite>/results.json`, clusters demiurge-arm
  failures by normalized error text. `TaskResult` (`evals/benchmarks/*/metrics.py`) carries no gate,
  mechanism, or criticality field today, so the emitted brief says so rather than claiming a richer
  taxonomy the data does not support. Emits `diagnosis_brief.md` and `diagnosis.json`.
- **`propose_candidate.py`** — bundles the diagnosis with the current content of the targeted
  surface file(s) into a proposer prompt (build mode), then validates a Marcus/Claude Code session's
  structured JSON reply into a `proposal_bundle.json` (parse mode). Matching `docs/INSTALLATION.md`
  §5's requirement that Marcus stay "fully offline and deterministic," this script never calls an
  external model API; it only assembles the prompt and parses the reply, and rejects a reply that
  targets an undeclared surface, leaves the surface unchanged, or omits a required narrative field.
- **`materialize_candidate.py`** — writes the proposed edit to a new git branch (`self-harness/<id>`)
  plus a `candidate_manifest.json` (candidate ID, proposal ID, branch, base and candidate commit
  SHAs). Refuses a dirty working tree and refuses a second active candidate branch.
  `docs/OPERATING_GUIDE.md` Gotcha 6 documents the failure mode this guards against: concurrent
  worktrees risk `.git/config.lock` contention and can destroy the primary `.git` directory — so
  this script never creates a worktree, only a single checked-out branch. It never pushes or merges.
- **`acceptance_gate.py`** — the no-drop-plus-improvement rule, computed per split directly from each
  task's `resolved` boolean and averaged across however many repeat result files are given per side.
  This script is Gate G5, applied to a harness-surface candidate instead of a generated skill.
- **`run_self_harness_loop.py`** — the orchestrator, a resumable state machine. The proposal step
  needs a human/Marcus turn, so each run inspects which stage
  artifacts already exist under `--work-dir` and either performs the next deterministic step itself
  or prints the exact next manual command. State records to `loop_state.json`
  (`demiurge.self_harness.loop_state.v0`).
- **`validate_self_harness_scripts.py`** — an integrity gate over the five scripts above, in the
  shape of `scripts/validate_benchmark_harness.py`. Implemented rules:
  - **S1** — none of the five scripts references fabricated ("mock") data.
  - **S2** — every stage script defines an explicit `FORMAT` version string for its output payload.
  - **S3** — `materialize_candidate.py` refuses a dirty working tree and a second active candidate
    branch.
  - **S4** — `acceptance_gate.py`'s decision is exactly the no-drop-plus-improvement rule.
  - **S5** — none of the five scripts contains `git push`, `git merge`, or `gh pr merge`. Merging
    stays a human action, per §7.
- **`test_self_harness.py`** — `unittest` coverage for every script above: split determinism,
  failure clustering (including the no-failure no-op case), proposal validation, git-branch
  materialization (including both refusal paths), the four acceptance-gate decision cases, and a
  self-check that the integrity validator passes against its own siblings.

## 6. Cost & Cadence Guardrails

Benchmark runs already carry real cost (`docs/BENCHMARKS.md` §7: $15–150 per tier). The self-harness
loop follows the existing "Bi-Weekly / Milestone" cadence row, scoped to each suite's 25-task
micro-slice, never triggered per commit. Every stage supports `--dry-run` first, reusing the
zero-cost simulation convention already present in every `evals/benchmarks/*/run_*_eval.py` runner,
so the loop's mechanics are verifiable before any `--yes` live spend.

## 7. Governance & Merge Flow

1. An accepted candidate (G5 pass on both splits) opens a pull request using the existing
   `.github/PULL_REQUEST_TEMPLATE.md`, with the acceptance-gate JSON attached as evidence.
2. An operator reviews the diff and the evidence, then merges by hand. No script in
   `scripts/self_harness/` holds merge permission.
3. A rejected candidate stays archived with its scores under
   `eval_results/self_harness/<candidate_id>/`, following the same archival behavior
   `docs/OPERATING_GUIDE.md` Gotcha 2 already describes for rejected Marcus drafts.
4. Production surfaces stay pinned to their last-merged version until an operator explicitly
   upgrades them, per Gotcha 7's version-pinning immutability rule.

## 8. Non-Goals

- No auto-merge, under any acceptance score.
- No continuous or per-commit loop. The cadence in §6 is a ceiling that operators must not exceed.
- Candidates edit Demiurge's own harness surfaces only. Benchmark task datasets stay untouched.
- The G0–G6 gate *thresholds* are fixed. Candidates may change the surfaces those gates check; they
  cannot change what the gates require.
- No vector store or embedding-based memory for the diagnosis step, per Rule K-3.

## 9. Evidence Status & Attribution

This subsystem's entire empirical basis is one preprint:

> Self-Harness (2026). Terminal-Bench 2.0, SWE-bench Verified, AppWorld. arXiv:2606.09498.
> Repository: [github.com/qzzqzzb/Self-Harness](https://github.com/qzzqzzb/Self-Harness).

Rule K-6 requires three independent, hyperlinked sources before a finding can move from `[EMERGING]`
to `[SETTLED]`. This spec supplies one. A future revision needs two more independent replications —
ideally outside the paper's own benchmark selection — before the loop in this document could ever
become a default rather than an opt-in tool.

## 10. Phased Rollout

- **Phase A — built.** All five stage scripts, `splits.py`, and the integrity validator exist under
  `scripts/self_harness/` with passing tests. `diagnose_failures.py` has been run against the real
  `eval_results/swebench/results.json` and produced a correct no-op brief (that results file
  currently records zero demiurge-arm failures).
- **Phase B — not started.** Running the full loop against a live `swebench` or `cybergym` slice
  with a real failing task, so a real proposal is diagnosed, materialized, and gated end to end.
  Requires an operator-run benchmark slice with at least one demiurge-arm failure, and a supervised
  Marcus session to answer the proposer prompt.
- **Phase C — not started.** Extend beyond `swebench`, `cybergym`, `exploitbench`, and `deepswe` to
  GAIA, Tau-bench, BIPIA, and BFCL, as their adapters land per the `docs/BENCHMARKS.md` §5 roadmap.
