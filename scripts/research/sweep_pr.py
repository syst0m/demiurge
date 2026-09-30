#!/usr/bin/env python3
"""
sweep_pr.py - Prepare and publish a research sweep branch as a pull request.

The research routine never pushes by hand. It runs ``prepare`` to get a fresh
worktree on a new branch, edits files there, commits, and runs ``publish``.
``publish`` is the only push path, and it refuses anything that is not a
research-only change on a research branch.

    prepare --date YYYY-MM-DD
        Creates branch ``research/sweep-<date>`` from the base ref and checks it
        out in the worktree ``scratch/sweep-<date>``. Refuses when the branch
        exists locally or on the remote, or when the worktree path exists.

    publish [--yes]
        Refuses when:
          - the branch does not match ``^research/(sweep|verify)-``
          - the branch is main
          - the working tree has uncommitted changes
          - the diff against the base ref has no ``research/`` change
          - the diff touches a path outside ``research/**`` or
            ``skills/marcus/references/**``
        Without --yes it prints the push and ``gh pr create`` commands.
        With --yes it runs them.

The ``gh`` command comes from ``DEMIURGE_GH``, split with shlex, default ``gh``.
Stdlib only; every subprocess call takes a list of arguments.

Usage:
    python scripts/research/sweep_pr.py prepare --date 2026-10-01
    python scripts/research/sweep_pr.py publish
    python scripts/research/sweep_pr.py publish --yes --title "..." --body-file body.md

--repo defaults to the current directory; publish runs against the checkout
that contains it, so run it from inside the sweep worktree.

Exit codes:
    0  success, or the dry-run commands were printed
    1  refused by a guard
    2  usage error, or a git or gh command failed
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

REMOTE = "origin"
MAIN = "main"
DEFAULT_BASE = f"{REMOTE}/{MAIN}"
BRANCH_RE = re.compile(r"^research/(sweep|verify)-")
ALLOWED_PREFIXES = ("research/", "skills/marcus/references/")
REQUIRED_PREFIX = "research/"


class GitError(RuntimeError):
    """A git or gh command exited non-zero."""


class Refused(RuntimeError):
    """A publish or prepare guard refused the request."""


def run(cmd: Sequence[str], cwd: Path) -> str:
    proc = subprocess.run(list(cmd), cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise GitError(f"{shlex.join(cmd)} exited {proc.returncode}: {detail}")
    return proc.stdout


def git(repo: Path, *args: str) -> str:
    return run(["git", *args], repo)


def ref_exists(repo: Path, ref: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def toplevel(path: Path) -> Path:
    return Path(git(path, "rev-parse", "--show-toplevel").strip()).resolve()


def gh_command() -> List[str]:
    raw = os.environ.get("DEMIURGE_GH", "").strip()
    return shlex.split(raw) if raw else ["gh"]


def sweep_names(date: dt.date) -> tuple[str, str]:
    stamp = date.isoformat()
    return f"research/sweep-{stamp}", f"scratch/sweep-{stamp}"


def prepare(repo: Path, date: dt.date, base: str) -> Path:
    root = toplevel(repo)
    branch, rel_worktree = sweep_names(date)
    worktree = root / rel_worktree
    git(root, "fetch", "--quiet", REMOTE, MAIN)
    if ref_exists(root, f"refs/heads/{branch}"):
        raise Refused(f"branch {branch} already exists locally")
    if ref_exists(root, f"refs/remotes/{REMOTE}/{branch}"):
        raise Refused(f"branch {branch} already exists on {REMOTE}")
    if git(root, "ls-remote", "--heads", REMOTE, branch).strip():
        raise Refused(f"branch {branch} already exists on {REMOTE}")
    if worktree.exists():
        raise Refused(f"worktree path {rel_worktree} already exists")
    git(root, "worktree", "add", "-b", branch, str(worktree), base)
    return worktree


def changed_paths(repo: Path, base: str) -> List[str]:
    out = git(repo, "diff", "--name-only", "--no-renames", f"{base}...HEAD")
    return [line.strip() for line in out.splitlines() if line.strip()]


def check_publish(repo: Path, base: str) -> tuple[str, List[str]]:
    """Return the branch and its changed paths, or raise Refused."""
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch in (MAIN, "HEAD"):
        raise Refused(f"refusing to publish from {branch}")
    if not BRANCH_RE.match(branch):
        raise Refused(f"branch {branch} does not match {BRANCH_RE.pattern}")
    if git(repo, "status", "--porcelain", "--untracked-files=no").strip():
        raise Refused("working tree has uncommitted changes; commit them first")
    paths = changed_paths(repo, base)
    if not any(path.startswith(REQUIRED_PREFIX) for path in paths):
        raise Refused(f"diff against {base} has no {REQUIRED_PREFIX} change")
    outside = [path for path in paths if not path.startswith(ALLOWED_PREFIXES)]
    if outside:
        listed = ", ".join(outside)
        raise Refused(f"diff touches paths outside {' or '.join(p + '**' for p in ALLOWED_PREFIXES)}: {listed}")
    return branch, paths


def default_body(branch: str, paths: Sequence[str]) -> str:
    lines = [f"Research changes from `{branch}`.", "", "Changed files:", ""]
    lines.extend(f"- `{path}`" for path in paths)
    return "\n".join(lines) + "\n"


def publish_commands(branch: str, title: str, body_file: Path) -> List[List[str]]:
    push = ["git", "push", "--set-upstream", REMOTE, f"refs/heads/{branch}:refs/heads/{branch}"]
    pr = [
        *gh_command(),
        "pr",
        "create",
        "--base",
        MAIN,
        "--head",
        branch,
        "--title",
        title,
        "--body-file",
        str(body_file),
    ]
    return [push, pr]


def publish(repo: Path, base: str, yes: bool, title: Optional[str], body_file: Optional[str]) -> int:
    root = toplevel(repo)
    git(root, "fetch", "--quiet", REMOTE, MAIN)
    branch, paths = check_publish(root, base)
    pr_title = title or f"research: {branch.split('/', 1)[1]}"
    if body_file:
        body_path = Path(body_file).resolve()
        if not body_path.is_file():
            print(f"ERROR: body file not found: {body_file}")
            return 2
    else:
        git_dir = Path(git(root, "rev-parse", "--absolute-git-dir").strip())
        body_path = git_dir / "SWEEP_PR_BODY.md"
        body_path.write_text(default_body(branch, paths), encoding="utf-8")
    commands = publish_commands(branch, pr_title, body_path)
    if not yes:
        print(f"OK: {branch} passes the publish guards ({len(paths)} changed files). Commands:")
        for cmd in commands:
            print(f"  {shlex.join(cmd)}")
        print("Re-run with --yes to execute them.")
        return 0
    for cmd in commands:
        out = run(cmd, root).strip()
        if out:
            print(out)
    print(f"OK: published {branch}")
    return 0


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0].strip())
    parser.add_argument("--repo", default=".", help="checkout to act on (default: current directory)")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"base ref (default: {DEFAULT_BASE})")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="create the sweep branch and worktree")
    prep.add_argument("--date", required=True, type=parse_date, help="sweep date, YYYY-MM-DD")
    pub = sub.add_parser("publish", help="push the branch and open the pull request")
    pub.add_argument("--yes", action="store_true", help="run the commands instead of printing them")
    pub.add_argument("--title", help="pull request title (default: research: <branch suffix>)")
    pub.add_argument("--body-file", help="pull request body file (default: list of changed files)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        if args.command == "prepare":
            worktree = prepare(repo, args.date, args.base)
            branch, _ = sweep_names(args.date)
            print(f"OK: created {branch} in {worktree}")
            return 0
        return publish(repo, args.base, args.yes, args.title, args.body_file)
    except Refused as exc:
        print(f"REFUSED: {exc}")
        return 1
    except GitError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
