# human-only/

**Nothing in this directory is for a model to read.** It holds finished, human-facing
deliverables — rendered documents meant to be opened in a browser, not parsed, summarised or
quoted by an agent.

## Contents

| File | What it is |
|---|---|
| `skill-factory-brief.html` | *The Skill Factory Brief* — the executive research summary behind this skill's specification. Open it in a browser. |

## The convention

A `human-only/` directory anywhere under `~/.claude/skills/` means: rendered output, read by
people, excluded from model context. Three things keep it that way, in decreasing order of
strength.

**1. A permission rule, which is the only part that actually enforces anything.**
`~/.claude/settings.json` carries:

```json
"permissions": {
  "deny": [
    "Read(/skills/*/human-only/**)",
    "Edit(/skills/*/human-only/**)"
  ]
}
```

In *user* settings a leading `/` anchors at `~/.claude/`, so this resolves to
`~/.claude/skills/*/human-only/**`. Deny rules outrank every allow rule. A `Read` deny also blocks
Edit and Write on the same path; the explicit `Edit` rule is there because `NotebookEdit` is not
covered by a `Read` rule.

> **Verify it before relying on it.** The rule was added mid-session and did not take effect in
> that session — reads still succeeded through both the Read tool and `head`. It has not been
> confirmed working after a restart. Check with:
>
> ```
> head -1 ~/.claude/skills/skill-forge/human-only/README.md
> ```
>
> A denial is the pass condition. If the text prints, the rule is not in force and this directory
> is protected only by the weaker layers below.

**2. Progressive disclosure.** No `SKILL.md` links here. A skill loads its own body on
activation and bundled files only when they are referenced, so an unlinked directory costs zero
tokens and is never opened in the ordinary course of work.

**3. This file.** Documentation is the weakest control of the three and is listed last for that
reason. It states intent; it does not enforce it.

## What the rule does not cover

Stated plainly, because a control you misjudge is worse than one you know the edges of:

- **Deny rules cover Claude's built-in file tools and the file commands Claude Code recognises in
  Bash** — `cat`, `head`, `tail`, `sed`. They do **not** cover arbitrary subprocesses. A Python or
  Node script that opens the file itself reads it fine. For OS-level enforcement across all
  processes, the sandbox is the mechanism, not this rule.
- **That gap is deliberate here.** `scripts/validate_skill.py` still scans this directory, because
  a security scanner that skips a folder on request is not a security scanner. *Not loaded into
  model context* and *not scanned by a deterministic script* are different guarantees, and only the
  first one is being claimed.
- **Other tools ignore it.** There is no cross-vendor standard for this. `.aiignore`, `.aiexclude`,
  `.cursorignore` and `.llmignore` all exist, none is widely adopted, and Claude Code does not
  document support for any of them. The permission rule above is Claude Code-specific.

## Editing anything in here

The `Edit` deny rule means an agent cannot change these files, by design. To update one, remove
the rule from `~/.claude/settings.json`, make the change, and put it back — settings reload
without a restart.
