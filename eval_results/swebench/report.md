# SWE-bench Comparative Evaluation Report

- **Model Backbone:** `gemini-3.1-flash-lite-preview`
- **Dataset:** `princeton-nlp/SWE-bench_Lite`
- **Execution Mode:** `Live Benchmark`
- **Resolution Lift ($\Delta$):** `0.00%`

| Metric | Bare Foundation Model | Demiurge Architecture | Delta |
|---|---|---|---|
| **Resolved Tasks** | 2 / 2 | 2 / 2 | +0 |
| **Pass Rate** | 100.00% | 100.00% | 0.00% |
| **Mean Turns to Solution** | 6.00 | 4.00 | -2.00 |
| **Total Cost (USD)** | $0.0004 | $0.0010 | $+0.0006 |
| **Cost per Resolved Task** | $0.0002 | $0.0005 | +150.00% |
| **Prompt-Cache Hit Ratio** | 0.00% | 0.00% | +0.00% |

## Interpretation

- **Effectiveness:** Demiurge achieved parity or did not exceed the bare model.
- **Cache Optimization:** Demiurge achieved a 0.0% cache hit ratio by isolating static rules at the prompt prefix.
