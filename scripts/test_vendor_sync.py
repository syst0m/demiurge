"""Tests for vendor_sync.py --check: pinned files pass, a hand edit fails."""

import hashlib
import tempfile
import unittest
from pathlib import Path

import vendor_sync


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vendored = self.root / "skills" / "demo" / "references" / "up"
        self.vendored.mkdir(parents=True)
        (self.vendored / "SKILL.upstream.md").write_bytes(b"upstream text\n")
        digest = hashlib.sha256(b"upstream text\n").hexdigest()
        (self.vendored / "UPSTREAM.yaml").write_text(
            "repo: https://example.invalid/up\ncommit: abc1234\n"
            f"files:\n  SKILL.md:\n    as: SKILL.upstream.md\n    sha256: {digest}\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_pinned_file_passes(self):
        self.assertEqual(vendor_sync.check(self.root), 0)

    def test_hand_edit_fails(self):
        (self.vendored / "SKILL.upstream.md").write_bytes(b"upstream text, edited\n")
        self.assertEqual(vendor_sync.check(self.root), 1)

    def test_missing_file_fails(self):
        (self.vendored / "SKILL.upstream.md").unlink()
        self.assertEqual(vendor_sync.check(self.root), 1)

    def test_real_repo_pins_hold(self):
        self.assertEqual(vendor_sync.check(), 0)


if __name__ == "__main__":
    unittest.main()
