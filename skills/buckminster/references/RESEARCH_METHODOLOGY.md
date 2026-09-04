# RESEARCH_METHODOLOGY.md

How Buckminster researches. Extracted 2026-08-30 from the toolchain available on this account and
from the patterns that actually worked during the 2026-08-29 agentic-engineering passes.

This is a *method*, not a checklist. The point of writing it down is that the same method produces
comparable snapshots over time — so version-to-version diffs in `RESEARCH.md` mean something.

---

## 1. The toolchain

### Scholarly connectors

Four, with genuinely different strengths. Using one alone produces a biased snapshot.

| Connector | Best for | Watch for |
|---|---|---|
| **Undermind** | `launch_deep_search` — a multi-agent review taking 2–5 min, producing a ranked list plus a summary. The heaviest instrument available. `search_papers` for iterative exploration; `read_pdfs` for targeted full text | One well-aimed deep search usually covers a whole brief. Check for an existing one before launching another |
| **scite** | Smart Citations — the actual sentences citing papers wrote, classified supporting/contrasting/mentioning. **`editorialNotices` for retractions and corrections** | The only source here that shows how a finding was *received*, not just what it claimed |
| **PubMed** | Biomedical and life sciences only | Returns nothing useful for CS/AI — do not use it for agentic-engineering work |
| **Consensus** | General paper search with citation counts | Requires numbered inline citations and reproducing its usage message verbatim |

**Call `get_orientation()` before any other Undermind tool.** It is required, and it names the
connected account.

### Web

- **WebSearch** — current state, adoption numbers, "what happened since". US-only results.
- **WebFetch** — primary sources. Prefer the vendor's own engineering blog over any summary of it.

### What is deliberately not used

- **arXiv scraping** — the scholarly connectors already index it, with citation context attached.
- **Social media / aggregator blogs** as evidence. Usable to *discover* a claim, never to support
  one. Every such claim gets traced to a primary source or marked unverified.

---

## 2. The method

### Step 1 — Frame the question so it can be answered wrongly

A brief that cannot return a disappointing answer is not research. Every brief must name what would
count as evidence *against* the expected conclusion, and must ask for null and critical findings
explicitly.

> Bad: *"Find evidence that agent memory improves performance."*
> Good: *"What does the evidence say about whether persistent agent memory improves performance,
> including any findings that it does not?"*

This is not pedantry. The 2026-08-29 pass found that memory scaffolds *hurt* long-horizon
performance across ten models — a result that a confirmation-shaped brief would have buried.

### Step 2 — Breadth before depth

Launch the Undermind deep search first (it runs asynchronously for minutes), then use that window
for targeted `search_papers`, WebSearch and primary-source WebFetch. Do not idle waiting for it.

### Step 3 — Check how findings were received

For any load-bearing claim, run it through scite:
- **`editorialNotices`** — retracted? corrected? subject to an expression of concern?
- **Smart Citations** — do citing papers support it, or contrast with it? A heavily-cited paper
  whose citations are largely *contrasting* is a disputed finding, not an established one.

### Step 4 — Grade every claim before writing it down

Confidence markers are assigned at capture time, not retrofitted. `RESEARCH.md` uses four:

- `[SETTLED]` — multiple independent sources, at least some empirical
- `[CONTESTED]` — credible sources disagree, or it rests on one study
- `[VENDOR]` — the claim originates with a party selling the thing
- `[EMERGING]` — real but too new to have been tested in practice

**The `[VENDOR]` marker is not optional.** Memory-system benchmarks, harness efficiency claims and
framework adoption numbers are routinely published by the party selling them, frequently scored by
LLM-as-judge on a benchmark they chose. Efficiency claims from such sources are more believable
than accuracy claims.

### Step 5 — Look for the disagreement, and keep it

Where credible sources conflict, record **both positions and the fact of the conflict**. Do not
resolve it by picking the more recent, the more cited, or the more convenient.

Live example carried in `RESEARCH.md`: Manus says keep failure traces in context; Anthropic's
compaction line says prune stale errors. Both are credible practitioners. Nobody has measured the
crossover. That is the finding.

### Step 6 — Separate what is settled from what is sold

Every snapshot ends with an explicit hype section. A field six months old will generate confident
claims faster than evidence. Naming the unsupported ones is as useful as listing the supported ones,
and it is the part that decays fastest between snapshots.

---

## 3. Standards for the output

**Attribute everything.** Working URL, publication date, and author or organisation. A claim with no
traceable source does not go in.

**Say when something could not be verified.** The 2026-08-29 pass could not confirm the reported
retirement of SWE-bench Verified, specific DORA percentages, or details of a widely-cited gist —
all reached only via aggregator blogs. Each was flagged rather than dropped or asserted.

**Prefer primary sources.** A vendor's own engineering post beats any write-up of it. A paper beats
a thread about the paper.

**Note the population.** A finding from a controlled benchmark, from an enterprise deployment, and
from a solo developer are three different findings. `RESEARCH.md` is consumed by Marcus to design
agents for a **solo operator** — a result that only holds at team scale must say so.

**Quantify where the source quantifies.** "Prompt injection is hard" is not usable. ">85% adaptive
attack success against state-of-the-art defences, most defences under 50%" is.

---

## 4. Producing an update

Buckminster does not rewrite `RESEARCH.md`. It produces a **diff proposal**:

1. **New findings** — with grade, source, and which section they belong in.
2. **Reclassifications** — a `[CONTESTED]` claim that has become `[SETTLED]`, or the reverse.
   Reclassification downward is more valuable than new findings and is easy to miss.
3. **Contradictions** — anything in the current snapshot that new evidence disputes. Flagged
   loudly; never silently overwritten.
4. **Retractions** — anything cited that has since been retracted or corrected.
5. **Unchanged** — an explicit statement that the rest was re-checked and still holds. Silence is
   ambiguous between "verified" and "not looked at".

The user signs off before anything is written. Rationale is in `RESEARCH.md` itself: the file is
Marcus's only source of truth about how agents should be built, so an unreviewed change propagates
into every agent generated afterwards.

**Append-only for the change log.** Entries are added, never rewritten — self-rewritten agent
memory has measured failure modes (brevity bias, context collapse), and this file is exactly the
kind of accumulated knowledge those findings describe.

---

## 5. Anti-patterns

Each of these was observed and corrected in practice, not imagined.

**Grep is not a survey.** Absence of evidence from one search method is not evidence of absence. In
prior work this produced two near-misses where a component looked unreferenced under one search
and was load-bearing under another. The research equivalent: a topic absent from PubMed is not
absent from the literature — it is absent from *biomedicine*.

**Do not unify sources that disagree.** When two credible sources conflict, the conflict is the
finding. Averaging them destroys information.

**Do not let a plausible mechanism substitute for evidence.** Something can be mechanistically
sensible and empirically untested — the routine-versus-novelty tension in domain passes was exactly
this: universally repeated, entirely undocumented. Mark it `[CONTESTED]` or leave it out.

**Do not treat a point estimate as meaningful under high heterogeneity.** A pooled figure at
I² ≈ 99.5% is close to uninterpretable. Report the range.

**Do not confuse self-report with measurement.** The single most robust finding in the productivity
literature is that practitioners' estimates of their own speedup were wrong by ~39 percentage
points, in the flattering direction.
