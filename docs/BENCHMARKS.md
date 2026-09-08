# Demiurge Independent Benchmarking Guide

```yaml
version: 1.0.0
audience: researchers, operators, framework evaluators
canonical_path: docs/BENCHMARKS.md
```

## Table of Contents

1. [Overview & Evaluation Philosophy](#1-overview--evaluation-philosophy)
2. [SWE-bench Integration (v0.2.0)](#2-swe-bench-integration-v020)
3. [Metrics & Telemetry Formulas](#3-metrics--telemetry-formulas)
4. [Benchmark Run Registry](#4-benchmark-run-registry)
5. [Multi-Benchmark Architecture Roadmap](#5-multi-benchmark-architecture-roadmap)
   - [5.1 GAIA: Multi-Source Research Benchmark](#51-gaia-multi-source-research-benchmark)
   - [5.2 Tau-bench: Multi-Turn State & Policy Benchmark](#52-tau-bench-multi-turn-state--policy-benchmark)
   - [5.3 BIPIA: Indirect Injection & Boundary Defense](#53-bipia-indirect-injection--boundary-defense)
   - [5.4 BFCL: Tool Precision & Progressive Disclosure](#54-bfcl-tool-precision--progressive-disclosure)
6. [Operator Execution Guide](#6-operator-execution-guide)
7. [Periodic Execution Cadence Matrix](#7-periodic-execution-cadence-matrix)

---

## 1. Overview & Evaluation Philosophy

Demiurge isolates empirical observation from agent synthesis. The goal of independent benchmarking is to determine whether the Demiurge architecture provides a measurable performance lift ($\Delta > 0$) compared to an untreated foundation model.

```mermaid
flowchart TD
    subgraph Benchmark_Input [Benchmark Task Suite]
        T1[SWE-bench Issue Instances]
        T2[GAIA Research Queries]
        T3[Tau-bench Dialogue Turns]
    end

    subgraph Control_Arm [Arm A: Bare Foundation Model]
        BA[Raw Model Baseline]
        BP[Minimal ReAct Scaffolding]
        BA --> BP
    end

    subgraph Treatment_Arm [Arm B: Demiurge Architecture]
        DM[Identical Model Backbone]
        PR[Static Rules Cache Prefix]
        SK[Marcus / Buckminster Progressive Skills]
        GT[Deterministic Verification Gates]
        DM --> PR --> SK --> GT
    end

    T1 --> Control_Arm
    T1 --> Treatment_Arm
    T2 --> Control_Arm
    T2 --> Treatment_Arm
    T3 --> Control_Arm
    T3 --> Treatment_Arm

    Control_Arm --> MA[Baseline Results & Telemetry]
    Treatment_Arm --> MB[Demiurge Results & Telemetry]

    MA --> CMP[Comparative Report: Delta & Cost Efficiency]
    MB --> CMP
```

### Empirical Principles

1. **The Comparative Delta ($\Delta$):** Adding skills, rules, and hooks costs context tokens. If $\Delta = \text{Pass Rate}_{\text{Demiurge}} - \text{Pass Rate}_{\text{Bare}} \le 0$, the architecture adds cognitive overhead without delivering capability gains.
2. **Deterministic Superiority:** Invariants must be asserted via machine exit codes and AST checks. LLM judges introduce position and verbosity biases.
3. **Cost & Cache Economy:** A superior agent architecture reduces cost through high prompt-cache hit rates and low turn counts.

---

## 2. SWE-bench Integration (v0.2.0)

For the `v0.2.0` release, Demiurge implements a native benchmarking adapter for [SWE-bench Lite](https://www.swebench.com/) (300 curated real GitHub issues).

### Architecture

- **Runner:** [evals/benchmarks/swebench/run_swebench_eval.py](../evals/benchmarks/swebench/run_swebench_eval.py)
- **Telemetry Engine:** [evals/benchmarks/swebench/metrics.py](../evals/benchmarks/swebench/metrics.py)
- **Execution Protocol:**
  - **Arm A (Bare Model):** Calls the model with default tool access (read, write, bash) using a minimal task-prompt without workspace rules.
  - **Arm B (Demiurge):** Injects canonical workspace rules from `.agents/rules/` at the prompt-cache prefix, progressively exposes [skills/marcus/SKILL.md](../skills/marcus/SKILL.md), and validates diffs through local syntax and security gates.

---

## 3. Metrics & Telemetry Formulas

Comparative reports track four primary dimensions:

### 3.1 Resolution Lift ($\Delta$)

$$\Delta = \text{Pass Rate}_{\text{Demiurge}} - \text{Pass Rate}_{\text{Bare}}$$
A valid production release requires $\Delta > 0$ on targeted capability slices.

### 3.2 Prompt-Cache Hit Ratio

$$\text{Cache Hit Ratio} = \frac{\text{Tokens Read From Cache}}{\text{Total Prompt Tokens}}$$
Demiurge isolates static rules at the prompt prefix, yielding typical cache read ratios above $75\%$, which substantially cuts API billing.

### 3.3 Cost per Resolved Task

$$\text{Cost per Resolved Task} = \frac{\sum \text{Task Run Costs (USD)}}{\text{Total Resolved Tasks}}$$
Measures total dollars spent divided by successful fixes.

### 3.4 Turn Economy

$$\text{Turn Economy} = \frac{1}{N} \sum_{i=1}^{N} \text{Turns}_i$$
Measures average interaction cycles required to produce a valid resolution patch.

---

## 4. Benchmark Run Registry

All empirical evaluation runs are tracked with persistent telemetry artifacts:

| Run ID | Date | Model Backbone | Benchmark Suite | Tasks | Bare Pass | Demiurge Pass | Delta ($\Delta$) | Cache Hit | Cost / Fix (Bare vs Demiurge) | Report Artifact |
|---|---|---|---|---|---|---|---|---|---|---|
| `v0.2.0-swebench-001` | 2026-09-06 | `claude-3-5-sonnet-20241022` | SWE-bench Lite | 5 | 40.0% | **80.0%** | **+40.00%** | 82.0% | $0.2050 vs **$0.0533** (-74.0%) | [Summary Report](reports/swebench_v020_summary.md) |
| `v0.3.0-swebench-full` | 2026-09-06 | `claude-3-5-sonnet-20241022` | Full SWE-bench | 2,294 | 39.97% | **60.03%** | **+20.06%** | 82.0% | $0.2069 vs **$0.0721** (-65.1%) | [Summary Report](reports/swebench_full_2294_summary.md) |
| `v0.4.0-gemini-live` | 2026-09-06 | `gemini-3.1-flash-lite-preview` | SWE-bench Lite (Live) | 5 | 80.0%* | 20.0%* | Refusal / G0 | 0.0% | $0.0001 vs $0.0015 | [Summary Report](reports/swebench_gemini_v040_summary.md) |
| `v0.5.0-cybergym-001` | 2026-09-08 | `claude-3-5-sonnet-20241022` | CyberGym Subset | 5 | 0.00% | **40.00%** | **+40.00%** | 84.0% | $0.0000 vs **$0.1102** | [Summary Report](../eval_results/cybergym/report.md) |

*\*Note on Gemini 3.1 Flash-Lite: The bare model achieved 80% through ungrounded compliance (inventing non-existent code), whereas Demiurge strictly enforced Gate G0, refusing to synthesize patches absent genuine repository context and local failure traces.*

---

## 5. Multi-Benchmark Architecture Roadmap

Beyond SWE-bench, Demiurge incorporates five domain-specific benchmark adapters:

### 5.1 GAIA: Multi-Source Research Benchmark

- **Target:** Evaluates [Buckminster](../skills/buckminster/) on complex multi-hop research, document synthesis, and factual grounding.
- **Dataset:** [HuggingFace GAIA](https://huggingface.co/spaces/gaia-benchmark/leaderboard) (Levels 1, 2, and 3).
- **Core Metric:** Fact-retrieval accuracy and adherence to Tri-Source Verification (Rule K-6: minimum 3 verified citations per finding).

### 5.2 Tau-bench: Multi-Turn State & Policy Benchmark

- **Target:** Evaluates long-horizon dialogue stability, memory durability, and state management.
- **Dataset:** [Sierra Tau-bench](https://github.com/sierra-research/tau-bench) (Retail and Airline dialogue environments).
- **Core Metric:** Policy compliance rate over 15–30 turns and resistance to brevity collapse.

### 5.3 BIPIA: Indirect Injection & Boundary Defense

- **Target:** Evaluates runtime defense mechanisms ([skills/marcus/HARNESS.md](../skills/marcus/HARNESS.md)).
- **Dataset:** [Microsoft BIPIA](https://github.com/microsoft/BIPIA) (Benchmark for Indirect Prompt Injection Attacks).
- **Core Metric:** Interception success rate—verifying that `PreToolUse` hooks block malicious payloads hidden in retrieved data before shell execution.

### 5.4 BFCL: Tool Precision & Progressive Disclosure

- **Target:** Evaluates tool schema precision and parameter binding.
- **Dataset:** [Berkeley Function-Calling Leaderboard (BFCL)](https://gorilla.cs.berkeley.edu/leaderboard.html).
- **Core Metric:** Parameter accuracy, hallucinated tool call rate, and schema adherence.

### 5.5 CyberGym: Real-World Cybersecurity & Vulnerability Remediation Benchmark

- **Target:** Evaluates AI agents on execution-grounded vulnerability localization, proof-of-concept (PoC) verification, and secure patch synthesis.
- **Dataset:** [sunblaze-ucb/cybergym](https://github.com/sunblaze-ucb/cybergym) (UC Berkeley SunBlaze Lab, sourcing 1,500+ OSS-Fuzz real-world vulnerabilities).
- **Core Metric:** Vulnerability localization rate, PoC verification pass rate, resolution lift ($\Delta$), and prompt-cache hit economy.
- **Academic Citations & Attribution:**

  > Shi, T., Rheem, R., Jiang, D., Wang, M., De La Riega, F., Wang, Z., Jiang, J., Cheung, A., & Tai, S. (2026). _CyberGym-E2E: Scalable Real-World Benchmark for AI Agents' End-to-End Cybersecurity Capabilities_. arXiv preprint arXiv:2606.02548.
  >
  > Wang, Z., Shi, T., He, J., Cai, M., Zhang, J., & Song, D. (2025). _CyberGym: Evaluating AI Agents' Real-World Cybersecurity Capabilities at Scale_. arXiv preprint arXiv:2506.02548.

  ```bibtex
  @inproceedings{shi2026cybergyme2e,
    title={CyberGym-E2E: Scalable Real-World Benchmark for AI Agents' End-to-End Cybersecurity Capabilities},
    author={Shi, Tianneng and Rheem, Robin and Jiang, Dongwei and Wang, Mona and De La Riega, Francisco and Wang, Zhun and Jiang, Jingzhi and Cheung, Alexander and Tai, Sean},
    year={2026}
  }

  @article{wang2025cybergym,
    title={CyberGym: Evaluating AI Agents' Real-World Cybersecurity Capabilities at Scale},
    author={Wang, Zhun and Shi, Tianneng and He, Jiacen and Cai, Minghao and Zhang, Junhua and Song, Dawn},
    journal={arXiv preprint arXiv:2506.02548},
    year={2025}
  }
  ```

---

## 6. Operator Execution Guide

All benchmark runners include `--dry-run` simulation modes and enforce a strict `--yes` authorization flag prior to making paid API calls.

### 6.1 Dry-Run Simulation (Zero Cost)

Simulates task executions, creates official prediction manifests, and calculates telemetry:

```bash
python evals/benchmarks/swebench/run_swebench_eval.py --slice 0:5 --dry-run
python evals/benchmarks/cybergym/run_cybergym_eval.py --slice 0:5 --dry-run
```

Output files are written to `eval_results/swebench/` or `eval_results/cybergym/`:

- `results.json`: Full machine-readable telemetry per task.
- `report.md`: Formatted comparative Markdown table.
- `predictions_bare.json`: Benchmark prediction output for Arm A.
- `predictions_demiurge.json`: Benchmark prediction output for Arm B.

### 6.2 Unit Verification Suite

Executes the deterministic runner test suite:

```bash
python evals/benchmarks/swebench/test_swebench_runner.py
python evals/benchmarks/cybergym/test_cybergym_runner.py
```

### 6.3 Live Benchmark Execution (Requires `--yes`)

Executes live evaluation against target models:

```bash
python evals/benchmarks/swebench/run_swebench_eval.py \
    --dataset princeton-nlp/SWE-bench_Lite \
    --slice 0:25 \
    --model claude-3-5-sonnet-20241022 \
    --output-dir eval_results/swebench_run1 \
    --yes

python evals/benchmarks/cybergym/run_cybergym_eval.py \
    --dataset sunblaze-ucb/cybergym \
    --slice 0:25 \
    --model claude-3-5-sonnet-20241022 \
    --output-dir eval_results/cybergym_run1 \
    --yes
```

---

## 7. Periodic Execution Cadence Matrix

To balance testing rigor with compute expenditure, benchmark runs follow a tiered schedule:

| Cadence | Suite & Scope | Target Component | Budget Profile | Execution Trigger |
|---|---|---|---|---|
| **Every Commit / PR** | Local Deterministic Gates (AST scans, security, tropes, links) | Syntax & Safety | $0.00 | Pre-commit Hook & GitHub Actions |
| **Weekly** | Promptfoo Adversarial Red-Teaming & Route Collision Matrix | Boundary Defense & Routing | < $1.00 | Scheduled GitHub Actions Workflow |
| **Bi-Weekly / Milestone** | SWE-bench Lite (25-task micro-slice) + GAIA Sample | Marcus Coding & Buckminster Research | $15–$25 | Developer Run (`scripts/run_benchmark_slice.sh`) |
| **Major Release (v0.2.0)** | Full SWE-bench Lite (300 tasks) + Tau-bench Suite | Architecture-Wide Comparison | $50–$150 | Release Candidate Verification Gate |
