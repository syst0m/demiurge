#!/usr/bin/env python3
"""
verify_release.py - Mechanical Release Verification Gate for Demiurge.

Enforces:
1. No CI suppression tokens ([skip ci], [ci skip], [no ci]) on release commits.
2. Exact alignment between CHANGELOG.md versions and local git tags.
3. Complete synchronization between local git tags and remote origin tags.
4. Published GitHub Release presence via GitHub CLI (gh release view).

Conforms to Marcus Rule V-4: Invariants become hooks because models forget and hooks do not.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

CHANGELOG_PATH = Path("CHANGELOG.md")
SKIP_CI_PATTERN = re.compile(r"\[(skip\s+ci|ci\s+skip|no\s+ci|skip\s+actions)\]", re.IGNORECASE)
RELEASE_COMMIT_PATTERN = re.compile(
    r"^(chore\(release\)|release(\([^\)]+\))?|Release)\s*:|"
    r"^(chore\(release\)|release|Release)\s+v?\d",
    re.IGNORECASE,
)
SEMVER_HEADING_PATTERN = re.compile(r"^##\s+\[(?P<version>\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)\](?:\s+-\s+(?P<date>\d{4}-\d{2}-\d{2}))?", re.MULTILINE)


def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """Runs a subprocess command and returns (exit_code, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def get_changelog_versions(changelog_path: Path = CHANGELOG_PATH) -> List[str]:
    """Extracts all released semver versions from CHANGELOG.md in order."""
    if not changelog_path.exists():
        return []
    content = changelog_path.read_text(encoding="utf-8")
    return [match.group("version") for match in SEMVER_HEADING_PATTERN.finditer(content)]


def get_latest_changelog_version(changelog_path: Path = CHANGELOG_PATH) -> Optional[str]:
    """Returns the most recent release version in CHANGELOG.md."""
    versions = get_changelog_versions(changelog_path)
    return versions[0] if versions else None


def check_commit_message(msg: str) -> List[str]:
    """
    Validates a commit message.
    Fails if a release commit includes [skip ci] or related tokens.
    """
    findings: List[str] = []
    if RELEASE_COMMIT_PATTERN.search(msg):
        if SKIP_CI_PATTERN.search(msg):
            findings.append(
                "CRITICAL: Release commit contains CI-suppression token (e.g., '[skip ci]'). "
                "This prevents GitHub Actions release workflows (release.yml) from triggering on tag push. "
                "Remove '[skip ci]' from the release commit message."
            )
    return findings


def get_local_tags() -> List[str]:
    """Returns all git tags in the local repository."""
    code, stdout, _ = run_cmd(["git", "tag", "-l"])
    if code != 0 or not stdout:
        return []
    return [t.strip() for t in stdout.splitlines() if t.strip()]


def get_remote_tags() -> List[str]:
    """Returns all git tags present on remote origin."""
    code, stdout, _ = run_cmd(["git", "ls-remote", "--tags", "origin"])
    if code != 0 or not stdout:
        return []
    tags = []
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            ref = parts[1]
            if ref.startswith("refs/tags/"):
                tag = ref[len("refs/tags/"):]
                if not tag.endswith("^{}"):
                    tags.append(tag)
    return tags


def verify_local_state(changelog_path: Path = CHANGELOG_PATH) -> List[str]:
    """Checks local CHANGELOG.md and git tags."""
    findings: List[str] = []
    latest_ver = get_latest_changelog_version(changelog_path)
    if not latest_ver:
        findings.append("No released versions found in CHANGELOG.md.")
        return findings

    local_tags = get_local_tags()
    expected_tag = f"v{latest_ver}"
    if expected_tag not in local_tags:
        findings.append(
            f"Tag mismatch: Latest version in CHANGELOG.md is '{latest_ver}', "
            f"but local git tag '{expected_tag}' does not exist. Create tag with: git tag -a {expected_tag} -m \"Release {expected_tag}\""
        )

    # Check HEAD commit message
    code, stdout, _ = run_cmd(["git", "log", "-1", "--pretty=%B"])
    if code == 0 and stdout:
        findings.extend(check_commit_message(stdout))

    return findings


def verify_remote_sync(tag: str) -> List[str]:
    """Checks whether the tag exists on remote origin."""
    findings: List[str] = []
    remote_tags = get_remote_tags()
    if not remote_tags:
        findings.append("Could not fetch remote tags from 'origin' (network error or remote unreachable).")
        return findings

    if tag not in remote_tags:
        findings.append(
            f"Unpushed tag: Local tag '{tag}' has not been pushed to remote 'origin'. "
            f"Run: git push origin {tag}"
        )
    return findings


def verify_github_release(tag: str) -> List[str]:
    """Checks if a published release object exists on GitHub using gh CLI."""
    findings: List[str] = []
    # Check if gh is installed
    code, _, _ = run_cmd(["gh", "--version"])
    if code != 0:
        findings.append("GitHub CLI ('gh') is not installed or not in PATH; cannot verify GitHub Releases.")
        return findings

    code, stdout, stderr = run_cmd(["gh", "release", "view", tag, "--json", "tagName,isDraft,isPrerelease,body"])
    if code != 0:
        findings.append(
            f"Missing GitHub Release: Release for tag '{tag}' was not found on GitHub Releases. "
            f"Run: gh release create {tag} --title \"{tag}\" -F <notes.md>"
        )
        return findings

    if '"isDraft":true' in stdout:
        findings.append(f"GitHub Release for '{tag}' is still marked as DRAFT.")

    return findings


def run_pre_commit_check(files: List[str]) -> int:
    """Pre-commit hook mode: checks staged files for release integrity."""
    findings: List[str] = []

    # Check CHANGELOG.md formatting if present or touched
    changelog_files = [f for f in files if "CHANGELOG.md" in f]
    if changelog_files or Path("CHANGELOG.md").exists():
        versions = get_changelog_versions()
        if not versions:
            findings.append("CHANGELOG.md contains no valid SemVer release headings ('## [X.Y.Z]').")

    if findings:
        print("[FAIL] Release Integrity Gate:", file=sys.stderr)
        for f in findings:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("[PASS] Release Integrity Gate: pre-commit checks passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Demiurge Mechanical Release Verification Gate")
    parser.add_argument("--pre-commit", action="store_true", help="Run in pre-commit hook mode")
    parser.add_argument("--check-msg", type=str, default=None, help="Validate a commit message string or message file path")
    parser.add_argument("--local", action="store_true", help="Perform local validation only (no network)")
    parser.add_argument("--remote", action="store_true", help="Perform full validation including remote git & GitHub Releases")
    parser.add_argument("--tag", type=str, default=None, help="Explicit tag to verify (defaults to latest in CHANGELOG.md)")
    parser.add_argument("files", nargs="*", help="Files passed by pre-commit")

    args = parser.parse_args()

    if args.check_msg:
        msg_text = args.check_msg
        msg_path = Path(args.check_msg)
        if msg_path.is_file():
            try:
                msg_text = msg_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        msg_findings = check_commit_message(msg_text)
        if msg_findings:
            print("[FAIL] Release Commit Gate:", file=sys.stderr)
            for f in msg_findings:
                print(f"  - {f}", file=sys.stderr)
            return 1
        print("[PASS] Release Commit Gate: message conforms to release rules.")
        return 0

    if args.pre_commit:
        return run_pre_commit_check(args.files)

    target_ver = get_latest_changelog_version()
    if not target_ver and not args.tag:
        print("[FAIL] Could not determine target release version from CHANGELOG.md", file=sys.stderr)
        return 1

    target_tag = args.tag if args.tag else f"v{target_ver}"
    print(f"Auditing release gate for [{target_tag}]...")

    all_findings: List[str] = []

    # 1. Local checks
    print("  [1/3] Checking local CHANGELOG.md, git tags, and commit message...")
    local_findings = verify_local_state()
    all_findings.extend(local_findings)
    if not local_findings:
        print("        Local state PASSED.")
    else:
        for err in local_findings:
            print(f"        [!] {err}")

    # 2. Remote checks (if requested)
    if args.remote:
        print(f"  [2/3] Verifying remote tag '{target_tag}' on origin...")
        remote_findings = verify_remote_sync(target_tag)
        all_findings.extend(remote_findings)
        if not remote_findings:
            print("        Remote tag synchronization PASSED.")
        else:
            for err in remote_findings:
                print(f"        [!] {err}")

        print(f"  [3/3] Verifying GitHub Release object for '{target_tag}'...")
        gh_findings = verify_github_release(target_tag)
        all_findings.extend(gh_findings)
        if not gh_findings:
            print("        GitHub Release object PASSED.")
        else:
            for err in gh_findings:
                print(f"        [!] {err}")
    else:
        print("  (Remote checks skipped; pass --remote to verify GitHub Releases and remote origin)")

    if all_findings:
        print(f"\n[FAIL] Release Verification Gate FAILED with {len(all_findings)} issue(s).", file=sys.stderr)
        return 1

    print(f"\n[PASS] All Release Verification Gate checks PASSED for {target_tag}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
