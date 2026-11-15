# Output-shaping skills: overlap, conflict and competition

Date: 2026-11-15. Scope: the skills and styles that shape or enforce the form of model output.

## Terms

- **Overlap:** two skills state the same rule.
- **Conflict:** two skills give opposite instructions for the same output.
- **Competition:** two skills claim the same output surface, and no rule sets which one wins.

Definitions live in [output-rules/GLOSSARY.md](../output-rules/GLOSSARY.md).

## Inventory

| Skill or style | Surface | Mechanism | State now |
|---|---|---|---|
| i-have-adhd | Chat and saved files | Session text, Stop hook, file and pre-save gates | Always on |
| ASD-STE100 | Chat | Output style setting | Always on |
| ponytail | Code changes, chat closer | Session-start text | Always on |
| caveman | Chat | Plugin, manual mode | Off by default |
| unsloppify | Text artifacts | Skill, invoked by hand | On demand |
| humanize | Any text, sent to an external service | Skill with web access, credit-based | On demand |
| my-writing-style | Messages sent as the user | Skill | On demand |
| writing-clearly-and-concisely | Prose | Disabled in skill overrides, folder still present | Disabled |

## Findings

1. **Overlap, trope rule.** Three copies of the negative-parallelism pattern existed: i-have-adhd, the demiurge gate and the agent-skills gate. Fixed. One pattern file, `trope_patterns.txt`, now serves the Stop hook, the pre-save hook and both file gates. unsloppify keeps its own list in `references/patterns.md`. It should point at the shared file.
2. **Conflict, closers.** i-have-adhd rule 10 bans closing lines. ponytail asks for a closing line of skipped work and risk on every implementation task. Both run in every chat. Resolution proposed: ponytail's closing line applies to code-change replies only. Prose replies follow rule 10. This needs your decision, because the text sits in ponytail's session-start hook.
3. **Conflict, terse voice.** caveman drops articles and filler. ASD-STE100 requires explicit articles and full sentences. caveman is off by default (`CAVEMAN_DEFAULT_MODE=manual`), so the conflict stays latent. Keep it off for chat.
4. **Competition, sentence shape.** ASD-STE100 and i-have-adhd both shape chat sentences. ASD-STE100 says a more specific instruction wins, and the session hook may count as more specific. Neither source settles the order. Proposed split: i-have-adhd sets structure (action first, numbering, closers). ASD-STE100 sets sentence grammar (one instruction per sentence, length caps).
5. **Competition, rewriting.** humanize, unsloppify and my-writing-style all rewrite text. humanize sends the text to an outside service and is built to evade AI detectors. It fails the privacy rule and is out of scope for this work.
6. **Premise correction.** writing-clearly-and-concisely is disabled. Its folder still exists in agent-skills, and the settings file still names it.

## Recommendation

### Keep

- i-have-adhd: always-on chat and file shape. Enforced by the trope gate.
- ASD-STE100: sentence grammar for chat.
- ponytail: code tasks. Closing line scoped to code replies (needs decision, finding 2).
- unsloppify: text artifacts, on demand.
- my-writing-style: outgoing messages, on demand.
- caveman: installed, off. Invoke only when you ask for terse output.

### Removed

- humanize: external upload of your text, evades detectors. Removed.
- writing-clearly-and-concisely: disabled and duplicated the rules above. Removed.

### Use by context

| Context | Skills |
|---|---|
| Chat reply | i-have-adhd and ASD-STE100. caveman on request only. |
| Code change | ponytail for code. i-have-adhd for prose in the reply. |
| Saved file (Markdown, code comments) | Pre-save trope hook, then unsloppify for artifact prose. |
| Message to another person | my-writing-style to draft. Run `gate-tropes.sh` on the text before you send it. |

## Reliability and usability improvements

1. **Existing violations.** The shared rule finds 47 hits in 22 tracked demiurge files. Several are vendored or synced and should not be rewritten by hand: `skills/imhotep/references/be-ambitious/SKILL.upstream.md`, `research/RESEARCH.md` (synced from Niccolo) and `CHANGELOG.md`. Decide whether these are excluded from the gate, or rewritten.
2. **Silent pass.** The hooks print nothing on a pass, so you cannot tell "ran and passed" from "never ran". Add one log line per run.
3. **Tests not in CI.** `test_trope_gate.py` (11 cases) runs by hand. Wire it into the repo's check script.
4. **Known misses.** A contrast with no comma ("X not Y") passes. So do "rather than" forms. The rule accepts these misses on purpose.
5. **Known false positives.** Hedges such as `, not yet` are excluded. Phrases such as `, not checked` are flagged. Tune the exception list after you review real transcripts.
6. **Cross-repo coupling.** demiurge's gate calls agent-skills through the user-level link. A machine without that link fails with an explicit error and does not pass silently. Set `TROPE_GATE` to override.

## Not measured

- The false-positive rate on real chat transcripts.
- The pre-save hook on a real session write. The hook blocked this document's first draft, which confirms it runs, but the clean-write path was not tested on a live file.
- The new Stop-hook text in a live session. The current session still shows the old rule text, which came from the session-start hook. A new session reads the updated skill.
