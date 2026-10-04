#!/usr/bin/env python3
"""
test_check_verifications.py - Unit tests for check_verifications.py.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

import check_verifications as cv
import research_lib as rl

SHA_A = "a" * 64
SHA_B = "b" * 64
SESSION = "c" * 64


def src(source_id: str, stype: str = "peer", **overrides) -> dict:
    base = {
        "id": source_id,
        "url": f"https://example.org/{source_id}",
        "title": source_id,
        "type": stype,
        "resolves_to": None,
        "resolves_to_type": None,
        "independence_group": f"g-{source_id}",
        "supports": "confirms",
        "quote": "a short quote",
        "accessed": "2026-09-20",
        "reception": {"checked": True, "retracted": False, "scite_supporting": None, "scite_contrasting": None},
    }
    base.update(overrides)
    return base


def claim(sources: list) -> dict:
    return {
        "section": 2,
        "kind": "prose",
        "population": "any",
        "polarity": "affirm",
        "grades": [{"scope": None, "asserted": "SETTLED"}],
        "sources": sources,
        "duplicates": [],
        "last_verified": None,
        "verified_by": None,
        "notes": "",
    }


def sidecar() -> dict:
    return {
        "schema": rl.SOURCES_SCHEMA,
        "meta": {"enforced": False, "enforce_after": None},
        "claims": {
            "ctx.up": claim([
                src("s1"),
                src("s2", "preprint"),
                src("s3", "spec"),
                src("agg", "aggregator"),
                src("m1", supports="mentions"),
            ]),
            "ctx.new": claim([src("n1")]),
            "ctx.down": claim([src("d1")]),
        },
        "rules": {},
    }


def compiled() -> dict:
    return {
        "schema": "demiurge.claims.compiled.v1",
        "claims": [
            {"id": "ctx.up", "claim_sha256": SHA_A},
            {"id": "ctx.new", "claim_sha256": SHA_B},
            {"id": "ctx.down", "claim_sha256": "d" * 64},
        ],
    }


def record_source(source_id: str, **overrides) -> dict:
    base = {
        "id": source_id,
        "url": f"https://example.org/{source_id}",
        "url_resolves": True,
        "quote_found": True,
        "reception": {"checked": True, "retracted": False},
        "independence_group_confirmed": True,
    }
    base.update(overrides)
    return base


def record(claim_id: str, claim_sha: str, source_ids: list) -> dict:
    return {
        "claim_id": claim_id,
        "claim_sha256": claim_sha,
        "verdict": "pass",
        "proposer": "research-sweep",
        "verifier": "research-verifier",
        "verifier_session_sha256": SESSION,
        "sources": [record_source(s) for s in source_ids],
        "notes": "",
    }


DIFF = {
    "schema": "demiurge.claims_diff.v1",
    "class": "upgrade",
    "tooling_changed": False,
    "upgraded_claims": ["ctx.up"],
    "new_claims": ["ctx.new"],
    "removed_claims": ["ctx.gone"],
    "needs_verification": [{"id": "ctx.up", "claim_sha256": SHA_A}, {"id": "ctx.new", "claim_sha256": SHA_B}],
    "claims": [
        {"id": "ctx.up", "status": "changed", "upgrade": True},
        {"id": "ctx.new", "status": "new", "upgrade": True},
        {"id": "ctx.down", "status": "changed", "upgrade": False},
        {"id": "ctx.gone", "status": "removed", "upgrade": True},
    ],
}


class Fixture:
    """A temp repo with claims.json, sources.yaml, a diff and passing records."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.claims_path = root / "skills/marcus/references/claims.json"
        self.claims_path.parent.mkdir(parents=True)
        self.claims_path.write_text(json.dumps(compiled()), encoding="utf-8")
        (root / "research").mkdir()
        rl.dump_sources(sidecar(), root / "research/sources.yaml")
        self.dir = root / "research/verifications"
        self.diff_path = root / "diff.json"
        self.write_diff(DIFF)
        self.write_record(record("ctx.up", SHA_A, ["s1", "s2", "s3"]))
        self.write_record(record("ctx.new", SHA_B, ["n1"]))

    def write_diff(self, diff: dict) -> None:
        self.diff_path.write_text(json.dumps(diff), encoding="utf-8")

    def record_file(self, claim_id: str, claim_sha: str) -> Path:
        return cv.record_path(self.dir, claim_id, claim_sha)

    def write_record(self, data: dict) -> None:
        path = self.record_file(data["claim_id"], data["claim_sha256"])
        path.parent.mkdir(parents=True, exist_ok=True)
        rl.dump_sources(data, path)

    def edit_record(self, claim_id: str, claim_sha: str, edit) -> None:
        path = self.record_file(claim_id, claim_sha)
        data = rl.yaml.safe_load(path.read_text(encoding="utf-8"))
        edit(data)
        rl.dump_sources(data, path)

    def run(self) -> tuple:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cv.main([
                "--repo", str(self.root),
                "--diff", str(self.diff_path),
                "--claims", "skills/marcus/references/claims.json",
                "--dir", "research/verifications",
            ])
        return code, out.getvalue()


