#!/usr/bin/env python3
"""Deterministic scanner for superfluous commentary, chat transcripts, and session diaries.

Usage:
    python scripts/scan_superfluous.py [paths...] [--strict] [--json]

Scans code comments, scripts, configurations, and documentation for conversational
meta-commentary, session transcripts, diary notes, and leftover assistant scaffolding.
Exit codes:
    0  clean
    1  superfluous commentary detected (or warnings with --strict)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Pattern, Tuple

# Patterns indicating conversational meta-commentary, session transcripts, or diary notes
SUPERFLUOUS_PATTERNS: List[Tuple[str, str, Pattern[str]]] = [
    (
        "chat-transcript",
        "Chat transcript or conversation reference in comment/prose",
        re.compile(
            r"\b(?:chat\s+transcript|previously\s+held\s+a\s+chat|transcript\s+describing"
            r"|in\s+(?:our\s+)?previous\s+(?:chat|session|conversation)"
            r"|from\s+(?:our\s+)?previous\s+(?:session|conversation))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "migration-war-story",
        "Historical migration narrative or war story in comment",
        re.compile(
            r"\b(?:working\s+copy\s+had\s+been\s+installed"
            r"|unversioned\s+and\s+would\s+be\s+displaced"
            r"|unversioned,\s+invisible\s+to\s+CI"
            r"|displaced\s+by\s+`?pre-commit"
            r"|lives\s+here\s+and\s+runs\s+as\s+a\s+local\s+hook,\s+so\s+it\s+survives)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "session-diary",
        "Session diary or date-stamped developer war story in comment",
        re.compile(
            r"\b(?:session\s+diary|war\s+story|diary\s+note"
            r"|\d{4}-\d{2}-\d{2}\s+(?:incident|debugging\s+session|war\s+story|we\s+lost\s+evals))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "conversational-prompt",
        "Conversational prompt artifact or meta-instruction in comment",
        re.compile(
            r"\b(?:as\s+requested\s+by\s+(?:the\s+)?user|as\s+discussed\s+with\s+(?:the\s+)?user"
            r"|note\s+to\s+AI|AI-generated\s+code\s+do\s+not\s+touch"
            r"|TODO:\s*remove\s+(?:after|before)\s+(?:shipping|testing|session))\b",
            re.IGNORECASE,
        ),
    ),
]

SUPPRESSION_TAG = "forge:allow superfluous-comment"

# File extensions inspected
TEXT_EXTENSIONS = {
    ".py",
    ".sh",
    ".bash",
    ".md",
    ".yml",
    ".yaml",
    ".json",
    ".html",
    ".toml",
    ".txt",
    ".ini",
}

# Directories always excluded
EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "env",
    "scratch",
}


@dataclass
class Finding:
    path: str
    line_number: int
    rule: str
    description: str
    line_content: str


def get_tracked_files(repo_root: Path) -> List[Path]:
    """Return all git-tracked files in the repository."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return [repo_root / p for p in res.stdout.splitlines() if p.strip()]
    except Exception:
        # Fallback to traversing filesystem if git is unavailable
        files = []
        for p in repo_root.rglob("*"):
            if p.is_file() and not any(part in EXCLUDED_DIRS for part in p.parts):
                files.append(p)
        return files


def collect_target_files(paths: Iterable[str], repo_root: Path) -> List[Path]:
    """Resolve user-supplied paths or default to git-tracked files."""
    if not paths:
        return [
            p
            for p in get_tracked_files(repo_root)
            if p.suffix.lower() in TEXT_EXTENSIONS
            and not any(part in EXCLUDED_DIRS for part in p.parts)
        ]

    targets: List[Path] = []
    for raw in paths:
        path = Path(raw).resolve()
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix.lower() in TEXT_EXTENSIONS:
                targets.append(path)
        elif path.is_dir():
            for child in path.rglob("*"):
                if (
                    child.is_file()
                    and child.suffix.lower() in TEXT_EXTENSIONS
                    and not any(part in EXCLUDED_DIRS for part in child.parts)
                ):
                    targets.append(child)
    return targets


def is_comment_or_doc(line: str, ext: str) -> bool:
    """Check if a line is a comment or documentation context."""
    stripped = line.strip()
    if not stripped:
        return False
    if ext in {".py", ".sh", ".bash", ".yml", ".yaml", ".ini", ".toml"}:
        return stripped.startswith("#") or '"""' in stripped or "'''" in stripped
    if ext in {".html"}:
        return "<!--" in stripped or "-->" in stripped
    if ext in {".md", ".txt"}:
        return True  # Full file is prose/documentation
    return True


def scan_file(path: Path, repo_root: Path) -> List[Finding]:
    """Scan a single file for superfluous comments and statements."""
    findings: List[Finding] = []
    ext = path.suffix.lower()

    # Self-skip: this scanner defines the trigger regexes
    try:
        if path.resolve() == Path(__file__).resolve():
            return findings
    except Exception:
        pass

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    try:
        rel_path = str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        rel_path = str(path)
    is_eval_file = "evals" in path.parts or path.name.endswith("evals.json")

    for idx, line in enumerate(content.splitlines(), 1):
        if SUPPRESSION_TAG in line:
            continue

        if not is_comment_or_doc(line, ext):
            continue

        for rule, desc, pattern in SUPERFLUOUS_PATTERNS:
            if is_eval_file and rule == "conversational-prompt":
                continue
            if pattern.search(line):
                findings.append(
                    Finding(
                        path=rel_path,
                        line_number=idx,
                        rule=rule,
                        description=desc,
                        line_content=line.strip(),
                    )
                )
                break

    return findings


def run_scan(targets: List[Path], repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for target in targets:
        findings.extend(scan_file(target, repo_root))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan repository or skills for superfluous comments and session transcripts."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Paths to files or directories to scan (default: all tracked text files)",
    )
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--strict", action="store_true", help="Enforce strict exit code")
    args = parser.parse_args()

    # Determine repo root
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent if script_dir.name == "scripts" else Path.cwd()

    targets = collect_target_files(args.paths, repo_root)
    findings = run_scan(targets, repo_root)

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
        return 1 if findings else 0

    if not findings:
        print(f"Scan complete: {len(targets)} files inspected. No superfluous commentary found.")
        return 0

    print(f"FAILED: Found {len(findings)} superfluous statement(s) across {len(targets)} files:\n")
    for f in findings:
        print(f"  {f.path}:{f.line_number} [{f.rule}] {f.description}")
        print(f"    > {f.line_content}\n")

    print("Remediation: Remove historical commentary, session diaries, and chat transcripts.")
    print("Code comments state invariants and present design intent. Git logs record history.")
    print(f"To suppress an intentional match, append: '{SUPPRESSION_TAG}'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
