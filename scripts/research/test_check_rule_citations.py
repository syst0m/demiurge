#!/usr/bin/env python3
"""
test_check_rule_citations.py - Unit tests for check_rule_citations.py.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import check_rule_citations as crc

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

CLAIMS = {
    "schema": "demiurge.claims.compiled.v1",
    "enforced": False,
    "claims": [
        {"id": "ctx.solid", "section": 2, "grades": [
            {"scope": None, "asserted": "SETTLED", "effective": "SETTLED", "unverified": True}]},
        {"id": "ctx.split", "section": 2, "grades": [
            {"scope": "a", "asserted": "SETTLED", "effective": "SETTLED", "unverified": False},
            {"scope": "b", "asserted": "EMERGING", "effective": "EMERGING", "unverified": False}]},
        {"id": "ma.contested", "section": 7, "grades": [
            {"scope": None, "asserted": "CONTESTED", "effective": "CONTESTED", "unverified": False}]},
        {"id": "fail.vendor", "section": 5, "grades": [
            {"scope": None, "asserted": "VENDOR", "effective": "VENDOR", "unverified": False}]},
    ],
}


def arch(*rules: str) -> str:
    """A minimal AGENT_ARCHITECTURE.md holding the given rule lines."""
    body = "\n\n".join(rules)
    return f"# AGENT_ARCHITECTURE.md\n\n## 2. Layers\n\n`[SETTLED §2]` Section intro.\n\n{body}\n\n## 3. Next\n"


def violations(text: str) -> list:
    return crc.check(text, CLAIMS)[2]


class ParseTokenTests(unittest.TestCase):
    def test_design(self) -> None:
        self.assertEqual(crc.parse_token("DESIGN").kind, "design")

    def test_multi_section_claims_token(self) -> None:
        token = crc.parse_token("SETTLED §2,§7 · ctx.solid, ma.contested")
        self.assertEqual(token.kind, "claims")
        self.assertEqual(token.grade, "SETTLED")
        self.assertEqual(token.sections, [2, 7])
        self.assertEqual(token.claims, ["ctx.solid", "ma.contested"])

    def test_evidence_token(self) -> None:
        token = crc.parse_token("CONTESTED EVIDENCE §1,§3")
        self.assertEqual((token.kind, token.grade, token.sections), ("evidence", "CONTESTED", [1, 3]))

    def test_bare_grade_is_malformed(self) -> None:
        self.assertIsNone(crc.parse_token("SETTLED §2"))
        self.assertIsNone(crc.parse_token("SETTLED §2 · "))


class CheckTests(unittest.TestCase):
    def test_valid_rules_pass(self) -> None:
        text = arch(
            "**Rule K-1.** `[SETTLED §2 · ctx.solid]` Load triggers.",
            "**Rule T-1.** `[CONTESTED §2,§7 · ctx.solid, ma.contested]` Default single-agent.",
            "**Rule G-1.** `[CONTESTED EVIDENCE §1]` Three failures.",
        )
        rules, tokens, errors = crc.check(text, CLAIMS)
        self.assertEqual(errors, [])
        self.assertEqual([rule.rule_id for rule in rules], ["K-1", "T-1", "G-1"])
        self.assertEqual(set(tokens), {"K-1", "T-1", "G-1"})

    def test_design_accepted_for_any_rule(self) -> None:
        self.assertEqual(violations(arch("**Rule C-5.** `[DESIGN]` Dump first.",
                                         "**Rule G-11.** `[DESIGN]` Reject thin claims.")), [])

    def test_missing_claim_id(self) -> None:
        errors = violations(arch("**Rule K-1.** `[SETTLED §2 · ctx.absent]` Load triggers."))
        self.assertTrue(any("unknown claim id ctx.absent" in error for error in errors), errors)

    def test_grade_above_ledger(self) -> None:
        errors = violations(arch("**Rule T-1.** `[SETTLED §7 · ma.contested]` Default single-agent."))
        self.assertTrue(any("above the ledger minimum CONTESTED" in error for error in errors), errors)

    def test_scoped_claim_uses_lowest_grade(self) -> None:
        errors = violations(arch("**Rule K-1.** `[SETTLED §2 · ctx.split]` Load triggers."))
        self.assertTrue(any("ledger minimum EMERGING" in error for error in errors), errors)
        self.assertEqual(violations(arch("**Rule K-1.** `[EMERGING §2 · ctx.split]` Load triggers.")), [])

    def test_lower_cited_grade_is_allowed(self) -> None:
        self.assertEqual(violations(arch("**Rule K-1.** `[CONTESTED §2 · ctx.solid]` Load triggers.")), [])

    def test_g_rule_without_evidence_fails(self) -> None:
        errors = violations(arch("**Rule G-6.** `[SETTLED §2 · ctx.solid]` Check collisions."))
        self.assertTrue(any("G-rules cite EVIDENCE.md" in error for error in errors), errors)

    def test_evidence_form_rejected_outside_g_rules(self) -> None:
        errors = violations(arch("**Rule V-2.** `[SETTLED EVIDENCE §4]` Start small."))
        self.assertTrue(any("EVIDENCE tokens are for G-rules" in error for error in errors), errors)

    def test_vendor_grade_rejected(self) -> None:
        errors = violations(arch("**Rule C-4.** `[VENDOR §5 · fail.vendor]` Guard writes."))
        self.assertTrue(any("nothing derives from [VENDOR]" in error for error in errors), errors)

    def test_section_must_match_cited_claims(self) -> None:
        errors = violations(arch("**Rule K-1.** `[SETTLED §3 · ctx.solid]` Load triggers."))
        self.assertTrue(any("ctx.solid is in §2" in error for error in errors), errors)
        self.assertTrue(any("§3 is listed but no cited claim" in error for error in errors), errors)

    def test_missing_token(self) -> None:
        errors = violations(arch("**Rule I-2.** Descriptions state what they do not cover."))
        self.assertEqual(errors, ["I-2: no citation token"])

    def test_old_style_token_is_malformed(self) -> None:
        errors = violations(arch("**Rule V-2.** `[SETTLED §2]` Start small."))
        self.assertEqual(errors, ["V-2: malformed token [SETTLED §2]"])

    def test_two_tokens_on_one_rule(self) -> None:
        text = arch("**Rule K-2.** `[SETTLED §2 · ctx.solid]` Append-only.\n`[SETTLED]` Rewrites degrade.")
        self.assertEqual(violations(text), ["K-2: 2 citation tokens, expected exactly one"])

    def test_rule_text_spans_continuation_lines(self) -> None:
        text = arch("**Rule V-1.** Ships evals, split:\n\n- regression\n- capability `[SETTLED §2 · ctx.solid]`")
        self.assertEqual(violations(text), [])

    def test_section_intro_is_not_a_rule_token(self) -> None:
        rules = crc.find_rules(arch("**Rule K-1.** `[SETTLED §2 · ctx.solid]` Load triggers."))
        self.assertEqual(len(rules), 1)
        self.assertNotIn("Section intro", rules[0].text)

    def test_duplicate_rule_id(self) -> None:
        errors = violations(arch("**Rule C-5.** `[DESIGN]` One.", "**Rule C-5.** `[DESIGN]` Two."))
        self.assertTrue(any("C-5: defined at lines" in error for error in errors), errors)


class ReportTests(unittest.TestCase):
    def test_report_lists_unverified_claims(self) -> None:
        text = arch("**Rule K-1.** `[SETTLED §2 · ctx.solid]` Load triggers.",
                    "**Rule C-5.** `[DESIGN]` Dump first.")
        rules, tokens, _ = crc.check(text, CLAIMS)
        lines = crc.report_lines(rules, tokens, CLAIMS)
        self.assertEqual(lines[0], "enforced=false")
        self.assertIn("K-1\tSETTLED\tledger=SETTLED\tunverified=ctx.solid", lines[1])
        self.assertEqual(lines[2], "C-5\tDESIGN")


class MainTests(unittest.TestCase):
    def run_main(self, argv: list) -> tuple:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = crc.main(argv)
        return code, out.getvalue()

    def write_inputs(self, root: Path, text: str) -> list:
        (root / "arch.md").write_text(text, encoding="utf-8")
        (root / "claims.json").write_text(json.dumps(CLAIMS), encoding="utf-8")
        return ["--repo", str(root), "--arch", "arch.md", "--claims", "claims.json"]

    def test_ok_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            argv = self.write_inputs(Path(tmp), arch("**Rule C-5.** `[DESIGN]` Dump first."))
            code, out = self.run_main(argv)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "OK: 1 rules, 0 violations")

    def test_violation_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            argv = self.write_inputs(Path(tmp), arch("**Rule C-5.** Dump first."))
            code, out = self.run_main(argv)
        self.assertEqual(code, 1)
        self.assertIn("ERROR: C-5: no citation token", out)
        self.assertIn("FAIL: 1 rules, 1 violations", out)

    def test_missing_claims_file_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_main(["--repo", tmp, "--arch", "arch.md", "--claims", "absent.json"])
        self.assertEqual(code, 2)
        self.assertIn("not found", out)

    def test_repo_architecture_passes(self) -> None:
        code, out = self.run_main(["--repo", str(REPO_ROOT)])
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "OK: 38 rules, 0 violations")


if __name__ == "__main__":
    unittest.main()
