#!/usr/bin/env python3
"""Benchmark metrics and comparative telemetry engine for CyberGym cybersecurity evaluations.

Calculates:
- Resolution lift: Delta = PassRate(Demiurge) - PassRate(Bare)
- Vulnerability localization & PoC generation success rates
- Prompt-cache efficiency: CacheHitRatio = CacheReadTokens / TotalPromptTokens
- Turn economy: Mean turns to valid patch or fix
- Cost per resolved task (USD)
- Citations & BibTeX references for CyberGym (sunblaze-ucb/cybergym)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Standard pricing models (per million tokens) for cost calculation
PRICING_PER_MILLION = {
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00,
        "cache_write": 2.50,
        "cache_read": 1.25,
    },
    "gemini-3-flash-preview": {
        "input": 0.15,
        "output": 0.60,
        "cache_write": 0.15,
        "cache_read": 0.0375,
    },
    "gemini-3.0-flash": {
        "input": 0.15,
        "output": 0.60,
        "cache_write": 0.15,
        "cache_read": 0.0375,
    },
    "gemini-3.1-pro-preview": {
        "input": 1.25,
        "output": 5.00,
        "cache_write": 1.25,
        "cache_read": 0.3125,
    },
    "gemini-3.0-pro": {
        "input": 1.25,
        "output": 5.00,
        "cache_write": 1.25,
        "cache_read": 0.3125,
    },
    "gemini-3.8-flash": {
        "input": 0.15,
        "output": 0.60,
        "cache_write": 0.15,
        "cache_read": 0.0375,
    },
    "gemini-3.1-flash-lite-preview": {
        "input": 0.075,
        "output": 0.30,
        "cache_write": 0.075,
        "cache_read": 0.01875,
    },
    "gemini-3.1-flash-lite": {
        "input": 0.075,
        "output": 0.30,
        "cache_write": 0.075,
        "cache_read": 0.01875,
    },
}

CYBERGYM_CITATIONS = {
    "framework_apa": (
        "Wang, Z., Shi, T., He, J., Cai, M., Zhang, J., & Song, D. (2025). "
        "CyberGym: Evaluating AI Agents' Real-World Cybersecurity Capabilities at Scale. "
        "arXiv preprint arXiv:2506.02548."
    ),
    "e2e_apa": (
        "Shi, T., Rheem, R., Jiang, D., Wang, M., De La Riega, F., Wang, Z., Jiang, J., Cheung, A., & Tai, S. (2026). "
        "CyberGym-E2E: Scalable Real-World Benchmark for AI Agents' End-to-End Cybersecurity Capabilities. "
        "arXiv preprint arXiv:2606.02548."
    ),
    "bibtex": (
        "@inproceedings{shi2026cybergyme2e,\n"
        "  title={CyberGym-E2E: Scalable Real-World Benchmark for AI Agents' End-to-End Cybersecurity Capabilities},\n"
        "  author={Shi, Tianneng and Rheem, Robin and Jiang, Dongwei and Wang, Mona and De La Riega, Francisco and "
        "Wang, Zhun and Jiang, Jingzhi and Cheung, Alexander and Tai, Sean},\n"
        "  year={2026}\n"
        "}\n\n"
        "@article{wang2025cybergym,\n"
        "  title={CyberGym: Evaluating AI Agents' Real-World Cybersecurity Capabilities at Scale},\n"
        "  author={Wang, Zhun and Shi, Tianneng and He, Jiacen and Cai, Minghao and Zhang, Junhua and Song, Dawn},\n"
        "  journal={arXiv preprint arXiv:2506.02548},\n"
        "  year={2025}\n"
        "}"
    ),
}


@dataclass
class TaskResult:
    instance_id: str
    arm: str  # "bare" or "demiurge"
    resolved: bool
    localized: bool
    poc_generated: bool
    turns: int
    prompt_tokens: int
    completion_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    error: Optional[str] = None


@dataclass
class ArmSummary:
    arm: str
    total_tasks: int
    resolved_count: int
    pass_rate: float
    localized_count: int
    localization_rate: float
    poc_count: int
    poc_rate: float
    mean_turns: float
    total_cost_usd: float
    cost_per_resolved_task: float
    cache_hit_ratio: float


@dataclass
class BenchmarkComparison:
    model: str
    dataset: str
    bare: ArmSummary
    demiurge: ArmSummary
    resolution_delta: float
    localization_delta: float
    poc_delta: float
    cost_reduction_percent: float
    cache_hit_delta: float


def compute_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Calculate USD execution cost based on provider token pricing."""
    rates = PRICING_PER_MILLION.get(model, PRICING_PER_MILLION["claude-3-5-sonnet-20241022"])
    uncached_input = max(0, prompt_tokens - cache_read_tokens - cache_write_tokens)

    cost = (
        (uncached_input * rates["input"] / 1_000_000)
        + (completion_tokens * rates["output"] / 1_000_000)
        + (cache_read_tokens * rates["cache_read"] / 1_000_000)
        + (cache_write_tokens * rates["cache_write"] / 1_000_000)
    )
    return round(cost, 6)


