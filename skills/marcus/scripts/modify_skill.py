#!/usr/bin/env python3
"""G0-G3 for modifications - scaffold a modification or feature addition to an existing skill.

Run it; do not read it.

    python modify_skill.py <path-or-name> \
        --feature "short feature description" \
        --evidence "what the skill failed to do, or why this feature is needed" \
        [--evidence "second failure or gap"] \
        [--evidence "third failure or gap"] \
        [--dir ~/.claude/skills]

Exit codes:
    0  scaffolded revision
    2  refused (missing target, insufficient evidence, invalid inputs)

Non-negotiable rule: Modifying a skill or adding a feature requires evidence of failure,
deficiency, or a real user gap (G0). Adding features without recorded failures produces
instruction creep and prompt bloat. Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

MIN_EVIDENCE = 1
RECOMMENDED_EVIDENCE = 3


def refuse(message: str) -> int:
    print(f"REFUSED: {message}", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Modify an existing skill, evidence-gated.")
    parser.add_argument("target", help="path to the skill directory, or skill name in --dir")
    parser.add_argument("--feature", required=True, help="description or name of the feature/modification")
    parser.add_argument("--evidence", action="append", default=[],
                        help="a real failure, deficiency, or user gap this modification addresses")
    parser.add_argument("--dir", type=Path, default=Path("~/.claude/skills"),
                        help="library directory if target is a bare skill name")
    args = parser.parse_args()

    # Resolve target directory
    raw_path = Path(args.target).expanduser()
    if raw_path.exists() and raw_path.is_dir():
        skill_dir = raw_path.resolve()
    else:
        candidate = (args.dir.expanduser() / args.target).resolve()
        if candidate.exists() and candidate.is_dir():
            skill_dir = candidate
        else:
            return refuse(f"skill directory not found: neither {raw_path} nor {candidate} exists")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return refuse(f"not a valid skill: {skill_md} does not exist")

    feature = args.feature.strip()
    if not feature:
        return refuse("feature description must not be empty")

    evidence = [e.strip() for e in args.evidence if e.strip()]
    if len(evidence) < MIN_EVIDENCE:
        print(f"REFUSED: {len(evidence)} recorded failure(s)/gap(s); at least {MIN_EVIDENCE} is required.\n",
              file=sys.stderr)
        print("This is gate G0 for skill modifications. Modifying instructions without evidence\n"
              "of an actual deficiency causes instruction creep and degrades performance.\n"
              "Provide real failures or gaps using --evidence.\n", file=sys.stderr)
        return 2

    # Update evals/evals.json if present, or create it
    evals_path = skill_dir / "evals" / "evals.json"
    evals_data = {}
    if evals_path.is_file():
        try:
            evals_data = json.loads(evals_path.read_text(encoding="utf-8"))
        except Exception:
            evals_data = {}

    timestamp = dt.date.today().isoformat()
    feature_slug = re.sub(r"[^a-z0-9]+", "-", feature.lower()).strip("-")[:32] or "mod"

    new_cases = [
        {
            "id": f"regression-{feature_slug}-{i}",
            "suite": "regression",
            "feature": feature,
            "query": f"TODO - request exercising {feature}: {e}",
            "expected_behavior": [f"TODO - what correct handling looks like for: {e}"],
        }
        for i, e in enumerate(evidence, 1)
    ]

    if "cases" in evals_data and isinstance(evals_data["cases"], list):
        evals_data["cases"].extend(new_cases)
    elif "suites" in evals_data and isinstance(evals_data["suites"], dict):
        reg = evals_data["suites"].setdefault("regression", {})
        if "cases" in reg and isinstance(reg["cases"], list):
            reg["cases"].extend(new_cases)
        else:
            reg["cases"] = new_cases
    else:
        evals_data = {
            "skill": skill_dir.name,
            "notes": "Regression cases from real failures. Must hold at 100%.",
            "cases": new_cases,
        }

    evals_path.parent.mkdir(parents=True, exist_ok=True)
    evals_path.write_text(json.dumps(evals_data, indent=2) + "\n", encoding="utf-8")

    # Update PROVENANCE.md (append-only)
    prov_path = skill_dir / "PROVENANCE.md"
    existing_prov = prov_path.read_text(encoding="utf-8") if prov_path.is_file() else "# PROVENANCE\n"

    # Count existing revisions
    rev_matches = re.findall(r"^## Revision \d+", existing_prov, flags=re.MULTILINE)
    rev_num = len(rev_matches) + 1

    evidence_formatted = "\n".join(f"{i}. {e}" for i, e in enumerate(evidence, 1))

    rev_block = f"""

## Revision {rev_num}: {feature} ({timestamp})

```yaml
revision: {rev_num}
feature: {feature}
date: {timestamp}
trust_tier: T2          # T2 until G5 passes; existing production deployment holds prior tier
gate_reached: G3
pre_revision_baseline: null   # G1 - fill from eval_runner.py {skill_dir.as_posix()} --baseline
post_revision_score: null     # G5 - fill from eval_runner.py {skill_dir.as_posix()}
delta: null
regression_pass_rate: null    # G5 - MUST be 100% on historical regression suite
model_harness_pair: null
```

### Evidence of need (G0)

{evidence_formatted}

### What has not been verified for this revision

- The skill instructions have been modified but not yet proven. Trust tier for this revision
  is T2 until `eval_runner.py` demonstrates a positive delta on the new test cases AND 100%
  pass rate on the pre-existing regression suite.
"""
    prov_path.write_text(existing_prov + rev_block, encoding="utf-8")

    print(f"Scaffolded revision {rev_num} for {skill_dir.as_posix()} at gate G3.")
    print(f"  Feature: {feature}")
    print(f"  Added {len(evidence)} new regression case(s) to evals/evals.json.")
    print(f"  Appended Revision {rev_num} to PROVENANCE.md.")
    print("\nNext steps:")
    print(f"  1. Fill the TODO queries/expected_behavior in evals/evals.json.")
    print(f"  2. Measure baseline of the UNMODIFIED skill on the new suite:")
    print(f"     python scripts/eval_runner.py {skill_dir.as_posix()} --baseline    # G1")
    print(f"  3. Apply the minimal instructions/changes to SKILL.md (and references/scripts).")
    print(f"  4. Format and security check:")
    print(f"     python scripts/validate_skill.py {skill_dir.as_posix()}            # G4")
    print(f"  5. Prove non-regression (100% historical pass) and positive lift:")
    print(f"     python scripts/eval_runner.py {skill_dir.as_posix()}               # G5")
    print(f"  6. Check route collisions if description was updated:")
    print(f"     python scripts/route_check.py {skill_dir.as_posix()} --library {args.dir.expanduser().as_posix()} # G6")

    return 0


if __name__ == "__main__":
    sys.exit(main())
