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
derived_from:
  - RESEARCH.md v{version} (2026-09-06)
---
# Architecture
"""


SOURCES_TEXT = """schema: demiurge.sources.v1
meta:
  enforced: false
claims: {}
"""

COUNTS = {"SETTLED": 3, "CONTESTED": 1, "EMERGING": 2, "VENDOR": 1, "UNVERIFIED": 4}


def compiled_claims(research: bytes, sources: bytes) -> str:
    """A claims.json whose hashes match the given RESEARCH.md and sources.yaml bytes."""
    data = {
        "schema": "demiurge.claims.compiled.v1",
        "research_version": "1.2.1",
        "sources_sha256": hashlib.sha256(sources).hexdigest(),
        "research_sha256": hashlib.sha256(research).hexdigest(),
        "enforced": False,
        "claims": [{"id": "ctx.one"}, {"id": "ctx.two"}],
        "rules": [],
        "counts": COUNTS,
    }
    return json.dumps(data, indent=2) + "\n"


class TempRepo:
    """A minimal repo tree: research/, skills/marcus/{scripts,references,evals}."""

    def __init__(self, root: Path, gate_stdout: str = "17/17 passing\n", arch_version: str = "1.2.1") -> None:
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
        (marcus / "AGENT_ARCHITECTURE.md").write_text(ARCH_TEXT.format(version=arch_version), encoding="utf-8")
        (marcus / "evals" / "run_gate_tests.py").write_text(
            f"import sys\nsys.stdout.write({gate_stdout!r})\n", encoding="utf-8"
        )
        self.script = marcus / "scripts" / "update_marcus.py"

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

    def test_apply_with_arch_drift_exits_1(self):
        repo = TempRepo(self.tmp, arch_version="1.2.0")
        proc = repo.run("--apply")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("RESULT:", proc.stdout)
        self.assertIn("Edit it by hand.", proc.stdout)


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


if __name__ == "__main__":
    unittest.main()
