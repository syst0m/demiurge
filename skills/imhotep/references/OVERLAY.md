# OVERLAY — where Imhotep departs from the vendored be-ambitious procedure

The vendored file `be-ambitious/SKILL.upstream.md` is a faithful translation of Felix Rieseberg's
"How to be more ambitious: a tutorial for humans with models" (13 Oct 2026). Imhotep follows it,
except for the rules below. This file is the only place they diverge, so an upstream update stays a
mechanical sync (`python scripts/vendor_sync.py --fetch`).

Each rule names its basis. **Claim** = a claim id in RESEARCH.md. **Judgement** = evidence read from
abstracts for `$DEMIURGE_REPO/docs/IMHOTEP_EVALUATION.md`, not yet graded by Niccolo. A judgement rule changes to a claim when Niccolo's proposal for
it is signed off.

| # | Upstream says | Imhotep does | Basis |
|---|---|---|---|
| O1 | An outside judge decides; a tool you can run is best | The judge has **two** parts: visible checks and held-out checks written by a fresh-context subagent that the builder never reads | Claim `fail.self-eval`, `eval.judge-bias`, `eval.visible-heldout-gap` |
| O2 | Treat the hard target as reasonable; keep going | Same, plus an **escalation channel**: a defective judge or an unreachable target is reported, never gamed. `judge_guard.py` fails a build that edits the judge | Claim `fail.reward-hacking`, `fail.escalation-channel` |
| O3 | If the model balks, say the goal is solvable | Push on **effort and method**, never on the score. Every Build Brief carries the fixed anti-exploit clause | Claim `fail.pressure-exploit` |
| O4 | Specific hard goals beat "do your best" | For novel work, set a **learning goal** first, then the numeric target | Claim `goal.learning-vs-outcome` |
| O5 | Give each field its own subagent if you can | Range subagents are **read-only** and return findings. One writer. No debate rounds | Claim `ma.value` [CONTESTED], `ma.cognition-stance`, rule R-MA-1 |
| O6 | Ask what the user wants to happen next | Ask the goal question **once, at intake**, only if ambiguous. Never mid-run | Claim `goal.clarification-timing` |
| O7 | Durable workflows take the human out of the loop | Rung-3 loops are **proposed** as `routines/*.md` for the user to approve | Demiurge governance (human sign-off), README |
| O8 | Do what the expert does, not how they talk | Unchanged, and the crew is chosen from **registry skills** where a measured one exists | Claim `eval.persona-prompting` |
| O9 | (none) | Progress is a **verified backlog**: a unit counts as done only when its check passes | Claim `pushbench.quant-goal-persistence` |
