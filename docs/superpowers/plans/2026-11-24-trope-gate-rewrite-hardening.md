# Trope Gate Rewrite Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the minor findings and open housekeeping items left by the trope gate rewrite loop (`d516dc3`, `6832dfc`), so the branch is ready to merge.

**Architecture:** Two small code tasks edit the `init_text` string in `scripts/sync-hermes-commands.py`. Task 1 makes the line splice keep the original shape of each line (indent, list marker, line endings). Task 2 makes the rewriter boundary strict and testable: the timeout becomes an argument, the reply parser checks numbering, and tests use a fake Hermes client. Task 3 holds the non-code finish steps. The controller runs it, and it asks the user before any merge or deletion.

**Tech Stack:** Python 3 stdlib, `unittest`, `unittest.mock`.

**Spec:** [2026-11-24-hermes-trope-gate-rewrite.md](2026-11-24-hermes-trope-gate-rewrite.md) is the parent plan. No separate spec exists. The final whole-branch review (`final-review.md` in the SDD workspace) returned NOT READY with one blocking finding, I-1. Task 1 covers it. Findings m-1 to m-5 and m-9 are in Tasks 1 and 2. Finding m-7 (the `||` table prefix) is fixed in Task 3 Step 1. Findings m-2, m-6, m-8 and m-10 stay open and Task 3 Step 6 reports them.

## Global Constraints

- Branch: `feat/hermes-trope-rewrite-impl`, in the main checkout `<repo>`. Commit there. The `bundle-parity` hook passes only in that checkout. Never use `--no-verify`.
- The plugin source is the `init_text` string in `scripts/sync-hermes-commands.py`. Never edit a generated `__init__.py`.
- Keep these names and values: `TROPE_FLAG`, `MAX_TRIES = 3`, `BUDGET_SECONDS = 25.0`, `trope_gate_transform_llm_output`.
- The hook never raises and never returns the "withheld" text. Total rewrite time stays under 25 s.
- Fenced code, inline code and block quotes stay exempt from the gate.
- Write no `auxiliary.*` or `model_catalog.*` config. The rewriter keeps `task="trope_rewrite"`.
- Test command: `python scripts/test_sync_hermes_commands.py -v`. The file must stay green after every task.
- AGENTS.md rule 5: this plan is linked from `docs/README.md`.

## Review Focus

- A flagged line inside a nested list item: the rewrite keeps the indent and the list marker.
- The model echoes the list marker in its reply: the final line shows one marker.
- A rewritten reply that starts with a number, such as `2.5x faster`: the parser keeps the whole number.
- A reply with CRLF line endings: the result keeps CRLF, including the final line ending.
- The rewriter returns empty content, `None`, or an unnumbered reply: the try fails, and the line is kept and flagged.
- Two gateway turns run at the same time: each call carries its own timeout. No shared state exists between turns.
- The model returns a line that is a code fence (` ``` `) or starts with `>`: the try fails, because the line would change the fence state for later lines. This is the blocking finding I-1 of the final review.

---

### Task 1: Keep the shape of each rewritten line

**Files:**

- Modify: `scripts/sync-hermes-commands.py` (inside `init_text`: add `_split_prefix`; edit `_rewrite_flagged`)
- Test: `scripts/test_sync_hermes_commands.py` (class `TropeRewriteTest`)

**Interfaces:**

- Consumes: `_trope_hits(text) -> list[tuple[int, str, str]]`, `_llm_rewrite(lines: list[str]) -> list[str]` (signature changes in Task 2).
- Produces: `_split_prefix(line: str) -> tuple[str, str]`. The first value is the leading whitespace plus one optional list marker (`-`, `*`, `+`, `N.` or `N)`, then whitespace). The second value is the rest of the line. `_rewrite_flagged(text: str) -> str` keeps its signature.

- [ ] **Step 1: Write the failing tests** in `TropeRewriteTest`, using the existing `setattr(module, "_llm_rewrite", stub)` pattern. Each stub records its input in a list.
  - `test_nested_list_item_keeps_indent_and_marker`: the text is `"- top\n    - It is a rework, not a fix.\n- end"`. The stub returns `["It is a rework."]`. The stub input equals `["It is a rework, not a fix."]` (body only). The result equals `"- top\n    - It is a rework.\n- end"`.
  - `test_marker_echoed_by_model_gives_one_marker`: the same text. The stub returns `["- It is a rework."]`. The result equals `"- top\n    - It is a rework.\n- end"`.
  - `test_numbered_list_prefix_is_kept`: the text is `"3. It is a rework, not a fix."`. The stub returns `["It is a rework."]`. The result equals `"3. It is a rework."`.
  - `test_crlf_text_keeps_crlf`: the text is `"a\r\nIt is a rework, not a fix.\r\nb\r\n"`. The stub returns `["It is a rework."]`. The result equals `"a\r\nIt is a rework.\r\nb\r\n"`. A second case where the stub never fixes the line shows `TROPE_FLAG` before `"\r\n"` and no bare `"\n"`.
  - `test_rewrite_that_is_a_fence_or_quote_marker_fails_the_try`: the text is a flagged line, a blank line, a fenced block whose body is `code sample`, and `End.`. The stub returns `["```"]` on every call. The stub is called 3 times. The result keeps the original flagged line plus `TROPE_FLAG`. The fenced block stays unchanged. A second case with the stub returning `["> It is a rework."]` gives the same outcome.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python scripts/test_sync_hermes_commands.py TropeRewriteTest -v`