def summarize_arm(arm_name: str, results: List[TaskResult]) -> ArmSummary:
    """Aggregate individual task telemetry into arm-level metrics summary."""
    if not results:
        return ArmSummary(
            arm=arm_name,
            total_tasks=0,
            resolved_count=0,
            pass_rate=0.0,
            localized_count=0,
            localization_rate=0.0,
            poc_count=0,
            poc_rate=0.0,
            mean_turns=0.0,
            total_cost_usd=0.0,
            cost_per_resolved_task=0.0,
            cache_hit_ratio=0.0,
        )

    total_tasks = len(results)
    resolved_count = sum(1 for r in results if r.resolved)
    localized_count = sum(1 for r in results if r.localized)
    poc_count = sum(1 for r in results if r.poc_generated)

    pass_rate = round(resolved_count / total_tasks, 4)
    localization_rate = round(localized_count / total_tasks, 4)
    poc_rate = round(poc_count / total_tasks, 4)

    mean_turns = round(sum(r.turns for r in results) / total_tasks, 2)
    total_cost = round(sum(r.cost_usd for r in results), 6)

    cost_per_resolved = round(total_cost / resolved_count, 6) if resolved_count > 0 else 0.0

    total_prompt = sum(r.prompt_tokens for r in results)
    total_cache_read = sum(r.cache_read_tokens for r in results)
    cache_hit_ratio = round(total_cache_read / total_prompt, 4) if total_prompt > 0 else 0.0

    return ArmSummary(
        arm=arm_name,
        total_tasks=total_tasks,
        resolved_count=resolved_count,
        pass_rate=pass_rate,
        localized_count=localized_count,
        localization_rate=localization_rate,
        poc_count=poc_count,
        poc_rate=poc_rate,
        mean_turns=mean_turns,
        total_cost_usd=total_cost,
        cost_per_resolved_task=cost_per_resolved,
        cache_hit_ratio=cache_hit_ratio,
    )


def compare_arms(
    model: str,
    dataset: str,
    bare_results: List[TaskResult],
    demiurge_results: List[TaskResult],
) -> BenchmarkComparison:
    """Compare Bare Model baseline vs Demiurge Architecture treatment."""
    bare_summary = summarize_arm("bare", bare_results)
    demiurge_summary = summarize_arm("demiurge", demiurge_results)

    resolution_delta = round(demiurge_summary.pass_rate - bare_summary.pass_rate, 4)
    localization_delta = round(demiurge_summary.localization_rate - bare_summary.localization_rate, 4)
    poc_delta = round(demiurge_summary.poc_rate - bare_summary.poc_rate, 4)
    cache_hit_delta = round(demiurge_summary.cache_hit_ratio - bare_summary.cache_hit_ratio, 4)

    if bare_summary.cost_per_resolved_task > 0:
        cost_reduction = (
            (bare_summary.cost_per_resolved_task - demiurge_summary.cost_per_resolved_task)
            / bare_summary.cost_per_resolved_task
        ) * 100
    else:
        cost_reduction = 0.0

    return BenchmarkComparison(
        model=model,
        dataset=dataset,
        bare=bare_summary,
        demiurge=demiurge_summary,
        resolution_delta=resolution_delta,
        localization_delta=localization_delta,
        poc_delta=poc_delta,
        cost_reduction_percent=round(cost_reduction, 2),
        cache_hit_delta=cache_hit_delta,
    )


