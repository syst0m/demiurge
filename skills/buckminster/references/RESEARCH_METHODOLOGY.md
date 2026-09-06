# RESEARCH_METHODOLOGY.md

This is a method. The point of writing it down is that the same method produces
comparable snapshots over time — so version-to-version diffs in `RESEARCH.md` mean something.

---

## 1. The toolchain

### Scholarly connectors

Four specialized connectors provide empirical coverage. Using one alone produces a biased snapshot.

| Connector | Best for | Documentation | Watch for |
|---|---|---|---|
| **Undermind** | `launch_deep_search` — a multi-agent review taking 2–5 min, producing a ranked list plus a summary. `search_papers` for exploration; `read_pdfs` for targeted full text | [Undermind Docs](https://undermind.ai) | One well-aimed deep search usually covers a whole brief. Call `get_orientation()` before any other Undermind tool |
| **scite** | Smart Citations — the actual sentences citing papers wrote, classified supporting/contrasting/mentioning. **`editorialNotices` for retractions and corrections** | [scite Docs](https://scite.ai/mcp) | The only source here that shows how a finding was *received*, not just what it claimed |
| **Consensus** | General paper search with citation counts across 220M+ papers | [Consensus Docs](https://consensus.app) | Requires numbered inline citations and reproducing its usage message verbatim |
| **PubMed** | Biomedical and life sciences only | [PubMed Central](https://pubmed.ncbi.nlm.nih.gov) | Returns nothing useful for CS/AI — do not use it for agentic-engineering work |

#### Connector Availability and Fresh Clone Fallbacks

Scholarly connectors are optional instruments. Fresh clones of Demiurge and Marcus operate with zero external tool dependencies.

If an operator environment lacks scholarly connectors:

1. **Avoid tool-call faults**: Do not attempt to invoke missing MCP tools.
2. **Degrade gracefully**: Rely on `WebSearch`, open-access repository lookups (arXiv, Semantic Scholar, IACR, ACM DL abstracts), standards bodies (IETF, W3C), and direct vendor engineering blogs.
3. **Disclose unverified reception**: Explicitly state in the diff proposal:
   > *"Scholarly connectors (scite, Undermind, Consensus) were unavailable in this environment. Citation reception (retraction checks and supporting vs contrasting sentiment) could not be verified via Smart Citations."*
4. **Conservative grading**: Findings whose reception cannot be verified via Smart Citations must not be marked `[SETTLED]`. Mark them `[CONTESTED]` or `[EMERGING]` until verified with scholarly connectors.

### Web

- **WebSearch** — current state, adoption numbers, "what happened since". US-only results.
- **WebFetch** — primary sources. Prefer the vendor's own engineering blog over any summary of it.

### Evidence hierarchy (Peer-Review Priority)

Evaluate and prioritize sources by epistemological rigor:

1. **First Tier (Highest Priority): Peer-reviewed academic literature and meta-analyses.** Queried
   via scholarly connectors (`scite`, `Consensus`, `PubMed` where appropriate). Provides empirical
   methodology, peer scrutiny, and citation context.
2. **Second Tier: Published technical RFCs and open specifications.** AAIF, Linux Foundation, IETF,
   W3C standards.
3. **Third Tier: Vendor engineering documentation or empirical benchmark reports.** Must be
   explicitly labeled `[VENDOR]` and **cannot constitute more than 1 of the 3 required sources**.

### What is deliberately not used

- **arXiv scraping** — the scholarly connectors already index it, with citation context attached.
- **Social media / aggregator blogs** as evidence. Usable to *discover* a claim, never to support
  one. Every such claim gets traced to a primary source or marked unverified.

---

## 2. The method

### Step 1 — Frame the question so it can be answered wrongly

Valid research briefs require falsifiability and permit null or disconfirming results. Every brief specifies criteria for evidence counter to expected hypotheses, requesting null and critical findings systematically.

> Bad: *"Find evidence that agent memory improves performance."*
> Good: *"What does the evidence say about whether persistent agent memory improves performance,
including any findings that it does not?"*

Empirical evaluations demonstrate that persistent memory scaffolds degrade long-horizon performance across multiple models—a critical negative finding obscured by confirmation-biased briefs.

### Step 2 — Breadth before depth

If Undermind is connected, launch the deep search first (it runs asynchronously for minutes), then use
that window for targeted `search_papers`, WebSearch and primary-source WebFetch. Do not idle waiting for
it. If Undermind is absent, proceed directly with web search engines and open-access repositories.

### Step 3 — Check how findings were received

For any load-bearing claim, run it through scite if available:

- **`editorialNotices`** — retracted? corrected? subject to an expression of concern?
- **Smart Citations** — do citing papers support it, or contrast with it? A heavily-cited paper
  whose citations are largely *contrasting* is classified as a disputed finding.

If scite is absent, record explicitly that reception analysis and retraction status could not be
empirically validated.

### Step 4 — Grade every claim before writing it down

Confidence markers are assigned at capture time. `RESEARCH.md` uses four:

- `[SETTLED]` — supported by at least 3 independent, verified resources, with all 3 confirming the finding (empirical backing)
- `[CONTESTED]` — credible sources disagree, or it rests on fewer than 3 independent studies
- `[VENDOR]` — the claim originates with a party selling the thing (capped at max 1 of the 3 required sources)
- `[EMERGING]` — real but too new to have been tested in practice

**Mandatory Tri-Source Verification Rule:**

- Every claim proposed for `RESEARCH.md` must be supported by **at least 3 independent, verified resources**.
- A claim cannot be graded `[SETTLED]` unless all 3 independent sources confirm the finding. If sources disagree, grade `[CONTESTED]` and state the conflict.
- Claims resting on 1 or 2 sources cannot be marked `[SETTLED]`. If unverified across 3 independent sources, flag explicitly or reject.
- Vendor sources (`[VENDOR]`) cannot constitute more than 1 of the 3 required sources.

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

**Mandatory Concrete Reference Links.** Every cited finding must include clickable markdown
hyperlinks (`[Source Name](https://...)`, `[Paper Title](https://doi.org/...)`, or arXiv URLs).
Vague domain-level mentions (e.g. *"Claude engineering blog 2026, scalably.io"* or *"arxiv.org
(2026)"*) are strictly disallowed. Every citation must resolve to an explicit primary source URL,
paper link, or DOI.

**Attribute everything.** Working URL, publication date, and author or organisation. A claim with no
traceable source does not go in.

**Explicitly record unverified claims.** When secondary aggregator sources report claims that cannot be traced to primary literature (such as unverified benchmark deprecations or unsubstantiated percentage gains), mark them explicitly as unverified for subsequent validation.

**Prefer primary sources.** A vendor's own engineering post beats any write-up of it. A paper beats
a thread about the paper.

**Note the population.** A finding from a controlled benchmark, from an enterprise deployment, and
from a solo developer are three different findings. `RESEARCH.md` is consumed by Marcus to design
agents for a **solo operator** — a result that only holds at team scale must say so.

**Quantify where the source quantifies.** "Prompt injection is hard" is not usable. ">85% adaptive
attack success against state-of-the-art defences, most defences under 50%" is.

---

## 4. Producing an update

Buckminster generates a **diff proposal** for human review before updating `RESEARCH.md`:

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

Each of these was observed and corrected directly in practice.

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
