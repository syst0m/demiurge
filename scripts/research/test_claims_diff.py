#!/usr/bin/env python3
"""
test_claims_diff.py - Unit tests for claims_diff.py (grade-change classification).

Each test builds a temp git repo with a base commit and a head commit (or a
working-tree edit) and checks the class, the exit code and the report.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import claims_diff as cd
import research_lib as rl

SCRIPT = Path(__file__).resolve().parent / "claims_diff.py"

RESEARCH = """# RESEARCH.md

```yaml
version: 1.3.0
```

## 2. Context Engineering

<!-- claim:ctx.solid --> `[SETTLED]` **Solid claim.**

<!-- claim:ctx.thin --> `[EMERGING]` **Thin claim.**

<!-- claim:ctx.gone --> `[CONTESTED]` **Claim that a PR may drop.**

<!-- rule:R-CTX-1 --> *Marcus Rule:* Use append-only files.

## Change log

| Version | Date | By | Change |
|---|---|---|---|
| 1.0.0 | 2026-08-30 | Extraction | Initial extract. |
"""

HEADINGS = (
    "## New findings",
    "## Reclassifications",
    "## Contradictions",
    "## Retractions",
    "## Unchanged",
    "## Marcus rule consequences",
)


def src(source_id: str, type_: str = "peer", **overrides) -> dict:
    """A fully retrieved, reception-checked confirming source in its own group."""
    base = {
        "id": source_id,
        "url": "https://example.com/" + source_id,
        "title": "Title",
        "type": type_,
        "resolves_to": None,
        "resolves_to_type": None,
        "independence_group": "g-" + source_id,
        "supports": "confirms",
        "quote": "a short quote",
        "accessed": "2026-09-20",
        "reception": {"checked": True, "retracted": False, "scite_supporting": None, "scite_contrasting": None},
    }
    base.update(overrides)
    return base


def primary3() -> list:
    return [src("s1"), src("s2", "preprint"), src("s3", "spec")]


def claim(sources: list, asserted: str) -> dict:
    return {
        "section": 2,
        "kind": "prose",
        "population": "any",
        "polarity": "affirm",
        "grades": [{"scope": None, "asserted": asserted}],
        "sources": sources,
        "duplicates": [],
        "last_verified": None,
        "verified_by": None,
        "notes": "",
    }


def sidecar(enforced: bool = False) -> dict:
    return {
        "schema": rl.SOURCES_SCHEMA,
        "meta": {"enforced": enforced, "enforce_after": None},
        "claims": {
            "ctx.solid": claim(primary3(), "SETTLED"),
            "ctx.thin": claim([], "EMERGING"),
            "ctx.gone": claim([src("c1"), src("c2")], "CONTESTED"),
        },
        "rules": {"R-CTX-1": {"section": 2, "basis": "evidence", "claims": ["ctx.solid", "ctx.thin"]}},
    }


def add_claim(research: str, cid: str, marker: str) -> str:
    return research.replace(
        "<!-- rule:R-CTX-1 -->", f"<!-- claim:{cid} --> `[{marker}]` **Another claim.**\n\n<!-- rule:R-CTX-1 -->"
    )


@unittest.skipUnless(shutil.which("git"), "git not found")
class DiffCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "research").mkdir()
        self.git("init", "-q")
        self.write(RESEARCH, sidecar())
        self.commit("base")
        self.git("tag", "base")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
            cwd=self.repo,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def write(self, research: str, sources: dict) -> None:
        (self.repo / "research" / "RESEARCH.md").write_bytes(research.encode("utf-8"))
        rl.dump_sources(sources, self.repo / "research" / "sources.yaml")

    def touch(self, rel: str, text: str = "x\n") -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str = "head") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def commit_empty(self):
        self.git("commit", "-q", "--allow-empty", "-m", "empty")

    def run_cli(self, *args: str, head: str = "HEAD"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cd.main(["--repo", str(self.repo), "--base", "base", "--head", head, *args])
        return code, out.getvalue()

    def diff(self, head: str = "HEAD"):
        code, out = self.run_cli("--json", head=head)
        return code, json.loads(out)

    def claim_entry(self, diff: dict, cid: str) -> dict:
        return next(c for c in diff["claims"] if c["id"] == cid)


class TestClasses(DiffCase):
    def test_no_change_is_downgrade_or_sourcing(self):
        self.commit_empty()
        code, diff = self.diff()
        self.assertEqual(code, 0)
        self.assertEqual(diff["class"], cd.DOWNGRADE_OR_SOURCING)
        self.assertEqual({c["status"] for c in diff["claims"]}, {"unchanged"})
        self.assertFalse(diff["tooling_changed"])

    def test_contrasting_source_is_a_downgrade(self):
        sources = sidecar()
        sources["claims"]["ctx.solid"]["sources"].append(src("x1", supports="contrasts"))
        self.write(RESEARCH, sources)
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, 0)
        self.assertEqual(diff["class"], cd.DOWNGRADE_OR_SOURCING)
        entry = self.claim_entry(diff, "ctx.solid")
        self.assertEqual(entry["new_contrasting"], ["x1"])
        self.assertEqual(entry["grade_moves"][0]["direction"], "down")
        self.assertEqual(entry["head"]["grades"][0]["effective"], "CONTESTED")

    def test_sourcing_only_is_not_an_upgrade(self):
        sources = sidecar()
        sources["claims"]["ctx.thin"]["sources"].append(src("t1", "practitioner"))
        self.write(RESEARCH, sources)
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, 0)
        self.assertEqual(self.claim_entry(diff, "ctx.thin")["sources_added"], ["t1"])

    def test_asserted_rise_is_an_upgrade(self):
        sources = sidecar()
        sources["claims"]["ctx.thin"] = claim(primary3(), "SETTLED")
        self.write(RESEARCH.replace("`[EMERGING]` **Thin", "`[SETTLED]` **Thin"), sources)
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, cd.EXIT_UPGRADE)
        self.assertEqual(diff["class"], cd.UPGRADE)
        self.assertEqual(diff["upgraded_claims"], ["ctx.thin"])
        entry = self.claim_entry(diff, "ctx.thin")
        self.assertIn("grade 0 asserted EMERGING→SETTLED", entry["upgrade_reasons"])
        self.assertEqual(diff["needs_verification"], [{"id": "ctx.thin", "claim_sha256": entry["head"]["claim_sha256"]}])

    def test_stored_caps_are_ignored(self):
        sources = sidecar()
        sources["claims"]["ctx.solid"]["sources"].append(src("x1", supports="contrasts"))
        self.write(RESEARCH, sources)
        self.commit()
        self.git("tag", "-f", "base")
        sources = copy.deepcopy(sources)
        sources["claims"]["ctx.solid"]["sources"].pop()
        sources["claims"]["ctx.solid"]["grades"][0]["cap"] = "CONTESTED"
        self.write(RESEARCH, sources)
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, cd.EXIT_UPGRADE)
        self.assertIn("grade 0 effective CONTESTED→SETTLED", self.claim_entry(diff, "ctx.solid")["upgrade_reasons"])

    def test_new_claim_at_contested_is_an_upgrade(self):
        sources = sidecar()
        sources["claims"]["ctx.new"] = claim([src("n1", supports="contrasts")], "CONTESTED")
        self.write(add_claim(RESEARCH, "ctx.new", "CONTESTED"), sources)
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, cd.EXIT_UPGRADE)
        self.assertEqual(diff["new_claims"], ["ctx.new"])
        self.assertEqual([item["id"] for item in diff["needs_verification"]], ["ctx.new"])

    def test_new_claim_at_emerging_is_not_an_upgrade(self):
        sources = sidecar()
        sources["claims"]["ctx.new"] = claim([], "EMERGING")
        self.write(add_claim(RESEARCH, "ctx.new", "EMERGING"), sources)
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, 0)
        self.assertEqual(diff["new_claims"], ["ctx.new"])
        self.assertEqual([item["id"] for item in diff["needs_verification"]], ["ctx.new"])

    def test_removed_claim_is_an_upgrade(self):
        sources = sidecar()
        del sources["claims"]["ctx.gone"]
        self.write(RESEARCH.replace("<!-- claim:ctx.gone --> `[CONTESTED]` **Claim that a PR may drop.**\n\n", ""), sources)
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, cd.EXIT_UPGRADE)
        self.assertEqual(diff["removed_claims"], ["ctx.gone"])
        self.assertIn("ctx.gone: claim removed", diff["upgrade_reasons"])

    def test_enforced_flip_to_false_is_an_upgrade(self):
        self.write(RESEARCH, sidecar(enforced=True))
        self.commit()
        self.git("tag", "-f", "base")
        self.write(RESEARCH, sidecar(enforced=False))
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, cd.EXIT_UPGRADE)
        self.assertEqual(diff["enforced"], {"base": True, "head": False})
        self.assertIn("meta.enforced true→false", diff["upgrade_reasons"])

    def test_enforced_flip_to_true_is_not_an_upgrade(self):
        self.write(RESEARCH, sidecar(enforced=True))
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, 0)
        self.assertEqual(diff["enforced"], {"base": False, "head": True})

    def test_tooling_change_is_an_upgrade(self):
        for rel in ("scripts/research/grade_cap.py", ".github/workflows/research-pr.yml"):
            with self.subTest(rel=rel):
                self.git("reset", "-q", "--hard", "base")
                self.touch(rel)
                self.commit()
                code, diff = self.diff()
                self.assertEqual(code, cd.EXIT_UPGRADE)
                self.assertTrue(diff["tooling_changed"])
                self.assertEqual(diff["out_of_scope_paths"], [rel])

    def test_other_paths_are_reported_but_not_tooling(self):
        self.touch("docs/NOTE.md")
        self.commit()
        code, diff = self.diff()
        self.assertEqual(code, 0)
        self.assertFalse(diff["tooling_changed"])
        self.assertEqual(diff["out_of_scope_paths"], ["docs/NOTE.md"])

    def test_worktree_head_reads_uncommitted_edits(self):
        sources = sidecar()
        sources["claims"]["ctx.thin"] = claim(primary3(), "SETTLED")
        self.write(RESEARCH.replace("`[EMERGING]` **Thin", "`[SETTLED]` **Thin"), sources)
        self.touch("scripts/research/new_tool.py")
        code, diff = self.diff(head=cd.WORKTREE)
        self.assertEqual(code, cd.EXIT_UPGRADE)
        self.assertEqual(diff["upgraded_claims"], ["ctx.thin"])
        self.assertTrue(diff["tooling_changed"])
        self.assertIn("scripts/research/new_tool.py", diff["changed_paths"])

    def test_bad_ref_is_an_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, _ = self.run_cli("--json", head="no-such-ref")
        self.assertEqual(code, 1)
        self.assertIn("ERROR:", err.getvalue())


class TestMarkdown(DiffCase):
    def test_headings_and_sections(self):
        sources = sidecar()
        sources["claims"]["ctx.solid"]["sources"].append(src("x1", supports="contrasts"))
        sources["claims"]["ctx.gone"]["sources"][0]["reception"]["retracted"] = True
        sources["claims"]["ctx.new"] = claim([], "EMERGING")
        self.write(add_claim(RESEARCH, "ctx.new", "EMERGING"), sources)
        self.commit()
        code, out = self.run_cli("--markdown")
        self.assertEqual(code, 0, out)
        positions = [out.index(heading) for heading in HEADINGS]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("- `ctx.new` (section 2): EMERGING", out)
        self.assertIn("- `ctx.solid`: grade 0: SETTLED/SETTLED → SETTLED/CONTESTED (down)", out)
        self.assertIn("- `ctx.solid`: new contrasting source(s) x1", out)
        self.assertIn("- `ctx.gone`: retracted source(s) c1", out)
        self.assertIn("1 claim(s) unchanged.", out)
        self.assertIn("- `R-CTX-1` (changed): floor EMERGING → EMERGING; moved claims `ctx.solid`", out)

    def test_markdown_is_the_default(self):
        self.commit_empty()
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        for heading in HEADINGS:
            self.assertIn(heading, out)
        self.assertEqual(out.count("None."), 5)

    def test_rule_floor_moves_with_its_claims(self):
        sources = sidecar()
        sources["rules"]["R-CTX-1"]["claims"] = ["ctx.solid"]
        self.write(RESEARCH, sources)
        self.commit()
        code, out = self.run_cli("--markdown")
        self.assertEqual(code, 0)
        self.assertIn("- `R-CTX-1` (changed): floor EMERGING → SETTLED; citations edited", out)


class TestExitCode(DiffCase):
    def test_process_exits_10_on_upgrade(self):
        self.touch(".github/workflows/x.yml")
        self.commit()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repo), "--base", "base", "--head", "HEAD", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(proc.returncode, 10, proc.stderr.decode("utf-8", "replace"))
        self.assertTrue(json.loads(proc.stdout.decode("utf-8"))["tooling_changed"])


if __name__ == "__main__":
    unittest.main()
