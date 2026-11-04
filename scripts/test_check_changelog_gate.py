"""Regression tests for the changelog gate. The failures are the real ones from PRs 28 to 31."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_changelog_gate as gate  # noqa: E402

BASE = """# Changelog

## [Unreleased]

## [0.16.0] - 2026-11-01

### Added

- old entry
"""

ENTRIES_ONLY = BASE.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Added\n\n- new entry\n")
RELEASED = BASE.replace("## [Unreleased]\n", "## [Unreleased]\n\n## [0.17.0] - 2026-11-04\n\n### Added\n\n- new entry\n")


class ChangelogGateTests(unittest.TestCase):
    def test_entries_under_unreleased_only_fail(self):
        errors, _ = gate.check(BASE, ENTRIES_ONLY, "Merge pull request")
        self.assertTrue(any("No new version heading" in e for e in errors))
        self.assertTrue(any("[Unreleased] still holds" in e for e in errors))

    def test_untouched_changelog_fails(self):
        errors, _ = gate.check(BASE, BASE, "Retitle heading")
        self.assertTrue(any("No new version heading" in e for e in errors))

    def test_release_heading_with_empty_unreleased_passes(self):
        self.assertEqual(gate.check(BASE, RELEASED, "Release 0.17.0"), ([], None))

    def test_leftover_unreleased_entries_fail_even_with_new_heading(self):
        head = RELEASED.replace("## [Unreleased]\n", "## [Unreleased]\n\n- stray\n")
        errors, _ = gate.check(BASE, head, "")
        self.assertTrue(any("[Unreleased] still holds" in e for e in errors))

    def test_version_not_greater_fails(self):
        head = RELEASED.replace("0.17.0", "0.15.9")
        errors, _ = gate.check(BASE, head, "")
        self.assertTrue(any("not greater" in e for e in errors))

    def test_missing_date_fails(self):
        head = RELEASED.replace("## [0.17.0] - 2026-11-04", "## [0.17.0]")
        errors, _ = gate.check(BASE, head, "")
        self.assertTrue(any("no date" in e for e in errors))

    def test_skip_line_passes_and_is_reported(self):
        errors, note = gate.check(BASE, BASE, "Fix typo\n\nChangelog: none\n")
        self.assertEqual(errors, [])
        self.assertIn("Changelog: none", note)

    def test_skip_line_must_be_its_own_line(self):
        errors, note = gate.check(BASE, BASE, "mentions Changelog: none inline")
        self.assertTrue(errors)
        self.assertIsNone(note)


if __name__ == "__main__":
    unittest.main()
