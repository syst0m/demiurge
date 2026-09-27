#!/usr/bin/env python3
"""
test_grade_cap.py - Unit tests for grade_cap.py (source-based grade caps).
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import grade_cap as gc
import research_lib as rl

RESEARCH = """# RESEARCH.md

```yaml
version: 1.3.0
```

| Marker | Criteria | Marcus Rule |
|---|---|---|
| `[SETTLED]` | Three sources | Encode as default. |

## 2. Context Engineering

<!-- claim:ctx.solid --> `[SETTLED]` **Solid claim.** Source: [Docs](https://example.com/a) `[VENDOR]`.

- <!-- claim:ctx.thin --> **Thin claim.** `[SETTLED]` and `[VENDOR: Cognition]` for exact scores.

<!-- claim:hype.negated --> `[SETTLED]` **Hype that does not hold.**

<!-- rule:R-CTX-1 --> *Marcus Rule:* Use append-only files.

## Change log

| Version | Date | By | Change |
|---|---|---|---|
| 1.0.0 | 2026-08-30 | Extraction | Initial extract. |
| 1.1.0 | 2026-09-01 | Buckminster | Added things. |
"""


def src(source_id: str, type_: str = "peer", group: str | None = None, **overrides) -> dict:
    """A fully retrieved, reception-checked confirming source."""
    base = {
        "id": source_id,
        "url": "https://example.com/" + source_id,
        "title": "Title",
        "type": type_,
        "resolves_to": None,
        "resolves_to_type": None,
        "independence_group": group if group is not None else "g-" + source_id,
        "supports": "confirms",
        "quote": "a short quote",
        "accessed": "2026-09-20",
        "reception": {"checked": True, "retracted": False, "scite_supporting": None, "scite_contrasting": None},
    }
    base.update(overrides)
    return base


def primary3() -> list:
    return [src("s1"), src("s2", "preprint"), src("s3", "spec")]


def grade(asserted: str) -> dict:
    return {"scope": None, "asserted": asserted, "cap": None, "cap_evidence": None, "unverified": False, "cap_reasons": []}


def claim(sources: list, grades: list, polarity: str = "affirm") -> dict:
    return {
        "section": 2,
        "kind": "prose",
        "population": "any",
        "polarity": polarity,
        "grades": grades,
        "sources": sources,
        "duplicates": [],
        "last_verified": None,
        "verified_by": None,
        "notes": "",
    }


def sidecar(enforced: bool = False, enforce_after=None) -> dict:
    return {
        "schema": rl.SOURCES_SCHEMA,
        "meta": {"enforced": enforced, "enforce_after": enforce_after},
        "claims": {
            "ctx.solid": claim(primary3(), [grade("SETTLED")]),
            "ctx.thin": claim([src("p1"), src("p2", "preprint")], [grade("SETTLED"), grade("VENDOR")]),
            "hype.negated": claim([], [grade("SETTLED")], polarity="negate"),
        },
        "rules": {"R-CTX-1": {"section": 2, "basis": None, "claims": ["ctx.solid"]}},
    }


def one(sources: list, asserted: str = "SETTLED", enforced: bool = False) -> gc.GradeResult:
    return gc.evaluate_claim("x.y", claim(sources, [grade(asserted)]), enforced).grades[0]


class TestAlgorithm(unittest.TestCase):
    def test_three_primary_groups_checked_and_quoted_is_settled(self):
        result = one(primary3())
        self.assertEqual(result.reasons, [])
        self.assertEqual((result.cap, result.effective, result.unverified), ("SETTLED", "SETTLED", False))

    def test_unchecked_reception_flags_until_enforced(self):
        sources = primary3()
        sources[0]["reception"]["checked"] = False
        loose = one(sources)
        self.assertEqual(loose.reasons, ["reception_unchecked"])
        self.assertEqual((loose.cap, loose.effective, loose.unverified), ("CONTESTED", "SETTLED", True))
        strict = one(sources, enforced=True)
        self.assertEqual((strict.effective, strict.unverified), ("CONTESTED", True))

    def test_three_practitioner_sources_lack_primary(self):
        result = one([src("p1", "practitioner"), src("p2", "practitioner"), src("p3", "practitioner")])
        self.assertEqual(result.reasons, ["lt2_primary"])
        self.assertEqual(result.cap, "CONTESTED")

    def test_null_groups_collapse_into_one(self):
        sources = [src(f"s{i}") for i in range(3)]
        for s in sources:
            s["independence_group"] = None
        result = one(sources)
        self.assertIn("lt3_independent", result.reasons)
        self.assertIn("independence_unset", result.reasons)
        self.assertEqual(result.effective, "SETTLED")

    def test_two_vendor_groups_lower_at_once(self):
        result = one([src("v1", "vendor"), src("v2", "vendor"), src("p1")])
        self.assertIn("vendor_gt1", result.reasons)
        self.assertEqual((result.cap_evidence, result.effective), ("CONTESTED", "CONTESTED"))

    def test_vendor_only_caps_at_vendor(self):
        result = one([src("v1", "vendor")])
        self.assertIn("vendor_only", result.reasons)
        self.assertEqual((result.cap, result.effective), ("VENDOR", "VENDOR"))

    def test_vendor_plus_unresolved_aggregator_is_not_vendor_only(self):
        aggregator = src("a1", "aggregator", quote=None, accessed=None)
        result = one([src("v1", "vendor"), aggregator])
        self.assertNotIn("vendor_only", result.reasons)
        self.assertIn("aggregator_unresolved", result.reasons)
        self.assertEqual((result.cap, result.effective, result.unverified), ("CONTESTED", "SETTLED", True))

    def test_resolved_aggregator_counts_as_its_target(self):
        resolved = src("a1", "aggregator", resolves_to="https://doi.org/10.0/x", resolves_to_type="peer")
        result = one([resolved, src("s2"), src("s3", "spec")])
        self.assertEqual(result.reasons, [])

    def test_zero_sources_asserted_emerging(self):
        result = one([], asserted="EMERGING")
        self.assertIn("no_countable_sources", result.reasons)
        self.assertEqual((result.cap, result.effective, result.unverified), ("EMERGING", "EMERGING", False))

    def test_all_aggregator_caps_emerging_and_flags(self):
        result = one([src("a1", "aggregator"), src("a2", "aggregator")])
        self.assertEqual(result.reasons[:2], ["no_countable_sources", "aggregator_unresolved"])
        self.assertEqual((result.cap, result.effective, result.unverified), ("EMERGING", "SETTLED", True))

    def test_contrasting_source_as_only_reason(self):
        result = one(primary3() + [src("c1", supports="contrasts")])
        self.assertEqual(result.reasons, ["contrasting_source"])
        self.assertEqual((result.cap, result.effective, result.unverified), ("CONTESTED", "CONTESTED", False))

    def test_contrasting_source_with_nothing_else(self):
        result = one([src("c1", supports="contrasts")])
        self.assertEqual(result.reasons, ["contrasting_source", "no_countable_sources", "lt2_primary"])
        self.assertEqual((result.cap_evidence, result.cap, result.effective), ("CONTESTED", "EMERGING", "CONTESTED"))
        self.assertTrue(result.unverified)

    def test_retracted_source_excluded_from_count(self):
        sources = primary3()
        sources[2]["reception"]["retracted"] = True
        result = one(sources)
        self.assertIn("retracted_source", result.reasons)
        self.assertIn("lt3_independent", result.reasons)
        self.assertEqual(len(gc.counted_sources(sources)), 2)

    def test_unretrieved_source_blocks_settled(self):
        sources = primary3()
        sources[1]["quote"] = None
        self.assertEqual(one(sources).reasons, ["unretrieved_source"])

    def test_asserted_contested_never_raised(self):
        result = one(primary3(), asserted="CONTESTED")
        self.assertEqual((result.cap, result.effective, result.unverified), ("SETTLED", "CONTESTED", False))

    def test_negate_claim_skipped(self):
        result = gc.evaluate_claim("hype.x", claim([], [grade("SETTLED")], polarity="negate"), True)
        self.assertTrue(result.skipped)
        self.assertEqual((result.grades[0].effective, result.grades[0].unverified), ("SETTLED", False))


class TestMarkers(unittest.TestCase):
    def test_rewrite_keeps_qualifier_and_sets_flag(self):
        line = "- **X.** `[SETTLED]` and `[VENDOR: Cognition]` `[UNVERIFIED]`, [Doc](https://e.com) `[VENDOR]`."
        rewritten = gc.rewrite_line(line, [("CONTESTED", True), ("VENDOR", False)])
        self.assertEqual(
            rewritten,
            "- **X.** `[CONTESTED]` `[UNVERIFIED]` and `[VENDOR: Cognition]`, [Doc](https://e.com) `[VENDOR]`.",
        )


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "research").mkdir()
        self.research = self.repo / "research" / "RESEARCH.md"
        self.sources = self.repo / "research" / "sources.yaml"
        self.claims_json = self.repo / "skills" / "marcus" / "references" / "claims.json"
        self.research.write_bytes(RESEARCH.encode("utf-8"))
        rl.dump_sources(sidecar(), self.sources)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args: str) -> tuple:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = gc.main(["--repo", str(self.repo), *args])
        return code, out.getvalue()


class TestWriteAndCheck(CliCase):
    def test_check_fails_before_write(self):
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("stale", out)

    def test_write_then_check_is_clean(self):
        code, out = self.run_cli("--write")
        self.assertEqual(code, 0, out)
        text = self.research.read_text(encoding="utf-8")
        self.assertIn("**Thin claim.** `[SETTLED]` `[UNVERIFIED]` and `[VENDOR: Cognition]` for", text)
        self.assertIn("<!-- claim:hype.negated --> `[SETTLED]` **Hype", text)
        self.assertIn("[Docs](https://example.com/a) `[VENDOR]`.", text)
        self.assertEqual(rl.strip_anchors(text).count("`[UNVERIFIED]`"), 1)
        code, out = self.run_cli("--check")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "OK: 3 claims, 4 grades, caps current (enforced=false)")

    def test_write_compiles_claims_json(self):
        self.run_cli("--write")
        compiled = json.loads(self.claims_json.read_text(encoding="utf-8"))
        self.assertEqual(compiled["schema"], gc.COMPILED_SCHEMA)
        self.assertEqual(compiled["research_version"], "1.3.0")
        self.assertEqual(compiled["research_sha256"], gc.sha256_bytes(self.research.read_bytes()))
        self.assertEqual(compiled["sources_sha256"], gc.sha256_bytes(self.sources.read_bytes()))
        self.assertEqual(compiled["counts"], {"SETTLED": 3, "CONTESTED": 0, "EMERGING": 0, "VENDOR": 1, "UNVERIFIED": 1})
        solid = compiled["claims"][0]
        self.assertEqual(solid["id"], "ctx.solid")
        self.assertEqual(solid["rules"], ["R-CTX-1"])
        self.assertEqual(compiled["rules"], [{"id": "R-CTX-1", "basis": None, "claims": ["ctx.solid"]}])

    def test_write_is_idempotent(self):
        self.run_cli("--write")
        first = (self.research.read_bytes(), self.sources.read_bytes(), self.claims_json.read_bytes())
        code, out = self.run_cli("--write")
        self.assertEqual(code, 0)
        self.assertIn("Wrote 0 change(s)", out)
        self.assertEqual(first, (self.research.read_bytes(), self.sources.read_bytes(), self.claims_json.read_bytes()))

    def test_check_detects_stale_caps(self):
        self.run_cli("--write")
        data = rl.load_sources(self.sources)
        data["claims"]["ctx.solid"]["sources"][0]["reception"]["checked"] = False
        rl.dump_sources(data, self.sources)
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("claim ctx.solid grade 0: stored cap fields are stale", out)
        self.assertIn("sources_sha256 is stale", out)

    def test_check_detects_marker_drift(self):
        self.run_cli("--write")
        text = self.research.read_text(encoding="utf-8")
        self.research.write_bytes(text.replace("`[SETTLED]` `[UNVERIFIED]`", "`[SETTLED]`").encode("utf-8"))
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("claim ctx.thin marker 0 is SETTLED, sidecar says SETTLED UNVERIFIED", out)
        self.assertIn("research_sha256 is stale", out)

    def test_check_reports_validation_errors(self):
        self.run_cli("--write")
        data = rl.load_sources(self.sources)
        del data["claims"]["ctx.solid"]
        rl.dump_sources(data, self.sources)
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("claim ctx.solid: anchored in RESEARCH.md but missing from sources.yaml", out)

    def test_check_warns_after_enforce_after(self):
        rl.dump_sources(sidecar(enforce_after="2000-01-01"), self.sources)
        self.run_cli("--write")
        code, out = self.run_cli("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: enforce_after 2000-01-01 has passed", out)

    def test_write_refuses_comments(self):
        self.sources.write_text(self.sources.read_text(encoding="utf-8") + "# note\n", encoding="utf-8")
        before = self.research.read_bytes()
        code, out = self.run_cli("--write")
        self.assertEqual(code, 1)
        self.assertIn("YAML comment not allowed", out)
        self.assertEqual(self.research.read_bytes(), before)

    def test_enforced_write_lowers_debt_grades(self):
        rl.dump_sources(sidecar(enforced=True), self.sources)
        self.run_cli("--write")
        self.assertIn("**Thin claim.** `[CONTESTED]` `[UNVERIFIED]` and", self.research.read_text(encoding="utf-8"))
        code, out = self.run_cli("--check")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.strip().endswith("(enforced=true)"))


class TestReports(CliCase):
    def test_stats(self):
        code, out = self.run_cli("--stats")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("SETTLED=3", lines)
        self.assertIn("SETTLED if enforced=2", lines)
        self.assertIn("UNVERIFIED=1", lines)
        self.assertIn("  lt3_independent=1", lines)
        self.assertIn("skipped_negate=1", lines)

    def test_debt_json_scores_and_sources(self):
        data = sidecar()
        data["claims"]["ctx.solid"]["sources"][0]["quote"] = None
        data["claims"]["ctx.solid"]["sources"].append(src("a9", "aggregator"))
        rl.dump_sources(data, self.sources)
        code, out = self.run_cli("--debt", "--json")
        self.assertEqual(code, 0)
        queue = json.loads(out)
        self.assertEqual([item["id"] for item in queue], ["ctx.solid", "ctx.thin"])
        self.assertEqual(queue[0]["score"], 3 + 2 + 1)
        self.assertEqual(queue[0]["sources"], {"s1": ["quote"], "a9": ["resolve"]})
        code, out = self.run_cli("--debt", "--limit", "1")
        self.assertEqual(len(out.splitlines()), 1)
        self.assertTrue(out.startswith("ctx.solid\tSETTLED→CONTESTED\t"))

    def test_changelog_row(self):
        rl.dump_sources(sidecar(enforced=True), self.sources)
        code, out = self.run_cli("--changelog-row", "--version", "1.3.0", "--by", "grade_cap", "--date", "2026-09-27")
        self.assertEqual(code, 0)
        self.assertEqual(
            out.strip(),
            "| 1.3.0 | 2026-09-27 | grade_cap | grade_cap: 1 grade lowered (ctx.thin#0 SETTLED→CONTESTED); "
            "1 flagged `[UNVERIFIED]`. |",
        )

    def test_debt_prints_arrows_through_a_pipe(self):
        script = Path(gc.__file__).resolve()
        proc = subprocess.run(
            [sys.executable, str(script), "--repo", str(self.repo), "--debt", "--limit", "1"],
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn("SETTLED→CONTESTED", proc.stdout.decode("utf-8"))

    def test_changelog_row_needs_version_and_by(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            gc.main(["--changelog-row", "--version", "1.3.0"])
        self.assertEqual(caught.exception.code, 2)


class TestChangelogCheck(unittest.TestCase):
    def test_prefix_rule(self):
        appended = RESEARCH + "| 1.2.0 | 2026-09-27 | grade_cap | More. |\n"
        self.assertEqual(gc.check_changelog(RESEARCH, appended), (True, "OK: changelog append-only (+1 rows)"))
        edited = RESEARCH.replace("Added things.", "Added other things.")
        ok, message = gc.check_changelog(RESEARCH, edited)
        self.assertFalse(ok)
        self.assertIn("row 2 was edited", message)


@unittest.skipUnless(shutil.which("git"), "git not found")
class TestCheckChangelogGit(CliCase):
    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
            cwd=self.repo,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        self.git("add", "research/RESEARCH.md")
        self.git("commit", "-q", "-m", "base")

    def test_appended_row_passes(self):
        self.research.write_bytes((RESEARCH + "| 1.2.0 | 2026-09-27 | grade_cap | More. |\n").encode("utf-8"))
        code, out = self.run_cli("--check-changelog", "--base", "HEAD")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "OK: changelog append-only (+1 rows)")

    def test_edited_old_row_rejected(self):
        self.research.write_bytes(RESEARCH.replace("Initial extract.", "Initial extract, edited.").encode("utf-8"))
        code, out = self.run_cli("--check-changelog", "--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertIn("row 1 was edited", out)


if __name__ == "__main__":
    unittest.main()
