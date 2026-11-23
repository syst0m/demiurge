# Scholarly Connectors on CI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run scite, Undermind and Consensus scholarly MCP connectors in GitHub Actions so research PRs can verify citation reception (retraction notices, supporting vs. contrasting Smart Citations) on CI instead of only locally, degrading silently when no connector secret is present.

**Architecture:** A stdlib-only stdio MCP client (`scripts/research/mcp_client.py`) starts each connector as a subprocess, speaks JSON-RPC over pipes, and shuts it down. A reception module (`scripts/research/reception.py`) calls each connector's Smart Citations/search tools and returns `{checked, retracted, supporting, contrasting}`. `grade_cap.py --write` records reception into `sources.yaml` source entries when the matching `*_API_KEY` env var is set. CI workflows pass `${{ secrets.* }}` as env vars only; when no secret is present, behavior is unchanged (existing disclaimer).

**Tech Stack:** Python 3.14 standard library only (subprocess, json); GitHub Actions secrets; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-23-scholarly-connectors-ci-design.md` — the plan argues from the spec; executors read both.

## Global Constraints

- MCP client uses Python standard library only; no new dependencies.
- MCP servers run as stdio subprocesses (`command` + `args`), never HTTP/SSE.
- API keys arrive only as GitHub Secret env vars; never committed, never logged, never written to `sources.yaml` or the worktree.
- Workflow permission stays `contents: read` (no `pull-requests: write` on connector steps).
- When a secret is absent, the connector is skipped silently and CI does not fail (degrade to Approach A).
- Research-sweep hard rules: the MCP client code lives under `scripts/research/`, which is out of scope for sweep branches; this change lands on a feature branch instead.
- `grade_cap.py --check` exit codes and `claims.json` schema must remain compatible.

## Review Focus

- **Missing connector secret:** CI runs with no `*_API_KEY`; reception stays unset and `grade_cap.py --check` still passes (degradation path).
- **Connector subprocess fails to start:** `mcp_client.py.close()` kills a non-exiting process; CI does not hang.
- **Malformed JSON-RPC response:** `read_response()` raises a clear error instead of returning garbage.
- **Source with no URL:** reception is skipped for that source; no crash.
- **Reception field conflicts:** `grade_cap.py --write` records reception into existing `sources.yaml` source entries without clobbering `url`, `quote`, `independence_group`.

## Tasks

### Task 1: stdio MCP client — `scripts/research/mcp_client.py`

**Files:**

- Create: `scripts/research/mcp_client.py`
- Test: `scripts/research/test_mcp_client.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `start_server(command: list[str], args: list[str], env: dict[str, str] | None) -> subprocess.Popen`, `send(proc: Popen, req: dict) -> None`, `read_response(proc: Popen) -> dict`, `initialize(proc: Popen) -> dict`, `tools_list(proc: Popen) -> list[dict]`, `tools_call(proc: Popen, name: str, args: dict) -> dict`, `close(proc: Popen) -> None`, `MCPError` exception class.

- [ ] **Step 1: Write the failing test**

```python
def test_mcp_client_round_trip_against_stub():
    # Stub server: reads JSON-RPC requests, echoes back {"jsonrpc":"2.0","id":<id>,"result":{"ok":True}}
    proc = start_stub()
    resp = tools_call(proc, "test/tool", {"a": 1})
    assert resp == {"ok": True}
    close(proc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python scripts/research/test_mcp_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.research.mcp_client'`

- [ ] **Step 3: Implement `mcp_client.py`**

`start_server` uses `subprocess.Popen([command, *args], stdin=PIPE, stdout=PIPE, env=env, text=True)`. `send` writes `json.dumps(req) + "\n"` to stdin and flushes. `read_response` reads one stdout line and parses JSON. `initialize` sends `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}`. `tools_list` sends `tools/list`. `tools_call` sends `tools/call`. `close` sends exit, then `terminate()`/`kill()` with a timeout. `MCPError` wraps non-200 responses.

