# Run Ledger: Failure Intake from Real Skill Runs

```yaml
version: 1.0.0
audience: operators, Marcus, maintainers
canonical_path: docs/RUN_LEDGER.md
```

The run ledger records which skill ran, in which harness, with which model, and whether the user marked the run good or bad. It holds metadata only and lives outside every repository. Its job is failure intake: a run labeled `bad` becomes G0 evidence for a revision, and a person can stage it as a regression eval case. Measured deltas still come only from paired replay at G5 ([SPEC.md](../skills/marcus/references/SPEC.md) §3).

---

## 1. The Hard Rule

**Ledger counts never gate, score or rank a skill or a harness, and "fewer `::bad`" is never a target.**

- A label reaches a skill only through `ledger.py promote`, which writes a staging file. A person reads it and copies the case into `evals.json` by hand.
- No ledger data is committed, and none reaches the G5 result.
- `inventory` numbers are a triage signal. At tens of runs, harness and model are aliased and the intervals are wide.
- Optimizing for fewer `::bad` labels only teaches the operator to stop labeling.

---

## 2. Storage and Schema

The ledger directory is `$DEMIURGE_LEDGER_DIR`, else `~/.demiurge/ledger/`. It holds one `runs-YYYY-MM.jsonl` file per UTC month, plus:

| File | Written by | Content |
|---|---|---|
| `ledger.lock` | every append and every purge | Lock file. `msvcrt.locking` on Windows, `fcntl.flock` elsewhere, with a 1-second timeout. |
| `hook-errors.log` | `ledger_hook.py` | One line per hook failure: timestamp, event, exception type. |
| `promoted/<skill>/<run_id>.json` | `ledger.py promote` | Staged regression cases awaiting review. |

The schema, enums and validation live in `skills/marcus/scripts/ledger_lib.py`. An append rejects unknown keys, a raw session id and a note over 120 characters.

| Field | Required | Values |
|---|---|---|
| `schema` | yes | `ledger.v0` |
| `run_id` | yes | shared by a run's invoke row and its verdict rows; the tools write 32 hex characters |
| `ts` | yes | UTC ISO-8601 ending in `Z` |
| `kind` | yes | `invoke` or `verdict` |
| `origin` | yes | `organic` (a real session) or `replay` (`eval_runner.py --ledger`) |
| `skill` | yes | skill name |
| `subject_type` | no | what `skill` names: `skill` (default when absent), `agent`, `gate` or `harness` |
| `trigger` | no | `slash`, `model` or `eval` |
| `session` | no | sha256 prefix of the session id; the raw id is never stored |
| `skill_sha` | no | sha256 over the skill bundle's files, independent of listing order |
| `harness`, `model_id`, `version` | no | the model-harness pair and the harness version |
| `arm`, `case_id`, `attempt`, `duration_ms` | no | replay rows only |
| `outcome` | on verdicts | `label` (`ok`, `bad`, `unknown`, `dismissed`), `source` (`user`, `deterministic`, `judge`, `proxy`), optional `failure_class` and `note` |
| `refs` | no | `promoted_to` (staging path), `evals_sha256` |

`failure_class` is one of `misroute`, `wrong_output`, `incomplete`, `ignored_rule`, `unsafe`, `tool_error`, `infra` or `other`. The `proxy` source stays in the enum, and nothing writes it.

A run's label is the label of its latest verdict row. A run with no verdict row is unlabeled.

---

## 3. Capture

`scripts/ledger/ledger_hook.py` runs on two Claude Code hook events.

| Event | Input | Row |
|---|---|---|
| `PostToolUse`, matcher `Skill` | a Skill tool call | `invoke`, `trigger: model`, with `skill_sha`, `model_id` and `version` read from the transcript tail |
| `UserPromptSubmit` | `/<name>` naming an installed skill | `invoke`, `trigger: slash`; the prompt passes through |
| `PostToolUse`, matcher `Agent\|Task` | a subagent call | `invoke`, `subject_type: agent`, `skill` = the `subagent_type` |
| `UserPromptSubmit` | `::bad [<class>] [text]` or `::ok` | `verdict` with `source: user` on the session's last **skill** invoke row (never an agent row); the prompt is blocked |
| `Stop` | opt-in: set `DEMIURGE_LEDGER_NUDGE=1` | no row; prints a reminder when the session has unlabeled skill runs |
| `--event record --harness H --subject-type T --subject N [--trigger X] [--label L --class C]` | no stdin; the caller names the subject | `invoke`, and a `deterministic` verdict when `--label` is given. Use it where the harness payload is not parsed. |

