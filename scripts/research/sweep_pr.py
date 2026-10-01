#!/usr/bin/env python3
"""
sweep_pr.py - Prepare and publish a research sweep branch as a pull request.

The research routine never pushes by hand. It runs ``prepare`` to get a fresh
worktree on a new branch, edits files there, commits, and runs ``publish``.
``publish`` is the sweep's only push path, and it refuses anything that is not
a research-only change on a research branch. ``push-verification`` is the
verifier's only push path.

    prepare --date YYYY-MM-DD
        Creates branch ``research/sweep-<date>`` from the base ref and checks it
        out in the worktree ``scratch/sweep-<date>``. Refuses when the branch
        exists locally or on the remote, or when the worktree path exists.

    publish [--yes]
        Refuses when:
          - --base is given and does not resolve to the same commit as origin/main
          - the branch does not match ``^research/(sweep|verify)-``
          - the branch is main
          - the working tree has uncommitted changes
          - the diff against origin/main has no ``research/`` change
          - the diff is out of scope (see check-scope)
        Without --yes it prints the push and ``gh pr create`` commands.
        With --yes it runs them.

    check-scope
        The scope guard alone, for CI. The diff against the base ref may touch
        ``research/**`` and ``skills/marcus/references/**``, plus the one
        ``RESEARCH.md v<version> (<date>) snapshot_sha256:<hex>`` line of
        ``skills/marcus/AGENT_ARCHITECTURE.md`` that ``update_marcus.py --apply``
        re-pins. Any other path, or any other line of that file, is refused.

    push-verification --pr N [--yes]
        The verifier routine's only push path. Looks up pull request N with
        ``gh pr view`` and refuses when its head branch does not match
        ``^research/sweep-``, when it comes from a fork, when ``origin/<branch>``
        is not the pull request's head commit, when HEAD does not descend from
        it, when the working tree is dirty, or when the new commits touch
        anything outside ``research/verifications/**``. Then it pushes HEAD to
        that branch without force.

The ``gh`` command comes from ``DEMIURGE_GH``, split with shlex, default ``gh``.
Stdlib only; every subprocess call takes a list of arguments.

Usage:
    python scripts/research/sweep_pr.py prepare --date 2026-10-01
    python scripts/research/sweep_pr.py publish
    python scripts/research/sweep_pr.py publish --yes --title "..." --body-file body.md
    python scripts/research/sweep_pr.py --base origin/main check-scope
    python scripts/research/sweep_pr.py push-verification --pr 42 --yes

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
import json
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
SWEEP_BRANCH_RE = re.compile(r"^research/sweep-[A-Za-z0-9._-]+$")
ALLOWED_PREFIXES = ("research/", "skills/marcus/references/")
REQUIRED_PREFIX = "research/"
ARCH_PATH = "skills/marcus/AGENT_ARCHITECTURE.md"
ARCH_PIN_RE = re.compile(
    r"^[ \t]*-[ \t]+RESEARCH\.md[ \t]+v[\d.]+[ \t]+\([\d-]+\)[ \t]+snapshot_sha256:[0-9a-f]{64}(?:[ \t]+#[^\n]*)?$"
)
VERIFICATION_PREFIX = "research/verifications/"


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


def arch_pin_only(repo: Path, base: str) -> bool:
    """True when the AGENT_ARCHITECTURE.md diff changes only its derived_from RESEARCH.md pin line."""
    out = git(repo, "diff", "--no-color", "--no-ext-diff", "--unified=0", f"{base}...HEAD", "--", ARCH_PATH)
    removed: List[str] = []
    added: List[str] = []
    for line in out.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    if len(removed) != 1 or len(added) != 1:
        return False
    return all(ARCH_PIN_RE.match(text) for text in removed + added)


def scope_violations(repo: Path, base: str, paths: Sequence[str]) -> List[str]:
    """Changed paths a research branch may not touch."""
    outside = []
    for path in paths:
        if path.startswith(ALLOWED_PREFIXES):
            continue
        if path == ARCH_PATH and arch_pin_only(repo, base):
            continue
        outside.append(path if path != ARCH_PATH else f"{path} (lines other than the derived_from pin)")
    return outside


def check_scope(repo: Path, base: str) -> List[str]:
    """Return the changed paths, or raise Refused when any is out of scope."""
    paths = changed_paths(repo, base)
    outside = scope_violations(repo, base, paths)
    if outside:
        allowed = " or ".join(p + "**" for p in ALLOWED_PREFIXES)
        raise Refused(
            f"diff touches paths outside {allowed} and the {ARCH_PATH} derived_from pin: {', '.join(outside)}"
        )
    return paths


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
    check_scope(repo, base)
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


def rev(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip()


def publish(repo: Path, base: str, yes: bool, title: Optional[str], body_file: Optional[str]) -> int:
    root = toplevel(repo)
    git(root, "fetch", "--quiet", REMOTE, MAIN)
    # The pull request always targets main, so the guards must judge the diff against main.
    if base != DEFAULT_BASE and rev(root, base) != rev(root, DEFAULT_BASE):
        raise Refused(f"--base {base} is not {DEFAULT_BASE}; publish opens the pull request against {MAIN}")
    branch, paths = check_publish(root, DEFAULT_BASE)
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


def pr_head(repo: Path, pr: int) -> tuple[str, str, bool]:
    """(head branch, head commit, from a fork) for pull request ``pr``."""
    out = run([*gh_command(), "pr", "view", str(pr), "--json", "headRefName,headRefOid,isCrossRepository"], repo)
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise GitError(f"gh pr view returned malformed JSON: {exc}") from exc
    branch, oid, cross = data.get("headRefName"), data.get("headRefOid"), data.get("isCrossRepository")
    if not isinstance(branch, str) or not isinstance(oid, str) or not isinstance(cross, bool):
        raise GitError("gh pr view is missing headRefName, headRefOid or isCrossRepository")
    return branch, oid, cross


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=str(repo), capture_output=True, text=True
    )
    if proc.returncode not in (0, 1):
        raise GitError(f"git merge-base --is-ancestor exited {proc.returncode}: {proc.stderr.strip()}")
    return proc.returncode == 0


def push_verification(repo: Path, pr: int, yes: bool) -> int:
    root = toplevel(repo)
    branch, pr_oid, cross = pr_head(root, pr)
    if cross:
        raise Refused(f"pull request #{pr} comes from a fork")
    if not SWEEP_BRANCH_RE.match(branch):
        raise Refused(f"pull request #{pr} head {branch} does not match {SWEEP_BRANCH_RE.pattern}")
    tracking = f"refs/remotes/{REMOTE}/{branch}"
    git(root, "fetch", "--quiet", REMOTE, f"+refs/heads/{branch}:{tracking}")
    remote_oid = rev(root, tracking)
    if remote_oid != pr_oid:
        raise Refused(f"{REMOTE}/{branch} is at {remote_oid}, but pull request #{pr} head is {pr_oid}")
    if git(root, "status", "--porcelain", "--untracked-files=no").strip():
        raise Refused("working tree has uncommitted changes; commit them first")
    head_oid = rev(root, "HEAD")
    if head_oid == remote_oid:
        raise Refused(f"HEAD has no commits on top of {REMOTE}/{branch}")
    if not is_ancestor(root, remote_oid, head_oid):
        raise Refused(f"HEAD does not descend from {REMOTE}/{branch}; refusing a non-fast-forward push")
    out = git(root, "diff", "--name-only", "--no-renames", f"{remote_oid}..{head_oid}")
    paths = [line.strip() for line in out.splitlines() if line.strip()]
    outside = [path for path in paths if not path.startswith(VERIFICATION_PREFIX)]
    if not paths or outside:
        raise Refused(f"new commits must touch only {VERIFICATION_PREFIX}**; found: {', '.join(outside) or 'nothing'}")
    push = ["git", "push", REMOTE, f"{head_oid}:refs/heads/{branch}"]
    if not yes:
        print(f"OK: {head_oid} passes the verification push guards ({len(paths)} changed files). Command:")
        print(f"  {shlex.join(push)}")
        print("Re-run with --yes to execute it.")
        return 0
    out = run(push, root).strip()
    if out:
        print(out)
    print(f"OK: pushed {head_oid} to {branch}")
    return 0


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}")
    return number


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
    sub.add_parser("check-scope", help="refuse a diff against --base that is out of research scope")
    ver = sub.add_parser("push-verification", help="push verification records to a sweep pull request branch")
    ver.add_argument("--pr", required=True, type=positive_int, help="pull request number")
    ver.add_argument("--yes", action="store_true", help="run the push instead of printing it")
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
        if args.command == "check-scope":
            paths = check_scope(toplevel(repo), args.base)
            print(f"OK: {len(paths)} changed files are in research scope")
            return 0
        if args.command == "push-verification":
            return push_verification(repo, args.pr, args.yes)
        return publish(repo, args.base, args.yes, args.title, args.body_file)
    except Refused as exc:
        print(f"REFUSED: {exc}")
        return 1
    except GitError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
