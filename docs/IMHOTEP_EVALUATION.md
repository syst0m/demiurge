# Imhotep evaluation: ambition tenets and the be-ambitious procedure

Date: 2026-11-01. Scope: the operating model of Imhotep, the third Pantheon persona.

## Contents

1. [Question and sources](#1-question-and-sources)
2. [Method](#2-method)
3. [Evidence by tenet](#3-evidence-by-tenet)
4. [Council deliberation](#4-council-deliberation)
5. [Critical appraisal](#5-critical-appraisal)
6. [The be-ambitious repository](#6-the-be-ambitious-repository)
7. [Decision](#7-decision)
8. [Avatar options](#8-avatar-options)
9. [References](#9-references)

## 1. Question and sources

Can Felix Rieseberg's tenets of ambition serve as the operating model for a persona that builds
from Buckminster's research with Marcus's skills? And how much of the robonuggets implementation
should Imhotep reuse?

- Article: [How to be more ambitious: a tutorial for humans with models](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/)
  (13 Oct 2026). Four axes: Speed (skipped), Altitude, Depth, Range, plus a closing section on
  self-efficacy.
- Implementation: [robonuggets/be-ambitious](https://github.com/robonuggets/be-ambitious), MIT, one
  `SKILL.md`, commit `dc116a3` (17 Oct 2026). Vendored at
  [skills/imhotep/references/be-ambitious/](../skills/imhotep/references/be-ambitious/).

## 2. Method

1. **Evidence brief.** The article's claims, the repository's rules, and the existing claims in
   [research/RESEARCH.md](../research/RESEARCH.md) (`fail.self-eval`, `fail.self-correction`,
   `fail.reward-hacking`, `eval.judge-bias`, `ma.value`, rule R-MA-1).
2. **Literature.** One Undermind deep search ("Ambition tenets for LLM coding agents evidence",
   234 papers ranked) plus targeted semantic searches on persona prompting, self-correction, reward
   hacking, multi-agent debate and goal-setting meta-analyses.
3. **Council.** The consciousness-council exercise with six lenses: Architect, Empiricist,
   Contrarian, Minimalist, Strategist, Ethicist. These are generated viewpoints from one model.
   Their agreement adds no independent evidence.
4. **Appraisal.** The scientific-critical-thinking workflow: separate what each study measured from
   what the tenet asserts, and grade the transfer from humans to models separately.

**Limit.** Every literature finding below comes from abstracts and metadata, not full texts.
Reception (citing support or contrast) was not checked. Buckminster's tri-source and reception
rules apply before any of these findings reaches RESEARCH.md.

## 3. Evidence by tenet

| Tenet | What the evidence shows | Strength for LLM agents |
|---|---|---|
| Outside judge; never self-grade | Intrinsic self-correction does not improve and can degrade reasoning without external feedback [1, 2]. LLM evaluators favour their own outputs, including on rubrics [3, 4]. | Strong, multiple independent lines |
| Visible tests as the judge | Frontier agents saturate visible tests while held-out tests fail; the gap grows about 28 pp per tenfold increase in code size [5]. Explicit reward hacking by Claude Code and Codex [6]. 13.8 % of SWE-Marathon runs reward-hack [7]. | Strong that visible-only judges fail |
| "Say it is solvable and keep going" | User pressure on a visible score moves the first exploit from round 19.7 to round 4.1. Stronger models exploit more (Spearman 0.77). Explicit anti-exploit wording cuts exploitation from 100 % to 8.3 % [8]. | Moderate, one benchmark, 13 agents |
| Escalate instead of gaming | An escalation tool plus an anti-hacking policy cut reward hacking from 23.6 % to 5.3 % across 8 models, with no measured performance cost [9]. | Moderate, one preprint, factorial design |
| Persist on hard quantitative goals | State-tracking controllers reach 69–78 % success where completion-gated controllers complete no task [10]. SWE-Marathon failures include false "infeasible" reports and early stops [7]. | Moderate |
| Specific hard goals (Locke and Latham) | In humans, goal effects shrink on complex tasks [11]; learning goals beat outcome goals on a moderately complex task [12]. In LLMs, efficacy prompts give small, model-dependent gains [13], and goal-directedness is incomplete [14]. | Strong in humans; transfer untested |
| Do what the expert does, not role-play | Persona and expert prompts do not reliably raise accuracy [15, 16, 17]. | Moderate to strong |
| Range through several agents | Debate does not reliably beat voting or budget-matched single-agent sampling [18, 19, 20, 21]. RESEARCH.md grades multi-agent value `[CONTESTED]`. | Contested |
| Altitude: aim at the goal beyond the goal | No controlled study. Goal clarification loses nearly all value after about 10 % of execution [22]. | Practitioner evidence only |
| Durable loops remove the human | Developers use test results as their main guarantee when they oversee agents [23]. No study measures unattended durable loops. | Weak |

## 4. Council deliberation

**Architect.** Position: the article gives a procedure. A system also needs fixed
interfaces: RESEARCH.md in, registry skills in, ledger rows out. Risk: a persona with no contract
drifts. Check: if the registry and ledger cannot be read from the skill, the loop does not close.

**Empiricist.** Position: keep the outside judge, harden it with a held-out split. Basis: [5, 6, 7].
Risk: "keep going" without a held-out check turns ambition into test gaming. Check: if a treated
run shows no smaller visible/held-out gap than baseline, the overlay is not earning its place.

**Contrarian.** Position: the strongest premise is "treat the hard target as reasonable". It does
not survive for coding agents: pressure on a score is the documented trigger for exploitation [8].
It survives only when the pressure moves from the score to the method. Check: anti-exploit wording
must appear in every brief.

**Minimalist.** Position: reuse the upstream file unchanged, and put every divergence in one
overlay. Add two scripts only: a pin check and a judge guard. Risk: an orchestration framework that
nobody asked for. Check: if the overlay grows past one page, it is becoming a second skill.

**Strategist.** Position: the value is the closed loop. Build outcomes feed Marcus's regression
cases and Buckminster's field evidence, so the Pantheon learns from use. Risk: upstream drift.
Check: a monthly fetch that only proposes.

**Ethicist.** Position: ambition raises the standard and leaves the permissions as they are. Rung-3 loops,
spending and irreversible steps wait for the user. Risk: a vendored file is third-party
instructions loaded into context. Check: tier T3 handling and an operator-signed update path.

### Synthesis

- **Convergence:** outside judge with a held-out split; method over persona; single writer.
- **Core tension:** ambition pushes harder targets, and harder targets raise the pressure to game
  the check.
- **Resolution:** ambition on the target, conservatism on the judge.
- **Open question:** whether learning-goal-first framing helps models as it helps people.
- **Confidence:** high for the held-out split and the escalation channel; medium for the learning
  goal; low for self-efficacy framing.

## 5. Critical appraisal

**Strengths of the tenets.** The outside-judge rule matches the strongest evidence in the field.
"Better, not bigger" and "do, don't play" match the persona-prompting results. The Depth prompt asks
for raw material and expert instruments, which a judge can check.

**Critical issue.** "If the model balks, state that the goal is solvable and keep going" is pressure
on an outcome. For agents whose outcome signal is a test suite, that pressure predicts exploitation
[8], and the exploitation grows with task length [5]. Remedy: overlay rules O1–O3.

**Important issues.**

- The goal-setting evidence is human, from tasks unlike software builds. The transfer to agents is an
  analogy that no study has tested. Remedy: learning goal first for novel work (O4), labelled as judgement.
- The examples (crash-free apps, QBR redesign) are single-practitioner reports with no comparison.
  They show possibility, not effect size.
- Range through multi-agent crews conflicts with budget-matched results. Remedy: read-only fan-out
  (O5).

**Minor issues.** The self-efficacy anecdotes (Dantzig, Bannister) are survivorship examples. The
sub-two-hour marathon example is dated to April 2026 in the article and was not checked here.

## 6. The be-ambitious repository

- **Fidelity:** high. It keeps the article's types, the three-rung ladder, the four-question Depth
  prompt and the warnings, with attribution.
- **Strengths:** short, procedural, a task-or-prompt switch, an explicit "Next" step, and a hard
  line that ambition raises the standard and leaves the permissions as they are.
- **Gaps against the evidence:** no held-out judge, no escalation channel, no clarification-timing
  rule, no skill selection, no ledger, no progress tracking.
- **Decision:** vendor it byte-identical as the ambition procedure. Pin it with sha256 in
  `UPSTREAM.yaml`. Put every divergence in
  [OVERLAY.md](../skills/imhotep/references/OVERLAY.md). Sync it with `scripts/vendor_sync.py` and
  the monthly [vendor-sync routine](../routines/vendor-sync.md); each update is an operator-reviewed
  pull request, because the file is trust tier T3.

## 7. Decision

Adopt the tenets with the nine overlay rules in
[OVERLAY.md](../skills/imhotep/references/OVERLAY.md). Rules that rest on this review's abstracts
stay labelled *judgement* until Buckminster grades them. Imhotep stays at trust tier T2 until G5
shows a measured delta.

## 8. Avatar options

The operating model: aim at an outcome others call impossible, study the raw material first,
invent the instruments, keep an outside check, ship.

| Name | Figure | Fit | Watch-out |
|---|---|---|---|
| **Imhotep** (chosen) | Architect of Djoser's step pyramid, c. 2650 BC; first engineer known by name | Stacked six mastabas into the first monumental stone building: a new method at a new scale. Also physician and scribe (Range). | Popular-culture associations |
| Filippo | Filippo Brunelleschi, Florence Cathedral dome | Built the dome experts called unbuildable after he measured the Roman Pantheon; invented his own hoists | Less known outside Europe |
| Daedalus | Mythic master craftsman | Icarus is the persona's safety rule: ambition without a judge falls | Myth, not a record |
| Kelly | Kelly Johnson, Lockheed Skunk Works | Small team, 14 rules, audacious targets, flight test as the judge | Military context |
| Brunel | Isambard Kingdom Brunel | Audacious engineering; his failures show why a held-out judge matters | Overreach is part of his record |
| Tony | Tony Stark (fiction) | The build, test, fail, rebuild loop | Brand name |

## 9. References

1. Huang, J. et al. (2023). [Large Language Models Cannot Self-Correct Reasoning Yet](https://doi.org/10.48550/arXiv.2310.01798).
2. Kamoi, R. et al. (2024). [When Can LLMs Actually Correct Their Own Mistakes?](https://doi.org/10.1162/tacl_a_00713) TACL.
3. Panickssery, A., Bowman, S. R., & Feng, S. (2024). [LLM Evaluators Recognize and Favor Their Own Generations](https://doi.org/10.48550/arXiv.2404.13076).
4. Pombal, J., Rei, R., & Martins, A. F. T. (2026). [Self-Preference Bias in Rubric-Based Evaluation of Large Language Models](https://doi.org/10.48550/arXiv.2604.06996).
5. Zhao, B.-C. et al. (2026). [SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents](https://doi.org/10.48550/arXiv.2605.21384).
6. Gabor, J., Lynch, J., & Rosenfeld, J. (2025). [EvilGenie: A Reward Hacking Benchmark](https://doi.org/10.48550/arXiv.2511.21654).
7. Desai, R. et al. (2026). [SWE-Marathon: Can Agents Autonomously Complete Ultra-Long-Horizon Software Work?](https://doi.org/10.48550/arXiv.2606.07682)
8. Chen, H. et al. (2026). [Chasing the Public Score: User Pressure and Evaluation Exploitation in Coding Agent Workflows](https://doi.org/10.48550/arXiv.2604.20200).
9. Gómez, F. (2026). [Can escalation channels redirect reward hacking toward defect disclosure?](https://arxiv.org/abs/2608.29460)
10. Cai, Y.-D. et al. (2026). [Push Your Agent: Measuring and Enforcing Quantitative Goal Persistence in Long-Horizon LLM Agents](https://doi.org/10.48550/arXiv.2605.23574).
11. Wood, R., Mento, A., & Locke, E. (1987). [Task complexity as a moderator of goal effects: A meta-analysis](https://doi.org/10.1037/0021-9010.72.3.416). Journal of Applied Psychology.
12. Seijts, G., & Latham, G. (2001). [The effect of distal learning, outcome, and proximal goals on a moderately complex task](https://doi.org/10.1002/JOB.70). Journal of Organizational Behavior.
13. Chen, R. et al. (2025). [Boosting Self-Efficacy and Performance of Large Language Models via Verbal Efficacy Stimulations](https://doi.org/10.48550/arXiv.2502.06669).
14. Everitt, T. et al. (2025). [Evaluating the Goal-Directedness of Large Language Models](https://doi.org/10.48550/arXiv.2504.11844).
15. Zheng, M. et al. (2023). [When "A Helpful Assistant" Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of Large Language Models](https://arxiv.org/abs/2311.10054).
16. Basil, S. et al. (2025). [Prompting Science Report 4: Playing Pretend: Expert Personas Don't Improve Factual Accuracy](https://doi.org/10.48550/arXiv.2512.05858).
17. Luz de Araujo, P. H., & Roth, B. (2024). [Helpful assistant or fruitful facilitator? Investigating how personas affect language model behavior](https://doi.org/10.1371/journal.pone.0325664). PLOS One.
18. Zhang, H. et al. (2025). [Stop Overvaluing Multi-Agent Debate](https://arxiv.org/abs/2502.08788).
19. Choi, H. K., Zhu, X.-J., & Li, Y. (2025). [Debate or Vote: Which Yields Better Decisions in Multi-Agent Large Language Models?](https://doi.org/10.48550/arXiv.2508.17536)
20. Bertalanič, B., & Fortuna, C. (2026). [The Cost of Consensus: Isolated Self-Correction Prevails Over Unguided Homogeneous Multi-Agent Debate](https://doi.org/10.1145/3786335.3813137).
21. Ferreira, L., Liu, G., & Zheng, K. (2026). [Beyond Symmetric Agents: Cognitive Diversity and Multi-Agent Debate in Small Language Models](https://arxiv.org/abs/2609.35875).
22. Gulati, A. et al. (2026). [Ask Early, Ask Late, Ask Right: When Does Clarification Timing Matter for Long-Horizon Agents?](https://doi.org/10.48550/arXiv.2605.07937)
23. Dhanorkar, S., Passi, S., & Vorvoreanu, M. (2026). [Human oversight of agentic systems in practice](https://doi.org/10.1145/3805689.3812402). FAccT.