**Other harnesses.**

| Harness | Capture | Status |
|---|---|---|
| Claude Code | the hook entries in section 4 | verified |
| Hermes | the `demiurge-skills` plugin records each `/niccolo`, `/marcus`, `/imhotep` slash command as a skill run (`pre_gateway_dispatch`, already live) and a harness row at `on_session_end` | both hook names are documented in the installed Hermes (`hooks.md`). `on_session_end` fires at each **turn** end, so it writes one harness row per turn: `ok` if completed, `bad`/`infra` if failed, unlabeled if interrupted. Not yet seen in a live session: a `hermes -z` test on 2026-11-05 stopped at the model provider (HTTP 403, no card on the gateway account). |
| Antigravity | `install-hook` prints a `Stop` entry that records a harness row | the entry follows the documented `hooks.json` schema (flat `Stop` array). The hook command writes a valid row when run by hand. `agy -p` (print mode) did not fire it on 2026-11-05, so no row came from a live turn. Test in an interactive `agy` session. Skill capture needs its tool payload and is not built |
| OpenCode | `scripts/ledger/opencode-ledger.js` records each `skill` tool call (copy it to `~/.config/opencode/plugins/demiurge-ledger.js`, an operator step) | the plugin shape matches the live `gh-minutes-gate.js`; the tool name `skill` and its `name` argument are **not verified** |

- **No prompt text is stored.** Text after a `::bad` class is accepted and dropped. An unknown class records `bad` with no class.
- **The capture prompt never reaches the model.** The hook answers `{"decision":"block","reason":"ledger: recorded <label> for <skill>"}`, so the harness shows the reason and discards the prompt.
- **Dedupe.** A Skill tool call is skipped when the session's last row is the same skill with `trigger: slash` from the last 60 seconds, so `/name` followed by the Skill call it causes records one run.
- **Why `::` and not `!`.** In Claude Code, a prompt that starts with `!` runs in bash mode as a shell command. It never reaches `UserPromptSubmit` as a prompt, so `!bad` would run a command named `bad`. `::` has no meaning in the prompt box.

Label a run later from the shell with `ledger.py verdict <run_id> --label bad --class <class>`.

**How each harness gets a label.**

| Harness or subject | Label source | What you do |
|---|---|---|
| Claude Code skill | `user`, from `::ok` or `::bad <class>` | Type it as a prompt after the run. It labels the session's last skill run. |
| Gate (`run-gate`) | `deterministic`, from the exit code | Nothing. Exit 0 is `ok`. Any other code is `bad`, class `other`. |
| Hermes turn | `deterministic`, from `on_session_end` | Nothing. Completed is `ok`. Failed is `bad`, class `infra`. Interrupted has no label. |
| Hermes slash command | none | Label by hand from the shell. |
| Antigravity | none | The `Stop` hook writes a harness row with no label. Label by hand from the shell. |
| OpenCode | none | The plugin writes a skill row with no label. Label by hand from the shell. |
| Agent (subagent) | none | `::bad` never targets an agent row. Label by hand from the shell. |

Find the `run_id` in `~/.demiurge/ledger/runs-YYYY-MM.jsonl`. Only a person writes a `user` label. Do not write labels on behalf of a person.

---

## 4. Installing the Hook

The hook runs from a pinned copy, so switching branches or deleting the checkout never changes what runs on every prompt.

1. Copy the hook and its library to the pinned directory. The command prints the settings entries and edits no settings file:

    ```bash
    python scripts/ledger/ledger.py install-hook --dest ~/.demiurge/bin
    ```

2. Add each entry as a **new element** of the existing `hooks.PostToolUse` and `hooks.UserPromptSubmit` arrays in your Claude Code settings. Keep every existing hook. Never replace an existing array with this one:

    ```json
    {
      "hooks": {
        "PostToolUse": [
          {
            "matcher": "Skill",
            "hooks": [
              {
                "type": "command",
                "timeout": 2,
                "command": "python \"$HOME/.demiurge/bin/ledger_hook.py\" --event post-tool || true"
              }
            ]
          }
        ],
        "UserPromptSubmit": [
          {
            "hooks": [
              {
                "type": "command",
                "timeout": 2,
                "command": "python \"$HOME/.demiurge/bin/ledger_hook.py\" --event prompt || true"
              }
            ]
          }
        ]
      }
    }
    ```

