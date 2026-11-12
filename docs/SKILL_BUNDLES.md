# Skill Bundles

A bundle is a manifest (`bundles/<name>/bundle.json`) naming skills. Skill bodies are never copied; each harness gets symlinks (or copies where symlinks are unavailable) into the skill library.

## The bundles

Seven manifests live in `bundles/`:

| Bundle | Skills |
| --- | --- |
| `agent-engineering` | marcus, niccolo, imhotep, skill-creator, agent-skills-release, autoskill, find-skills, arbor, rhadamanthus |
|| `baseline-coding` | code-review-and-quality, concise-commit-gate, github-pr-workflow, github-issue-to-pr, requesting-code-review, test-driven-development, systematic-debugging, simplify-code, dead-code-removal, plan, spike, setup-pre-commit, changelog-automation, secret-scanning, handoff |
| `infosec-governance` | secret-scanning, github-auth, fleet-auditor, analytical-method-validation, experimental-design |
| `personal-writing` | my-writing-style, humanize, unsloppify |
| `writing` | writing-for-agents, caveman, i-have-adhd, writing-clearly-and-concisely |
| `research-writing` | arxiv, paper-lookup, literature-review, research-lookup, citation-management, grounded-citations, scientific-writing, venue-templates, markdown-mermaid-writing, baoyu-format-markdown |

`baseline-coding` declares `"hooks": true`, so the materializer registers the testing-matrix gate with every harness it installs into.

## Materializer: scripts/sync_bundles.py

Materializes bundles into each harness's native plugin shape.

```
python scripts/sync_bundles.py --apply        # all bundles, this repo (project scope)
python scripts/sync_bundles.py --check        # report drift, write nothing
python scripts/sync_bundles.py --bundle baseline-coding --apply
python scripts/sync_bundles.py --bundle writing --project ~/code/app --apply
python scripts/sync_bundles.py --scope global --apply
```

Exit codes: 0 clean, 1 drift or refused, 2 usage error.

Targets:

| Harness | Target |
| --- | --- |
| antigravity | `<root>/.agents/plugins/<bundle>/plugin.json` + `skills/` |
| claude-code | `<root>/.claude/skills/<skill>` links + `.claude/settings.json` `hooks.Stop` + `enabledPlugins` (see below) |
| hermes | `%LOCALAPPDATA%/hermes/plugins/<bundle>/plugin.yaml` + `skills/` plus `plugins.enabled` in `config.yaml` |

A bundle or profile may carry a `"plugins"` list of names from `agent-skills/plugins/registry.json` (for example `"ponytail"`). The registry gives each plugin's id per harness and the skills it provides. A plugin is used only where its harness supports it and it is installed there (`scripts/plugin_registry.py status`):

- `USE`: installed. Claude Code: the id is merged as `true` into `enabledPlugins` of `<project>/.claude/settings.local.json`, or `~/.claude/settings.json` at global scope. Existing keys are never removed or flipped. Hermes: the id joins `plugins.enabled`. The skills the plugin provides are not deployed standalone (`SKIP`).
- `FALLBACK`: supported but not installed. The standalone skills are deployed and the install command is printed. Sync never installs plugin code.
- `UNSUPP`: the harness has no build of the plugin. The standalone skills are deployed.

Machine-wide plugins go in `profiles/global.json` (agent-skills). Apply with `--profile <file> --scope global`. A profile alone enables plugins and deploys no skills. `--check` reports `DRIFT claude-code plugin <id> not enabled`. Invalid settings JSON is refused (exit 1) and the file is left unchanged.

Claude Code does not auto-load `.claude/plugins/<name>/` without a marketplace install record, so there is no bundle directory for it. The Hermes desktop gateway never loads `./.hermes/plugins`, so `--scope project` still targets the user dir for Hermes and says so.

Guards:

- a bundle skill missing from every library is a hard error
- a target holding different real content is refused, never overwritten
- `--check` writes nothing and exits 1 on drift

Symlinks are preferred; on Windows without Developer Mode the materializer falls back to a recursive copy and reports `copy` instead of `link`.

`--scope project` (default) writes `<project>/.agents\.claude\.hermes/plugins/<bundle>/`; `--scope global` writes the harness home. `--project` selects the repo. `--bundle` and `--harness` are repeatable.

## Gate: scripts/testing_matrix_gate.py

Blocking gate: a source change with no corresponding test change is not a complete task.

Reads the working tree (staged, unstaged, untracked), separates source from test files, and exits 1 when source changed without tests. Segment-based test detection (`test_*.py`, `*_test.py`, directories named `test`/`tests`/`spec`/`specs`) — no substring matching, so `testing_matrix_gate.py` itself is never mistaken for a test.

CI wiring:

- .agents/local-ci.json test command runs sync_bundles.py --bundle baseline-coding --check
- pre-commit bundle-parity hook runs the same check
- .claude/settings.json registers two Stop hooks (internal + claude-code formats) calling testing_matrix_gate.py --json

## What's still pending

- scripts/sync-skills.sh still exists as a separate deploy script; it no longer writes into agent-skills/skills, but it has not been reworked into the bundle materializer.
- check_harness_parity.py has not been extended to cover Hermes or to ignore __pycache__.
- sync_agent_skills.ps1's copy-back path (in the agent-skills repo) has not been removed.

## Personal bundles vs public bundles

demiurge/bundles/ is public — it is published to GitHub with every release. It contains only bundles safe to publish. dark-strategist is __not__ among them and must never be added.

Personal bundles live in a separate directory outside this repo (for example ~/bundles/personal/). The materializer's --bundles-dir flag selects the manifest directory:

```
# Public demiurge bundles (default bundles_dir = this repo's bundles/)
python scripts/sync_bundles.py --bundle baseline-coding --apply

# Personal bundles (never published)
python scripts/sync_bundles.py --bundles-dir ~/bundles/personal --bundle dark-strategist --apply
```

The two directories are never mixed. --bundles-dir points at exactly one directory, so a personal bundle cannot leak into the public set by mistake. The --check command reports drift for whichever --bundles-dir is active, without writing anything.

Rule: if it is personal, it never goes in demiurge/bundles/. If it is public, it goes in demiurge/bundles/ and nowhere else.
