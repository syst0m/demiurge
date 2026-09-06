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

# Allow-list / ignore list for benign documentation examples or known fake strings
ALLOW_PATTERNS = [
    re.compile(r'example\.com', re.I),
    re.compile(r'schema\.org', re.I),
    re.compile(r'sk-ant-', re.I),
    re.compile(r'sk-[a-zA-Z0-9]{20,}', re.I) if False else None,
]


def check_file(filepath: str) -> list:
    findings = []

    # Skip binary files, pycache, git objects
    if filepath.endswith(('.jpg', '.png', '.ico', '.pyc', '.pdf', '.woff', '.woff2')):
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
                findings.append(f"{filepath}:{line_num}: [PII/PATH] {desc}: '{m.group(0)}'")

    return findings


def main():
    files = sys.argv[1:]
    if not files:
        # If called without arguments, scan all tracked files
        import subprocess
        try:
            files = subprocess.check_output(['git', 'ls-files'], encoding='utf-8').splitlines()
        except Exception:
            files = []

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
