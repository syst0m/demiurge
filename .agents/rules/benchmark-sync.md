---
name: Benchmark Synchronization
description: Permanent rule to automatically update BENCHMARKS.md with latest benchmark results.
always_on: true
---

# Context & Trigger

Whenever a benchmark evaluation is run or integrated into Demiurge (e.g. SWE-bench, CyberGym, ExploitBench, GAIA, Tau-bench, BIPIA, BFCL), you MUST:

1. Record full machine-readable telemetry artifacts in `eval_results/<benchmark>/`.
2. Update the canonical **Benchmark Run Registry** in [`docs/BENCHMARKS.md`](../../docs/BENCHMARKS.md).

## Enforcement & Verification

- No benchmark run or release is complete without an updated registry row in `docs/BENCHMARKS.md`. The top-level `README.md` holds no registry.
- Run link validation (`python scripts/check_links.py`) after updating registry links to ensure target paths exist.
