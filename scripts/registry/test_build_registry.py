#!/usr/bin/env python3
"""
test_build_registry.py - Unit tests for build_registry.py (local skill registry).
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

import build_registry as br

SNAPSHOT = "a" * 64

YAML_HEADER = """# PROVENANCE - alpha

```yaml
skill: alpha
created: 2026-08-30
trust_tier: T1-conditional
gate_reached: G4 (G0 partial, G1/G5 pending isolated runner)
research_snapshot:
  version: 1.3.0
  snapshot_sha256: {sha}
research_claims: [ctx.one]
```

## Evidence of need (G0)

Prose.
"""

HEADER_AND_REVISIONS = """# PROVENANCE

```yaml
skill: beta
created: 2026-09-04
trust_tier: T1-conditional
gate_reached: G4
```

## Revision 1: first change (2026-09-12)

```yaml
revision: 1
feature: first change
date: 2026-09-12
trust_tier: T2          # T2 until G5 passes
gate_reached: G3
```

## Revision 2: second change (2026-09-25)

```yaml
revision: 2
feature: second change
date: 2026-09-25
trust_tier: T2
gate_reached: G4
```
"""

REVISIONS_ONLY = """# PROVENANCE

## Revision 1: rework (2026-09-12)

```yaml
revision: 1
date: 2026-09-12
trust_tier: T2
gate_reached: G3
```
"""

ADDENDA = """# PROVENANCE

```yaml
name: delta
origin: generated at direct user request
trust_tier: T2 -> T1 pending G5 review below
```

## G5 - Prove

```
## not a heading inside a plain fence
```

## Addendum, 2026-09-11 - docket

```yaml
trigger: direct user request
derived_from_addendum:
  - lessons/docket.md
```
"""

PROSE = """# PROVENANCE

## scripts/gate.sh

Ported from another repo. No yaml here.
"""

INVALID_YAML = """# PROVENANCE

