# Claims Ledger: Anchors, Sources and grade_cap

```yaml
version: 1.0.0
audience: operators, Buckminster, maintainers
canonical_path: docs/CLAIMS_LEDGER.md
```

The claims ledger ties every graded claim in `research/RESEARCH.md` to the sources behind it. RESEARCH.md stays the canonical prose. `research/sources.yaml` records the sources, and `scripts/research/grade_cap.py` checks each grade against them. A grade can go down when its sources fall short. Only a human-reviewed PR raises one.

Source discipline itself lives in [RESEARCH_METHODOLOGY.md](../skills/buckminster/references/RESEARCH_METHODOLOGY.md). This page covers the data model and the tooling.

---

## 1. Anchors in RESEARCH.md

Each graded claim line starts with an HTML comment anchor:

| Line kind | Anchor position | Example |
|---|---|---|
| Bullet | After the list marker | `- <!-- claim:ctx.length-degradation --> text` |
| Table row | Inside the first cell | `\| <!-- claim:x --> cell \|` |
| Prose or header | At the start of the line | `<!-- claim:disc.agentic-eng --> **Agentic engineering** ...` |

- Claim ids match `^[a-z]+\.[a-z0-9-]+$`. Rule ids match `^R-[A-Z]+-\d+$`.
- Rules carry `<!-- rule:R-CTX-1 -->` on their first line and show the id in the text, as in `*Marcus Rule (R-CTX-1):*` or `- *R-SEC-1:*`. A rule runs until the next blank line or the next rule anchor. Each rule states one requirement.
- The grade markers on an anchored line map, in order, to the claim's `grades` list.
- A `[VENDOR]` directly after a link `](...)` is a source tag. It is not a grade.
- Every graded marker line needs an anchor, so a new claim cannot bypass the sidecar. The legend, the change-log table and fenced blocks are exempt.
- `grade_cap.py --write` rewrites each marker to the effective grade and appends `` `[UNVERIFIED]` `` when that grade is flagged.

Stripping the anchors returns the unanchored prose byte for byte:

```bash
sed -E 's/<!-- (claim|rule):[^>]* --> //' research/RESEARCH.md
```

---

## 2. The Sidecar: `research/sources.yaml`

The sidecar is canonical and reviewed in PRs. It carries **no YAML comments**, because `yaml.safe_dump` drops them on every rewrite. Every `--write` rejects a file with comments. Put notes in the `notes:` string field.

```yaml
schema: demiurge.sources.v1
meta:
  enforced: false
  enforce_after: null
claims:
  ctx.length-degradation:
    section: 2
    kind: prose
    population: any
    polarity: affirm
    grades:
      - {scope: null, asserted: SETTLED, cap: EMERGING, cap_evidence: SETTLED,
         unverified: true, cap_reasons: [no_countable_sources, aggregator_unresolved]}
    sources:
      - id: s1
        url: "https://consensus.app/papers/details/..."
        title: "Context Length Alone Hurts LLM Performance"
        type: aggregator
        resolves_to: null
        resolves_to_type: null
        independence_group: null
        supports: confirms
        quote: null
        accessed: null
        reception: {checked: false, retracted: null, scite_supporting: null, scite_contrasting: null}
    duplicates: []
    last_verified: null
    verified_by: null
    notes: ""
rules:
  R-CTX-1: {section: 2, basis: evidence, claims: [ctx.self-rewritten-memory]}
```

### 2.1 Field enums

| Field | Allowed values |
|---|---|
| `kind` | `prose`, `bullet`, `table_row`, `header` |
| `polarity` | `affirm`, `negate` |
| `asserted`, `cap`, `cap_evidence` | `SETTLED`, `CONTESTED`, `EMERGING`, `VENDOR` |
| `type`, `resolves_to_type` | `peer`, `preprint`, `spec`, `vendor`, `practitioner`, `aggregator`, `none` |
| `supports` | `confirms`, `contrasts`, `mentions` |
| `basis` (rules) | `evidence`, `design` |

### 2.2 Field meanings

- `asserted` is the grade a human wrote. No tool changes it.
- `cap`, `cap_evidence`, `unverified` and `cap_reasons` are computed by `grade_cap.py --write`. Do not edit them by hand.
- `resolves_to` is the primary source behind an aggregator link, such as the DOI behind a consensus.app page.
- `independence_group` names the research group or organisation behind a source. Sources sharing a group count once.
- `quote` is a verbatim excerpt of 25 words or fewer. `accessed` is the retrieval date.
- `duplicates` lists claims that restate this one. Pairs are recorded in both directions and never merged.
- A named source with no URL is recorded as `{url: null, type: none, title: "<name as written>"}`.
- A rule's `claims` lists the claim ids it rests on. `basis: evidence` needs at least one. A rule that rests on a specification or on practice alone is `basis: design` with `claims: []`. `validate` rejects an unknown claim id and a missing `basis`.

### 2.3 Compiled output: `skills/marcus/references/claims.json`

`grade_cap.py --write` compiles the sidecar into `claims.json`, which Marcus reads with the standard library only. It records `research_sha256`, `sources_sha256` and a combined `snapshot_sha256`, plus per-claim effective grades, the `unverified` flag, a `claim_sha256` over the claim text and its sources, and grade counts. A hash mismatch means the compiled file is stale.

---

## 3. The grade_cap Algorithm

Grades are ordered `SETTLED(4) > CONTESTED(3) > EMERGING(2) > VENDOR(1)`. A cap can only lower a grade: `effective = lower_rank(asserted, cap)`.

