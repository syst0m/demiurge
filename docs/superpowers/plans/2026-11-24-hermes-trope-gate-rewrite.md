# Hermes Trope Gate Rewrite Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Hermes `transform_llm_output` trope gate rewrites only the flagged lines of an assistant reply, re-checks them, and delivers the reply, instead of withholding it.

**Architecture:** The hook runs `_trope_hits`, sends the original text of each flagged line to a rewriter model call (`_llm_rewrite`), splices the answers back by line number, and re-checks. It makes at most 3 tries inside a 25 second budget. A line that still trips the gate after the last try stays in the reply with a visible flag suffix. Any failure keeps the reply and flags the lines. The hook never withholds and never raises.

**Tech Stack:** Python 3 stdlib, `unittest`. The rewriter calls Hermes `agent.auxiliary_client.call_llm`, imported lazily inside the function.

**Spec:** None written. The decisions from the brainstorm are: line-level rewrite (whole-reply rewrite rejected), 3 tries, keep and flag the line after the 3rd failure. The user chose to go from brainstorm straight to this plan.

## Global Constraints

- Hook budget: Hermes stops a hook after 30 s (`plugins.hook_callback_timeout`). Total rewrite time stays under 25 s.
- Fail-open: no exception leaves the hook. No path returns the "withheld" text.
- Fenced code, inline code and block quotes stay exempt (reuse `_trope_prose_lines`).
- Do not write any `auxiliary.*` or `model_catalog.*` config (global rule: ask first). The rewriter calls `call_llm(task="trope_rewrite", ...)` and relies on Hermes defaults for an unconfigured task. Verify in Task 1 Step 6.
- The plugin source is the `init_text` string in `scripts/sync-hermes-commands.py`. Edit the string. Never edit the generated `__init__.py`.
- AGENTS.md rule 5: link this plan from `docs/README.md`.

## Review Focus

- A flagged line that contains inline code spans: the splice uses the original line, because `_trope_hits` returns text with the code blanked.
- The rewriter returns the wrong number of lines: counts as a failed try.
- The rewriter returns a line that still trips the gate: counts as a failed try. The next try sends the new text.
- The rewriter raises, or Hermes is missing (the `call_llm` import fails): the reply stays, the lines are flagged, nothing is raised.
- The flag suffix itself must not trip the gate.

---

### Task 1: Rewrite loop in the transform hook

**Files:**

- Modify: `scripts/sync-hermes-commands.py` (inside `init_text`: replace the body of `trope_gate_transform_llm_output` at ~line 317; add `_llm_rewrite` and `_rewrite_flagged` above it; update its docstring)
- Test: `scripts/test_sync_hermes_commands.py`
- Modify: `CHANGELOG.md`, `docs/README.md`

**Interfaces:**

- Consumes: `_trope_hits(text) -> list[tuple[int, str, str]]` (lineno is 1-based over `text.splitlines()`).
- Produces:
  - `_llm_rewrite(lines: list[str]) -> list[str]`: one rewritten line per input line. Raises on any failure.
  - `_rewrite_flagged(text: str) -> str`: returns `text` with flagged lines rewritten or flagged.
  - `TROPE_FLAG = "  [trope gate: could not rewrite]"`, `MAX_TRIES = 3`, `BUDGET_SECONDS = 25.0`.
  - `trope_gate_transform_llm_output(response_text=None, **kwargs) -> str | None`: `None` when there is no hit. Otherwise the rewritten text.

