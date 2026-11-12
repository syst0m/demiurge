# Harness package targets: native plugin and hook shapes

Verified against each harness's own loader or validator, not against its documentation. The docs
lag, and they often describe a *different scope* than the one you are writing for (user-level config
vs plugin-level config, CLI vs gateway). Every shape below was confirmed by running the tool.

## Verify before you claim

A manifest that parses but is never loaded looks installed and is not. Run the harness's own
checker, and read its summary line.

| Harness | Tool | Command | Passing looks like |
|---|---|---|---|
| Antigravity | `agy plugin validate` | `agy plugin validate <plugin-dir>` | `skills N · hooks N` then `✔ Validation passed` |
| Hermes | `hermes plugins validate` | `hermes plugins validate <plugin-dir>` | `✓ loadable`, `✓ capability probe — register() ran in isolation`, `✓ declared hooks — matches registrations` |
| Hermes | `hermes plugins list` | `hermes plugins list` | the plugin appears with status `enabled` and source `user` |
| Claude Code | none headless | — | `settings.json` parses; every skill link resolves to a `SKILL.md` |

Validate the **directory** itself. For Antigravity the validator also reports component
counts, so a hook file it silently skipped shows up as `hooks 0` rather than as an error.

## Antigravity (`agy`, IDE, App)

Workspace plugin: `<project>/.agents/plugins/<name>/`. It activates only for that project.
Global: `~/.gemini/config/plugins/<name>/`.

```
<plugin>/
├── plugin.json      # required marker
├── hooks.json       # optional lifecycle hooks
├── skills/<skill>/SKILL.md
├── agents/, rules/, mcp_config.json
```

`plugin.json` carries `name`, `version`, `description`. Nothing else is required.

`hooks.json` is **named hook groups** at the top level, not bare events — a bare `{"Stop": [...]}`
fails to unmarshal, and wrapping events in a `"hooks"` key loads them as one hook literally named
`"hooks"`.

```json
{
  "<hook-name>": {
    "enabled": true,
    "Stop": [
      {"type": "command", "command": "python gate.py --json", "timeout": 30}
    ]
  }
}
```

Handler list shape per event: `Stop`, `SessionStart`, `PreInvocation`, `PostInvocation` take a
**flat** handler list. `PreToolUse` and `PostToolUse` take a list of
`{"matcher": "<tool regex>", "hooks": [ ... ]}` groups.

**Stop blocks with `{"decision": "continue"}`.** Any other value — including `"block"` — lets
the stop through. Handlers receive event JSON on stdin and must exit 0 with the decision on stdout.

## Claude Code

**Project-local plugin directories are not a load path.** `.claude/plugins/<name>/` does nothing
without a marketplace install record; the session reports the plugin as "enabled in project
settings but isn't installed here". Plugins reach Claude Code through a marketplace
(`extraKnownMarketplaces` + `enabledPlugins`), through `--plugin-dir` for one session, or as a
relative-path source in a marketplace added from a local path.

Native skill scope is the directory: `<project>/.claude/skills/<skill>/`. Use it.

Hooks live in `<project>/.claude/settings.json` and are merged into any existing file — never
replace the file.

```json
{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python gate.py --json", "timeout": 30}]}]}}
```

**Stop blocks with a top-level `{"decision": "block", "reason": "..."}`** (`reason` required), or
by exiting 2 with the reason on stderr. A Stop hook that blocks eight times in a row with no tool
call between them is overridden and the turn ends.

## Hermes Agent

**The desktop gateway does not load `./.hermes/plugins`.** That path is CLI-only: the gateway
emits a warning that `HERMES_ENABLE_PROJECT_PLUGINS` has no effect there. The desktop app spawns
the gateway, so project-scoped plugins are inert in it.

Load path that works everywhere: the **user** plugin dir,
`%LOCALAPPDATA%/hermes/plugins/<name>/`, plus the name in `plugins.enabled` in `config.yaml`.

```
<plugin>/
├── plugin.yaml      # name, version, description, provides_hooks, provides_skills
├── __init__.py      # def register(ctx): ctx.register_hook(...)
├── hooks/           # helper modules
└── skills/<skill>/SKILL.md
```

A plugin hook vetoes a turn by returning `{"action": "block", "message": "<non-empty>"}` from
**`pre_llm_call`**. The turn ends with no inference request. A block without a message is
**silently ignored**. Other useful events: `post_tool_call`, `pre_tool_call` (fails closed),
`on_session_end` (observer only — far too late to block anything).

The running gateway keeps the plugin set it started with. A newly installed plugin is discovered
by `plugins list` and `plugins validate` but is not live in the current session until the gateway
reloads.

## Pitfalls

- **Block dialects are not interchangeable.** Claude Code `"block"`, Antigravity `"continue"`,
  Hermes `{"action": "block"}`. Rendering one shape for all three silently disables the gate on
  two of them, and the failure is invisible because the hook still exits 0.
- **Docs describe a different scope than the file you are editing.** Antigravity documents a flat
  `Stop` list while the CLI's loader wants a named group; the plugin-level file differs from the
  user-level `hooks.json`. When docs and validator disagree, the validator wins.
- **A hook that only observes cannot gate.** `on_session_end` fires after the turn; registering a
  blocking check there looks correct and does nothing.
- **Classify files by path segment, not substring.** `testing_matrix_gate.py` and `latest.py` both
  contain `test`; a substring test passes every source-only diff. Match `test_*.py`, `*_test.py`,
  `*.test.*`, and directory names (`tests/`, `spec/`, `__tests__/`) as whole segments.
- **Symlinked skills are flagged as `symlink_escape`** by `hermes plugins validate`. That is the
  intended cost of one library with links instead of copies; it is a security-scan finding. It is not a
  load failure, and `plugins list` still shows the plugin enabled.
- **Insert list entries under their own key.** A line-based YAML edit that walks indented lines
  without comparing indent will append after a sibling key (`disabled: []`) and leave the plugin
  unenabled.
