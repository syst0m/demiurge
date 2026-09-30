#!/usr/bin/env python3
"""
test_research_lib.py - Unit tests for research_lib.py (claims ledger parsing and validation).
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import research_lib as rl

RESEARCH = """# RESEARCH.md

```yaml
version: 1.3.0
```

| Marker | Criteria | Marcus Rule |
|---|---|---|
| `[SETTLED]` | Three sources | Encode as default. |
| `[VENDOR]` | Source sells it | Do not encode. |

## 2. Context Engineering

<!-- claim:ctx.cache-thrashing --> `[SETTLED]` **Cache thrashing.** Source: [Docs](https://example.com/a) `[VENDOR]`, [Spec](https://example.com/b).

- <!-- claim:eval.frontiercode --> **FrontierCode** scores 30-50%. `[VENDOR]` for exact scores.

| Practice | Core Idea |
|---|---|
| <!-- claim:ctx.budget --> **Budget** `[EMERGING]` | Quality drops. |

<!-- claim:fail.compound --> `[VENDOR: Cognition]` **Errors compound.** `[SETTLED]` `[UNVERIFIED]` as framing.

<!-- rule:R-CTX-1 --> *Marcus Rule:* Use append-only files.
Never regenerate wholesale.

```text
# not a heading
`[SETTLED]` inside a fence
```

## Change log

| Version | Date | By | Change |
|---|---|---|---|
| 1.0.0 | 2026-08-30 | Extraction | Initial `[SETTLED]` extract. |
| 1.1.0 | 2026-09-01 | Buckminster | Added things. |
"""


def grade(asserted: str) -> dict:
    return {"scope": None, "asserted": asserted, "cap": None, "cap_evidence": None, "unverified": False, "cap_reasons": []}


def source(source_id: str, **overrides) -> dict:
    base = {
        "id": source_id,
        "url": "https://example.com/" + source_id,
        "title": "Title",
        "type": "peer",
        "resolves_to": None,
        "resolves_to_type": None,
        "independence_group": None,
        "supports": "confirms",
        "quote": None,
        "accessed": None,
        "reception": {"checked": False, "retracted": None, "scite_supporting": None, "scite_contrasting": None},
    }
    base.update(overrides)
    return base


def claim(section: int, grades: list, kind: str = "prose") -> dict:
    return {
        "section": section,
        "kind": kind,
        "population": "any",
        "polarity": "affirm",
        "grades": grades,
        "sources": [source("s1")],
        "duplicates": [],
        "last_verified": None,
        "verified_by": None,
        "notes": "",
    }


def valid_sources() -> dict:
    return {
        "schema": rl.SOURCES_SCHEMA,
        "meta": {"enforced": False, "enforce_after": None},
        "claims": {
            "ctx.cache-thrashing": claim(2, [grade("SETTLED")]),
            "eval.frontiercode": claim(4, [grade("VENDOR")], kind="bullet"),
            "ctx.budget": claim(2, [grade("EMERGING")], kind="table_row"),
            "fail.compound": claim(5, [grade("VENDOR"), grade("SETTLED")]),
        },
        "rules": {"R-CTX-1": {"section": 2, "basis": "evidence", "claims": ["ctx.cache-thrashing"]}},
    }


class TestParseResearch(unittest.TestCase):
    def setUp(self):
        self.parsed = rl.parse_research(RESEARCH)
        self.claims = self.parsed.claim_map()

    def test_finds_all_anchor_forms(self):
        self.assertEqual(
            [c.id for c in self.parsed.claims],
            ["ctx.cache-thrashing", "eval.frontiercode", "ctx.budget", "fail.compound"],
        )

    def test_link_suffix_vendor_is_a_source_tag(self):
        markers = self.claims["ctx.cache-thrashing"].markers
        self.assertEqual([m.grade for m in markers], ["SETTLED"])

    def test_scoped_vendor_is_a_grade(self):
        self.assertEqual([m.grade for m in self.claims["eval.frontiercode"].markers], ["VENDOR"])

    def test_two_markers_qualifier_and_unverified_flag(self):
        markers = self.claims["fail.compound"].markers
        self.assertEqual([(m.grade, m.qualifier, m.unverified) for m in markers],
                         [("VENDOR", "Cognition", False), ("SETTLED", None, True)])

    def test_table_cell_marker(self):
        self.assertEqual([m.grade for m in self.claims["ctx.budget"].markers], ["EMERGING"])

    def test_legend_changelog_and_fence_skipped(self):
        self.assertEqual(self.parsed.unanchored_marker_lines, [])

    def test_changelog_rows(self):
        self.assertEqual(len(self.parsed.changelog_rows), 2)
        self.assertTrue(self.parsed.changelog_rows[0].startswith("| 1.0.0 |"))
        self.assertTrue(self.parsed.changelog_rows[1].startswith("| 1.1.0 |"))

    def test_multi_line_rule_runs_to_blank_line(self):
        (rule,) = self.parsed.rules
        self.assertEqual(rule.id, "R-CTX-1")
        self.assertEqual(rule.end_line_no, rule.line_no + 1)
        self.assertIn("Never regenerate wholesale.", rule.text)

    def test_rule_ends_at_next_rule_anchor(self):
        text = RESEARCH.replace(
            "Never regenerate wholesale.\n",
            "Never regenerate wholesale.\n- <!-- rule:R-CTX-2 --> *R-CTX-2:* Keep a scratchpad.\n",
        )
        first, second = rl.parse_research(text).rules
        self.assertEqual((first.id, second.id), ("R-CTX-1", "R-CTX-2"))
        self.assertEqual(first.end_line_no, first.line_no + 1)
        self.assertNotIn("R-CTX-2", first.text)
        self.assertEqual(second.line_no, first.end_line_no + 1)

    def test_unanchored_marker_line_reported(self):
        text = RESEARCH.replace("<!-- claim:ctx.budget --> ", "")
        parsed = rl.parse_research(text)
        self.assertEqual(len(parsed.unanchored_marker_lines), 1)
        line = text.split("\n")[parsed.unanchored_marker_lines[0] - 1]
        self.assertIn("**Budget**", line)

    def test_strip_anchors(self):
        stripped = rl.strip_anchors(RESEARCH)
        self.assertNotIn("<!--", stripped)
        self.assertIn("\n`[SETTLED]` **Cache thrashing.**", stripped)
        self.assertIn("| **Budget** `[EMERGING]` |", stripped)


class TestValidate(unittest.TestCase):
    def test_valid_pair_is_clean(self):
        self.assertEqual(rl.validate(valid_sources(), RESEARCH), [])

    def test_accepts_parsed_research(self):
        self.assertEqual(rl.validate(valid_sources(), rl.parse_research(RESEARCH)), [])

    def test_missing_sidecar_entry(self):
        sources = valid_sources()
        del sources["claims"]["ctx.budget"]
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any("ctx.budget" in e and "missing from sources.yaml" in e for e in errors))

    def test_sidecar_entry_without_anchor(self):
        sources = valid_sources()
        sources["claims"]["mem.extra"] = claim(3, [])
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any("mem.extra" in e and "not anchored" in e for e in errors))

    def test_rule_bijection(self):
        sources = valid_sources()
        sources["rules"] = {"R-MEM-2": {"section": 3, "basis": "design", "claims": []}}
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any("R-CTX-1" in e for e in errors))
        self.assertTrue(any("R-MEM-2" in e for e in errors))

    def test_grade_count_must_match_markers(self):
        sources = valid_sources()
        sources["claims"]["fail.compound"]["grades"] = [grade("VENDOR")]
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any("fail.compound" in e and "1 grades" in e and "2 markers" in e for e in errors))

    def test_bad_ids(self):
        text = RESEARCH.replace("claim:ctx.budget", "claim:Ctx_Budget").replace("rule:R-CTX-1", "rule:r-ctx-1")
        sources = valid_sources()
        sources["claims"]["Ctx_Budget"] = sources["claims"].pop("ctx.budget")
        sources["rules"] = {"r-ctx-1": {"section": 2, "basis": "design", "claims": []}}
        errors = rl.validate(sources, text)
        self.assertTrue(any("Ctx_Budget" in e and "does not match" in e for e in errors))
        self.assertTrue(any("r-ctx-1" in e and "does not match" in e for e in errors))

    def test_duplicate_anchor(self):
        text = RESEARCH.replace("claim:ctx.budget", "claim:ctx.cache-thrashing")
        sources = valid_sources()
        del sources["claims"]["ctx.budget"]
        errors = rl.validate(sources, text)
        self.assertTrue(any("anchored 2 times" in e for e in errors))

    def test_unanchored_marker_is_an_error(self):
        text = RESEARCH + "\n`[EMERGING]` A new claim with no anchor.\n"
        errors = rl.validate(valid_sources(), text)
        self.assertTrue(any("without a claim anchor" in e for e in errors))

    def test_enum_values(self):
        sources = valid_sources()
        entry = sources["claims"]["ctx.budget"]
        entry["kind"] = "paragraph"
        entry["polarity"] = "maybe"
        entry["grades"][0]["asserted"] = "PROVEN"
        entry["grades"][0]["cap_reasons"] = ["made_up"]
        entry["sources"][0]["type"] = "blog"
        entry["sources"][0]["supports"] = "agrees"
        sources["rules"]["R-CTX-1"]["basis"] = "vibes"
        errors = "\n".join(rl.validate(sources, RESEARCH))
        for token in ("paragraph", "maybe", "PROVEN", "made_up", "blog", "agrees", "vibes"):
            self.assertIn(repr(token), errors)

    def test_rule_basis_must_be_set(self):
        sources = valid_sources()
        sources["rules"]["R-CTX-1"]["basis"] = None
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any("R-CTX-1" in e and "basis None" in e for e in errors))
        self.assertEqual(rl.validate(sources, RESEARCH, allow_unset_basis=True), [])

    def test_evidence_rule_needs_a_claim(self):
        sources = valid_sources()
        sources["rules"]["R-CTX-1"]["claims"] = []
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any("R-CTX-1" in e and "cites no claim" in e for e in errors))

    def test_design_rule_needs_no_claim(self):
        sources = valid_sources()
        sources["rules"]["R-CTX-1"] = {"section": 2, "basis": "design", "claims": []}
        self.assertEqual(rl.validate(sources, RESEARCH), [])

    def test_quote_word_limit(self):
        sources = valid_sources()
        sources["claims"]["ctx.budget"]["sources"][0]["quote"] = " ".join(["word"] * 25)
        self.assertEqual(rl.validate(sources, RESEARCH), [])
        sources["claims"]["ctx.budget"]["sources"][0]["quote"] = " ".join(["word"] * 26)
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any("26 words" in e for e in errors))

    def test_unknown_references(self):
        sources = valid_sources()
        sources["claims"]["ctx.budget"]["duplicates"] = ["ctx.nowhere"]
        sources["rules"]["R-CTX-1"]["claims"] = ["ctx.missing"]
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any("ctx.nowhere" in e for e in errors))
        self.assertTrue(any("ctx.missing" in e for e in errors))

    def test_schema_and_meta(self):
        sources = valid_sources()
        sources["schema"] = "other"
        sources["meta"] = {"enforced": "no"}
        errors = rl.validate(sources, RESEARCH)
        self.assertTrue(any(e.startswith("schema") for e in errors))
        self.assertTrue(any("meta.enforced" in e for e in errors))


class TestCheckNoComments(unittest.TestCase):
    def test_clean_yaml_with_hash_in_scalars(self):
        text = (
            "schema: demiurge.sources.v1\n"
            "claims:\n"
            "  a.b:\n"
            "    url: https://example.com/page#frag\n"
            "    title: \"C# notes\"\n"
            "    notes: 'issue #4'\n"
            "    body: |\n"
            "      line with # inside\n"
        )
        self.assertEqual(rl.check_no_comments(text), [])

    def test_trailing_comment_rejected(self):
        text = "schema: demiurge.sources.v1  # the schema\nmeta: {}\n"
        errors = rl.check_no_comments(text)
        self.assertEqual(len(errors), 1)
        self.assertIn("line 1", errors[0])

    def test_full_line_comment_rejected(self):
        text = "schema: demiurge.sources.v1\n# a note\nmeta: {}\n"
        errors = rl.check_no_comments(text)
        self.assertEqual(len(errors), 1)
        self.assertIn("line 2", errors[0])


class TestSourcesIO(unittest.TestCase):
    def test_round_trip_is_stable_and_comment_free(self):
        data = valid_sources()
        data["claims"]["ctx.budget"]["notes"] = "Weng — résumé #1"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yaml"
            first = rl.dump_sources(data, path)
            loaded = rl.load_sources(path)
            self.assertEqual(loaded, data)
            self.assertEqual(rl.dump_sources(loaded), first)
            self.assertEqual(rl.check_no_comments(first), [])
            self.assertIn("résumé", path.read_text(encoding="utf-8"))
            self.assertEqual(list(loaded), ["schema", "meta", "claims", "rules"])

    def test_non_mapping_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yaml"
            path.write_text("- a\n- b\n", encoding="utf-8")
            with self.assertRaises(rl.SourcesError):
                rl.load_sources(path)


class TestHashingAndGrades(unittest.TestCase):
    def test_claim_sha_ignores_markers_anchor_whitespace_and_volatile_fields(self):
        sources_a = [source("s1")]
        sources_b = copy.deepcopy(sources_a)
        sources_b[0]["quote"] = "a verbatim quote"
        sources_b[0]["accessed"] = "2026-09-27"
        sources_b[0]["reception"]["checked"] = True
        line_a = "<!-- claim:x.y --> `[SETTLED]` **Claim**  text."
        line_b = "`[CONTESTED]` `[UNVERIFIED]` **Claim** text."
        self.assertEqual(rl.claim_sha256("x.y", line_a, sources_a), rl.claim_sha256("x.y", line_b, sources_b))

    def test_claim_sha_changes_with_text_sources_or_id(self):
        base = rl.claim_sha256("x.y", "`[SETTLED]` Claim.", [source("s1")])
        self.assertNotEqual(base, rl.claim_sha256("x.y", "`[SETTLED]` Claim changed.", [source("s1")]))
        self.assertNotEqual(base, rl.claim_sha256("x.y", "`[SETTLED]` Claim.", [source("s1", type="vendor")]))
        self.assertNotEqual(base, rl.claim_sha256("x.z", "`[SETTLED]` Claim.", [source("s1")]))

    def test_claim_sha_keeps_source_tags(self):
        with_tag = rl.canonical_line("`[SETTLED]` See [Doc](https://example.com) `[VENDOR]`.")
        self.assertEqual(with_tag, "See [Doc](https://example.com) `[VENDOR]`.")

    def test_grade_rank_and_lower_grade(self):
        self.assertEqual([g for g in sorted(rl.GRADE_RANK, key=rl.GRADE_RANK.get, reverse=True)],
                         ["SETTLED", "CONTESTED", "EMERGING", "VENDOR"])
        self.assertEqual(rl.lower_grade("SETTLED", "EMERGING"), "EMERGING")
        self.assertEqual(rl.lower_grade("VENDOR", "SETTLED"), "VENDOR")
        self.assertEqual(rl.lower_grade("CONTESTED", "CONTESTED"), "CONTESTED")


if __name__ == "__main__":
    unittest.main()