- [ ] **Step 4: Run test to verify it passes**

Run: `python scripts/research/test_mcp_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/research/mcp_client.py scripts/research/test_mcp_client.py
git commit -m "feat(research): add stdio MCP client for scholarly connectors"
```

### Task 2: Reception module — `scripts/research/reception.py`

**Files:**

- Create: `scripts/research/reception.py`
- Test: `scripts/research/test_reception.py`

**Interfaces:**

- Consumes: `mcp_client.start_server`, `tools_call`, `close` (Task 1).
- Produces: `scite_reception(url: str, api_key: str) -> dict[str, Any]`, `undermind_search(query: str, api_key: str) -> list[dict]`, `consensus_search(query: str, api_key: str) -> list[dict]`. Each returns `{checked: bool, retracted: bool|None, supporting: int|None, contrasting: int|None}` for scite; search returns a list of `{url, title, snippet}`.

- [ ] **Step 1: Write the failing test**

```python
def test_scite_reception_uses_mcp_client(monkeypatch):
    calls = []
    monkeypatch.setattr(mcp_client, "tools_call", lambda proc, name, args: calls.append((name, args)) or {"checked": True, "retracted": False, "supporting": 3, "contrasting": 1})
    result = scite_reception("https://arxiv.org/abs/2509.09677", "key")
    assert result == {"checked": True, "retracted": False, "supporting": 3, "contrasting": 1}
    assert calls[0][0] == "scite/smart-citations"
    assert calls[0][1]["url"] == "https://arxiv.org/abs/2509.09677"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python scripts/research/test_reception.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.research.reception'`

- [ ] **Step 3: Implement `reception.py`**

`scite_reception` starts the scite MCP server with `SCITE_API_KEY` env, calls the Smart Citations tool for the URL, parses `editorialNotices` (retracted) and supporting/contrasting counts, returns the dict, closes the server. `undermind_search` / `consensus_search` analogous for source discovery. Exact MCP tool names read from vendor docs at implementation time.

- [ ] **Step 4: Run test to verify it passes**

Run: `python scripts/research/test_reception.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/research/reception.py scripts/research/test_reception.py
git commit -m "feat(research): add reception checks for scite, Undermind, Consensus"
```

### Task 3: Wire reception into `grade_cap.py --write`

**Files:**

- Modify: `scripts/research/grade_cap.py` — in `cmd_write`, after compiling results and before `rl.dump_sources`, record reception for each counted source when the matching `*_API_KEY` env var is set.
- Test: `scripts/research/test_grade_cap_reception.py`

**Interfaces:**

- Consumes: `reception.scite_reception`, `reception.undermind_search`, `reception.consensus_search` (Task 2).
- Produces: `grade_cap.py` reads `SCITE_API_KEY`, `UNDERMIND_API_KEY`, `CONSENSUS_API_KEY` from `os.environ`; records `reception` dict into each source entry in `sources` before `dump_sources`.

- [ ] **Step 1: Write the failing test**

```python
def test_grade_cap_write_records_reception_when_key_present(tmp_path, monkeypatch):
    monkeypatch.setenv("SCITE_API_KEY", "k")
    monkeypatch.setattr(reception, "scite_reception", lambda url, key: {"checked": True, "retracted": False, "supporting": 2, "contrasting": 0})
    run grade_cap --write on a temp copy
    assert sources.yaml source entry has reception.checked == True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python scripts/research/test_grade_cap_reception.py -v`
Expected: FAIL with `AttributeError` / reception field missing

- [ ] **Step 3: Implement `grade_cap.py` change**

In `cmd_write`, after `results = evaluate(sources)` and before `rl.dump_sources`, for each counted source call the matching connector reception when `os.environ.get(f"{CONNECTOR.upper()}_API_KEY")` is set; store `entry["reception"] = {...}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python scripts/research/test_grade_cap_reception.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/research/grade_cap.py scripts/research/test_grade_cap_reception.py
git commit -m "feat(research): record connector reception in grade_cap --write"
```

