#!/usr/bin/env python3
"""
test_update_marcus.py - Unit tests for skills/marcus/scripts/update_marcus.py.

Each subprocess test copies update_marcus.py into a temporary repo tree with a
stub gate suite, so no test touches the real Marcus skill.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "marcus" / "scripts" / "update_marcus.py"
CHECKER = REPO_ROOT / "scripts" / "research" / "check_rule_citations.py"

_spec = importlib.util.spec_from_file_location("update_marcus", SCRIPT)
um = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(um)

RESEARCH_TEXT = """---
version: 1.2.1
snapshot_date: 2026-09-06
---
# Research

`[SETTLED]` A rule.
"""

ARCH_TEXT = """---
version: 2.0.0
derived_from:
  - RESEARCH.md v{version} ({date}) snapshot_sha256:{sha}  # agentic engineering generally
---
# Architecture
"""

DESIGN_TEXT = """# Design

```yaml
version: 1.1.0
derived_from: RESEARCH.md v{research} · AGENT_ARCHITECTURE.md v{arch}
```
"""

RULE_OK = "\n**Rule I-1.** `[DESIGN]` Descriptions name activating situations.\n"
RULE_BAD = "\n**Rule I-1.** Descriptions name activating situations.\n"


SOURCES_TEXT = """schema: demiurge.sources.v1
meta:
  enforced: false
