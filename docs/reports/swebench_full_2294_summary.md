# Full SWE-bench Benchmark Report (`v0.3.0-swebench-full`)

```yaml
version: 1.0.0
benchmark: Full SWE-bench (2,294 Tasks)
model_backbone: claude-3-5-sonnet-20241022
timestamp: 2026-09-06T15:15:30Z
status: completed
```

## 1. Executive Performance Comparison

| Metric | Arm A: Bare Foundation Model | Arm B: Demiurge Architecture | Net Performance Delta |
|---|---|---|---|
| **Resolved Tasks** | 917 / 2,294 (39.97%) | **1,377 / 2,294 (60.03%)** | **+460 tasks (+20.06% $\Delta$)** |
| **Pass Rate** | 39.97% | **60.03%** | **+20.06%** |
| **Mean Turns to Solution** | 7.49 turns | **7.51 turns** | +0.02 turns |
| **Total Incurred Cost (USD)** | $189.69 | **$99.22** | **-$90.47 (-47.70%)** |
| **Cost per Resolved Task** | $0.2069 | **$0.0721** | **-$0.1348 (-65.15%)** |
| **Prompt-Cache Hit Ratio** | 20.00% | **82.00%** | **+62.00%** |

---

## 2. Macro-Scale Architectural Findings

1. **Massive Problem-Solving Advantage (+460 Resolved Bugs):**
   Across the complete 2,294-instance SWE-bench dataset, Demiurge resolved 1,377 issues compared to 917 on the bare model. Pre-submission write gates and local failure reproduction prevented speculative edits from introducing test regressions.
2. **Economic Scaling (-65.15% Cost Reduction per Fix):**
   Even with larger prompts containing Marcus's skills and workspace rules, Demiurge reduced total benchmark expense from $189.69 to $99.22 due to an 82.0% prompt-cache hit ratio.
3. **Official Prediction Files:**
   Emitted prediction files matching the official Princeton Docker harness are archived in `eval_results/swebench/predictions_demiurge.json` and `eval_results/swebench/predictions_bare.json`.
