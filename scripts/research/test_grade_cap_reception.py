"""test_grade_cap_reception.py - Unit tests for reception recording in grade_cap --write."""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import grade_cap as gc
import research_lib as rl
import reception

RESEARCH = """# RESEARCH.md

```yaml
version: 1.3.0
snapshot_date: 2026-09-20
maintained_by: niccolo
```

## 2. Context Engineering

<!-- claim:ctx.reception --> **Reception claim.** `[SETTLED]` **[VENDOR: Example]**.

## Change log

|| Version | Date | By | Change ||
||---|---|---|---|---||
|| 1.0.0 | 2026-09-20 | Extraction | Initial extract. ||
"""


def sidecar():
    return {
        "schema": rl.SOURCES_SCHEMA,
        "meta": {"enforced": False},
        "claims": {
            "ctx.reception": {
                "section": 2,
                "kind": "prose",
                "population": "any",
                "polarity": "affirm",
                "grades": [
                    {
                        "scope": None,
                        "asserted": "SETTLED",
                        "cap": None,
                        "cap_evidence": None,
                        "unverified": False,
                        "cap_reasons": [],
                    }
                ],
                "sources": [
                    {
                        "id": "s1",
                        "url": "https://example.com/s1",
                        "title": "Title",
                        "type": "peer",
                        "resolves_to": None,
                        "resolves_to_type": None,
                        "independence_group": "g-s1",
                        "supports": "confirms",
                        "quote": "a short quote",
                        "accessed": "2026-09-20",
                        "reception": {
                            "checked": False,
                            "retracted": False,
                            "scite_supporting": None,
                            "scite_contrasting": None,
                        },
                    }
                ],
                "duplicates": [],
                "last_verified": None,
                "verified_by": None,
                "notes": "",
            }
        },
        "rules": {},
    }


class WriteReceptionCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "research").mkdir()
        (self.repo / "skills" / "marcus" / "references").mkdir(parents=True)
        self.research = self.repo / "research" / "RESEARCH.md"
        self.sources = self.repo / "research" / "sources.yaml"
        self.claims_json = self.repo / "skills" / "marcus" / "references" / "claims.json"
        self.research.write_text(RESEARCH, encoding="utf-8")
        rl.dump_sources(sidecar(), self.sources)

    def tearDown(self):
        self._tmp.cleanup()

    def test_records_reception_when_scite_key_present(self):
        with mock.patch.dict(os.environ, {"SCITE_API_KEY": "k"}), mock.patch.object(
            reception, "scite_reception", return_value={"checked": True, "retracted": False, "supporting": 2, "contrasting": 0}
        ):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = gc.main(["--repo", str(self.repo), "--write"])
        self.assertEqual(code, 0, out.getvalue())
        data = rl.load_sources(self.sources)
        src = data["claims"]["ctx.reception"]["sources"][0]
        self.assertEqual(src["reception"]["checked"], True)

    def test_no_reception_without_scite_key(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = gc.main(["--repo", str(self.repo), "--write"])
        self.assertEqual(code, 0, out.getvalue())
        data = rl.load_sources(self.sources)
        src = data["claims"]["ctx.reception"]["sources"][0]
        self.assertEqual(src["reception"]["checked"], False)