class ClaimsToVerifyTests(unittest.TestCase):
    def test_needs_verification_carries_hashes(self):
        self.assertEqual(cv.claims_to_verify(DIFF), [("ctx.up", SHA_A), ("ctx.new", SHA_B)])

    def test_falls_back_to_id_lists(self):
        diff = {"upgraded_claims": ["ctx.up"], "new_claims": ["ctx.new", "ctx.up"]}
        self.assertEqual(cv.claims_to_verify(diff), [("ctx.up", None), ("ctx.new", None)])

    def test_falls_back_to_claim_entries(self):
        diff = {"claims": DIFF["claims"]}
        self.assertEqual(cv.claims_to_verify(diff), [("ctx.up", None), ("ctx.new", None)])

    def test_unknown_shape_fails_closed(self):
        with self.assertRaises(cv.InputError):
            cv.claims_to_verify({"class": "upgrade"})

    def test_entry_without_id_rejected(self):
        with self.assertRaises(cv.InputError):
            cv.claims_to_verify({"needs_verification": [{"claim_sha256": SHA_A}]})

    def test_non_list_rejected(self):
        with self.assertRaises(cv.InputError):
            cv.claims_to_verify({"needs_verification": "ctx.up"})


class CheckRecordTests(unittest.TestCase):
    def setUp(self):
        self.counted = [src("s1"), src("s2", "preprint")]
        self.good = record("ctx.up", SHA_A, ["s1", "s2"])

    def problems(self, data) -> list:
        return cv.check_record("ctx.up", data, SHA_A, self.counted)

    def test_passing_record(self):
        self.assertEqual(self.problems(self.good), [])

    def test_verifier_equals_proposer(self):
        self.good["verifier"] = " Research-Sweep "
        self.assertTrue(any("is the proposer" in p for p in self.problems(self.good)))

    def test_bad_session_hash(self):
        self.good["verifier_session_sha256"] = "session-42"
        self.assertTrue(any("verifier_session_sha256" in p for p in self.problems(self.good)))

    def test_each_source_flag_required(self):
        for flag in ("url_resolves", "quote_found", "independence_group_confirmed"):
            with self.subTest(flag=flag):
                data = copy.deepcopy(self.good)
                data["sources"][1][flag] = False
                self.assertEqual(self.problems(data), [f"source s2: {flag} is not true"])

    def test_reception_checked_required(self):
        self.good["sources"][0]["reception"] = {"checked": False}
        self.assertEqual(self.problems(self.good), ["source s1: reception.checked is not true"])

    def test_source_matched_by_url_when_id_absent(self):
        del self.good["sources"][0]["id"]
        self.assertEqual(self.problems(self.good), [])

    def test_url_mismatch(self):
        self.good["sources"][0]["url"] = "https://example.org/other"
        self.assertTrue(any("differs from sources.yaml" in p for p in self.problems(self.good)))

    def test_claim_id_mismatch(self):
        self.good["claim_id"] = "ctx.other"
        self.assertTrue(any("claim_id" in p for p in self.problems(self.good)))

    def test_not_a_mapping(self):
        self.assertEqual(self.problems(["x"]), ["record is not a mapping"])


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_records_pass(self):
        code, out = self.fx.run()
        self.assertEqual(code, 0, out)
        self.assertIn("OK: 2 upgraded or new claim(s) verified", out)

    def test_missing_record(self):
        self.fx.record_file("ctx.new", SHA_B).unlink()
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("ctx.new: no verification record at research/verifications/ctx.new/bbbbbbbbbbbb.yaml", out)

    def test_stale_record_for_old_content(self):
        stale = record("ctx.up", "e" * 64, ["s1", "s2", "s3"])
        self.fx.record_file("ctx.up", SHA_A).unlink()
        self.fx.write_record(stale)
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("ctx.up: no verification record", out)

    def test_sha_mismatch_inside_record(self):
        self.fx.edit_record("ctx.up", SHA_A, lambda d: d.update(claim_sha256=SHA_A[:-1] + "f"))
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("claim_sha256", out)

    def test_verdict_fail(self):
        self.fx.edit_record("ctx.new", SHA_B, lambda d: d.update(verdict="fail"))
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("ctx.new: verdict is 'fail'", out)

    def test_self_verification(self):
        self.fx.edit_record("ctx.up", SHA_A, lambda d: d.update(verifier=d["proposer"]))
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("is the proposer", out)

    def test_counted_source_missing(self):
        self.fx.edit_record("ctx.up", SHA_A, lambda d: d.update(sources=d["sources"][:2]))
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("ctx.up: source s3: counted source missing from the record", out)

    def test_uncounted_sources_not_required(self):
        code, out = self.fx.run()
        self.assertEqual(code, 0, out)
        self.assertNotIn("agg", out)
        self.assertNotIn("m1", out)

    def test_claim_missing_from_claims_json(self):
        self.fx.write_diff({"needs_verification": [{"id": "ctx.ghost"}]})
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("ctx.ghost: not in claims.json", out)

    def test_no_upgrades_passes(self):
        self.fx.write_diff(dict(DIFF, **{"class": "downgrade-or-sourcing", "needs_verification": []}))
        code, out = self.fx.run()
        self.assertEqual(code, 0, out)
        self.assertIn("OK: 0 upgraded", out)

    def test_unrecognized_diff_is_usage_error(self):
        self.fx.write_diff({"class": "upgrade"})
        code, out = self.fx.run()
        self.assertEqual(code, 2)
        self.assertIn("no claim list found", out)

    def test_diff_hash_disagrees_with_claims_json(self):
        diff = dict(DIFF, needs_verification=[{"id": "ctx.up", "claim_sha256": "f" * 64}])
        self.fx.write_diff(diff)
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("ctx.up: diff claim_sha256", out)

    def test_missing_diff_file(self):
        self.fx.diff_path.unlink()
        code, out = self.fx.run()
        self.assertEqual(code, 2)
        self.assertIn("not found", out)

    def test_invalid_record_yaml(self):
        self.fx.record_file("ctx.new", SHA_B).write_text("verdict: [pass\n", encoding="utf-8")
        code, out = self.fx.run()
        self.assertEqual(code, 1)
        self.assertIn("is not valid YAML", out)


if __name__ == "__main__":
    unittest.main()
