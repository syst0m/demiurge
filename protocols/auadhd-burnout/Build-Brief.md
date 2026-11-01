# Build Brief — REDACTED REDACTED recovery protocol

**Goal beyond the goal:** a durable, paced self-management operating system that lets the
user recover from REDACTED and keep from tipping back into it — absorbing dexamphetamine
side-effects, holding trauma at a safe distance, and refusing overcommitment — with honest
numbers, not a document.

**Types:** Altitude (outcome = stable daily functioning, the protocol is the tool). Depth
(work like the field's best: raw symptom/side-effect material first, expert instruments).
Range (clinical psychopharmacology + trauma therapy + OT + ADHD coaching + peer support).
Speed skipped (not relevant); Range is read-only fan-out, not a debate.

**Altitude ladder:**
1. Understand, don't fill in — map the depletion cycle before changing anything.
2. Get to the decisions — three decisions that most reduce harm (medication timing, sleep
   priority, capacity-based planning).
3. Replace the ritual — a daily/weekly operating loop, shown to catch problems earlier from
   the user's own history, run for a week.

**Depth (Felix's prompt):** (1) top professionals would do: psychiatrist review medication
timing + side-effect management; trauma clinician sets pacing/grounding boundaries;
OT builds sensory diet + energy accounting; coach designs habit + accountability. (2) raw
material: un-digested symptom log, sleep record, dex side-effect diary, capacity scores,
trauma trigger list. (3) instruments: medication-timing matrix, sleep log, capacity ruler,
grounding protocols, sensory diet, body-doubling. (4) the result is right only when shown by
a week of daily scores, a sleep/hours record, medication adherence, absence of crisis events,
and the outside clinician's sign-off.

**Range verbs + crew (read-only, no edits):**
- understand -> decide -> design -> verify
- Crew: clinical psychopharmacologist, trauma-informed clinician, occupational therapist,
  ADHD/executive-function coach, peer supporter. Each returns findings only.

**Target:** learning goal first — identify the medication-timing + pacing combination that
reduces the worst dex side-effects (crash/anxiety/sleep disruption) while keeping function.
Then a number: no severe side-effect day on >=4 of 7 days; sleep >=6.5h on >=5 nights/week;
zero overcommitment breaches; no crisis-gate events.

**Judge:** visible checks (written by builder) + held-out checks (written by a fresh-context
read-only subagent, never read by builder) into .judge/heldout/. Judge paths recorded
below; base commit 45558bc (HEAD, main).

**Access:** present — writable repo, python3, git, scripts/judge_guard.py. Missing —
registry.yaml (absent) and any T1/T2 measured skill for these crew methods: per imhotep Step
4, write a one-paragraph build request for Marcus and use plain tools for now.

**Backlog (each unit done only when its check passes):**
- B1: protocol documents all 4 required factors. Check: V1.
- B2: protocol states NOT medical advice; requires professional coordination; crisis gate.
  Check: V2.
- B3: every element tagged [my judgement]/[SETTLED]/[CONTESTED]/[VENDOR]/[EMERGING]; process
  claims cite RESEARCH.md claim ids. Check: V3.
- B4: daily operating system (energy ruler, dex timing matrix, sensory diet, trauma pacing,
  overcommitment guardrail). Check: V4.
- B5: weekly plan->run->review cycle. Check: V5.
- B6: held-out checks H1-H4 compose and pass. Check: H-run.
- B7: judge_guard.py passes on judge paths at base commit. Check: jury.

**Fixed clause:** *"Report the real result against the judge. A missed target with real
numbers passes; a gamed check fails. If the judge looks wrong, escalate; never edit it."*
