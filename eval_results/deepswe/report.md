# DeepSWE Comparative Evaluation Report

> [!WARNING]
> **SIMULATION BASELINE**: This run was generated using `--dry-run` simulation mode.
> Token counts, turn counts, and resolution outcomes are synthetic mock estimates and DO NOT represent live API benchmark results.

- **Model Backbone:** `gemini-3.0-flash`
- **Dataset:** `datacurve-ai/deep-swe`
- **Execution Mode:** `Simulated (Dry-Run)`
- **Resolution Lift ($\Delta$):** `+100.00%`

| Metric | Bare Foundation Model | Demiurge Architecture | Delta |
|---|---|---|---|
| **Resolved Tasks** | 0 / 10 | 10 / 10 | +10 |
| **Pass Rate** | 0.00% | 100.00% | +100.00% |
| **Mean Turns to Solution** | 6.00 | 4.00 | -2.00 |
| **Total Cost (USD)** | $0.0213 | $0.0132 | $-0.0081 |
| **Cost per Resolved Task** | $0.0000 | $0.0013 | +0.00% |
| **Prompt-Cache Hit Ratio** | 0.00% | 76.00% | +76.00% |

## Interpretation

- **Effectiveness:** Demiurge outperformed the bare model baseline.
- **Cache Optimization:** Demiurge achieved a 76.0% cache hit ratio by isolating static rules at the prompt prefix.