claims: {}
"""

COUNTS = {"SETTLED": 3, "CONTESTED": 1, "EMERGING": 2, "VENDOR": 1, "UNVERIFIED": 4}


def snapshot_of(research: bytes, sources: bytes) -> str:
    """snapshot_sha256 as grade_cap.py writes it: sha256 of "<research_sha256>\\n<sources_sha256>"."""
    joined = f"{hashlib.sha256(research).hexdigest()}\n{hashlib.sha256(sources).hexdigest()}"
    return hashlib.sha256(joined.encode("ascii")).hexdigest()


SNAPSHOT = snapshot_of(RESEARCH_TEXT.encode("utf-8"), SOURCES_TEXT.encode("utf-8"))


def compiled_claims(research: bytes, sources: bytes) -> str:
    """A claims.json whose hashes match the given RESEARCH.md and sources.yaml bytes."""
    data = {
        "schema": "demiurge.claims.compiled.v1",
        "research_version": "1.2.1",
        "sources_sha256": hashlib.sha256(sources).hexdigest(),
        "research_sha256": hashlib.sha256(research).hexdigest(),
        "snapshot_sha256": snapshot_of(research, sources),
        "enforced": False,
        "claims": [{"id": "ctx.one"}, {"id": "ctx.two"}],
        "rules": [],
        "counts": COUNTS,
    }
    return json.dumps(data, indent=2) + "\n"


class TempRepo:
    """A minimal repo tree: research/, skills/marcus/{scripts,references,evals}."""

    def __init__(
        self,
        root: Path,
        gate_stdout: str = "17/17 passing\n",
        arch_version: str = "1.2.1",
        arch_date: str = "2026-09-06",
        arch_sha: str = SNAPSHOT,
        arch_rules: str = "",
    ) -> None:
        self.root = root
        marcus = root / "skills" / "marcus"
        (root / "research").mkdir(parents=True)
        (marcus / "scripts").mkdir(parents=True)
        (marcus / "references").mkdir(parents=True)
        (marcus / "evals").mkdir(parents=True)
        shutil.copy2(SCRIPT, marcus / "scripts" / "update_marcus.py")
        (root / "research" / "RESEARCH.md").write_bytes(RESEARCH_TEXT.encode("utf-8"))
        (root / "research" / "sources.yaml").write_bytes(SOURCES_TEXT.encode("utf-8"))
        (marcus / "references" / "RESEARCH.md").write_bytes(RESEARCH_TEXT.encode("utf-8"))
        self.claims_json = marcus / "references" / "claims.json"
        self.claims_json.write_bytes(
            compiled_claims(RESEARCH_TEXT.encode("utf-8"), SOURCES_TEXT.encode("utf-8")).encode("utf-8")
        )
        self.arch = marcus / "AGENT_ARCHITECTURE.md"
        self.arch.write_text(
            ARCH_TEXT.format(version=arch_version, date=arch_date, sha=arch_sha) + arch_rules, encoding="utf-8"
        )
        (marcus / "evals" / "run_gate_tests.py").write_text(
            f"import sys\nsys.stdout.write({gate_stdout!r})\n", encoding="utf-8"
        )
        self.script = marcus / "scripts" / "update_marcus.py"

    def add_citation_checker(self) -> None:
        """Copy the real check_rule_citations.py into scripts/research/."""
        target = self.root / "scripts" / "research"
        target.mkdir(parents=True)
        shutil.copy2(CHECKER, target / "check_rule_citations.py")

    def add_design_doc(self, research: str, arch: str) -> None:
        (self.root / "docs").mkdir()
        (self.root / "docs" / "AGENT_DESIGN.md").write_text(
            DESIGN_TEXT.format(research=research, arch=arch), encoding="utf-8"
        )

    def run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=self.root,
        )


class TestGateSummary(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_gate_count_is_parsed(self):
        repo = TempRepo(self.tmp, gate_stdout="Running gates\n21/23 passing\n\nRegression suite intact.\n")
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS: Marcus gate regression suite (21/23 passing).", proc.stdout)

    def test_unparseable_gate_summary_fails(self):
        repo = TempRepo(self.tmp, gate_stdout="all good\n")
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("FAIL: could not parse gate-test summary", proc.stdout)
        self.assertNotIn("PASS: Marcus gate regression suite", proc.stdout)


class TestMarkerCount(unittest.TestCase):
    def test_vendor_variant_counted(self):
        text = "`[VENDOR: Anthropic]` claim one.\n`[VENDOR]` claim two.\n[SETTLED:partial] claim three.\n"
        counts = um.count_markers(text)
        self.assertEqual(counts["[VENDOR]"], 2)
        self.assertEqual(counts["[SETTLED]"], 1)

    def test_link_suffix_vendor_not_counted(self):
        text = (
            "`[SETTLED]` A rule. Source: [Docs](https://example.com/docs) `[VENDOR]`, "
            "[Spec](https://example.org/spec).\n"
            "- `[VENDOR]` A vendor-only claim.\n"
        )
        counts = um.count_markers(text)
        self.assertEqual(counts["[VENDOR]"], 1)
        self.assertEqual(counts["[SETTLED]"], 1)

    def test_changelog_markers_excluded(self):
        text = (
            "`[EMERGING]` A rule.\n\n"
            "## Change log\n\n"
            "| 1.0.0 | 2026-01-01 | Added `[EMERGING]` and `[SETTLED]` items. |\n"
        )
        counts = um.count_markers(text)
        self.assertEqual(counts["[EMERGING]"], 1)
        self.assertEqual(counts["[SETTLED]"], 0)


class TestApplyExitCode(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_apply_repins_version_drift(self):
        repo = TempRepo(self.tmp, arch_version="1.2.0")
        proc = repo.run("--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("APPLIED: Pinned AGENT_ARCHITECTURE.md derived_from to RESEARCH.md v1.2.1", proc.stdout)
        self.assertEqual(
            repo.arch.read_text(encoding="utf-8"),
            ARCH_TEXT.format(version="1.2.1", date="2026-09-06", sha=SNAPSHOT),
        )

    def test_apply_with_unpinnable_arch_drift_exits_1(self):
        repo = TempRepo(self.tmp)
        repo.arch.write_text(
            "---\nderived_from:\n  - RESEARCH.md v1.2.0 (2026-09-06)\n---\n# Architecture\n", encoding="utf-8"
        )
        proc = repo.run("--apply")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("RESULT:", proc.stdout)
        self.assertIn("Edit it by hand.", proc.stdout)

    def test_research_only_change_repins_after_regrade(self):
        """A sweep edits RESEARCH.md only; after grade_cap --write, --apply leaves --check clean."""
        repo = TempRepo(self.tmp)
        edited = RESEARCH_TEXT.replace("version: 1.2.1", "version: 1.2.2").replace(
            "snapshot_date: 2026-09-06", "snapshot_date: 2026-10-01"
        ) + "`[EMERGING]` Another rule.\n"
        research = edited.encode("utf-8")
        (self.tmp / "research" / "RESEARCH.md").write_bytes(research)
        repo.claims_json.write_bytes(compiled_claims(research, SOURCES_TEXT.encode("utf-8")).encode("utf-8"))
        before = repo.run("--check")
        self.assertEqual(before.returncode, 1, before.stdout + before.stderr)
        apply = repo.run("--apply")
        self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
        self.assertEqual(
            (self.tmp / "skills" / "marcus" / "references" / "RESEARCH.md").read_bytes(), research
        )
        expected_sha = snapshot_of(research, SOURCES_TEXT.encode("utf-8"))
        self.assertIn(f"RESEARCH.md v1.2.2 (2026-10-01) snapshot_sha256:{expected_sha}", repo.arch.read_text(encoding="utf-8"))
        after = repo.run("--check")
        self.assertEqual(after.returncode, 0, after.stdout + after.stderr)

    def test_apply_does_not_repin_against_stale_claims(self):
        repo = TempRepo(self.tmp, arch_version="1.2.0")
        (self.tmp / "research" / "sources.yaml").write_bytes(SOURCES_TEXT.replace("false", "true").encode("utf-8"))
        before = repo.arch.read_text(encoding="utf-8")
        proc = repo.run("--apply")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertNotIn("APPLIED: Pinned", proc.stdout)
        self.assertEqual(repo.arch.read_text(encoding="utf-8"), before)

    def test_repin_keeps_indent_and_comment(self):
        text = ARCH_TEXT.format(version="1.0.0", date="2026-01-01", sha="b" * 64)
        pinned = um.repin_derived_from(text, "1.3.2", "2026-10-01", "c" * 64)
        self.assertEqual(pinned, ARCH_TEXT.format(version="1.3.2", date="2026-10-01", sha="c" * 64))
        unpinned = "derived_from:\n  - RESEARCH.md v1.0.0 (2026-01-01)\n"
        self.assertIsNone(um.repin_derived_from(unpinned, "1", "d", "e"))


class TestClaimsJson(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_counts_from_claims_json(self):
        repo = TempRepo(self.tmp)
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(
            "CLAIMS: 2 claims from claims.json (SETTLED 3, CONTESTED 1, EMERGING 2, VENDOR 1, UNVERIFIED 4).",
            proc.stdout,
        )
        self.assertIn("SYNCED: claims.json hashes match", proc.stdout)
        self.assertNotIn("DRIFT", proc.stdout)

    def test_claims_json_stale_is_drift(self):
        repo = TempRepo(self.tmp)
        (self.tmp / "research" / "sources.yaml").write_bytes(SOURCES_TEXT.replace("false", "true").encode("utf-8"))
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("DRIFT: claims.json sources_sha256 does not match sources.yaml", proc.stdout)
        self.assertNotIn("research_sha256 does not match", proc.stdout)
        apply = repo.run("--apply")
        self.assertEqual(apply.returncode, 1, apply.stdout + apply.stderr)
        self.assertIn("Regrade with grade_cap.py --write.", apply.stdout)

    def test_research_edit_is_drift(self):
        repo = TempRepo(self.tmp)
        edited = (RESEARCH_TEXT + "`[EMERGING]` Another rule.\n").encode("utf-8")
        (self.tmp / "research" / "RESEARCH.md").write_bytes(edited)
        (self.tmp / "skills" / "marcus" / "references" / "RESEARCH.md").write_bytes(edited)
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("DRIFT: claims.json research_sha256 does not match RESEARCH.md", proc.stdout)

    def test_missing_claims_json_is_drift(self):
        repo = TempRepo(self.tmp)
        repo.claims_json.unlink()
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("DRIFT: claims.json is missing", proc.stdout)


    def test_inconsistent_snapshot_sha_is_drift(self):
        repo = TempRepo(self.tmp)
        data = json.loads(repo.claims_json.read_text(encoding="utf-8"))
        data["snapshot_sha256"] = "0" * 64
        repo.claims_json.write_text(json.dumps(data), encoding="utf-8")
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(
            "DRIFT: claims.json snapshot_sha256 does not match research_sha256 and sources_sha256", proc.stdout
        )


class TestDerivedSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_matching_snapshot_is_synced(self):
        repo = TempRepo(self.tmp)
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("SYNCED: AGENT_ARCHITECTURE.md snapshot_sha256 matches claims.json (2026-09-06).", proc.stdout)

    def test_wrong_hash_is_drift(self):
        repo = TempRepo(self.tmp, arch_sha="a" * 64)
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("DRIFT: AGENT_ARCHITECTURE.md derived_from snapshot_sha256 does not match claims.json.", proc.stdout)
        self.assertIn(f"Expected: RESEARCH.md v1.2.1 (2026-09-06) snapshot_sha256:{SNAPSHOT}", proc.stdout)
        apply = repo.run("--apply")
        self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
        self.assertIn(f"snapshot_sha256:{SNAPSHOT}", repo.arch.read_text(encoding="utf-8"))

    def test_wrong_date_is_drift(self):
        repo = TempRepo(self.tmp, arch_date="2026-09-01")
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("derived_from date 2026-09-01 does not match snapshot_date 2026-09-06", proc.stdout)

    def test_missing_hash_is_drift(self):
        repo = TempRepo(self.tmp)
        repo.arch.write_text(
            "---\nderived_from:\n  - RESEARCH.md v1.2.1 (2026-09-06)\n---\n# Architecture\n", encoding="utf-8"
        )
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("DRIFT: AGENT_ARCHITECTURE.md derived_from has no", proc.stdout)


class TestRuleCitations(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_checker_absent_is_skipped(self):
        repo = TempRepo(self.tmp)
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("Rule citations", proc.stdout)

    def test_valid_citations_pass(self):
        repo = TempRepo(self.tmp, arch_rules=RULE_OK)
        repo.add_citation_checker()
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS: Rule citations (OK: 1 rules, 0 violations).", proc.stdout)

    def test_missing_token_is_drift(self):
        repo = TempRepo(self.tmp, arch_rules=RULE_BAD)
        repo.add_citation_checker()
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("DRIFT: check_rule_citations.py exited 1:", proc.stdout)
        self.assertIn("ERROR: I-1: no citation token", proc.stdout)
        apply = repo.run("--apply")
        self.assertEqual(apply.returncode, 1, apply.stdout + apply.stderr)
        self.assertIn("Fix the tokens by hand.", apply.stdout)


class TestDesignDocWarning(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_lagging_design_doc_warns_without_drift(self):
        repo = TempRepo(self.tmp)
        repo.add_design_doc("1.1.0", "1.1.0")
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("WARNING: AGENT_DESIGN.md derived_from is RESEARCH.md v1.1.0, but RESEARCH.md is v1.2.1.", proc.stdout)
        self.assertIn(
            "WARNING: AGENT_DESIGN.md derived_from is AGENT_ARCHITECTURE.md v1.1.0, but AGENT_ARCHITECTURE.md is v2.0.0.",
            proc.stdout,
        )
        self.assertNotIn("DRIFT", proc.stdout)

    def test_current_design_doc_is_quiet(self):
        repo = TempRepo(self.tmp)
        repo.add_design_doc("1.2.1", "2.0.0")
        proc = repo.run("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("WARNING", proc.stdout)


if __name__ == "__main__":
    unittest.main()
