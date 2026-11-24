# Trope Gate Open Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the open and parked items left after the trope gate rewrite merged in PR #58, so the rewrite loop keeps line endings, fails bad rewrites cleanly, and stays inside its budget.

**Architecture:** The same single-file change as the merged work. Every fix lives in the `init_text` string of `scripts/sync-hermes-commands.py`. Each fix ships with a test in `scripts/test_sync_hermes_commands.py`. No fix changes the hook contract: one call, text in and text out, never withholds, never raises.

**Tech Stack:** Python 3 stdlib, `unittest`. The rewriter calls Hermes `agent.auxiliary_client.call_llm`, imported lazily.

**Spec:** `docs/superpowers/plans/2026-11-24-hermes-trope-gate-rewrite.md` (parent plan, merged) and `docs/superpowers/plans/2026-11-24-trope-gate-rewrite-hardening.md` (hardening plan, merged). The open items come from the ledger at `.superpowers/sdd/2026-11-24-trope-gate-rewrite-hardening/progress.md`.

## Global Constraints

- Hook budget: Hermes stops a hook after 30 s (`plugins.hook_callback_timeout`). Total rewrite time stays under 25 s (`BUDGET_SECONDS = 25.0`).
- Fail-open: no exception leaves the hook. No path returns the "withheld" text.
- Fenced code, inline code and block quotes stay exempt.
- Do not write any `auxiliary.*` or `model_catalog.*` config. Ask first.
- The plugin source is the `init_text` string. Never edit the generated `__init__.py`.
- Use `<repo>` in docs. Never write an absolute user path (the PII hook blocks it).
- Work on a new branch `feat/trope-gate-open-items` from `main`. Do not push or merge without the user's yes.

## Review Focus

- A line that starts with `2.5x` keeps its digits after a rewrite. Expected: `2.5x` stays `2.5x`.
- A file with mixed CRLF and LF endings keeps each line's own ending. Expected: no line changes its ending.
- A rewrite that starts with a fence after a list marker fails the whole try. Expected: the try counts as failed and the line keeps its original text.
- No model call starts after the deadline. Expected: a late try is skipped, and the lines are flagged.
- A rewrite retry after a count mismatch tells the model the exact count. Expected: the second call's user message names the count.

---

### Task 1: Consistent regex escapes in init_text

**Files:**

- Modify: `scripts/sync-hermes-commands.py` (inside `init_text`: `_PREFIX_RE` at about line 359, and any other regex that uses a single backslash)
- Test: `scripts/test_sync_hermes_commands.py`

**Interfaces:**

- Consumes: `_PREFIX_RE`, `_FENCE_RE`, `_parse_numbered` (unchanged signatures).
- Produces: none.

- [ ] **Step 1: Write the failing test** in a new `TropeOpenItemsTest` class. The test reads the outer source file and compiles it with warnings as errors:

```python
def test_outer_source_has_no_invalid_escape_warning(self):
    import warnings
    src = (Path(__file__).parent / "sync-hermes-commands.py").read_text(encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        compile(src, "sync-hermes-commands.py", "exec")  # must not raise
```

- [ ] **Step 2: Run the test to verify it fails.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: FAIL with a `SyntaxWarning` for `\s` in `_PREFIX_RE`.

- [ ] **Step 3: Double every backslash inside `init_text`** that belongs to a regex, so the generated file holds the same pattern. Keep the `r` prefix in the generated text.

- [ ] **Step 4: Run the tests to verify they pass.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py
git commit -m "fix(hermes): escape trope regexes in init_text"
```

---

### Task 2: Keep each line's own line ending

**Files:**

- Modify: `scripts/sync-hermes-commands.py` (`_rewrite_flagged`, about lines 369-405)
- Test: `scripts/test_sync_hermes_commands.py`

**Interfaces:**

- Consumes: `_rewrite_flagged(text: str) -> str` (signature unchanged).
- Produces: none.

- [ ] **Step 1: Write the failing tests**:
  - `test_mixed_line_endings_are_kept`: text is `"Intro.\r\nThis is a pipeline rework, not a bug fix.\nEnd.\r\n"`. The stub returns `["This is a pipeline rework."]`. The result equals `"Intro.\r\nThis is a pipeline rework.\nEnd.\r\n"`.
  - `test_final_newline_is_kept_for_lf_text`: text is `"Intro.\nThis is a pipeline rework, not a bug fix.\n"`. The result ends with `"\n"`.

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: FAIL on the mixed-ending test (the flagged line gains CRLF).

- [ ] **Step 3: Change `_rewrite_flagged`** to split with `splitlines(keepends=True)`. Keep each line's own ending when the line is spliced. Remove the single `nl` join for the rewrite path. Keep the flag suffix on the body, before the ending.

- [ ] **Step 4: Run the tests to verify they pass.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py
git commit -m "fix(hermes): keep each line's ending in trope rewrites"
```

