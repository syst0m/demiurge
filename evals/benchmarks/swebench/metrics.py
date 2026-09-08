#!/usr/bin/env python3
"""Benchmark metrics and comparative telemetry engine for SWE-bench evaluations.

Calculates:
- Resolution lift: Delta = PassRate(Demiurge) - PassRate(Bare)
- Prompt-cache efficiency: CacheHitRatio = CacheReadTokens / TotalPromptTokens
- Turn economy: Mean turns to valid patch
- Cost per resolved task (USD)
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


@dataclass
class TaskResult:
    instance_id: str
    arm: str  # "bare" or "demiurge"
    resolved: bool
    turns: int
    prompt_tokens: int
    completion_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    simulated: bool = False
    error: Optional[str] = None


@dataclass
class ArmSummary:
    arm: str
    total_tasks: int
    resolved_count: int
    pass_rate: float
    mean_turns: float
    total_cost_usd: float
    cost_per_resolved_task: float
    cache_hit_ratio: float
    simulated: bool = False


@dataclass
class BenchmarkComparison:
    model: str
    dataset: str
    bare: ArmSummary
    demiurge: ArmSummary
    resolution_delta: float
    cost_delta_percentage: float
    cache_savings_percentage: float
    simulated: bool = False


def compute_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
) -> float:
    """Calculate USD cost based on token usage and model pricing."""
    pricing = PRICING_PER_MILLION.get(
        model,
        {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    )
    base_prompt = max(0, prompt_tokens - cache_read_tokens - cache_write_tokens)
    cost = (
        (base_prompt / 1_000_000.0) * pricing["input"]
        + (completion_tokens / 1_000_000.0) * pricing["output"]
        + (cache_write_tokens / 1_000_000.0) * pricing["cache_write"]
        + (cache_read_tokens / 1_000_000.0) * pricing["cache_read"]
    )
    return round(cost, 6)


def summarize_arm(arm_name: str, results: List[TaskResult]) -> ArmSummary:
    """Summarize performance and cost metrics for an experimental arm."""
    if not results:
        return ArmSummary(
            arm=arm_name,
            total_tasks=0,
            resolved_count=0,
            pass_rate=0.0,
            mean_turns=0.0,
            total_cost_usd=0.0,
            cost_per_resolved_task=0.0,
            cache_hit_ratio=0.0,
            simulated=False,
        )

    total = len(results)
    resolved = sum(1 for r in results if r.resolved)
    total_turns = sum(r.turns for r in results)
    total_cost = sum(r.cost_usd for r in results)
    total_prompt = sum(r.prompt_tokens for r in results)
    total_cache_read = sum(r.cache_read_tokens for r in results)
    is_simulated = any(r.simulated for r in results)

    pass_rate = resolved / total if total > 0 else 0.0
    mean_turns = total_turns / total if total > 0 else 0.0
    cost_per_resolved = total_cost / resolved if resolved > 0 else 0.0
    cache_hit_ratio = total_cache_read / total_prompt if total_prompt > 0 else 0.0

    return ArmSummary(
        arm=arm_name,
        total_tasks=total,
        resolved_count=resolved,
        pass_rate=round(pass_rate, 4),
        mean_turns=round(mean_turns, 2),
        total_cost_usd=round(total_cost, 4),
        cost_per_resolved_task=round(cost_per_resolved, 4),
        cache_hit_ratio=round(cache_hit_ratio, 4),
        simulated=is_simulated,
    )


def compare_arms(
    model: str,
    dataset: str,
    bare_results: List[TaskResult],
    demiurge_results: List[TaskResult],
) -> BenchmarkComparison:
    """Compare Bare Baseline against Demiurge Treatment."""
    bare = summarize_arm("bare", bare_results)
    demiurge = summarize_arm("demiurge", demiurge_results)

    delta = round(demiurge.pass_rate - bare.pass_rate, 4)

    if bare.cost_per_resolved_task > 0:
        cost_delta = round(
            ((demiurge.cost_per_resolved_task - bare.cost_per_resolved_task)
             / bare.cost_per_resolved_task)
            * 100.0,
            2,
        )
    else:
        cost_delta = 0.0

    savings = round((demiurge.cache_hit_ratio - bare.cache_hit_ratio) * 100.0, 2)
    is_simulated = bare.simulated or demiurge.simulated

    return BenchmarkComparison(
        model=model,
        dataset=dataset,
        bare=bare,
        demiurge=demiurge,
        resolution_delta=delta,
        cost_delta_percentage=cost_delta,
        cache_savings_percentage=savings,
        simulated=is_simulated,
    )


def render_markdown_report(comparison: BenchmarkComparison) -> str:
    """Render a GitHub-flavored Markdown comparison table."""
    delta_symbol = "+" if comparison.resolution_delta > 0 else ""
    simulated_banner = ""
    if comparison.simulated:
        simulated_banner = (
            "> [!WARNING]\n"
            "> **SIMULATION BASELINE**: This run was generated using `--dry-run` simulation mode.\n"
            "> Token counts, turn counts, and resolution outcomes are synthetic mock estimates and DO NOT represent live API benchmark results.\n\n"
        )

    return f"""# SWE-bench Comparative Evaluation Report

{simulated_banner}- **Model Backbone:** `{comparison.model}`
- **Dataset:** `{comparison.dataset}`
- **Execution Mode:** `{'Simulated (Dry-Run)' if comparison.simulated else 'Live Benchmark'}`
- **Resolution Lift ($\\Delta$):** `{delta_symbol}{comparison.resolution_delta * 100:.2f}%`

| Metric | Bare Foundation Model | Demiurge Architecture | Delta |
|---|---|---|---|
| **Resolved Tasks** | {comparison.bare.resolved_count} / {comparison.bare.total_tasks} | {comparison.demiurge.resolved_count} / {comparison.demiurge.total_tasks} | {comparison.demiurge.resolved_count - comparison.bare.resolved_count:+d} |
| **Pass Rate** | {comparison.bare.pass_rate * 100:.2f}% | {comparison.demiurge.pass_rate * 100:.2f}% | {delta_symbol}{comparison.resolution_delta * 100:.2f}% |
| **Mean Turns to Solution** | {comparison.bare.mean_turns:.2f} | {comparison.demiurge.mean_turns:.2f} | {comparison.demiurge.mean_turns - comparison.bare.mean_turns:+.2f} |
| **Total Cost (USD)** | ${comparison.bare.total_cost_usd:.4f} | ${comparison.demiurge.total_cost_usd:.4f} | ${comparison.demiurge.total_cost_usd - comparison.bare.total_cost_usd:+.4f} |
| **Cost per Resolved Task** | ${comparison.bare.cost_per_resolved_task:.4f} | ${comparison.demiurge.cost_per_resolved_task:.4f} | {comparison.cost_delta_percentage:+.2f}% |
| **Prompt-Cache Hit Ratio** | {comparison.bare.cache_hit_ratio * 100:.2f}% | {comparison.demiurge.cache_hit_ratio * 100:.2f}% | {comparison.cache_savings_percentage:+.2f}% |

### Interpretation
- **Effectiveness:** {'Demiurge outperformed the bare model baseline.' if comparison.resolution_delta > 0 else 'Demiurge achieved parity or did not exceed the bare model.'}
- **Cache Optimization:** Demiurge achieved a {comparison.demiurge.cache_hit_ratio * 100:.1f}% cache hit ratio by isolating static rules at the prompt prefix.
"""
