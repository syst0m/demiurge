# PROVENANCE — marcus

```yaml
skill: marcus
created: 2026-08-30
merged: 2026-09-04
trust_tier: T1-conditional
gate_reached: G4 (G0 partial, G1/G5 pending isolated runner)
baseline_score: null
treated_score: null
delta: null
model_harness_pair: null
supersedes: skill-forge@1.0.0
```

## Current Specification

Marcus pairs design guidance with mechanical harness enforcement. Seven design steps map directly to seven machine-checkable validation gates.

The self-audit checklist previously in `AGENT_ARCHITECTURE.md` §6 executes as a deterministic hook via `scripts/validate_skill.py`. Per **Rule V-4**, invariants execute as automated hooks to ensure consistent enforcement across sessions.

## Evidence of Need (Gate G0)

Marcus incorporates failure cases identified during skill evaluation:

1. **Injection-Shaped Fixtures in Templates:**
   `templates/agent-skill/evals/evals.json:16` contains `IGNORE PREVIOUS INSTRUCTIONS` as an injection-resistance fixture. The validator requires recorded, reason-bearing suppressions for intentional test fixtures.
2. **Scanner Self-Inspection Integrity:**
   Pattern definitions within validators must be auditable. The validator requires explicit suppressions for intentional regex test patterns.
3. **`SKILL.md` Inclusion in Security Scanning:**
   `SKILL.md` is scanned directly during security checks alongside all executable scripts.
4. **Baseline Eval Suites:**
   Every skill in the library requires an evaluation suite at the root directory to verify performance against unassisted baselines.

## Script Architecture

The four scripts implement the quality gates: G4 (`validate_skill.py`), G5 (`eval_runner.py`), G6 (`route_check.py`), and the G0–G3 scaffold (`new_skill.py`), alongside `evals/run_gate_tests.py` for Marcus's regression suite. Each performs a deterministic check independent of model judgment.

All scripts use standard-library Python 3: zero network access, zero package installation, and zero writes outside target directories. `eval_runner.py` requires `--yes` prior to API execution.

## Open Validation Scope

- **Self-Referential Gate G5 Evaluation:** End-to-end G5 execution on Marcus's full skill factory workflow requires isolated execution environments to prevent nested agents from inheriting the installed skill library.
- **Comparative Baseline Definition:** Designing an agent lacks an automated benchmark baseline; empirical validation is tracked via task-specific evaluation suites.
- **Validator Recall Boundaries:** The validator enforces published structural constraints and static scans; edge cases outside current rules require manual review.
- **Route Collision Bounds:** `route_check.py` evaluates bag-of-words cosine similarity with a weighted trigger clause.
- **Evaluation Grading Variance:** `eval_runner.py` incorporates deterministic test assertions alongside model grading.

## Deterministic Suite

Execute local regression tests: `python skills/marcus/evals/run_gate_tests.py` (14/14 passing). Regression test cases are derived from the four findings above and maintain 100% pass rates.

## Trifecta Position

- **Private data touched:** Local skills directory only.
- **Untrusted content ingested:** Third-party `SKILL.md` and reference files during audit.
- **Exfiltration vector:** Zero in scripts. Zero network calls; zero writes outside the target.

The scripts remain network-free to prevent audit path exploitation.