3. Before relying on capture, confirm three things in a live session:
    - the field that names the skill in the real `PostToolUse` `tool_input` (the hook reads `skill`, then `name`, else records `unknown`)
    - that `::bad` reaches `UserPromptSubmit` unchanged and is blocked
    - whether `/<name>` fires both `UserPromptSubmit` and `PostToolUse`, and that dedupe leaves one invoke row

    Check each with `ledger.py inventory --days 1` and the newest lines of the month file.

Editing the settings file changes persistent configuration. It is an operator step.

### 4.1 Fail-Open Behaviour

The hook never blocks the user, except to swallow a `::` capture prompt.

- **Fast path.** For `--event prompt`, the hook reads stdin and exits 0 before any import unless the prompt starts with `::` or `/`. Ordinary prompts pay for one interpreter start and a string search.
- **One top-level catch.** Every import, `ledger_lib` included, sits inside a single `try`. Any failure writes `ts, event, exception type` to `hook-errors.log` and exits 0.
- **Lock timeout.** When `ledger.lock` stays held for more than 1 second, the row is dropped and logged the same way.
- **Missing script.** The `|| true` in the command line exits 0 even when the pinned file is gone. `scripts/ledger/test_ledger_hook.py` runs that exact command line with the script deleted.
- **No network.** The hook reads stdin, the transcript tail and the installed skill directories, and writes only inside the ledger directory.

---

## 5. Commands

`scripts/ledger/ledger.py`, stdlib only, no network:

| Command | Effect |
|---|---|
| `failures <skill> [--last 10] [--source user,deterministic] [--json]` | Runs of a skill whose latest label is `bad` from the listed sources. |
| `verdict <run_id> --label ok\|bad\|unknown [--class <class>] [--note]` | Appends a user verdict. `bad` needs `--class`. |
| `dismiss <run_id> --reason <text>` | Appends a `dismissed` verdict. |
| `promote <run_id> --skill <name>` | Stages a regression case (section 6). |
| `run-gate [--name <gate>] -- <command>` | Runs a gate, appends a `gate` invoke row and a `deterministic` verdict (exit 0 is `ok`, else `bad`), returns the command's exit code. `skill_sha` is the sha256 of the first `.py` argument. A ledger fault warns and never changes the exit code. |
| `inventory [--by skill\|harness\|failure_class\|subject_type] [--days 90] [--min-n 20]` | Organic runs per group. Counts only below `--min-n` labeled runs; a 95% Wilson interval at or above it. It never prints a bare rate. |
| `purge --older-than 180` | Rewrites closed months older than the cutoff under the lock, keeping unpromoted `bad` runs. Temp file, then atomic rename. |
| `check-kill --installed YYYY-MM-DD [--today YYYY-MM-DD]` | Evaluates the kill criteria (section 8) and prints PASS or KILL. |
| `install-hook --dest <dir>` | Copies `ledger_hook.py` and `ledger_lib.py` and prints the settings entries. |

`inventory --by skill` and `--by harness` answer the per-skill and per-harness question directly. Read them under the hard rule in section 1.

**Gate rows.** A gate that fails is working. A `bad` gate row means the gated change failed. It is not a fault of the gate. A gate run without `run-gate` leaves no row.

**Risk tiers for a change that a failure motivates.** `promote` and `modify_skill.py --evidence` accept skills only. Failures of gates and agents go to a human review.

| Change | Proof before you accept it |
|---|---|
| Skill text, memory | G5 repeats on held-out cases, a regression check, a rollback path |
| Routing, tool policy, gate logic | the above, a constraint check, human sign-off |
| Code, model, permission | an isolated run, an independent evaluator, a staged release |

A change that edits a skill and its own `evals.json` or its own gate in one PR needs human review. An agent that edits its own evaluator can pass any test.

`scripts/check_eval_tamper.py` enforces this rule in the `checks` workflow. It fails a PR that modifies an existing `skills/<name>/evals/evals.json` and also changes another file of the same skill. A new skill is not flagged. A commit message line `Evals: reviewed` skips the gate. The gate prints the skip. It does not cover gate scripts.

