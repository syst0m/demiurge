#!/usr/bin/env python3
"""Blocking gate: a code change with no corresponding test change is not a complete task.

Implements the testing-matrix mandate. Reads the repo's working changes (staged, unstaged and
untracked), separates source from test files, and blocks when source changed without tests.

Standalone:
    python scripts/testing_matrix_gate.py [--repo DIR] [--json]

Exit codes: 0 pass, 1 blocked. `--json` prints the hook response object for harnesses that
expect one on stdout (Claude Code Stop, Antigravity Stop) and always exits 0.

A hook that cannot find a git repository passes: the gate judges changes, not the absence of them.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence, Set

SOURCE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java", ".cs", ".c",
              ".h", ".cpp", ".hpp", ".sh", ".bash", ".ps1", ".sql", ".yaml", ".yml", ".toml"}


def changed_files(repo: Path) -> List[str]:
    def run(*args: str) -> List[str]:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return []
        return [line.strip() for line in r.stdout.splitlines() if line.strip()]

    files: Set[str] = set()
    files.update(run("diff", "--name-only", "HEAD"))
    files.update(run("diff", "--name-only", "--cached"))
    files.update(run("ls-files", "--others", "--exclude-standard"))
    return sorted(files)


TEST_MARKERS_DIR = {"test", "tests", "spec", "specs", "__tests__", "__snapshots__"}
TEST_NAMES = {"conftest.py", "test.py"}


def is_test(path: str) -> bool:
    """Segment-based: `test_*.py`, `*_test.py`, `*.test.*`, and anything under a test directory.

    A substring match is wrong — it marks `testing_matrix_gate.py` and `latest.py` as tests,
    which lets a source-only diff straight through.
    """
    parts = [p.lower() for p in path.split("/")]
    dirs, name = parts[:-1], parts[-1]
    if any(d in TEST_MARKERS_DIR for d in dirs):
        return True
    if any(d.startswith("test_") or d.endswith("_test") or ".test." in d or ".spec." in d
           for d in dirs):
        return True
    if name in TEST_NAMES:
        return True
    return (name.startswith("test_") or name.endswith("_test.py") or name.endswith("-test.py")
            or ".test." in name or ".spec." in name)


def classify(files: Sequence[str]) -> tuple[List[str], List[str]]:
    source = [f for f in files if Path(f).suffix in SOURCE_EXT and not is_test(f)]
    tests = [f for f in files if is_test(f)]
    return source, tests


def report(source: Sequence[str], tests: Sequence[str]) -> str:
    lines = [
        f"BLOCKED: {len(source)} source file(s) changed with no test change.",
        "",
        "Impact Analysis:",
        "- Unit:        " + ("affected" if source else "none"),
        "- Integration: " + ("likely" if any("/" in f for f in source) else "none"),
        "- System/E2E:  " + ("assess" if len(source) > 2 else "none"),
        "- Regression:  at risk — no test change accompanies this diff",
        "- Security:    " + ("scan new paths for exposure" if source else "none"),
        "- Performance: " + ("assess if the change is on a hot path" if source else "none"),
        "",
        "Implementation/Update/Deletion Plan:",
        "- For each file above, add or update the test that pins its behaviour.",
        "- Removing a feature: delete its tests and any stale mocks in the same change.",
        "- If this change genuinely needs no test, say why explicitly and re-run.",
        "",
        "Execution Approach:",
        "- Automated: the repo's unit suite plus this gate, in CI.",
        "- Manual: name the commands you ran and what they showed.",
        "",
        "Changed source files:",
        *( [f"  {f}" for f in source] or ["  (none)"] ),
        "",
        "Changed test files:",
        *( [f"  {f}" for f in tests] or ["  (none)"] ),
    ]
    return "\n".join(lines)


def hook_response(fmt: str, source: Sequence[str], tests: Sequence[str]) -> str:
    """Render the block response in one harness's native dialect.

    The dialects genuinely differ: Claude Code blocks a Stop with {"decision":"block"}, while
    Antigravity blocks with {"decision":"continue"} (any other value lets the stop through).
    """
    blocked = bool(source) and not tests
    text = report(source, tests) if blocked else "tests accompany the change"
    if fmt == "antigravity":
        return json.dumps({"decision": "continue" if blocked else "stop",
                           "reason": text} if blocked else {"decision": "stop"})
    if fmt == "claude-code":
        return json.dumps({"decision": "block", "reason": text} if blocked else {})
    return json.dumps({"decision": "block" if blocked else "allow", "reason": text})


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--json", action="store_true", help="print a hook response object")
    p.add_argument("--hook-format", choices=["internal", "claude-code", "antigravity"],
                   default="internal",
                   help="dialect for --json (default internal)")
    args = p.parse_args(argv)

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        if args.json:
            print(hook_response(args.hook_format, [], []))
        return 0

    source, tests = classify(changed_files(repo))
    if source and not tests:
        if args.json:
            print(hook_response(args.hook_format, source, tests))
            return 0
        print(report(source, tests))
        return 1

    if args.json:
        print(hook_response(args.hook_format, source, tests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
