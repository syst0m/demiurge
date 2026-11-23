# Scholarly connectors on CI — design doc

**Topic:** Run scite, Undermind and Consensus scholarly MCP connectors in GitHub Actions so
research PRs can verify citation reception (retraction notices, supporting vs. contrasting
Smart Citations) on CI instead of only locally.
**File:** `docs/superpowers/specs/2026-11-23-scholarly-connectors-ci-design.md`
**Author:** builder (me), for operator approval

## Intent and why

Niccolo's research sweep proposes grade changes in `research/RESEARCH.md` / `research/sources.yaml`.
`grade_cap.py` caps any claim whose reception can't be verified at `[CONTESTED]` / `[EMERGING]` —
no grade rises to `[SETTLED]` without Smart Citation reception checked. On a local dev machine the
operator can configure the scite/Undermind/Consensus MCP servers in Hermes and run the verifier
routine. On GitHub Actions there is no MCP client and no connector API key, so every CI run degrades
to Approach A: reception `null`, disclaimer printed, no claim promoted to `[SETTLED]`.

Upgrade claims therefore stall until a human verifier runs locally with scite configured. CI cannot
independently confirm reception, which is the security-critical check (retractions, supporting vs.
contrasting sentiment). This design makes that check run on CI.

## Goals

1. scite, Undermind and Consensus MCP servers run in CI as stdio subprocesses, one per connector.
2. Each connector authenticates with a single GitHub Secret (`SCITE_API_KEY`, `UNDERMIND_API_KEY`,
   `CONSENSUS_API_KEY`) passed as an env var; secrets never touch the worktree or `sources.yaml`.
3. When a secret is present, `grade_cap.py --write` records `reception.checked / retracted /
   supporting / contrasting` for each counted source; when absent, the step degrades silently to the
   existing disclaimer and CI never fails for a missing optional connector.
4. `check_verifications.py` continues to require `reception.checked == true` for upgraded/new claims
   on CI, so a PR can't merge with unverified reception unless the operator deliberately degrades.
5. Zero new attack surface when secrets are absent: the MCP subprocesses are never started.

## Non-goals

- Authenticating the end user to scite/Undermind/Consensus (operator owns their accounts/keys).
- Caching connector results across CI runs (each run re-retrieves; the verifier's fresh-context rule
  still applies).
- Supporting PubMed on CI (PubMed is biomedical-only; OUT OF SCOPE for agentic-engineering research
  per INSTALLATION.md).
- Running MCP over HTTP/SSE on CI (stdio subprocess only, matching the `chrome-devtools-autoconnect`
  pattern in Hermes config).

## Anti-goals (would make this a failure even if it technically works)