`eval_runner.py` does not shuffle case order. Each attempt is a separate process with no shared state, and pairing is by case id. Order cannot change a result.

---

## 6. Promote Staging

`ledger.py promote <run_id> --skill <name>` turns a labeled run into a candidate regression case without touching any skill.

1. It finds the run's transcript by hashing transcript file names under `$DEMIURGE_TRANSCRIPTS_DIR`, else `~/.claude/projects`, or reads `--transcript <file>`.
2. It takes the last user-typed message at or before the invoke row, skipping tool results and `::` captures.
3. It redacts that message with the secret and user-path patterns from `scripts/scan_security_and_pii.py`, plus email and absolute-path patterns.
4. It writes `<ledger>/promoted/<skill>/<run_id>.json` and refuses when that file exists:

    ```json
    {
      "id": "ledger-<run_id[:12]>",
      "suite": "regression",
      "query": "<redacted message>",
      "expected_behavior": "",
      "needs_expected_behavior": true,
      "provenance": "ledger:<run_id>"
    }
    ```

5. It appends a verdict row whose `refs.promoted_to` names the staging file.

`promote` has no `--yes` and never writes into a skill directory. **Regex redaction misses free-text personal content.** Read the staged case, write its `expected_behavior`, drop `needs_expected_behavior`, then copy it into the skill's `evals.json` by hand. `eval_runner.py` exits 2 and lists the ids of any case still flagged `needs_expected_behavior` or missing an expectation.

---

## 7. Links to G0 and G5

- **G0.** `modify_skill.py <skill> --feature <desc> --evidence ledger:<run_id>` cites a run as a real failure. The run must exist, belong to the target skill and carry `bad` as its latest label. The ledger is read and never written, and only metadata reaches `PROVENANCE.md`.
- **G5.** `eval_runner.py --ledger`, or `ledger_enabled: true` in the Marcus config (default `false`), appends `origin: replay` rows with `outcome.source: judge`. `inventory` counts organic runs only, so replay rows never mix with real usage.

---

## 8. Kill Criteria

The ledger costs a hook on every prompt and some operator attention. It stays only while it produces cases. The review falls 56 days after install and repeats at the quarter. The planned schedule, which shifts day for day with the real install date:

```yaml
kill_schedule:
  planned_install: 2026-09-28
  kill_review: 2026-11-23
  quarter_check: 2026-12-28
```

On each date, run `ledger.py check-kill --installed <install date>`. It counts organic rows from the install date on:

| # | Kill when | Why |
|---|---|---|
| 1 | fewer than 3 failures staged by `promote` | The ledger exists to feed eval cases. |
| 2 | no invoke runs at all, or more than 80% of invoke runs unlabeled **and** fewer than 10 `bad` runs from `user` or `deterministic` sources | Capture happens and labeling does not. |
| 3 | any row with `source: proxy` | Nothing writes proxy labels, so such a row needs an audit. |
| 4 | a stretch of 14 days or more with no rows | The hook is broken or unused. The line also counts `hook-errors.log` entries. |

The kill review is a check that the ledger earns its cost. It does not repair anything. Criteria 1 and 2 fail until a person labels runs and runs `promote`.

The real install date is the date of the first ledger row. The ledger directory dates from 2026-11-03. With that date, `check-kill` puts the review at 2026-12-29. A run on 2026-11-23 is an early check.

When any criterion fails, `check-kill` prints KILL and exits 1. The operator then removes the two hook entries from the settings file. Scheduling the reviews and removing the hooks are operator steps.

---

## 9. Related Files

| Path | Role |
|---|---|
| `skills/marcus/scripts/ledger_lib.py` | Schema, locked append, reads, `skill_sha`, `wilson`, `mcnemar_exact`. Ships inside Marcus. |
| `scripts/ledger/ledger_hook.py` | The fail-open capture hook. |
| `scripts/ledger/ledger.py` | The command line in section 5. |
| `skills/marcus/scripts/eval_runner.py` | G5 per-case pairing and opt-in replay rows. |
| `skills/marcus/scripts/modify_skill.py` | Accepts `--evidence ledger:<run_id>` at G0. |
| `scripts/ledger/test_ledger_lib.py`, `test_ledger_hook.py`, `test_ledger_cli.py` | Unit tests. |
