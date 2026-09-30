# Skill Registry: Local Inventory of Skills

```yaml
version: 1.0.0
audience: operators, maintainers
canonical_path: docs/SKILL_REGISTRY.md
```

The skill registry lists every skill Marcus knows about, with its trust tier, the last gate it reached, the research snapshot it was built from and the state of its evals. `scripts/registry/build_registry.py` derives it from each skill's `PROVENANCE.md` and `evals.json`. Nobody edits it by hand.

---

## 1. Local Only

The registry lives at `~/.demiurge/registry.yaml` and is never committed.

- **This repo is public.** The registry also scans the installed skill library, and that library holds private skills. Committing the registry would publish their names, tiers and findings.
- **The builder enforces this.** Every mode that writes refuses a target inside a git working tree and exits 1. The default output path and the default backfill directory, `~/.demiurge/backfill/`, both sit outside every checkout.
- **CI parses without writing.** `--repo-only --check` reads the two repo skills and prints their findings. It writes nothing, so nothing about the private library reaches a CI log.

Findings for private skills stay in `~/.demiurge/`.

---

## 2. What It Records

Each skill entry carries:

| Field | Source |
|---|---|
| `trust_tier`, `gate_reached` | Latest `PROVENANCE.md` revision, else its header. A missing tier defaults to T4 and raises `tier_default`. |
| `research_snapshot` | `{version, snapshot_sha256}` from `PROVENANCE.md`, written by `new_skill.py` and `modify_skill.py`. |
| `research_claims` | The `claims.json` claim ids recorded in `PROVENANCE.md` as the ones the skill rests on. |
| `evals` | Shape (`cases` or `suites`), case count and a hash of `evals.json`. |
| `results` | Each `evals/results-*.json` and `evals/last_run.json`, with the case count it scored. |
| `deployed`, `deploy_in_sync` | Whether the installed copy exists and matches the repo copy (full builds only). |

The top-level `research_snapshot` is read from `claims.json`, and `last_built` records the build date.

### 2.1 Findings

| Code | Fires when |
|---|---|
| `parse_error` | `PROVENANCE.md` or `evals.json` fails to parse. The only finding that fails a check. |
| `provenance_missing` | The skill has no `PROVENANCE.md`. |
| `provenance_unstructured` | `PROVENANCE.md` has no YAML block. |
| `tier_default` | No `trust_tier` is recorded. |
| `name_mismatch` | The directory name differs from the `SKILL.md` frontmatter or the `PROVENANCE.md` header. |
| `research_snapshot_behind` | The recorded `snapshot_sha256` differs from the current one in `claims.json`. |
| `evals_missing` | The skill has no `evals.json`. |
| `stale_results` | A results file scored a different number of cases than `evals.json` now holds. |
| `deploy_drift` | The installed copy differs from the repo copy. |

---

## 3. Commands

Run every command from the demiurge checkout root. The builder needs PyYAML: `python -m pip install -r requirements-dev.txt`.

| Command | Effect |
|---|---|
| `python scripts/registry/build_registry.py` | Scans the repo skills and the installed library, then writes `~/.demiurge/registry.yaml`. |
| `python scripts/registry/build_registry.py --check` | Exits 1 on a parse failure or when the written registry is out of date. Writes nothing. |
| `python scripts/registry/build_registry.py --repo-only --check` | The CI mode: prints `OK: 2 repo skills parsed`, or exits 1 on a parse failure. |
| `python scripts/registry/build_registry.py --propose-backfill [DIR]` | Also writes a proposed `PROVENANCE.md` header for each skill with a missing or unstructured `PROVENANCE.md`, no recorded tier or a name mismatch. |

`--library <dir>` points at another installed library and `--out <path>` at another output file. Both must stay outside every git working tree.

CI runs `--repo-only --check` on every push and pull request (`.github/workflows/checks.yml`).

---

## 4. Related Checks

`skills/marcus/scripts/update_marcus.py` checks the snapshot side of the same chain. The `derived_from` line in `skills/marcus/AGENT_ARCHITECTURE.md` reads `RESEARCH.md v<version> (<snapshot_date>) snapshot_sha256:<hex>`. The date must match `research/RESEARCH.md` and the hash must match `claims.json`, or the check reports DRIFT. It also runs `scripts/research/check_rule_citations.py` and warns when the `derived_from` line in `docs/AGENT_DESIGN.md` lags. See [CLAIMS_LEDGER.md](CLAIMS_LEDGER.md) for how `claims.json` is compiled.
