#!/usr/bin/env python3
"""Pricing, cost and prompt helpers shared by every benchmark runner in this directory."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# USD per million tokens.
PRICING_PER_MILLION = {
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3},
    "claude-opus-4-8": {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.5},
    "gpt-5.5": {"input": 2.5, "output": 10.0, "cache_write": 2.5, "cache_read": 1.25},
    "gpt-4o": {"input": 2.5, "output": 10.0, "cache_write": 2.5, "cache_read": 1.25},
    "gemini-3.0-flash": {"input": 0.15, "output": 0.6, "cache_write": 0.15, "cache_read": 0.0375},
    "gemini-3.1-flash-lite-preview": {"input": 0.075, "output": 0.3, "cache_write": 0.075, "cache_read": 0.01875},
    "gemini-3-flash-preview": {"input": 0.15, "output": 0.6, "cache_write": 0.15, "cache_read": 0.0375},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.0, "cache_write": 1.25, "cache_read": 0.3125},
    "gemini-3.0-pro": {"input": 1.25, "output": 5.0, "cache_write": 1.25, "cache_read": 0.3125},
    "gemini-3.8-flash": {"input": 0.15, "output": 0.6, "cache_write": 0.15, "cache_read": 0.0375},
    "gemini-3.1-flash-lite": {"input": 0.075, "output": 0.3, "cache_write": 0.075, "cache_read": 0.01875},
}


def compute_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """USD cost of one task. An unpriced model raises instead of borrowing another model's rates."""
    rates = PRICING_PER_MILLION.get(model)
    if rates is None:
        raise ValueError(f"No price for model {model!r}; add it to PRICING_PER_MILLION in {Path(__file__).name}.")
    uncached = max(0, prompt_tokens - cache_read_tokens - cache_write_tokens)
    cost = (
        uncached * rates["input"]
        + completion_tokens * rates["output"]
        + cache_write_tokens * rates["cache_write"]
        + cache_read_tokens * rates["cache_read"]
    ) / 1_000_000
    return round(cost, 6)


def cost_change_percent(bare_cost: float, bare_resolved: int, demiurge_cost: float, demiurge_resolved: int) -> Optional[float]:
    """Percent change in cost per resolved task, or None when either arm resolved nothing.

    An arm with no resolved task has no cost per resolved task, so a 0 there would read as free.
    """
    if bare_resolved == 0 or demiurge_resolved == 0 or bare_cost <= 0:
        return None
    return round((demiurge_cost - bare_cost) / bare_cost * 100.0, 2)


def format_percent(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def load_rules(repo_root: Path) -> str:
    """Load canonical workspace rules from .agents/rules/ for prompt-cache prefix."""
    rules_dir = repo_root / ".agents" / "rules"
    if not rules_dir.is_dir():
        return ""

    contents = []
    for p in sorted(rules_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        contents.append(f"<!-- RULE: {p.name} -->\n{text.strip()}")
    return "\n\n".join(contents)


def load_marcus_skill(repo_root: Path) -> str:
    """Load the Marcus SKILL.md body without its frontmatter."""
    skill_path = repo_root / "skills" / "marcus" / "SKILL.md"
    if not skill_path.is_file():
        return ""
    text = skill_path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].strip()
    return text.strip()
