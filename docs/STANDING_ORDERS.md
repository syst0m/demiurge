# Standing orders: reference

The short form lives in [AGENTS.md](../AGENTS.md). This page explains how each order is enforced
and how to wire it into a machine.

## Order 1: GitHub minutes gate

[`scripts/gh_minutes_gate.py`](../scripts/gh_minutes_gate.py) answers one question: can GitHub
Actions run for this repo right now?

```bash
python scripts/gh_minutes_gate.py --status            # GITHUB or LOCAL, with the reason
python scripts/gh_minutes_gate.py --status --refresh  # skip the 15-minute cache
GH_MINUTES_MODE=local python scripts/gh_minutes_gate.py --status   # manual override
```

Evidence, in order: the `GH_MINUTES_MODE` override, the cache, whether the repo is public (Actions
minutes are free there), the legacy quota endpoint, then the repo's recent Actions runs. A latest
run that failed with a billing annotation means `LOCAL`. A successful run in the last 48 hours
means `GITHUB`. The billing usage-summary endpoint needs the `user` token scope and reports no
remaining quota, so the gate does not call it. An undetermined state is `LOCAL`.

In `LOCAL` mode the hook blocks `gh pr create`, `gh pr merge`, `gh workflow run`, `gh run watch` and
`gh run rerun` with exit code 2 and prints the local flow. Reads such as `gh pr view`, plus `git push`
and `gh release create`, stay open. A repo can name its local commands in `.agents/local-ci.json`
(`{"test": "...", "release": "..."}`); the block message prints them.

### Wiring the hook (user level, once per machine)

The gate reads the hook payload on stdin, so the same command serves every harness.

Claude Code, in `~/.claude/settings.json`:

```json
{ "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [
  { "type": "command", "command": "python <demiurge-checkout>/scripts/gh_minutes_gate.py --hook" }
] } ] } }
```

Antigravity CLI and IDE, in `~/.gemini/config/hooks.json`:

```json
{ "gh-minutes-gate": { "PreToolUse": [ { "matcher": "run_command", "hooks": [
  { "type": "command", "command": "python <demiurge-checkout>/scripts/gh_minutes_gate.py --hook", "timeout": 30 }
] } ] } }
```

OpenCode, as `~/.config/opencode/plugins/gh-minutes-gate.js`: see
[`docs/standing-orders/opencode-gh-minutes-gate.js`](standing-orders/opencode-gh-minutes-gate.js).

Marcus never writes the two user-level hook files itself (SPEC section 6.1). Merge the snippets by hand.

## Order 2: harness parity

| Harness | Skill library | Project directory |
|---|---|---|
| Claude Code | `~/.claude/skills` | `.claude/skills` |
| Antigravity | `~/.agents/skills` | `.agents/skills` |
| OpenCode | `~/.config/opencode/skills` | `.opencode/skills` |

- `install_skill.py --harness all` links the skill into all three project directories. OpenCode
  hooks are JavaScript plugins that the installer does not generate, so it installs the link and
  prints a note.
- `sync-skills.sh` deploys to each library whose harness home exists, and refuses the whole deploy
  when any target holds uncommitted work.
- `check_harness_parity.py` fails on a missing or stale copy. It runs on `pre-push`.