Expected: the four new tests FAIL. The older tests pass.

- [ ] **Step 3: Implement `_split_prefix(line: str) -> tuple[str, str]`** with one compiled regex: `^(\s*(?:(?:[-*+]|\d+[.)])\s+)?)(.*)$`, group 1 and group 2.

- [ ] **Step 4: Edit `_rewrite_flagged`.** Find `eol = "\r\n" if "\r\n" in text else "\n"` once at entry, and use `eol` for every join and for the trailing line ending check. For each flagged line, send only the body from `_split_prefix` to `_llm_rewrite`. Splice `prefix + new_body`. Before the splice, remove one leading marker from `new_body` with the same prefix regex, so an echoed marker shows once. The final flag pass uses `eol` too. After the marker strip, a new body that matches the fence regex used by `_trope_prose_lines`, or that starts with `>`, counts as a failed try: keep the old line and continue to the next try.

- [ ] **Step 5: Run the full test file**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit** from the main checkout.

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py docs/README.md docs/superpowers/plans/2026-11-24-trope-gate-rewrite-hardening.md
git commit -m "fix(hermes): keep indent, list marker and line endings in trope rewrites"
```

### Task 2: Strict, testable rewriter boundary

**Files:**

- Modify: `scripts/sync-hermes-commands.py` (inside `init_text`: change `_llm_rewrite`, add `_parse_numbered`, remove `_call_timeout`, edit the `pool.submit` call in `_rewrite_flagged`, move `import concurrent.futures` above `import json`)
- Modify: `CHANGELOG.md` (add one line to the entry that covers the rewrite loop)
- Test: `scripts/test_sync_hermes_commands.py`

**Interfaces:**

- Consumes: `_split_prefix` and the Task 1 splice.
- Produces:
  - `_llm_rewrite(lines: list[str], timeout: float = 8.0) -> list[str]`.
  - `_parse_numbered(content: str, count: int) -> list[str]`. A line matches `^\s*(\d+)[.):]\s+(.*)$`. The number must equal the line position, 1 to `count`. Any mismatch, a wrong count, or empty content raises `ValueError`.
  - The module has no `_call_timeout` global.
  - `_rewrite_flagged` calls `pool.submit(_llm_rewrite, bodies, per_call)`, where `per_call = max(1.0, min(8.0, remaining))`.

- [ ] **Step 1: Write the failing tests.** A helper builds a fake Hermes module: a `types.ModuleType("agent.auxiliary_client")` with a `call_llm(**kwargs)` that records `kwargs` and returns `SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=REPLY))])`. Tests inject it with `unittest.mock.patch.dict(sys.modules, {"agent": ModuleType("agent"), "agent.auxiliary_client": fake})`. Tests in a new class `LlmRewriteBoundaryTest`:
  - `test_parses_numbered_reply`: reply `"1. First plain.\n2. Second plain."` gives `["First plain.", "Second plain."]` for two input lines.
  - `test_keeps_text_that_starts_with_a_number`: reply `"1. 2.5x faster than before."` gives `["2.5x faster than before."]`.
  - `test_sends_task_temperature_and_timeout`: after `_llm_rewrite(["x"], 3.5)`, the recorded kwargs have `task == "trope_rewrite"`, `temperature == 0`, `timeout == 3.5`.
  - `test_rejects_count_mismatch`: reply `"1. only one."` for two lines raises `ValueError`.
  - `test_rejects_empty_none_and_unnumbered_reply`: content `""`, `None` and `"Plain line."` each raise `ValueError`.
  - `test_missing_hermes_keeps_and_flags`: with `sys.modules["agent.auxiliary_client"] = None` (import raises `ImportError`), the hook returns the text with `TROPE_FLAG` on the flagged line and does not raise.
  - `test_timeout_is_a_call_argument`: a stub records its second positional argument. The value is between 1.0 and 8.0. `hasattr(module, "_call_timeout")` is `False`.

- [ ] **Step 2: Update the existing stubs** in `TropeRewriteTest` and any other stub to the signature `lambda lines, timeout=8.0: ...`. Run the tests.

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: the seven new tests FAIL. The older tests PASS.

- [ ] **Step 3: Implement `_parse_numbered(content: str, count: int) -> list[str]`** and change `_llm_rewrite` to take `timeout` and to call `_parse_numbered(content, len(lines))`. Delete `_call_timeout` and the `global` line in `_rewrite_flagged`.

- [ ] **Step 4: Run the full test file**

Run: `python scripts/test_sync_hermes_commands.py -v`
Expected: all tests PASS, including the 15 earlier tests and the Task 1 tests.

- [ ] **Step 5: Run the repo gates**

Run: `python scripts/sync-hermes-commands.py --check`
Expected: drift only for the installed plugin copy.

- [ ] **Step 6: Commit** from the main checkout.

```bash
git add scripts/sync-hermes-commands.py scripts/test_sync_hermes_commands.py CHANGELOG.md
git commit -m "fix(hermes): pass the rewrite timeout as an argument and parse replies strictly"
```

### Task 3: Finish steps (controller runs; the user decides gated steps)

**Files:** none changed by an agent, except the copy in Step 1.

- [ ] **Step 0: Fix the index table.** In `docs/README.md`, change the `||` prefix on the two rows this branch added (the parent plan row and the hardening plan row) to a single `|`. Older rows keep their prefix. Report them in Step 6.

- [ ] **Step 1: Copy the reports.** Copy `task-1-report.md`, `task-1-review.md` and `task-1-brief.md` from the worktree workspace `<repo>-trope-rewrite\.superpowers\sdd\2026-11-24-hermes-trope-gate-rewrite\` to the main checkout workspace of the same name. Do not overwrite `progress.md`.

- [ ] **Step 2: Whole-branch re-review.** Run the final whole-branch review again on `2d47406..HEAD`, on the most capable model. Expected verdict: READY. Fix every Critical or Important finding before Step 3.

- [ ] **Step 3: Check the release mode.** Run `python scripts/gh_minutes_gate.py --status`. Report `GITHUB` or `LOCAL`. The changelog heading is `[0.18.6]` and the version files say 0.18.5. Report this to the user. The release flow bumps the version. This plan does not.

- [ ] **Step 4: Ask the user, then clean up the worktree.** The worktree `demiurge-trope-rewrite` holds a staged copy of the old four files and an uncommitted `.claude/settings.json` edit. Ask first. After a yes, run `git worktree remove --force ../demiurge-trope-rewrite`, then `git branch -d feat/hermes-trope-rewrite`. The plan commit `2d47406` is already in the impl branch, so the delete succeeds.

- [ ] **Step 5: Ask the user to choose the finish.** Merge locally with `git merge --no-ff`, or open a PR. Follow AGENTS.md rule 1 and the mode from Step 3. Take neither step before the user says yes.

- [ ] **Step 6: Report the user-run items.** The user syncs the plugin into the installed Hermes directory (the installed copy still has the old gate until then). `python scripts/check_harness_parity.py` reports `STALE claude-code marcus`. This is an older issue and it stays open. Report it. Do not fix it here. Also report parity `MISSING git-lifecycle-guard` and the open review findings: m-2 (a timed-out rewrite call keeps running in the background), m-6 (the 25 s budget exceeds a user-set `plugins.hook_callback_timeout` below about 26 s), m-8 (retries after a count mismatch resend the same input) and m-10 (`init_text` is not a raw string). Also report the older `||` prefix on other index rows.