def render_markdown_report(comp: BenchmarkComparison) -> str:
    """Render human-readable Markdown telemetry comparison table."""
    delta_str = f"+{comp.resolution_delta * 100:.2f}%" if comp.resolution_delta >= 0 else f"{comp.resolution_delta * 100:.2f}%"
    loc_delta_str = f"+{comp.localization_delta * 100:.2f}%" if comp.localization_delta >= 0 else f"{comp.localization_delta * 100:.2f}%"
    poc_delta_str = f"+{comp.poc_delta * 100:.2f}%" if comp.poc_delta >= 0 else f"{comp.poc_delta * 100:.2f}%"

    return rf"""# CyberGym Cybersecurity Benchmark Telemetry Report

- **Model Backbone:** `{comp.model}`
- **Dataset Suite:** `{comp.dataset}`
- **Evaluation Arm A:** Bare Model Baseline (Minimal ReAct Scaffolding)
- **Evaluation Arm B:** Demiurge Architecture (Rules Cache Prefix + Marcus Skills + Security Gates)

## Comparative Results Summary

| Metric Dimension | Arm A: Bare Model | Arm B: Demiurge | Comparative Delta ($\Delta$) |
|---|---|---|---|
| **Patch Resolution Rate** | {comp.bare.pass_rate * 100:.2f}% ({comp.bare.resolved_count}/{comp.bare.total_tasks}) | **{comp.demiurge.pass_rate * 100:.2f}%** ({comp.demiurge.resolved_count}/{comp.demiurge.total_tasks}) | **{delta_str}** |
| **Vulnerability Localization** | {comp.bare.localization_rate * 100:.2f}% ({comp.bare.localized_count}/{comp.bare.total_tasks}) | **{comp.demiurge.localization_rate * 100:.2f}%** ({comp.demiurge.localized_count}/{comp.demiurge.total_tasks}) | **{loc_delta_str}** |
| **PoC Verification Rate** | {comp.bare.poc_rate * 100:.2f}% ({comp.bare.poc_count}/{comp.bare.total_tasks}) | **{comp.demiurge.poc_rate * 100:.2f}%** ({comp.demiurge.poc_count}/{comp.demiurge.total_tasks}) | **{poc_delta_str}** |
| **Mean Turns to Fix** | {comp.bare.mean_turns:.2f} turns | **{comp.demiurge.mean_turns:.2f} turns** | {comp.demiurge.mean_turns - comp.bare.mean_turns:+.2f} turns |
| **Prompt-Cache Hit Ratio** | {comp.bare.cache_hit_ratio * 100:.2f}% | **{comp.demiurge.cache_hit_ratio * 100:.2f}%** | **+{comp.cache_hit_delta * 100:.2f}%** |
| **Total Cost (USD)** | ${comp.bare.total_cost_usd:.4f} | **${comp.demiurge.total_cost_usd:.4f}** | - |
| **Cost per Resolved Task** | ${comp.bare.cost_per_resolved_task:.4f} | **${comp.demiurge.cost_per_resolved_task:.4f}** | **{comp.cost_reduction_percent:+.2f}%** |

---

## Benchmark Citation & Attribution

When utilizing the CyberGym benchmark within research publications or evaluation protocols, please include the following academic citations:

> {CYBERGYM_CITATIONS['e2e_apa']}

```bibtex
{CYBERGYM_CITATIONS['bibtex']}
```
"""
