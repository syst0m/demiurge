---
name: Benchmark Synchronization
description: Permanent rule to automatically update README.md and BENCHMARKS.md with latest benchmark results.
always_on: true
---

# Context & Trigger

Whenever a benchmark evaluation is run or integrated into Demiurge (e.g. SWE-bench, CyberGym, ExploitBench, GAIA, Tau-bench, BIPIA, BFCL), you MUST:

1. Record full machine-readable telemetry artifacts in `eval_results/<benchmark>/`.
2. Update the canonical **Benchmark Run Registry** in [`docs/BENCHMARKS.md`](../../docs/BENCHMARKS.md).
3. Synchronize the top-level **Benchmark Run Registry** table in [`README.md`](../../README.md) with the latest model backbone, pass rates, resolution delta ($\Delta$), turn economy, and cost figures.

## Enforcement & Verification

- No benchmark run or release is complete without mirror updates in both `README.md` and `docs/BENCHMARKS.md`.
- Run link validation (`python scripts/check_links.py`) after updating registry links to ensure target paths exist.