---

### Task 3: A fence or quote result fails the whole try

**Files:**

- Modify: `scripts/sync-hermes-commands.py` (`_rewrite_flagged`)
- Test: `scripts/test_sync_hermes_commands.py`

**Interfaces:**

- Consumes: `_llm_rewrite(lines, timeout) -> list[str]`.
- Produces: none.

- [ ] **Step 1: Write the failing test** `test_fence_result_fails_the_try`: one flagged line. The stub returns `["```"]` on every call. The call count is 3. The result's flagged line equals the original line plus `module.TROPE_FLAG`.

- [ ] **Step 2: Run the test to verify it fails.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: FAIL. The current code skips the line once and does not retry it, so the count is 1.

- [ ] **Step 3: Change the guard in `_rewrite_flagged`.** When any result of one try is a fence or quote, skip splicing that try and go to the next try. The lines from that try are not spliced.

- [ ] **Step 4: Run the tests to verify they pass.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py
git commit -m "fix(hermes): fail the whole trope try on a fence result"
```

---

### Task 4: Tell the rewriter the exact count on retry

**Files:**

- Modify: `scripts/sync-hermes-commands.py` (`_llm_rewrite` and `_rewrite_flagged`)
- Test: `scripts/test_sync_hermes_commands.py`

**Interfaces:**

- Consumes: `_llm_rewrite(lines: list[str], timeout: float = 8.0) -> list[str]`.
- Produces: `_llm_rewrite(lines: list[str], timeout: float = 8.0, retry: bool = False) -> list[str]`. When `retry` is true, the user message starts with the line "Your last reply had the wrong count. Answer with exactly N numbered lines."

- [ ] **Step 1: Write the failing test** `test_retry_names_the_count`: the fake `call_llm` records the user message. The first reply has one line for two inputs. The second reply is correct. The second user message contains `exactly 2`.

- [ ] **Step 2: Run the test to verify it fails.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: FAIL. The second message does not contain the phrase.

- [ ] **Step 3: Add the `retry` parameter.** Set `retry=True` in `_rewrite_flagged` after a `ValueError` from a previous try. Add the sentence above to the user message only when `retry` is true.

- [ ] **Step 4: Run the tests to verify they pass.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py
git commit -m "fix(hermes): name the count when retrying a trope rewrite"
```

---

### Task 5: No call starts after the deadline

**Files:**

- Modify: `scripts/sync-hermes-commands.py` (`_rewrite_flagged`)
- Test: `scripts/test_sync_hermes_commands.py`

**Interfaces:**

- Consumes: `BUDGET_SECONDS`, `MAX_TRIES` (module constants).
- Produces: none.

- [ ] **Step 1: Write the failing test** `test_no_call_when_budget_is_nearly_spent`: patch `module.BUDGET_SECONDS` to `0.5`. The stub sleeps 0 s and counts calls. Expected call count is 0 when less than 1.0 s remains at the first try.

- [ ] **Step 2: Run the test to verify it fails.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: FAIL. The current floor of 1.0 s still starts a call.

- [ ] **Step 3: Change `per_call`.** Start a call only when at least 1.0 s remains. Otherwise break out of the loop and flag the lines. Remove the `max(1.0, ...)` floor.

- [ ] **Step 4: Run the tests to verify they pass.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py
git commit -m "fix(hermes): skip trope rewrite calls after the budget"
```

---

### Task 6: Check the hook timeout before changing the budget

**Files:**

- Read only: the Hermes source for `hook_callback_timeout` (path set by the user's Hermes install).
- Modify only if a reader exists: `scripts/sync-hermes-commands.py`

**Interfaces:**

- Consumes: none.
- Produces: a ledger note with the result.

- [ ] **Step 1: Find the config reader.** Search the Hermes source for `hook_callback_timeout`. Record the file and line in the ledger.

- [ ] **Step 2: Choose the path.**
  - If a reader exists that the plugin can call: add `_budget_for(timeout: float | None) -> float` that returns `min(BUDGET_SECONDS, timeout - 5.0)` when a timeout is set, and `BUDGET_SECONDS` otherwise. Add a test for a timeout of 20 s, which must give 15.0.
  - If no reader exists: keep `BUDGET_SECONDS = 25.0`. Add a code comment: `shortcut: budget assumes the default 30 s hook timeout, upgrade when Hermes exposes the setting`.

- [ ] **Step 3: Run the tests.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py
git commit -m "fix(hermes): tie the trope budget to the hook timeout"
```