```
etype(s)  = s.resolves_to_type if s.type == aggregator and s.resolves_to else s.type
counted   = [s for s in sources if s.supports == confirms
             and etype(s) not in {aggregator, none} and not s.reception.retracted]
groups    = {s.independence_group for s in counted if s.independence_group}
            ∪ ({"_unset"} if any counted s has null independence_group)
primary   = groups containing any s with etype in {peer, preprint, spec}
vgroups   = groups whose members are all vendor
```

### 3.1 Reasons

| Reason | Class | Fires when |
|---|---|---|
| `contrasting_source` | Evidence | Any source with `supports: contrasts` whose type counts |
| `retracted_source` | Evidence | Any source with `reception.retracted` true |
| `vendor_gt1` | Evidence | More than one all-vendor group |
| `vendor_only` | Evidence | Every counted source is vendor, no aggregator is unresolved and no source has `type: none` |
| `no_countable_sources` | Debt | No counted source |
| `aggregator_unresolved` | Debt | An aggregator source has no `resolves_to` |
| `lt3_independent` | Debt | Between one and two independence groups |
| `lt2_primary` | Debt | Fewer than two primary groups |
| `independence_unset` | Debt | A counted source has a null `independence_group` |
| `reception_unchecked` | Debt | A counted peer or preprint source has `reception.checked` false |
| `unretrieved_source` | Debt | A counted source lacks `quote` or `accessed` |

Specs, vendor documents and practitioner sources are exempt from the reception check. Practitioner sources count as groups, but SETTLED also needs two primary groups, so three blog posts cannot reach SETTLED.

### 3.2 Caps

```
BLOCKING = {contrasting_source, vendor_gt1, lt3_independent, lt2_primary,
            independence_unset, reception_unchecked, unretrieved_source}
cap(R): VENDOR    if vendor_only in R
        EMERGING  elif no_countable_sources in R
        CONTESTED elif R ∩ BLOCKING
        SETTLED   otherwise
cap_evidence = cap(reasons ∩ EVIDENCE)
cap          = cap(reasons)
effective    = lower_rank(asserted, cap if meta.enforced else cap_evidence)
unverified   = rank(cap) < rank(asserted) and (reasons ∩ DEBT) non-empty
```

- With no countable source the cap is EMERGING. The legend keeps CONTESTED for conflicting sources or a single study.
- `polarity: negate` claims (the hype list) are skipped and reported as `skipped_negate`.

---

## 4. Enforcement Transition

The methodology applies to existing claims in two stages.

1. **Evidence reasons lower the grade at once.** A contrasting, retracted or second vendor source is already in the record, so `cap_evidence` applies while `meta.enforced` is false.
2. **Debt reasons only flag the grade** while `meta.enforced` is false. RESEARCH.md shows `` `[UNVERIFIED]` `` beside the grade and Marcus keeps acting on the grade shown.

`meta.enforce_after` holds the date after which the operator runs the debt pass and opens a PR that sets `enforced: true`. The flip is a PR, so CI stays deterministic. From that date on, while `enforced` is false, `grade_cap.py --check` prints a WARNING and still exits 0.

`--stats` prints `SETTLED if enforced=<n>`, the count of SETTLED grades that would survive enforcement today.

---

## 5. Commands

Run every command from the demiurge checkout root. Path flags also accept `--repo <dir>`.

| Command | Effect |
|---|---|
| `python scripts/research/grade_cap.py --write` | Stores caps, rewrites markers and `[UNVERIFIED]` flags on anchored lines, compiles `claims.json` and prints a per-claim change table. |
| `python scripts/research/grade_cap.py --check` | Exits 1 when stored caps, markers or `claims.json` hashes are stale, or validation fails. |
| `python scripts/research/grade_cap.py --stats` | Counts by effective grade, `SETTLED if enforced`, the unverified count, a reason histogram and `skipped_negate`. |
| `python scripts/research/grade_cap.py --debt --limit 10 [--json]` | The debt queue, highest score first. |
| `python scripts/research/grade_cap.py --changelog-row --version X --by Y` | Prints a change-log row summarising grade moves. |
| `python scripts/research/grade_cap.py --check-changelog --base <ref>` | Exits 1 unless the base change-log rows are a byte-equal prefix of the head rows. |

`scripts/research/anchor_claims.py` is the one-off bootstrap that inserted the anchors and emitted the first sidecar skeleton. `scripts/research/research_lib.py` holds the shared loader, parser and validator. Tooling under `scripts/research/` needs PyYAML: `python -m pip install -r requirements-dev.txt`.

CI runs `--check` on every push and pull request, and `--check-changelog --base origin/<base branch>` on pull requests (`.github/workflows/checks.yml`).

---

## 6. Debt Workflow

Step 0 of every Buckminster sweep is the debt queue:

```bash
python scripts/research/grade_cap.py --debt --limit 10
```

Each row prints `id`, `asserted→cap`, the reasons and the work each source still needs (`resolve`, `independence_group`, `reception`, `quote`, `accessed`). The score is `3 × rules citing the claim + 2 × (asserted is SETTLED) + 1 × aggregator_unresolved`.

For each claim:

1. Resolve aggregator links to their primary source and set `resolves_to` and `resolves_to_type`.
2. Run the reception check on peer and preprint sources and fill `reception`.
3. Record `accessed`, a verbatim `quote` of 25 words or fewer, `independence_group` and `verified_by`.
4. Run `grade_cap.py --write`, then `grade_cap.py --check`.
5. Open a PR with the prose and sidecar diff together.

Never add a source that was not retrieved in the same session. Never raise `asserted` without a PR that names the new sources.
