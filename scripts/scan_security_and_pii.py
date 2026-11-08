#!/usr/bin/env python3
"""
Pre-commit hook: Scans files for secrets, PII, local user paths, and agent policy invariants.
Stdlib-only, cross-platform (Windows / macOS / Linux).
"""

import os
import re
import sys

SECRET_PATTERNS = [
    (re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}\b'), "GitHub personal access token"),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), "AWS access key ID"),
    (re.compile(r'\bsk-[a-zA-Z0-9]{20,}\b'), "OpenAI / LLM API key"),
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), "Private encryption key"),
    (re.compile(r'\bhf_[a-zA-Z0-9]{34,}\b'), "HuggingFace API token"),
]

PII_PATH_PATTERNS = [
    (re.compile(r'[a-zA-Z]:[\\/][Uu]sers[\\/][a-zA-Z0-9_.-]+', re.I), "Local Windows user profile path"),
    (re.compile(r'/home/(?!runner|circleci|travis)[a-zA-Z0-9_.-]+', re.I), "Local Unix user home path"),
]

# Personal / health-regimen markers and structural personal identifiers.
# The generic secret-key patterns above cannot see private medical, crisis, or
# identity-adjacent data. A public repo must never carry these markers.
# NOTE: populate your personal list locally — this public file intentionally
# carries no names, medications, or crisis keywords.
PERSONAL_PII_PATTERNS = [
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), "email address"),
    (re.compile(r'\b(?:\d{3}[-.]?){2}\d{4}\b'), "phone number"),
]

# Allow-list / ignore list for benign documentation examples or known fake strings
ALLOW_PATTERNS = [
    # Test email domains (RFC 2606 reserved + common test fixtures)
    "example.com",
    "example.invalid",
    "corp.io",
    "a@b.co",
    # Version strings that match email regex
    ".md@",
    "-forge@",
    # Schema.org
    "schema.org",
]



def check_file(filepath: str) -> list:
    findings = []

    # Skip binary files, pycache, git objects
    if filepath.endswith(('.jpg', '.png', '.ico', '.pyc', '.pdf', '.woff', '.woff2')):
        return findings

    # Skip the policy document itself (documents the patterns)
    if filepath == 'SECURE.md' or filepath.endswith('/SECURE.md'):
        return findings

    # Skip held-out test fixtures (safety gate tests use self-harm keywords)
    if filepath.startswith('.judge/heldout/') or '/.judge/heldout/' in filepath:
        return findings

    if not os.path.exists(filepath):
        return findings

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        return [f"Could not read {filepath}: {e}"]

    for line_num, line in enumerate(lines, 1):
        # 1. Secret patterns
        for pattern, desc in SECRET_PATTERNS:
            if pattern.search(line):
                # Ignore references in this scanner script or documentation explaining the pattern
                if "SECRET_PATTERNS" in line or "scan_security_and_pii.py" in filepath:
                    continue
                findings.append(f"{filepath}:{line_num}: [SECRET] Potential {desc}")

        # 2. PII / Local user path patterns
        for pattern, desc in PII_PATH_PATTERNS:
            m = pattern.search(line)
            if m:
                if "PII_PATH_PATTERNS" in line or "scan_security_and_pii.py" in filepath:
                    continue
                matched = m.group(0)
                if any(ap in matched or ap in line for ap in ALLOW_PATTERNS if ap):
                    continue
                findings.append(f"{filepath}:{line_num}: [PII/PATH] {desc}: '{matched}'")

        # 3. Personal / health-regimen markers and structural personal identifiers
        for pattern, desc in PERSONAL_PII_PATTERNS:
            m = pattern.search(line)
            if m:
                if "PERSONAL_PII_PATTERNS" in line or "scan_security_and_pii.py" in filepath:
                    continue
                matched = m.group(0)
                if any(ap in matched or ap in line for ap in ALLOW_PATTERNS if ap):
                    continue
                findings.append(f"{filepath}:{line_num}: [PERSONAL] {desc}: '{matched}'")

    return findings


def main():
    files = sys.argv[1:]
    if not files:
        # If called without arguments, scan all tracked files
        import subprocess
        try:
            files = subprocess.check_output(['git', 'ls-files'], encoding='utf-8').splitlines()
        except (OSError, subprocess.CalledProcessError) as e:
            # An empty file list would report a clean repo that was never scanned.
            print(f"ERROR: could not list tracked files with git ls-files: {e}", file=sys.stderr)
            sys.exit(2)

    all_findings = []
    for filepath in files:
        findings = check_file(filepath)
        if findings:
            all_findings.extend(findings)

    if all_findings:
        print("\n❌ Security / PII / Path issues detected:")
        for f in all_findings:
            print(f"  - {f}")
        print("\nPlease scrub or sanitize these before committing.\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