---

### Task 7: Pin the list and number cases

**Files:**

- Test: `scripts/test_sync_hermes_commands.py`
- Modify only if a test fails: `scripts/sync-hermes-commands.py`

**Interfaces:**

- Consumes: `_split_prefix(line: str) -> tuple[str, str]`, `_rewrite_flagged`.
- Produces: none.

- [ ] **Step 1: Write the tests**:
  - `test_nested_list_indent_is_kept`: the flagged line is `"  - sub item, not a bug fix."`. The stub returns `"sub item."`. The result is `"  - sub item."`.
  - `test_leading_number_survives_marker_strip`: the flagged line is `"- 2.5x faster, not slower."`. The stub returns `"2.5x faster."`. The result is `"- 2.5x faster."`.

- [ ] **Step 2: Run the tests.**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: PASS. If a test fails, fix the code in the same task and record the change in the ledger.

- [ ] **Step 3: Commit**

```bash
git add scripts/test_sync_hermes_commands.py
git commit -m "test(hermes): pin nested list and leading number rewrites"
```

---

### Task 8: Check the real Hermes call contract

**Files:**

- Read only: the Hermes `agent/auxiliary_client.py` source.

**Interfaces:**

- Consumes: `call_llm(task=..., messages=..., temperature=..., timeout=...)`.
- Produces: a ledger note with the result.

- [ ] **Step 1: Read the signature** of `call_llm` in the installed Hermes source. Confirm the four keyword arguments exist and that `task="trope_rewrite"` falls back to the default runtime.

- [ ] **Step 2: Record the result.** If the Hermes source is not on this machine, record "not verified here, user to check" and move on. Do not change code for this task.

---

### Task 9: Index and changelog

**Files:**

- Modify: `CHANGELOG.md` (add an `## [Unreleased]` section at the top, with one `### Fixed` entry for each merged fix)
- Modify: `docs/README.md` (add one row for this plan next to the hardening plan row)
- Modify: `docs/DOCUMENTATION.md` only if it lists the hardening plan

- [ ] **Step 1: Add the changelog entry** under `## [Unreleased]`. One line per fix from Tasks 1 to 5.

- [ ] **Step 2: Add the index row.** Link this plan from `docs/README.md` (AGENTS.md rule 5).

- [ ] **Step 3: Run the PII scan on the plan.**

Run: `python scripts/scan_security_and_pii.py docs/superpowers/plans/2026-11-24-trope-gate-open-items.md`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md docs/README.md docs/superpowers/plans/2026-11-24-trope-gate-open-items.md
git commit -m "docs: index the trope gate open-items plan"
```

---

### Task 10: User-run items

These steps need the user. Agents do not run them.

- [ ] **Step 1: Sync the Hermes plugin.** The user runs `python scripts/sync-hermes-commands.py` and restarts Hermes.
- [ ] **Step 2: Check a live reply.** The user sends a reply with a flagged line and confirms the line is rewritten or flagged.
- [ ] **Step 3: Harness parity.** The user runs `python scripts/check_harness_parity.py`. Two lines are known: `MISSING git-lifecycle-guard` and `STALE marcus`. They stay open until the user fixes them. Agents report them and do not declare the work finished while they remain.

---

## Self-Review

- **Coverage:** Every open item from the ledger has a task: m-A (Task 3), m-B and the CRLF note (Task 2), m-C and m-10 (Task 1), m-2 (Task 5), m-6 (Task 6), m-8 (Task 4), the nested list and leading number notes (Task 7), the real-call contract (Task 8). Task 9 indexes the work. Task 10 lists the user-run steps.
- **Types:** `_llm_rewrite` gains the `retry` parameter in Task 4 only. Task 2 keeps the `_rewrite_flagged(text: str) -> str` signature.
- **Proportion:** Each task is a few lines of change and one or two tests.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-11-24-trope-gate-open-items.md`. Please review the plan. Which execution approach would you prefer?

- **Subagent-driven:** A fresh subagent implements each task and a fresh reviewer checks it before the next starts. Most thorough.
- **Native:** I implement every task in this session, then one fresh reviewer checks the whole branch. Cheapest and fastest.

For this plan I recommend subagent-driven, because the tasks all touch one function and a regression there reaches every reply.
