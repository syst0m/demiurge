# Package templates

One canonical internal representation → N target projections. Marcus fills these.

`{{PLACEHOLDER}}` markers are substituted at generation time. Comments marked `>>>` are
instructions to Marcus and must not survive into emitted output.

**Fidelity** is how much of the four-layer design (Identity / Knowledge / Capability /
Verification) the target can actually express. Where a target cannot express a rule, the emitted
package says so — rule E-1.

| Template | Target | Fidelity |
|---|---|---|
| `agent-skill/` | Claude, Claude Code, Gemini CLI, ~45 clients | Full |
| `claude-code-subagent.md` | Claude Code subagent | High |
| `agents-md.md` | Any tool reading AGENTS.md | Medium |
| `gemini-gem.md` | Gemini / Gemini Spark | Medium |
| `cli-harness.md` | Harness-agnostic CLI | Medium |
| `web-chat.md` | Pasteable single prompt | Low |
| `antigravity-plugin/` | Antigravity workspace plugin (`.agents/plugins/<name>/`) | High |
| `hermes-plugin/` | Hermes user plugin (`%LOCALAPPDATA%/hermes/plugins/<name>/`) | High |

The two plugin templates are bundle manifests, not filled projections: they list skill names and the
hook wiring. Emit them into the target harness's own load path — see
`references/harness-package-targets.md` for the verified shapes and the validator command for each.
Claude Code has no plugin template because `.claude/plugins/<name>/` is not a load path; its
project skill scope is `.claude/skills/<skill>/` plus a `settings.json` hook.

Rule E-2: the Agent Skills version is emitted **always**, whatever else was asked for.
