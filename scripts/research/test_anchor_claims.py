#!/usr/bin/env python3
"""
test_anchor_claims.py - Unit tests for anchor_claims.py (claim anchor bootstrap).
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Optional

import anchor_claims as ac
import research_lib as rl

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_RESEARCH = FIXTURES / "anchor_claims_research.txt"
FIXTURE_IDMAP = FIXTURES / "anchor_claims_idmap.tsv"
SED_STRIP = r"s/<!-- (claim|rule):[^>]* --> //"
STRIP_RE = re.compile(r"<!-- (claim|rule):[^>]* --> ")


def resolve_bash() -> Optional[str]:
    """DEMIURGE_BASH, then Git for Windows bash beside git, then PATH; WSL bash is refused."""
    candidates = [os.environ.get("DEMIURGE_BASH")]
    git = shutil.which("git")
    if git:
        git_root = Path(git).resolve().parent.parent
        candidates.append(str(git_root / "bin" / "bash.exe"))
    candidates.append(shutil.which("bash"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            if "system32" in str(Path(candidate)).lower():
                return None
            return candidate
    return None


def run_main(*args: str):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ac.main(list(args))
    return code, out.getvalue(), err.getvalue()


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.text = FIXTURE_RESEARCH.read_bytes().decode("utf-8")
        self.rows = ac.parse_idmap(FIXTURE_IDMAP.read_text(encoding="utf-8"))
        self.plan = ac.build_plan(self.text, self.rows)
        self.claims = self.plan.sidecar["claims"]


class TestPlanOnFixture(FixtureCase):
    def test_stripping_anchors_restores_fixture_bytes(self):
        self.assertEqual(STRIP_RE.sub("", self.plan.anchored_text), self.text)
        self.assertEqual(rl.strip_anchors(self.plan.anchored_text), self.text)

    def test_found_equals_assigned(self):
        self.assertEqual(self.plan.markers_found, 10)
        self.assertEqual(self.plan.markers_assigned, 10)
        self.assertEqual(self.plan.stats_line(), "markers_found=10 markers_assigned=10 claims=8 rules=1")

    def test_sidecar_validates(self):
        self.assertEqual(self.plan.errors, [])
        self.assertEqual(rl.validate(self.plan.sidecar, self.plan.anchored_text), [])

    def test_two_grades_on_one_line_with_scopes(self):
        grades = self.claims["disc.framing"]["grades"]
        self.assertEqual([(g["asserted"], g["scope"]) for g in grades],
                         [("SETTLED", "a framing"), ("EMERGING", "a codified practice")])
        self.assertTrue(all(g["cap"] is None and g["cap_reasons"] == [] for g in grades))

    def test_link_suffix_vendor_is_a_source_tag(self):
        claim = self.claims["ctx.cache-thrashing"]
        self.assertEqual([g["asserted"] for g in claim["grades"]], ["SETTLED"])
        self.assertEqual([(s["id"], s["type"]) for s in claim["sources"]], [("s1", "vendor"), ("s2", "preprint")])
        self.assertEqual(claim["sources"][0]["title"], "Docs")

    def test_scoped_vendor(self):
        claim = self.claims["eval.frontiercode"]
        self.assertEqual(claim["kind"], "bullet")
        self.assertEqual([(g["asserted"], g["scope"]) for g in claim["grades"]], [("VENDOR", "exact scores")])
        self.assertEqual(claim["sources"][0]["type"], "vendor")

    def test_qualified_vendor_is_a_grade(self):
        grades = self.claims["fail.compound"]["grades"]
        self.assertEqual([(g["asserted"], g["scope"]) for g in grades], [("VENDOR", None), ("SETTLED", "framing")])

    def test_table_cell_grade(self):
        claim = self.claims["proto.mcp"]
        self.assertEqual(claim["kind"], "table_row")
        self.assertEqual(claim["section"], 2)
        self.assertEqual(claim["sources"][0]["type"], "spec")
        self.assertIn("| <!-- claim:proto.mcp --> **MCP** `[SETTLED]` |", self.plan.anchored_text)

    def test_header_claim_uses_idmap_kind(self):
        self.assertEqual(self.claims["eval.new-benchmarks"]["kind"], "header")
        self.assertIn("### <!-- claim:eval.new-benchmarks --> New benchmarks", self.plan.anchored_text)

    def test_blockquote_anchor_after_quote_marker(self):
        self.assertIn("> <!-- claim:multi.single-writer --> **Blockquote claim.**", self.plan.anchored_text)
        self.assertEqual(self.claims["multi.single-writer"]["kind"], "prose")

    def test_bullet_anchor_after_list_marker(self):
        self.assertIn("- <!-- claim:eval.frontiercode --> **FrontierCode**", self.plan.anchored_text)

    def test_multi_line_rule(self):
        parsed = rl.parse_research(self.plan.anchored_text)
        rule = parsed.rule_map()["R-CTX-1"]
        self.assertEqual((rule.line_no, rule.end_line_no), (36, 37))
        self.assertEqual(self.plan.sidecar["rules"], {"R-CTX-1": {"section": 2, "basis": None, "claims": []}})

    def test_fence_legend_and_changelog_untouched(self):
        lines = self.plan.anchored_text.split("\n")
        self.assertEqual(lines[39:41], ["# not a heading", "`[SETTLED]` inside a fence"])
        self.assertEqual(lines[10], "| `[SETTLED]` | Three sources | Encode as default. |")
        self.assertEqual(lines[51], "| 1.0.0 | 2026-08-30 | Extraction | Initial `[SETTLED]` extract. |")

    def test_unmapped_line_gets_default_id_and_hype_is_negate(self):
        claim = self.claims["sec.s3-l46"]
        self.assertEqual(claim["polarity"], "negate")
        self.assertEqual([s["type"] for s in claim["sources"]], ["peer", "preprint"])
        self.assertEqual(self.plan.defaulted_count, 1)
        self.assertEqual(self.claims["disc.framing"]["polarity"], "affirm")

    def test_skeleton_fields(self):
        claim = self.claims["ctx.cache-thrashing"]
        self.assertEqual(list(claim), ["section", "kind", "population", "polarity", "grades", "sources",
                                       "duplicates", "last_verified", "verified_by", "notes"])
        source = claim["sources"][1]
        self.assertEqual(source["reception"], {"checked": False, "retracted": None,
                                               "scite_supporting": None, "scite_contrasting": None})
        self.assertIsNone(source["quote"])
        self.assertEqual(self.plan.sidecar["meta"], {"enforced": False, "enforce_after": None})


class TestSedStrip(FixtureCase):
    def test_sed_strip_gives_fixture_byte_for_byte(self):
        bash = resolve_bash()
        if bash is None:
            self.skipTest("bash not found (WSL bash refused)")
        with tempfile.TemporaryDirectory() as tmp:
            anchored = Path(tmp) / "anchored.md"
            anchored.write_bytes(self.plan.anchored_text.encode("utf-8"))
            result = subprocess.run(
                [bash, "-c", 'sed -E "$1" "$2"', "strip", SED_STRIP, anchored.as_posix()],
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, FIXTURE_RESEARCH.read_bytes())


class TestIdmapAndRefusals(unittest.TestCase):
    TEXT = FIXTURE_RESEARCH.read_bytes().decode("utf-8")

    def test_idmap_rejects_bad_rows(self):
        bad = {
            "16\tNotAnId\n": "does not match",
            "16\ta.b\n16\tc.d\n": "already mapped",
            "16\ta.b\n18\ta.b\n": "already mapped",
            "x\ta.b\n": "positive integer",
            "16\ta.b\tpara\n": "kind",
            "16\n": "expected",
        }
        for text, message in bad.items():
            with self.subTest(text=text):
                with self.assertRaisesRegex(ac.UsageError, message):
                    ac.parse_idmap(text)

    def test_idmap_skips_comments_and_header(self):
        self.assertEqual(ac.parse_idmap("line\tid\n# note\n\n16\ta.b\n"), [(16, "a.b", None)])

    def test_line_past_end_is_usage_error(self):
        with self.assertRaisesRegex(ac.UsageError, "past the end"):
            ac.build_plan(self.TEXT, [(999, "a.b", None)])

    def test_already_anchored_file_is_refused(self):
        with self.assertRaisesRegex(ac.UsageError, "already carries"):
            ac.build_plan("<!-- claim:a.b --> `[SETTLED]` x\n", [])

    def test_rule_on_graded_line_leaves_marker_unassigned(self):
        plan = ac.build_plan(self.TEXT, [(16, "R-DISC-1", None)])
        self.assertEqual((plan.markers_found, plan.markers_assigned), (10, 8))

    def test_claim_inside_fence_is_an_error(self):
        plan = ac.build_plan(self.TEXT, [(41, "fence.claim", None)])
        self.assertTrue(any("fence" in error for error in plan.errors), plan.errors)

    def test_classify_url(self):
        cases = {
            "https://consensus.app/papers/details/x/": "aggregator",
            "https://arxiv.org/abs/2601.00001": "preprint",
            "https://doi.org/10.48550/arxiv.2606.12344": "preprint",
            "https://doi.org/10.1145/1234567": "peer",
            "https://docs.anthropic.com/en/docs": "vendor",
            "https://www.cursor.com/blog": "vendor",
            "https://aaif.io/": "spec",
            "https://lilianweng.github.io/posts/x/": "practitioner",
            "https://unknown.example/post": "practitioner",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(ac.classify_url(url), expected)


class TestMain(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.research = self.tmp / "RESEARCH.md"
        self.research.write_bytes(FIXTURE_RESEARCH.read_bytes())
        self.idmap = self.tmp / "idmap.tsv"
        self.idmap.write_bytes(FIXTURE_IDMAP.read_bytes())
        self.sources = self.tmp / "sources.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    def args(self, *extra: str):
        return ("--research", str(self.research), "--idmap", str(self.idmap), *extra)

    def test_stats_clean(self):
        code, out, _ = run_main(*self.args("--stats"))
        self.assertEqual(code, 0)
        self.assertIn("markers_found=10 markers_assigned=10 claims=8 rules=1", out)
        self.assertFalse(self.sources.exists())

    def test_stats_mismatch_exits_1(self):
        self.idmap.write_text("16\tR-DISC-1\n", encoding="utf-8")
        code, out, _ = run_main(*self.args("--stats"))
        self.assertEqual(code, 1)
        self.assertIn("markers_found=10 markers_assigned=8", out)

    def test_dry_run_writes_nothing(self):
        code, out, _ = run_main(*self.args())
        self.assertEqual(code, 0)
        self.assertIn("eval.frontiercode", out)
        self.assertEqual(self.research.read_bytes(), FIXTURE_RESEARCH.read_bytes())

    def test_write_produces_valid_pair(self):
        code, _, err = run_main(*self.args("--write"))
        self.assertEqual(code, 0, err)
        anchored = self.research.read_bytes().decode("utf-8")
        self.assertEqual(STRIP_RE.sub("", anchored).encode("utf-8"), FIXTURE_RESEARCH.read_bytes())
        sidecar_text = self.sources.read_text(encoding="utf-8")
        self.assertEqual(rl.check_no_comments(sidecar_text), [])
        self.assertEqual(rl.validate(rl.load_sources(self.sources), anchored), [])

    def test_second_write_is_refused(self):
        self.assertEqual(run_main(*self.args("--write"))[0], 0)
        code, _, err = run_main(*self.args("--write", "--force"))
        self.assertEqual(code, 2)
        self.assertIn("already carries", err)

    def test_existing_sidecar_needs_force(self):
        self.sources.write_text("schema: old\n", encoding="utf-8")
        code, _, err = run_main(*self.args("--write"))
        self.assertEqual(code, 2)
        self.assertIn("--force", err)
        self.assertEqual(self.research.read_bytes(), FIXTURE_RESEARCH.read_bytes())
        code, _, err = run_main(*self.args("--write", "--force"))
        self.assertEqual(code, 0, err)

    def test_force_refuses_tracked_dirty_sidecar(self):
        if shutil.which("git") is None:
            self.skipTest("git not found")
        self.sources.write_text("schema: old\n", encoding="utf-8")
        git = ["git", "-C", str(self.tmp), "-c", "user.name=test", "-c", "user.email=test@example.com",
               "-c", "commit.gpgsign=false"]
        subprocess.run(git + ["init", "-q"], check=True, capture_output=True)
        subprocess.run(git + ["add", "sources.yaml"], check=True, capture_output=True)
        subprocess.run(git + ["commit", "-q", "-m", "seed"], check=True, capture_output=True)
        self.sources.write_text("schema: edited\n", encoding="utf-8")
        code, _, err = run_main(*self.args("--write", "--force"))
        self.assertEqual(code, 2)
        self.assertIn("uncommitted", err)
        subprocess.run(git + ["checkout", "--", "sources.yaml"], check=True, capture_output=True)
        code, _, err = run_main(*self.args("--write", "--force"))
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