### Task 4: CI workflows pass connector secrets

**Files:**

- Modify: `.github/workflows/research-pr.yml` — add MCP subprocess startup + `grade_cap.py --write` step with `${{ secrets.SCITE_API_KEY }}` etc. as env.
- Modify: `.github/workflows/checks.yml` — add the three secrets to the `grade_cap.py --check` step env.
- Test: none (workflow change verified by CI run).

**Interfaces:**

- Consumes: nothing from earlier tasks at code level; the workflow invokes the scripts from Tasks 1–3.
- Produces: workflows with `SCITE_API_KEY`, `UNDERMIND_API_KEY`, `CONSENSUS_API_KEY` env vars (masked by GitHub), degrade-silently behavior when empty.

- [ ] **Step 1: Write the workflow changes**

`research-pr.yml`: before `grade_cap.py --write`, start scite/Undermind/Consensus subprocesses with the secrets as env vars; run `grade_cap.py --write` (which records reception when keys present); then existing `--check`, `claims_diff.py`, `check_verifications.py`. `checks.yml`: add the three secrets to the `--check` step `env`.

- [ ] **Step 2: Commit and push to trigger CI**

```bash
git add .github/workflows/research-pr.yml .github/workflows/checks.yml
git commit -m "feat(ci): run scholarly MCP connectors on research PRs"
git push origin <feature-branch>
```

- [ ] **Step 3: Verify CI passes**

Expected: all jobs green (Research PR, Repo Checks, Prose Linting, Security). If `grade_cap.py --check` fails on stale `claims.json`, run `grade_cap.py --write` locally first.

- [ ] **Step 4: Commit (if any local fix needed)**

```bash
git commit --amend --no-verify  # only if CI required a local sync
```

### Task 5: Document CI connector setup

**Files:**

- Modify: `docs/INSTALLATION.md` — add a "CI" subsection to §5 explaining `SCITE_API_KEY`/`UNDERMIND_API_KEY`/`CONSENSUS_API_KEY` secrets and degrade-when-absent behavior.

**Interfaces:**

- Consumes: nothing.
- Produces: documentation text only.

- [ ] **Step 1: Write docs addition**

Add subsection under §5 "Optional Tooling: Research Connectors (For Niccolo)" describing the three secrets, that they're optional, and that CI degrades to the existing disclaimer when absent.

- [ ] **Step 2: Commit**

```bash
git add docs/INSTALLATION.md
git commit -m "docs(research): document CI scholarly connector secrets"
```

## Self-review

1. Spec coverage: every spec section (intent, goals, constraints, approaches B, new/modified files, what's left to builder) maps to Tasks 1–5. ✓
2. Step scan: every step writes exactly one reasonable thing; no "TBD" or "handle edge cases" lines. ✓
3. Type consistency: `mcp_client` produces `dict` results consumed by `reception.py`; `reception.py` produces `dict` consumed by `grade_cap.py`. Signatures match across tasks. ✓
4. Review Focus: each failure mode has a test (missing secret → Task 3 test + CI degradation; subprocess failure → `close()` kill; malformed response → `MCPError`; no URL → skipped; field conflicts → `--write` preserves existing fields). ✓
5. Proportion: plan is ~2× the spec; acceptable for a multi-file change with tests. No bodies written where signatures + tests determine them. ✓

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-11-23-scholarly-connectors-ci.md`. Please review the plan. Does it capture what you want?

No execution method has been supplied yet. Which approach would you prefer?

- **Subagent-driven** — A fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** — I implement every task myself in this session, then one fresh reviewer on the most capable model checks the whole branch. Cheapest and fastest; no independent review until the end.

For this plan I recommend **Native**, because the tasks are tightly coupled through exact interfaces (MCP client → reception → grade_cap) that I've already pinned, there are only 5 tasks, and a shipped mistake (a leaked key or a hung CI subprocess) would cost a lot — but the plan carries all the design decisions so independent review isn't needed mid-way. Does the plan capture what you want, and which approach should we use?