- [ ] **Step 1: Write the failing tests** in a new `TropeRewriteTest` class in `scripts/test_sync_hermes_commands.py`. Each test builds the plugin with `_load(_build_plugin(Path(tmp)))` and sets `module._llm_rewrite` with `setattr`, as the existing tests do. Names and assertions:
  - `test_clean_reply_returns_none`: `hook(response_text="All plain.")` is `None`.
  - `test_flagged_line_is_rewritten_and_others_untouched`: text is three lines: `Intro.`, a flagged line (`This is a pipeline rework`, then a comma, then `not a bug fix.`), and `End.`. The stub returns `["This is a pipeline rework."]`. The result equals `"Intro.\nThis is a pipeline rework.\nEnd."`. The stub received the original flagged line.
  - `test_still_flagged_after_three_tries_is_kept_and_flagged`: the stub always returns its input unchanged. Call count is 3. The result's flagged line equals the original line plus `module.TROPE_FLAG`. The result never contains "withheld".
  - `test_second_try_succeeds_stops_early`: the stub returns a bad line first and a clean line second. Call count is 2. No flag in the result.
  - `test_rewriter_exception_keeps_and_flags`: the stub raises `RuntimeError`. The hook does not raise. The flagged line carries `TROPE_FLAG`. Call count is 1.
  - `test_wrong_line_count_counts_as_failed_try`: two flagged lines, the stub returns one line each time. Call count is 3. Both lines carry `TROPE_FLAG`.
  - `test_inline_code_line_splices_original_text`: one flagged line that holds a backtick code span. The stub returns the same line with the contrast clause removed and the code span kept. The result line equals the stub output exactly.
  - `test_flag_suffix_does_not_trip_the_gate`: `module._trope_hits("x" + module.TROPE_FLAG) == []`.
  - `test_fenced_code_is_exempt`: a fenced block that holds a flagged phrase yields `None`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest scripts.test_sync_hermes_commands.TropeRewriteTest -v`
Expected: FAIL (`_llm_rewrite` and `TROPE_FLAG` do not exist; the hook still returns the withheld text).

- [ ] **Step 3: Implement `_llm_rewrite(lines: list[str]) -> list[str]`** in `init_text`. Lazy `from agent.auxiliary_client import call_llm`. One call with `task="trope_rewrite"`, `temperature=0`, `timeout=8`. The system message tells the model to rewrite each numbered line as one plain statement of the point meant, with no negated contrast, to keep the meaning and any inline code, and to answer with exactly one line per input line, numbered the same. Parse the reply into a list. Raise `ValueError` when the count differs from `len(lines)`. Strip the number prefixes.

- [ ] **Step 4: Implement `_rewrite_flagged(text: str) -> str`**. Loop up to `MAX_TRIES` while `time.monotonic()` is under the deadline (`BUDGET_SECONDS` from entry). Each pass: `hits = _trope_hits(text)`; stop when empty. Split `text` with `splitlines()`. Call `_llm_rewrite` on the original lines at the hit line numbers. Replace them. On any exception, break. After the loop, recompute hits. Append `TROPE_FLAG` to each remaining flagged line. Add `import time` to the `init_text` imports.

- [ ] **Step 5: Replace the hook body** of `trope_gate_transform_llm_output`: keep the empty-text and no-hit `None` returns and the try/except fail-open. When there are hits, return `_rewrite_flagged(text)`. If `_rewrite_flagged` raises, return `None`. Update the docstring: the hook rewrites and never withholds.

- [ ] **Step 6: Check the rewriter task default.** Read `_call_llm_impl` in the Hermes `agent/auxiliary_client.py` for how an unknown `task` resolves. Expected: it falls back to the default auxiliary or main runtime. If it raises for an unknown task, stop and ask the user (an `auxiliary.*` write is their decision).

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m unittest scripts.test_sync_hermes_commands -v`
Expected: all PASS, including the older tests.

- [ ] **Step 8: Run the repo gates**

Run: `python scripts/sync-hermes-commands.py --check` then `python scripts/check_harness_parity.py`
Expected: the sync check reports drift only for the installed plugin copy (the user runs the sync). The parity check shows no new `MISSING` or `STALE` line.

- [ ] **Step 9: Update the changelog and index.** Add a `### Changed` entry under a new version heading in `CHANGELOG.md`: "Hermes chat trope gate now rewrites flagged lines (3 tries) and keeps and flags a line it cannot fix, instead of withholding the reply." Add a row for this plan in `docs/README.md` next to the scholarly plan row.

- [ ] **Step 10: Commit**

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py CHANGELOG.md docs/README.md docs/superpowers/plans/2026-11-24-hermes-trope-gate-rewrite.md
git commit -m "feat(hermes): rewrite flagged trope lines instead of withholding the reply"
```

Release bump and install (`bash scripts/sync-skills.sh` or the Hermes plugin sync) follow the repo release workflow and the user's own run. They are outside this plan.
