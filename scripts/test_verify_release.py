#!/usr/bin/env python3
"""
test_verify_release.py - Unit tests for verify_release.py release gate.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.verify_release as vr


class TestReleaseGateCommitMessage(unittest.TestCase):
    def test_release_commit_with_skip_ci_fails(self):
        msg = "chore(release): v1.0.0 [skip ci]"
        findings = vr.check_commit_message(msg)
        self.assertEqual(len(findings), 1)
        self.assertIn("CRITICAL", findings[0])
        self.assertIn("[skip ci]", findings[0])

    def test_release_commit_with_ci_skip_fails(self):
        msg = "Release v1.2.0 [ci skip]\n\nRelease notes"
        findings = vr.check_commit_message(msg)
        self.assertEqual(len(findings), 1)
        self.assertIn("CRITICAL", findings[0])

    def test_release_commit_with_skip_actions_fails(self):
        msg = "release: v2.0.0 [skip actions]"
        findings = vr.check_commit_message(msg)
        self.assertEqual(len(findings), 1)
        self.assertIn("CRITICAL", findings[0])

    def test_valid_release_commit_passes(self):
        msg = "chore(release): v1.0.0\n\nRelease notes without CI suppression"
        findings = vr.check_commit_message(msg)
        self.assertEqual(len(findings), 0)

    def test_non_release_commit_with_skip_ci_passes(self):
        msg = "docs: update typo in README [skip ci]"
        findings = vr.check_commit_message(msg)
        self.assertEqual(len(findings), 0)


class TestChangelogParsing(unittest.TestCase):
    def test_extract_changelog_versions(self):
        sample = """# Changelog
## [Unreleased]
## [1.2.3] - 2026-09-11
### Added
- Item
## [1.2.2] - 2026-09-10
## [1.0.0-rc.1] - 2026-09-01
"""
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "read_text", return_value=sample):
            versions = vr.get_changelog_versions(Path("DUMMY.md"))
            self.assertEqual(versions, ["1.2.3", "1.2.2", "1.0.0-rc.1"])
            latest = vr.get_latest_changelog_version(Path("DUMMY.md"))
            self.assertEqual(latest, "1.2.3")


class TestLocalAndRemoteTagVerification(unittest.TestCase):
    @patch("scripts.verify_release.run_cmd")
    def test_local_tag_missing_reports_finding(self, mock_run_cmd):
        mock_run_cmd.side_effect = [
            (0, "v0.8.0\nv0.8.1", ""),  # git tag -l
            (0, "feat: some normal work", ""),  # git log -1
        ]
        with patch("scripts.verify_release.get_latest_changelog_version", return_value="0.9.0"):
            findings = vr.verify_local_state(Path("CHANGELOG.md"))
            self.assertTrue(any("Tag mismatch" in f and "v0.9.0" in f for f in findings))

    @patch("scripts.verify_release.run_cmd")
    def test_remote_tag_missing_reports_finding(self, mock_run_cmd):
        mock_run_cmd.return_value = (
            0,
            "hash1\trefs/tags/v0.8.0\nhash2\trefs/tags/v0.8.1",
            "",
        )
        findings = vr.verify_remote_sync("v0.9.0")
        self.assertTrue(any("Unpushed tag" in f and "v0.9.0" in f for f in findings))

    @patch("scripts.verify_release.run_cmd")
    def test_remote_tag_present_passes(self, mock_run_cmd):
        mock_run_cmd.return_value = (
            0,
            "hash1\trefs/tags/v0.8.0\nhash2\trefs/tags/v0.9.0",
            "",
        )
        findings = vr.verify_remote_sync("v0.9.0")
        self.assertEqual(len(findings), 0)


class TestGitHubReleaseVerification(unittest.TestCase):
    @patch("scripts.verify_release.run_cmd")
    def test_github_release_missing_reports_finding(self, mock_run_cmd):
        mock_run_cmd.side_effect = [
            (0, "gh version 2.93.0", ""),  # gh --version
            (1, "", "release not found"),   # gh release view
        ]
        findings = vr.verify_github_release("v0.9.0")
        self.assertTrue(any("Missing GitHub Release" in f for f in findings))

    @patch("scripts.verify_release.run_cmd")
    def test_github_release_present_passes(self, mock_run_cmd):
        mock_run_cmd.side_effect = [
            (0, "gh version 2.93.0", ""),  # gh --version
            (0, '{"tagName":"v0.9.0","isDraft":false,"body":"Notes"}', ""),  # gh release view
        ]
        findings = vr.verify_github_release("v0.9.0")
        self.assertEqual(len(findings), 0)

    @patch("scripts.verify_release.run_cmd")
    def test_github_release_draft_reports_finding(self, mock_run_cmd):
        mock_run_cmd.side_effect = [
            (0, "gh version 2.93.0", ""),  # gh --version
            (0, '{"tagName":"v0.9.0","isDraft":true,"body":"Draft"}', ""),  # gh release view
        ]
        findings = vr.verify_github_release("v0.9.0")
        self.assertTrue(any("DRAFT" in f for f in findings))


class TestPreCommitMode(unittest.TestCase):
    def test_pre_commit_passes_when_changelog_valid(self):
        ret = vr.run_pre_commit_check(["CHANGELOG.md"])
        self.assertEqual(ret, 0)

    @patch("scripts.verify_release.get_changelog_versions", return_value=[])
    def test_pre_commit_fails_when_no_versions(self, mock_get_versions):
        ret = vr.run_pre_commit_check(["CHANGELOG.md"])
        self.assertEqual(ret, 1)


class TestReleaseNotes(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "CHANGELOG.md"
        self.path.write_text(
            "# Changelog\n\n## [Unreleased]\n\n## [1.1.0] - 2026-11-01\n\n### Added\n\n- new\n\n"
            "## [1.0.0] - 2026-10-01\n\n### Fixed\n\n- old\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_middle_section(self):
        self.assertEqual(vr.release_notes("1.1.0", self.path), "### Added\n\n- new\n")

    def test_last_section(self):
        self.assertEqual(vr.release_notes("1.0.0", self.path), "### Fixed\n\n- old\n")

    def test_missing_version_is_empty(self):
        self.assertEqual(vr.release_notes("9.9.9", self.path), "")


class TestCutRelease(unittest.TestCase):
    @patch("scripts.verify_release.get_remote_tags", return_value=["v1.0.0"])
    @patch("scripts.verify_release.get_local_tags", return_value=["v1.0.0"])
    @patch("scripts.verify_release.run_cmd", return_value=(0, "", ""))
    def test_done_release_runs_nothing_but_the_view(self, run_cmd, _local, _remote):
        self.assertEqual(vr.cut_release("v1.0.0"), [])
        run_cmd.assert_called_once_with(["gh", "release", "view", "v1.0.0"])

    @patch("scripts.verify_release.get_remote_tags", return_value=[])
    @patch("scripts.verify_release.get_local_tags", return_value=[])
    @patch("scripts.verify_release.run_cmd", return_value=(1, "", "denied"))
    def test_failed_tag_stops_before_push(self, run_cmd, _local, _remote):
        self.assertEqual(vr.cut_release("v1.1.0"), ["git tag failed: denied"])
        self.assertEqual(run_cmd.call_count, 1)


if __name__ == "__main__":
    unittest.main()