- A connector API key committed to the repo or printed in CI logs.
- CI failing because a connector secret is missing (connectors are optional).
- The sweep branch touching any path outside `research/**` and `skills/marcus/references/**`
  (the research-sweep hard rule still holds; the MCP client code lives under `scripts/research/`,
  which is out of scope for a research PR — it must land on a feature branch instead.

## Constraints

- Research-sweep hard rules: no push to `main`, no merge, no comment/label/review on the sweep PR;
  a research PR's diff may touch only `research/**`, `skills/marcus/references/**`, and the
  `derived_from` pin line of `skills/marcus/AGENT_ARCHITECTURE.md`.
- CI workflows already run `grade_cap.py --check`, `claims_diff.py`, `check_verifications.py`
  under `contents: read` (no broader token).
- GitHub Secrets mask values in logs automatically; use `::add-mask` only if logging a derived value
  is ever needed (it isn't).
- Hermes config pattern: MCP servers are `command` + `args` (stdio) or `url` (HTTP), with optional
  `auth: oauth` and `connect_timeout`.

## Approaches considered

**A — Keep graceful degradation (no build).** CI stays connector-free. Reception `null`, disclaimer
printed, no claim promoted to `[SETTLED]` until a human verifier runs locally with scite.
Tradeoff: zero new surface, but upgrade claims stall on CI; the security-critical reception check
never runs autonomously.

**B — Full MCP on CI via GitHub Secrets (SELECTED).** All three connectors run as stdio
subprocesses in CI, each keyed by one GitHub Secret. A new `scripts/research/mcp_client.py` stdio
MCP client starts a server, initializes, lists tools, calls the reception/search tools, and shuts it
down. `grade_cap.py --write` calls reception when the corresponding secret is present; otherwise
degrades to A. Tradeoff: full reception on CI, but expands CI's trusted computing base with three
third-party network services and long-lived secrets; most code to build and audit.

**C — Credential-gated scite reception only.** One secret (`SCITE_API_KEY`), scite only (the
reception gate); Undermind/Consensus stay local-only search aids. Tradeoff: covers the
security-critical check with minimal surface, but Undermind/Consensus reception never runs on CI.

**Why B over C:** The operator asked for all three connectors to work on CI, not just scite. B is the
superset; C is a strict subset that can be reached later by dropping Undermind/Consensus steps.

## The how (as decided)

### New files

1. `scripts/research/mcp_client.py` — stdio MCP client (stdlib only: `subprocess`, `json`).
   - `start_server(command, args, env)` → Popen with stdin/stdout pipes.
   - `send(req)` / `read_response()` — JSON-RPC over the pipes, with a request-id counter.
   - `initialize()`, `tools_list()`, `tools_call(name, args)`.
   - `close()` — terminates the subprocess; kills it if it doesn't exit in `CONNECT_TIMEOUT`.
   - Reads env vars for API keys; never logs key values.

2. `scripts/research/reception.py` — connector-specific reception checks.
   - `scite_reception(url, api_key)` → `{checked, retracted, supporting, contrasting}` via the scite
     MCP server's Smart Citations tool.
   - `undermind_search(...)`, `consensus_search(...)` — source discovery (not reception; used when
     a source URL fails to resolve).
   - Each returns a plain dict; callers decide what to do with `checked == false`.

### Modified files

1. `scripts/research/grade_cap.py` — in `--write`, after compiling each claim's sources, call
   `reception.<connector>_reception()` for each counted source when the matching `*_API_KEY` env
   var is set; record `reception.checked / retracted / supporting / contrasting` in
   `sources.yaml` source entries. When no key is set, skip and leave `reception` unset
   (existing disclaimer behavior). `--check` continues to require `claims.json` to match compiled
   output (unchanged).

2. `.github/workflows/research-pr.yml` — add a job step (or expand the existing Python step) that
   starts the three MCP subprocesses with `${{ secrets.SCITE_API_KEY }}` etc. as env vars, runs
   `grade_cap.py --write` (which records reception), then the existing `--check` /
   `claims_diff.py` / `check_verifications.py` sequence. Secrets passed only as env vars; workflow
   stays `contents: read`.

3. `.github/workflows/checks.yml` — add `SCITE_API_KEY`, `UNDERMIND_API_KEY`, `CONSENSUS_API_KEY`
   to the `grade_cap.py --check` step env (masked by GitHub), so the repo-checks job also sees
   reception when secrets exist.

4. `docs/INSTALLATION.md` — add a "CI" subsection to §5 explaining the three secrets and the
   degrade-when-absent behavior.

### What's left to the builder

- The exact MCP tool names/parameters for scite Smart Citations, Undermind search, Consensus search
  (read each vendor's MCP docs at implementation time).
- Whether `reception` fields live in `sources.yaml` source entries or a separate sidecar file
  (decide at implementation; `sources.yaml` already has `scite_supporting`/`scite_contrasting`
  placeholders, so extending those is the natural fit).
- Test: a small assert-based self-check that `mcp_client.py` round-trips a JSON-RPC request against
  a local stub server.

## Builder check

Self-reviewed as the builder (no `builder-check-prompt.md` exists in the repo or skill
directory; the skill's fallback applies: read the document as that builder yourself).

Three-pile sort:

- **Answered already** (by the conversation or project): approach B selected by the operator;
  security constraints (no committed keys, masked logs, `contents: read`, degrade silently);
  MCP stdio config pattern from Hermes `config.yaml`. All documented above.

- **Minor** (settled myself, my call): exact MCP tool names/parameters for scite Smart
  Citations, Undermind search and Consensus search — read each vendor's MCP docs at
  implementation time. Reception fields go in `sources.yaml` source entries (the
  `scite_supporting`/`scite_contrasting` placeholders already exist). An assert-based
  self-check for `mcp_client.py` JSON-RPC round-trip against a local stub server.

- **Theirs** (only the operator can answer, and it changes what gets built): none. Every
  decision that changes what gets built is either already made (approach B) or a minor
  implementation detail above.

No round of questions returned to you; the document is complete as written.

## Approval

This design covers the full project. Once you approve it, I'll invoke `superpowers:writing-plans`
to produce the plan, then implement. Approve or correct.
