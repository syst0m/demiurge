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
| **Context** | `RESEARCH.md` and `EVIDENCE.md` are read, never written by Marcus. The build archive is a **selected** population, not an accumulated transcript — expanding context with every previous design measures *worse* than ignoring prior designs entirely, so accepted entries and same-family near-misses load, and nothing else. |
| **Control** | Seven gates in fixed order. Each names an owner (`human` / `auto` / `model`) and a failure action. Gates G0, G1, G4, G5 and G6 are `auto` or `human` — Marcus does not adjudicate them. G2 and G3 are `model`, and they are the only steps where his judgement is the mechanism. |
| **Action** | Reads open. Writes confined to the target skill directory. The scripts make no network calls and install no packages. `eval_runner.py` is the only one that spends money and refuses to without `--yes`. Nothing Marcus generates inherits write permissions by default. |
| **State** | `PROVENANCE.md` per generated skill (origin, trust tier, measured deltas, what was not verified) and `archive/index.jsonl` append-only across builds. Rejected drafts are archived with their measured delta rather than deleted — the rejections are what make the archive worth keeping. Never rewritten wholesale. |
| **Verification** | Deterministic where one exists: `validate_skill.py` (G4), `eval_runner.py` (G5), `route_check.py` (G6), `run_gate_tests.py` for the harness itself. Fresh-context review where none exists — the reviewer must not be the context that produced the work. |

## 2. How a run actually proceeds

```
G0  human   Three real failures, definition of correct, volume estimate
            └─ fewer than three → stop and say so. Not a refusal; a finding.
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
    +human  └─ high overlap → this is a revision of an existing skill, not a new one.
```

The loop closes at G5 → G2, not G5 → G3. A failed measurement means the *candidates* were wrong,
not that the prose needs another polish.

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

A gate a model can talk itself past is not a gate. That is why G4 and G5 are scripts and why their
exit codes, not their prose, are the result.

## 4. Baselines, and reporting

Every number is recorded with its **model-harness pair**. A score without its harness is not a
result — that is the finding this file is built on, and it applies to Marcus's own outputs first.

For a harness build, the baseline is the **plain-agent** configuration: no specialised scaffolding.
Plain coding CLIs already solve a large share of tasks, and specialised-harness gains are routinely
misattributed. Nothing is credited to a harness that was not measured against running without it.

Capability and safety are reported **separately**. They do not co-vary: in one benchmark the top
five models sat inside a 10-point band on task success while unsafe-action rates spanned 7–23% with
no consistent ordering. A configuration that raises success and raises unsafe actions has not
improved.

## 5. Limits

- **G5 has never been run on Marcus himself.** The harness enforces a rule its owner has not
  satisfied. Recorded in `PROVENANCE.md`; not hidden.
- **G5 was unrunnable until 2026-09-05.** A nested agent inherits the installed skill library,
  so every baseline silently ran with the skill under test. The runner now generates a
  settings file hiding every installed skill, passed through a `{settings}` placeholder it
  refuses to run without, and it retains transcripts so a suspect number can be diagnosed
  rather than re-run.
- **Deny rules cover Claude's file tools and the Bash file commands Claude Code recognises** —
  `cat`, `head`, `tail`, `sed` — not arbitrary subprocesses. `validate_skill.py` still scans
  `human-only/` deliberately: *not loaded into model context* and *not scanned by a script* are
  different guarantees, and only the first is claimed.
- **The validator's recall is unmeasured.** It encodes published constraints and two published
  scans. It will miss things.
- **`eval_runner.py` grades with an LLM judge**, whose agreement with humans tops out at moderate.
  Its numbers are evidence, not truth. Read the transcripts.