```yaml
skill: broken
trust_tier: [T2
```
"""


def cases(*suites: str) -> List[Dict[str, Any]]:
    return [{"id": f"case-{i}", "suite": s, "query": "q"} for i, s in enumerate(suites, 1)]


def write_skill(
    root: Path,
    name: str,
    provenance: Optional[str] = None,
    evals: Any = None,
    frontmatter_name: Optional[str] = None,
    results: Optional[Dict[str, Any]] = None,
) -> Path:
    skill = root / name
    (skill / "evals").mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {frontmatter_name or name}\ndescription: test skill\n---\n\nBody.\n",
        encoding="utf-8",
    )
    if provenance is not None:
        (skill / "PROVENANCE.md").write_text(provenance, encoding="utf-8")
    if evals is not None:
        text = evals if isinstance(evals, str) else json.dumps(evals)
        (skill / "evals" / "evals.json").write_text(text, encoding="utf-8")
    for file_name, data in (results or {}).items():
        (skill / "evals" / file_name).write_text(json.dumps(data), encoding="utf-8")
    return skill


class RegistryCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        if br.inside_git_tree(self.tmp) is not None:
            self.skipTest("temp directory is inside a git working tree")
        self.repo = self.tmp / "repo"
        self.skills = self.repo / "skills"
        self.skills.mkdir(parents=True)
        self.claims = self.repo / "claims.json"
        self.claims.write_text(
            json.dumps({"research_version": "1.3.0", "snapshot_sha256": SNAPSHOT}), encoding="utf-8"
        )
        self.library = self.tmp / "library"
        self.library.mkdir()
        self.home = self.tmp / "home"
        self.home.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_main(self, *extra: str, repo_only: bool = True) -> tuple[int, str, str]:
        argv = [
            "--repo", str(self.repo),
            "--repo-skills", "skills",
            "--claims-json", str(self.claims),
            "--library", str(self.library),
            "--out", str(self.home / "registry.yaml"),
        ]
        if repo_only:
            argv.append("--repo-only")
        argv.extend(extra)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = br.main(argv)
        return code, out.getvalue(), err.getvalue()

    def entry(self, name: str) -> br.SkillEntry:
        return br.scan_skill(self.skills / name, "repo", SNAPSHOT)

    def codes(self, entry: br.SkillEntry) -> List[str]:
        return [f.code for f in entry.findings]


class ProvenanceFormatTests(RegistryCase):
    def test_yaml_header(self) -> None:
        write_skill(self.skills, "alpha", YAML_HEADER.format(sha=SNAPSHOT), {"cases": cases("regression")})
        entry = self.entry("alpha")
        self.assertEqual(entry.data["provenance"]["format"], "yaml-header")
        self.assertEqual(entry.data["trust_tier"], "T1-conditional")
        self.assertEqual(entry.data["gate_reached"], "G4")
        self.assertEqual(entry.data["research_snapshot"], {"version": "1.3.0", "snapshot_sha256": SNAPSHOT})
        self.assertEqual(entry.data["research_claims"], ["ctx.one"])
        self.assertEqual(entry.findings, [])

    def test_header_and_revisions_takes_latest_revision(self) -> None:
        write_skill(self.skills, "beta", HEADER_AND_REVISIONS, {"cases": cases("regression")})
        entry = self.entry("beta")
        self.assertEqual(entry.data["provenance"]["format"], "yaml-header+revisions")
        self.assertEqual(entry.data["provenance"]["revisions"], 2)
        self.assertEqual(entry.data["provenance"]["latest_date"], "2026-09-25")
        self.assertEqual(entry.data["trust_tier"], "T2")
        self.assertEqual(entry.data["gate_reached"], "G4")

    def test_revisions_only(self) -> None:
        write_skill(self.skills, "gamma", REVISIONS_ONLY, {"cases": cases("regression")})
        entry = self.entry("gamma")
        self.assertEqual(entry.data["provenance"]["format"], "revisions")
        self.assertEqual(entry.data["trust_tier"], "T2")
        self.assertEqual(entry.data["gate_reached"], "G3")

    def test_addenda_and_name_key(self) -> None:
        write_skill(self.skills, "delta", ADDENDA, {"cases": cases("regression")})
        entry = self.entry("delta")
        self.assertEqual(entry.data["provenance"]["format"], "yaml-header+addenda")
        self.assertEqual(entry.data["trust_tier"], "T2")
        self.assertEqual(entry.data["trust_tier_declared"], "T2 -> T1 pending G5 review below")
        self.assertIsNone(entry.data["gate_reached"])
        self.assertNotIn("name_mismatch", self.codes(entry))

    def test_prose_only(self) -> None:
        write_skill(self.skills, "eps", PROSE, {"cases": cases("regression")})
        entry = self.entry("eps")
        self.assertEqual(entry.data["provenance"]["format"], "prose")
        self.assertIn("provenance_unstructured", self.codes(entry))

    def test_missing(self) -> None:
        write_skill(self.skills, "zeta", None, {"cases": cases("regression")})
        entry = self.entry("zeta")
        self.assertEqual(entry.data["provenance"]["format"], "missing")
        self.assertIn("provenance_missing", self.codes(entry))

    def test_invalid_yaml_is_parse_error(self) -> None:
        write_skill(self.skills, "broken", INVALID_YAML, {"cases": cases("regression")})
        self.assertIn(br.PARSE_ERROR, self.codes(self.entry("broken")))
        code, out, _ = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: 1 parse failure(s)", out)


class EvalsShapeTests(RegistryCase):
    def test_cases_list(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, {"skill": "a", "cases": cases("regression", "capability", "regression")})
        evals = self.entry("a").data["evals"]
        self.assertEqual((evals["shape"], evals["total"], evals["regression"], evals["capability"]), ("cases", 3, 2, 1))
        self.assertEqual(evals["file"], "evals/evals.json")

    def test_cases_without_suite_default_to_capability(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, {"cases": [{"id": 1, "prompt": "p"}]})
        self.assertEqual(self.entry("a").data["evals"]["capability"], 1)

    def test_suites_bare_lists(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, {"suites": {"regression": cases("regression", "regression"), "capability": cases("capability")}})
        evals = self.entry("a").data["evals"]
        self.assertEqual((evals["shape"], evals["total"], evals["regression"]), ("suites", 3, 2))

    def test_suites_with_cases_objects(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, {"suites": {"regression": {"cases": cases("regression")}}})
        evals = self.entry("a").data["evals"]
        self.assertEqual((evals["shape"], evals["total"]), ("suites", 1))

    def test_invalid_json_is_parse_error(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, "{not json")
        self.assertIn(br.PARSE_ERROR, self.codes(self.entry("a")))
        self.assertEqual(self.run_main("--check")[0], 1)

    def test_unknown_shape_is_parse_error(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, {"tests": []})
        self.assertIn(br.PARSE_ERROR, self.codes(self.entry("a")))

    def test_missing_evals(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, None)
        entry = self.entry("a")
        self.assertEqual(entry.data["evals"]["shape"], "missing")
        self.assertIn("evals_missing", self.codes(entry))


class StaleTests(RegistryCase):
    @staticmethod
    def result(n: int) -> Dict[str, Any]:
        return {
            "skill": "a", "gate": "G1", "mode": "baseline", "date": "2026-09-04T22:41:13", "k": 1,
            "model_harness_pair": {"runner": "claude -p {prompt}", "judge": "unrecorded"},
            "pass_pow_k_overall": 0.0,
            "cases": [{"id": i, "suite": "regression", "attempts": ["FAIL"]} for i in range(n)],
        }

    def test_fewer_cases_than_evals_is_stale(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, {"cases": cases("regression", "regression", "capability")},
                    results={"results-baseline.json": self.result(2)})
        entry = self.entry("a")
        self.assertTrue(entry.data["results"][0]["stale"])
        self.assertEqual(entry.data["results"][0]["n_cases_at_run"], 2)
        self.assertIn("stale_results", self.codes(entry))

    def test_matching_count_is_fresh(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, {"cases": cases("regression", "capability")},
                    results={"results-treated.json": self.result(2)})
        entry = self.entry("a")
        self.assertFalse(entry.data["results"][0]["stale"])
        self.assertNotIn("stale_results", self.codes(entry))

    def test_deterministic_last_run_is_not_compared(self) -> None:
        write_skill(self.skills, "a", REVISIONS_ONLY, {"cases": cases("regression")},
                    results={"last_run.json": {"suite": "gates", "passed": 53, "total": 53, "results": []}})
        result = self.entry("a").data["results"][0]
        self.assertEqual(result["gate"], "deterministic")
        self.assertIsNone(result["stale"])


class NameAndTierTests(RegistryCase):
    def test_provenance_name_mismatch(self) -> None:
        write_skill(self.skills, "event-finder", YAML_HEADER.replace("skill: alpha", "skill: finding-events").format(sha=SNAPSHOT),
                    {"cases": cases("regression")})
        entry = self.entry("event-finder")
        self.assertIn("name_mismatch", self.codes(entry))
        self.assertEqual(entry.data["aliases"], ["finding-events"])

    def test_frontmatter_name_mismatch(self) -> None:
        write_skill(self.skills, "dir-name", REVISIONS_ONLY, {"cases": cases("regression")}, frontmatter_name="other")
        self.assertIn("name_mismatch", self.codes(self.entry("dir-name")))

    def test_t4_default_without_tier(self) -> None:
        write_skill(self.skills, "a", PROSE, {"cases": cases("regression")})
        entry = self.entry("a")
        self.assertEqual(entry.data["trust_tier"], "T4")
        self.assertIsNone(entry.data["trust_tier_declared"])
        self.assertIn("tier_default", self.codes(entry))

    def test_t4_default_when_provenance_missing(self) -> None:
        write_skill(self.skills, "a", None, {"cases": cases("regression")})
        self.assertEqual(self.entry("a").data["trust_tier"], "T4")

    def test_research_snapshot_behind(self) -> None:
        write_skill(self.skills, "alpha", YAML_HEADER.format(sha="b" * 64), {"cases": cases("regression")})
        self.assertIn("research_snapshot_behind", self.codes(self.entry("alpha")))


class CliTests(RegistryCase):
    ABS_PATH = re.compile(r"[A-Za-z]:[\\/]|(?<![\w.~])/(?:home|Users|tmp|var)/")

    def populate(self) -> None:
        write_skill(self.skills, "alpha", YAML_HEADER.format(sha=SNAPSHOT), {"cases": cases("regression")})
        write_skill(self.skills, "beta", HEADER_AND_REVISIONS, {"cases": cases("regression")})
        write_skill(self.library, "alpha", YAML_HEADER.format(sha=SNAPSHOT), {"cases": cases("regression")})
        write_skill(self.library, "private-one", PROSE, None)

    def test_repo_only_check_output(self) -> None:
        self.populate()
        code, out, _ = self.run_main("--check")
        self.assertEqual(code, 0)
        self.assertIn("OK: 2 repo skills parsed", out)
        self.assertNotIn("private-one", out)
        self.assertFalse((self.home / "registry.yaml").exists())

    def test_no_absolute_path_in_output(self) -> None:
        self.populate()
        code, out, err = self.run_main("--propose-backfill", str(self.home / "backfill"), repo_only=False)
        self.assertEqual(code, 0, err)
        written = [self.home / "registry.yaml", *sorted((self.home / "backfill").iterdir())]
        texts = [p.read_text(encoding="utf-8") for p in written] + [out, err]
        for text in texts:
            for needle in (str(self.tmp), self.tmp.as_posix(), str(Path.home()), Path.home().as_posix()):
                self.assertNotIn(needle, text)
            self.assertIsNone(self.ABS_PATH.search(text), text)

    def test_registry_contents(self) -> None:
        self.populate()
        self.assertEqual(self.run_main(repo_only=False)[0], 0)
        registry = yaml.safe_load((self.home / "registry.yaml").read_text(encoding="utf-8"))
        self.assertEqual(registry["schema_version"], 1)
        self.assertEqual(registry["research_snapshot"]["snapshot_sha256"], SNAPSHOT)
        self.assertIn("last_built", registry)
        by_name = {s["name"]: s for s in registry["skills"]}
        self.assertEqual(sorted(by_name), ["alpha", "beta", "private-one"])
        self.assertEqual(by_name["alpha"]["origin"], "repo")
        self.assertTrue(by_name["alpha"]["deploy_in_sync"])
        self.assertFalse(by_name["beta"]["deployed"])
        self.assertEqual(by_name["private-one"]["origin"], "library")

    def test_check_ignores_last_built_and_reports_drift(self) -> None:
        self.populate()
        self.assertEqual(self.run_main(repo_only=False)[0], 0)
        path = self.home / "registry.yaml"
        registry = yaml.safe_load(path.read_text(encoding="utf-8"))
        registry["last_built"] = "2000-01-01"
        path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
        code, out, _ = self.run_main("--check", repo_only=False)
        self.assertEqual(code, 0, out)
        self.assertIn("OK: 3 skills parsed", out)
        write_skill(self.skills, "beta", HEADER_AND_REVISIONS, {"cases": cases("regression", "capability")})
        code, out, _ = self.run_main("--check", repo_only=False)
        self.assertEqual(code, 1)
        self.assertIn("DRIFT", out)

    def test_backfill_proposals(self) -> None:
        self.populate()
        self.assertEqual(self.run_main("--propose-backfill", str(self.home / "backfill"), repo_only=False)[0], 0)
        names = sorted(p.name for p in (self.home / "backfill").iterdir())
        self.assertEqual(names, ["private-one.PROVENANCE.md"])
        text = (self.home / "backfill" / "private-one.PROVENANCE.md").read_text(encoding="utf-8")
        self.assertIn("trust_tier: T4", text)

    def test_check_with_backfill_is_usage_error(self) -> None:
        self.populate()
        self.assertEqual(self.run_main("--check", "--propose-backfill", str(self.home / "b"))[0], 2)


class RefusalTests(RegistryCase):
    def setUp(self) -> None:
        super().setUp()
        self.tree = self.tmp / "worktree"
        (self.tree / ".git").mkdir(parents=True)
        write_skill(self.skills, "alpha", YAML_HEADER.format(sha=SNAPSHOT), {"cases": cases("regression")})

    def test_refuses_out_inside_git_tree(self) -> None:
        target = self.tree / "sub" / "registry.yaml"
        code, _, err = self.run_main("--out", str(target))
        self.assertEqual(code, 1)
        self.assertIn("refusing", err)
        self.assertFalse(target.exists())
        self.assertFalse(target.parent.exists())

    def test_refuses_git_file_worktree(self) -> None:
        other = self.tmp / "linked"
        other.mkdir()
        (other / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        self.assertEqual(self.run_main("--out", str(other / "registry.yaml"))[0], 1)
        self.assertFalse((other / "registry.yaml").exists())

    def test_refuses_backfill_inside_git_tree(self) -> None:
        code, _, err = self.run_main("--propose-backfill", str(self.tree / "backfill"))
        self.assertEqual(code, 1)
        self.assertIn("refusing", err)
        self.assertFalse((self.tree / "backfill").exists())
        self.assertFalse((self.home / "registry.yaml").exists())

    def test_repo_only_check_writes_nothing_even_with_out_in_tree(self) -> None:
        target = self.tree / "registry.yaml"
        code, out, _ = self.run_main("--check", "--out", str(target))
        self.assertEqual(code, 0)
        self.assertIn("OK: 1 repo skills parsed", out)
        self.assertEqual(sorted(p.name for p in self.tree.iterdir()), [".git"])

    def test_default_out_in_repo_is_refused(self) -> None:
        (self.repo / ".git").mkdir()
        code, _, _ = self.run_main("--out", str(self.repo / "registry.yaml"))
        self.assertEqual(code, 1)
        self.assertFalse((self.repo / "registry.yaml").exists())


if __name__ == "__main__":
    unittest.main()
