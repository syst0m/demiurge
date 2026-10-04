#!/usr/bin/env python3
"""G0-G3 for modifications - scaffold a modification or feature addition to an existing skill.

Run it; do not read it.

    python modify_skill.py <path-or-name> \
        --feature "short feature description" \
        --evidence "what the skill failed to do, or why this feature is needed" \
        [--evidence "second failure or gap"] \
        [--evidence ledger:<run_id>] \
        [--dir ~/.claude/skills]

An --evidence value of the form `ledger:<run_id>` cites a run from the run ledger
($DEMIURGE_LEDGER_DIR or ~/.demiurge/ledger/). The run must exist, belong to the target
skill, and carry `bad` as its latest label. The ledger is read and never written. Only the
run id, failure class, label source and origin reach PROVENANCE.md and the new regression
case. Ledger rows hold no prompt text, and the verdict note is not copied.

Exit codes:
    0  scaffolded revision
    2  refused (missing target, insufficient evidence, invalid inputs, or a ledger run
       that is missing, belongs to another skill, or is not labeled bad)

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

from new_skill import research_snapshot

MIN_EVIDENCE = 1
RECOMMENDED_EVIDENCE = 3
LEDGER_PREFIX = "ledger:"
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def refuse(message: str) -> int:
    print(f"REFUSED: {message}", file=sys.stderr)
    return 2


def skill_names(skill_dir: Path) -> set[str]:
    """Names a ledger row may use for this skill: its directory name and frontmatter name."""
    names = {skill_dir.name}
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    front = re.match(r"^---\s*\n(.*?)\n---", text, flags=re.DOTALL)
    if front:
        name = re.search(r"^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", front.group(1),
                         flags=re.MULTILINE)
        if name:
            names.add(name.group(1).strip())
    return names


def ledger_evidence(run_id: str, names: set[str]) -> tuple[str | None, str]:
    """Resolve one `ledger:<run_id>` citation to (evidence line, "") or (None, refusal)."""
    if not RUN_ID.match(run_id):
        return None, f"ledger run id {run_id!r} must match {RUN_ID.pattern}"
    import ledger_lib

    rows = ledger_lib.find(run_id)
    if not rows:
        return None, (f"no ledger row for run_id {run_id!r} in "
                      f"{ledger_lib.ledger_dir().as_posix()}")
    skill = rows[0]["skill"]
    if skill not in names and skill.rsplit(":", 1)[-1] not in names:
        return None, f"ledger run {run_id} belongs to {skill!r}, not {sorted(names)}"
    verdicts = [row for row in rows if row["kind"] == "verdict"]
    if not verdicts:
        return None, (f"ledger run {run_id} has no verdict; label it first with "
                      f"ledger.py verdict {run_id} --label bad --class <class>")
    outcome = verdicts[-1]["outcome"]
    if outcome["label"] != "bad":
        return None, (f"ledger run {run_id} is labeled {outcome['label']!r}; only a run "
                      f"labeled 'bad' is evidence of a failure")
    failure_class = outcome.get("failure_class", "unclassified")
    return (f"{LEDGER_PREFIX}{run_id} - {skill} run labeled bad ({failure_class}) by "
            f"{outcome['source']}, {rows[0]['origin']} run"), ""


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

    # Resolve ledger citations before anything is written; one bad citation refuses the run.
    ledger_runs: list[str] = []
    names = skill_names(skill_dir)
    for index, item in enumerate(evidence):
        if not item.startswith(LEDGER_PREFIX):
            continue
        run_id = item[len(LEDGER_PREFIX):].strip()
        if run_id in ledger_runs:
            return refuse(f"ledger run {run_id} is cited more than once")
        line, reason = ledger_evidence(run_id, names)
        if line is None:
            return refuse(reason)
        evidence[index] = line
        ledger_runs.append(run_id)

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

    new_cases = []
    for i, e in enumerate(evidence, 1):
        case = {
            "id": f"regression-{feature_slug}-{i}",
            "suite": "regression",
            "feature": feature,
            "query": f"TODO - request exercising {feature}: {e}",
            "expected_behavior": [f"TODO - what correct handling looks like for: {e}"],
        }
        if e.startswith(LEDGER_PREFIX):
            case["provenance"] = e.split(" ", 1)[0]
        new_cases.append(case)

    if "cases" in evals_data and isinstance(evals_data["cases"], list):
        evals_data["cases"].extend(new_cases)
    elif "suites" in evals_data and isinstance(evals_data["suites"], dict):
        suites = evals_data["suites"]
        if "regression" not in suites:
            suites["regression"] = {"cases": new_cases}
        elif isinstance(suites["regression"], list):
            suites["regression"].extend(new_cases)
        elif isinstance(suites["regression"], dict):
            reg = suites["regression"]
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
research_snapshot: {research_snapshot()}
research_claims: []           # claim ids from marcus references/claims.json this revision rests on
ledger_evidence: {json.dumps(ledger_runs)}   # run ids cited as ledger:<run_id>, metadata only
```

### Evidence of need (G0)

{evidence_formatted}

### What has not been verified for this revision

- The skill instructions have been modified but not yet proven. Trust tier for this revision
  is T2 until `eval_runner.py` shows b > c per case; McNemar p < alpha at 20 or more cases; regression at 100%
  against the G1 baseline.
"""
    prov_path.write_text(existing_prov + rev_block, encoding="utf-8")

    print(f"Scaffolded revision {rev_num} for {skill_dir.as_posix()} at gate G3.")
    print(f"  Feature: {feature}")
    print(f"  Added {len(evidence)} new regression case(s) to evals/evals.json.")
    if ledger_runs:
        print(f"  Cited {len(ledger_runs)} ledger run(s): {', '.join(ledger_runs)}. A case "
              "staged by ledger.py promote is copied into evals.json by hand.")
    print(f"  Appended Revision {rev_num} to PROVENANCE.md.")
    print("\nNext steps:")
    print(f"  1. Fill the TODO queries/expected_behavior in evals/evals.json.")
    print(f"  2. Measure baseline of the UNMODIFIED skill on the new suite:")
    print(f"     python scripts/eval_runner.py {skill_dir.as_posix()} --baseline    # G1")
    print(f"  3. Apply the minimal instructions/changes to SKILL.md (and references/scripts).")
    print(f"  4. Format and security check:")
    print(f"     python scripts/validate_skill.py {skill_dir.as_posix()}            # G4")
    print(f"  5. Prove it per case (b > c, McNemar at 20+ cases) with regression at 100%:")
    print(f"     python scripts/eval_runner.py {skill_dir.as_posix()}               # G5")
    print(f"  6. Check route collisions if description was updated:")
    print(f"     python scripts/route_check.py {skill_dir.as_posix()} --library {args.dir.expanduser().as_posix()} # G6")

    return 0


if __name__ == "__main__":
    sys.exit(main())
