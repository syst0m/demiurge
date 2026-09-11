#!/usr/bin/env python3
"""Deterministic train/heldout task splitting for the self-harness acceptance gate.

Benchmark runners load task instances live (dataset library, REST fallback, or a
generated fallback list), so the instance-ID universe for a suite is not fixed ahead
of a run. This module partitions whatever instance-ID list a run actually produced,
and caches the partition so repeat runs against the same task set stay comparable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "demiurge.self_harness.splits.v0"
DEFAULT_HELDOUT_FRACTION = 0.3


def _bucket_score(seed: int, task_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def compute_split(
    task_ids: list[str],
    seed: int,
    heldout_fraction: float = DEFAULT_HELDOUT_FRACTION,
) -> dict[str, list[str]]:
    """Partition task_ids into train/heldout, independent of input order.

    The same set of task_ids and seed always produce the same split, regardless of
    the order task_ids arrive in.
    """
    if not 0.0 < heldout_fraction < 1.0:
        raise ValueError("heldout_fraction must be between 0 and 1, exclusive")

    unique_ids = sorted(set(task_ids))
    if not unique_ids:
        return {"train": [], "heldout": []}

    ranked = sorted(unique_ids, key=lambda task_id: (_bucket_score(seed, task_id), task_id))
    heldout_count = max(1, round(len(ranked) * heldout_fraction)) if len(ranked) > 1 else 0
    heldout = sorted(ranked[:heldout_count])
    train = sorted(ranked[heldout_count:])
    return {"train": train, "heldout": heldout}


def load_or_create_splits(
    path: Path,
    task_ids: list[str],
    seed: int,
    heldout_fraction: float = DEFAULT_HELDOUT_FRACTION,
) -> dict[str, Any]:
    """Load a cached splits.json, extending it deterministically for unseen task_ids.

    Existing train/heldout assignments never move once cached; only task_ids absent
    from the cache are freshly assigned, so accepted-candidate history stays stable.
    """
    requested = set(task_ids)
    if path.is_file():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("format") != FORMAT:
            raise ValueError(f"{path}: unrecognized splits format {cached.get('format')!r}")
        if cached.get("seed") != seed:
            raise ValueError(
                f"{path}: cached seed {cached.get('seed')!r} does not match requested seed {seed!r}"
            )
        known_train = set(cached.get("train", []))
        known_heldout = set(cached.get("heldout", []))
        covered = known_train | known_heldout
        missing = sorted(requested - covered)
        if missing:
            fresh = compute_split(missing, seed, heldout_fraction)
            known_train |= set(fresh["train"])
            known_heldout |= set(fresh["heldout"])
        payload = {
            "format": FORMAT,
            "seed": seed,
            "heldout_fraction": heldout_fraction,
            "train": sorted(known_train),
            "heldout": sorted(known_heldout),
        }
    else:
        split = compute_split(sorted(requested), seed, heldout_fraction)
        payload = {
            "format": FORMAT,
            "seed": seed,
            "heldout_fraction": heldout_fraction,
            "train": split["train"],
            "heldout": split["heldout"],
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
