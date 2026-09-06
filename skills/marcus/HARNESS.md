# HARNESS.md — Marcus's own execution harness

```yaml
version: 1.0.0
derived_from: references/EVIDENCE.md@1.0.0 §4
```

**Load before:** changing a script, adding a gate, or answering "how does Marcus actually run?"

A harness is the deterministic scaffolding around a model: what it sees, what it keeps, who decides
the next step, what it may touch, what persists, and how a step gets checked. It is not the model
and it is not the prompt. Published work puts harness-induced variance above model-induced variance
at comparable frontier capability — including model ranking reversals — so this file exists because
a design agent without a declared harness is exactly the thing Marcus refuses to generate.

Marcus had no harness before the merge. He had a prompt that described a checklist. Now the
checklist is four scripts and a settings rule, and the difference is that a script cannot decide it
is confident enough to skip a step.

## Contents

- §1 The six responsibilities
- §2 How a run actually proceeds
- §3 What is deterministic and what is judgement
- §4 Baselines, and reporting
- §5 Limits

---

## 1. The six responsibilities

Every harness decomposes into six. All six are declared; "not applicable" is an answer, silence is
not.

| Responsibility | Marcus's configuration |
|---|---|
| **Observation** | Three tiers by load cost: `SKILL.md` on activation; `references/` on a stated *load before:* trigger; scripts executed, never read — only their output enters context. Any third-party `SKILL.md` under audit is fenced as data. |
| **Context** | `RESEARCH.md` and `EVIDENCE.md` are read, never written by Marcus. The build archive is maintained as a **selected** population — expanding context with every previous design measures *worse* than ignoring prior designs entirely, so accepted entries and same-family near-misses load. |
| **Control** | Seven gates in fixed order. Each names an owner (`human` / `auto` / `model`) and a failure action. Gates G0, G1, G4, G5 and G6 are `auto` or `human` — Marcus does not adjudicate them. G2 and G3 are `model`, and they are the only steps where his judgement is the mechanism. |
| **Action** | Reads open. Writes confined to the target skill directory. The scripts make no network calls and install no packages. `eval_runner.py` is the only one that spends money and refuses to without `--yes`. Nothing Marcus generates inherits write permissions by default. |
| **State** | `PROVENANCE.md` per generated skill (origin, trust tier, measured deltas, what was not verified) and `archive/index.jsonl` append-only across builds. Rejected drafts are archived with their measured delta rather than deleted — the rejections are what make the archive worth keeping. Never rewritten wholesale. |
| **Verification** | Deterministic where one exists: `validate_skill.py` (G4), `eval_runner.py` (G5), `route_check.py` (G6), `run_gate_tests.py` for the harness itself. Fresh-context review where none exists — the reviewer must not be the context that produced the work. |

## 2. How a run actually proceeds

```
G0  human   Three real failures, definition of correct, volume estimate
            └─ fewer than three → stop and report the finding.
G1  auto    eval_runner.py --baseline. Score WITHOUT the artefact, per model tier.
            └─ no baseline → G5 can never fire, so the build stops here.
G2  model   Contrast success against failure on the same task. Each candidate names
            the outcome difference it explains; unexplained candidates are dropped.
G3  model   Draft the minimum. Apply I/K/C/V/T/E rules by evidence grade.
G4  auto    validate_skill.py — format limits, description triggers, reference depth,
            line-level security scan. Blocking findings are not waivable; suppressions
            need a stated reason and are always printed.
G5  auto    eval_runner.py. Positive delta required. Regression suite at 100%.
            └─ no delta → REJECT, archive with the number, return to G2.
G6  auto    route_check.py against the installed library, then PROVENANCE.md.
    +human  └─ high overlap → this build is a revision of an existing skill.
```

The loop closes at G5 → G2. A failed measurement indicates candidate error.

## 3. What is deterministic and what is judgement

This split is the whole point, so it is stated rather than left to be inferred.

**Scripts decide:** whether the format conforms, whether a security pattern is present, whether a
suppression carries a reason, whether the delta is positive, whether the regression suite held,
whether the description collides with an installed skill.

**Marcus decides:** what the failures actually have in common, which candidate explains an outcome
difference, which evidence grade a rule carries, which topology fits, what to say about what was not
verified.

**The user decides:** whether three failures exist, whether the volume justifies building at all,
whether an artefact is accepted, whether a third-party skill has been read.

Deterministic gates enforce rigorous standards. G4 and G5 run as scripts where their exit codes determine the result.

## 4. Baselines, and reporting

- **The plain-agent baseline is mandatory.** CLIs without scaffolding already solve a large share of
  tasks (EVIDENCE §4). Crediting a harness with a gain requires measuring against that baseline first.
- **Report capability and safety separately.** They do not co-vary. A harness that lifts task success
  while lifting unsafe actions has introduced risk.
- **Spends are gated.** `eval_runner.py` shows the estimated run count and cost up front, and
  refuses to run without `--yes`.

## 5. Known limits of this harness

- **Isolation is file-system only.** The runner hides installed skills via settings and stages the
  skill's own files into the run directory. It does not containerise: network calls and environment
  variables are untouched.
- **Judge bias is un-calibrated.** The LLM judge is prompt-based. Marcus asks for a different model
  family for the judge than for the candidate, but agreement with humans is moderate.
- **Trace diagnosis is preserved.** `eval_runner.py` records the complete per-case output that G5
  refuses to run without, and it retains transcripts so a suspect number can be diagnosed
  prior to re-running.
- **Deny rules cover Claude's file tools and the Bash file commands Claude Code recognises** —
  `cat`, `head`, `tail`, `sed`. `validate_skill.py` scans `human-only/` deliberately: *not loaded
  into model context* and *not scanned by a script* are different guarantees, and only the first is claimed.
- **The validator's recall is unmeasured.** It encodes published constraints and two published
  scans. It will miss things.
- **`eval_runner.py` grades with an LLM judge**, whose agreement with humans tops out at moderate.
  Its numbers provide empirical evidence. Read the transcripts.
