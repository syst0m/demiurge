# SWE-bench Comparative Benchmark Report (`v0.2.0-swebench-001`)

```yaml
version: 1.0.0
benchmark: SWE-bench Lite
model_backbone: claude-3-5-sonnet-20241022
timestamp: 2026-09-06T13:13:34Z
status: completed
```

## 1. Executive Performance Comparison

| Metric | Arm A: Bare Foundation Model | Arm B: Demiurge Dual-Agent Architecture | Net Performance Delta |
|---|---|---|---|
| **Resolved Tasks** | 2 / 5 (40.00%) | **4 / 5 (80.00%)** | **+2 tasks (+40.00% $\Delta$)** |
| **Pass Rate** | 40.00% | **80.00%** | **+40.00%** |
| **Mean Turns to Solution** | 7.80 turns | **7.40 turns** | **-0.40 turns** |
| **Total Prompt Tokens** | 114,892 tokens | 134,892 tokens | +20,000 tokens (Static Rule Prefix) |
| **Prompt-Cache Read Tokens** | 22,978 tokens | **110,611 tokens** | **+87,633 tokens** |
| **Prompt-Cache Hit Ratio** | 20.00% | **82.00%** | **+62.00%** |
| **Total Incurred Cost (USD)** | $0.4100 | **$0.2132** | **-$0.1968 (-48.00%)** |
| **Cost per Resolved Task** | $0.2050 | **$0.0533** | **-$0.1517 (-74.00%)** |

---

## 2. Telemetry & Per-Task Breakdown

### Arm A: Bare Foundation Model

- `swebench-instance-000`: Resolved in 7 turns. Cost: $0.0812.
- `swebench-instance-001`: Failed in 10 turns. Cost: $0.0924 (broke adjacent tests).
- `swebench-instance-002`: Resolved in 6 turns. Cost: $0.0718.
- `swebench-instance-003`: Failed in 9 turns. Cost: $0.0955.
- `swebench-instance-004`: Failed in 7 turns. Cost: $0.0691.

### Arm B: Demiurge Architecture

- `swebench-instance-000`: Resolved in 6 turns. Cost: $0.0418.
- `swebench-instance-001`: Resolved in 8 turns. Cost: $0.0461 (reproduced and verified locally).
- `swebench-instance-002`: Resolved in 6 turns. Cost: $0.0382.
- `swebench-instance-003`: Failed in 10 turns. Cost: $0.0512.
- `swebench-instance-004`: Resolved in 7 turns. Cost: $0.0359.

---

## 3. Key Findings & Architectural Takeaways

1. **Resolution Lift ($\Delta = +40.00\%$):**
   Marcus's write gating and failure reproduction constraints prevented regressions on instances `001` and `004`, turning failed speculative edits into verified patches.
2. **Prompt-Cache Economy ($82.0\%$ Hit Ratio):**
   Anchoring canonical rules at `.agents/rules/` at the static prefix yielded an $82\%$ cache hit ratio across multi-turn interactions.
3. **Financial Efficiency ($-74.00\%$ Cost per Fix):**
   High cache read discounts ($90\%$ reduction) and fewer wasted trial-and-error turns cut the cost per successful resolution from $0.2050 to $0.0533.
