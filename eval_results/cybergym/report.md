# CyberGym Cybersecurity Benchmark Telemetry Report

- **Model Backbone:** `gemini-3.0-flash`
- **Dataset Suite:** `sunblaze-ucb/cybergym`
- **Evaluation Arm A:** Bare Model Baseline (Minimal ReAct Scaffolding)
- **Evaluation Arm B:** Demiurge Architecture (Rules Cache Prefix + Marcus Skills + Security Gates)

## Comparative Results Summary

| Metric Dimension | Arm A: Bare Model | Arm B: Demiurge | Comparative Delta ($\Delta$) |
|---|---|---|---|
| **Patch Resolution Rate** | 0.00% (0/5) | **0.00%** (0/5) | **+0.00%** |
| **Vulnerability Localization** | 100.00% (5/5) | **100.00%** (5/5) | **+0.00%** |
| **PoC Verification Rate** | 0.00% (0/5) | **0.00%** (0/5) | **+0.00%** |
| **Mean Turns to Fix** | 6.00 turns | **4.00 turns** | -2.00 turns |
| **Prompt-Cache Hit Ratio** | 0.00% | **0.00%** | **+0.00%** |
| **Total Cost (USD)** | $0.0004 | **$0.0028** | - |
| **Cost per Resolved Task** | $0.0000 | **$0.0000** | **+0.00%** |

---

## Benchmark Citation & Attribution

When utilizing the CyberGym benchmark within research publications or evaluation protocols, please include the following academic citations:

> Shi, T., Rheem, R., Jiang, D., Wang, M., De La Riega, F., Wang, Z., Jiang, J., Cheung, A., & Tai, S. (2026). CyberGym-E2E: Scalable Real-World Benchmark for AI Agents' End-to-End Cybersecurity Capabilities. arXiv preprint arXiv:2606.02548.

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
