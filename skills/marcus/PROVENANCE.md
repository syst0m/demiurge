# PROVENANCE — marcus

```yaml
skill: marcus
created: 2026-08-30
merged: 2026-09-04          # skill-forge folded in; skill-forge removed
trust_tier: T1-conditional
gate_reached: G4 (G0 partial, G1/G5 not run)
baseline_score: null
treated_score: null
delta: null
model_harness_pair: null
supersedes: skill-forge@1.0.0
```

## What this skill is now

Marcus was a designer with a checklist. He is now a designer with a harness. The merge folded
`skill-forge` into him on 2026-09-04: the seven design steps stayed, and the seven gates became
their machine-checkable enforcement.

The merge was not additive. It removed something — the self-audit checklist in
`AGENT_ARCHITECTURE.md` §6, which Marcus performed from memory. His own **Rule V-4** says invariants
become hooks rather than prompt lines, because models forget and hooks do not. A self-audit
checklist inside a prompt is precisely the failure that rule names. It is now
`scripts/validate_skill.py`, and the exit code is the result.

## G0 — evidence of need, stated honestly

The merge was directed by the user, not derived from three recorded failures. **By its own G0 rule
this build would be refused.** Stating that rather than hiding it, since the same rule governs
everything Marcus produces.

Real failure evidence gathered while building, which is not the same as the user's three failures:

1. **Injection-shaped text sat unflagged in this skill's own templates.**
   `templates/agent-skill/evals/evals.json:16` contains `IGNORE PREVIOUS INSTRUCTIONS` as an
   injection-resistance fixture. Benign in intent, indistinguishable from the real thing, and
   invisible until the validator flagged it. It now clears only through a recorded suppression.
2. **A security scanner exempts itself silently unless forced not to.** The validator's first run
   flagged its own pattern definitions. The easy fix — exempting itself by filename — would have
   created exactly the blind spot that makes skill supply chains unauditable. Reason-bearing
   suppressions exist because of that.
3. **`SKILL.md` was excluded from the security scan**: the single file a malicious skill would most
   likely use, and the one most likely to be read without audit. Fixed.
4. **No skill in this library had ever been measured.** Neither Marcus nor Buckminster shipped an
   evals suite at the skill root, so nothing here has been compared against not having it.

## Why scripts are bundled

Justified deliberately against the finding that script-bundling skills are 2.12× more likely to
carry a vulnerability. The four scripts *are* the gates: G4 (`validate_skill.py`), G5
(`eval_runner.py`), G6 (`route_check.py`), and the G0–G3 scaffold (`new_skill.py`), plus
`evals/run_gate_tests.py` for Marcus's own regression suite. Each performs a deterministic check
that must not depend on model judgement — a gate a model can talk itself past is not a gate.

All are stdlib-only Python 3: no network access, no package installation, no writes outside the
target skill directory. `eval_runner.py` is the only one that spends anything and refuses to without
`--yes`.

## What has not been verified

- **G5 has never been run on Marcus.** The harness enforces a rule its owner has not satisfied.
- **Until 2026-09-05, G5 could not have worked at all.** The first real attempt showed that a
  nested agent inherits the installed skill library, so the baseline ran *with* the skill it
  was meant to lack; the runner also discarded transcripts, so the resulting 0.0% with 5 of 9
  UNKNOWN verdicts could not be diagnosed without reproducing a case by hand. Fixed with
  skill isolation, transcript retention and three refusal guards. The lesson worth keeping is
  that the gate reported a number rather than an error, and a number is what gets believed.
- **The merge has not been measured against the pre-merge Marcus.** No baseline exists for
  "designing an agent", so the claim that gated Marcus is better than checklist Marcus is
  reasoning, not evidence.
- The validator's **recall is unmeasured**. It encodes published constraints and two published
  scans. It will miss things.
- `route_check.py` scores bag-of-words cosine with a weighted trigger clause — a cheap proxy for a
  documented problem, and it will disagree with a human on near-miss cases.
- `eval_runner.py` grades with an **LLM judge**, whose agreement with humans is moderate at best.

## Deterministic suite

`python evals/run_gate_tests.py` — **7/7 passing** as of 2026-09-04. Costs nothing, calls no model.
Regression cases come from the four findings above and must hold at 100%.

## Trifecta position

- **Private data touched:** the local skills directory only.
- **Untrusted content ingested:** yes — third-party `SKILL.md` and reference files during an audit.
- **Exfiltration vector:** none in the scripts. No network calls, no writes outside the target.

Two of three. The scripts must stay network-free for that to hold; adding an outbound call to any
of them completes the trifecta and makes the audit path exploitable.
