#!/usr/bin/env python3
"""G6 - description collision check across an installed skill library.

Run it; do not read it.

    python route_check.py <skill-dir> --library <skills-root> [--json] [--threshold 0.45]

Exit codes:
    0  distinct enough to register
    1  moderate overlap - the description must name a distinguishing situation
    2  high overlap - this build is a revision of an existing skill

Why this gate exists: selection accuracy does not decay smoothly as a library grows, it
falls off a cliff, and same-capability ambiguity is the documented failure mode. Scoring
weights the *trigger* clause above the *what it does* clause, because the trigger is what a
request is actually matched against - the reviewed result here is that retrieval must score
constraint consistency. See references/EVIDENCE.md section 6.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

HIGH_OVERLAP = 0.45      # above this, treat the build as a revision
MODERATE_OVERLAP = 0.28  # above this, demand a distinguishing situation

# Words that carry no discriminating power in a skill description. Keeping them inflates
# every pairwise score and hides real collisions.
STOPWORDS = frozenset("""
a an the and or but if then than that this these those of to in on for with without from by as at
is are was were be been being it its use used uses using when whenever where which who whom what
how why can may might should must will would shall could do does did done not no any all some
you your user users claude agent agents skill skills task tasks file files work works working
""".split())

TOKEN = re.compile(r"[a-z][a-z0-9-]{1,}")
TRIGGER_SPLIT = re.compile(r"(?i)\b(use when|use for|when the user|when asked|whenever|when working)\b")


def read_description(skill_md: Path) -> str | None:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    key, parts = None, {}
    for raw in text[3:end].splitlines():
        if raw[:1] in " \t" and key:
            parts[key] += " " + raw.strip()
            continue
        if ":" in raw:
            key, _, value = raw.partition(":")
            key = key.strip()
            parts[key] = value.strip().strip("'\"")
    return parts.get("description")


def split_clauses(description: str) -> tuple[str, str]:
    """Return (what-it-does, when-to-use). The trigger clause is weighted higher."""
    match = TRIGGER_SPLIT.search(description)
    if not match:
        return description, ""
    return description[:match.start()], description[match.start():]


def vectorise(description: str) -> Counter:
    what, when = split_clauses(description)
    vector: Counter = Counter()
    for text, weight in ((what, 1.0), (when, 2.0)):
        for token in TOKEN.findall(text.lower()):
            if token not in STOPWORDS and len(token) > 2:
                vector[token] += weight
    return vector


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    numerator = sum(a[t] * b[t] for t in shared)
    if not numerator:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return numerator / (norm_a * norm_b)


def main() -> int:
    parser = argparse.ArgumentParser(description="G6 routing collision check.")
    parser.add_argument("skill_dir", type=Path)
    parser.add_argument("--library", type=Path, required=True, help="root containing installed skills")
    parser.add_argument("--threshold", type=float, default=HIGH_OVERLAP)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    skill_dir = args.skill_dir.expanduser().resolve()
    library = args.library.expanduser().resolve()

    candidate = read_description(skill_dir / "SKILL.md")
    if candidate is None:
        print(f"error: no readable description in {skill_dir}/SKILL.md", file=sys.stderr)
        return 2

    candidate_vector = vectorise(candidate)
    scores: list[tuple[float, str, list[str]]] = []
    for other_md in sorted(library.glob("*/SKILL.md")):
        if other_md.parent.resolve() == skill_dir:
            continue
        other = read_description(other_md)
        if not other:
            continue
        other_vector = vectorise(other)
        score = cosine(candidate_vector, other_vector)
        shared = sorted(set(candidate_vector) & set(other_vector),
                        key=lambda t: -(candidate_vector[t] + other_vector[t]))[:8]
        scores.append((score, other_md.parent.name, shared))

    scores.sort(reverse=True, key=lambda row: row[0])
    top = scores[0] if scores else (0.0, None, [])
    verdict = ("revision" if top[0] >= args.threshold
               else "needs-distinguishing" if top[0] >= MODERATE_OVERLAP
               else "distinct")

    if args.json:
        print(json.dumps({
            "gate": "G6",
            "skill": skill_dir.name,
            "compared_against": len(scores),
            "verdict": verdict,
            "top_overlap": round(top[0], 3),
            "nearest": top[1],
            "shared_terms": top[2],
            "all": [{"skill": n, "overlap": round(s, 3)} for s, n, _ in scores],
        }, indent=2))
    else:
        print(f"G6 routing check: {skill_dir.name}")
        print(f"compared against {len(scores)} installed skill(s) in {library.as_posix()}")
        print("-" * 72)
        for score, name, shared in scores[:6]:
            flag = "!!" if score >= args.threshold else " !" if score >= MODERATE_OVERLAP else "  "
            print(f"{flag} {score:5.3f}  {name}")
            if shared and score >= MODERATE_OVERLAP:
                print(f"          shared: {', '.join(shared)}")
        print("-" * 72)
        if verdict == "revision":
            print(f"G6 FAILED. Overlap {top[0]:.3f} with '{top[1]}' is above {args.threshold}.")
            print("This build is a revision of that skill. Edit it instead, or make the")
            print("two descriptions name genuinely different situations.")
        elif verdict == "needs-distinguishing":
            print(f"G6 WARNING. Overlap {top[0]:.3f} with '{top[1]}'.")
            print("Add a clause naming a situation that selects this skill and not that one,")
            print("then re-run. Selection accuracy falls off a cliff, it does not degrade gently.")
        else:
            print("G6 passed - description is distinct. Write PROVENANCE.md and register.")

    return {"revision": 2, "needs-distinguishing": 1, "distinct": 0}[verdict]


if __name__ == "__main__":
    sys.exit(main())
