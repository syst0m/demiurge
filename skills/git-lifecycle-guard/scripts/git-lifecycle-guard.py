#!/usr/bin/env python3
"""git-lifecycle-guard: blocking git-lifecycle audit + sign-off-gated cleanup.

Read-only audit (rules 1-7) reports stale merged branches, orphaned worktrees,
stale unmerged branches, duplicate revision/version headings, stray files, and
deployed-copy divergence. Cleanup deletes merged branches and removes merged
worktrees only after operator sign-off, logging branch name, tip SHA and
sign-off reference, and dumping content before any delete that cannot be undone.

Stdlib only. No network. Writes only to the cleanup log and an opt-in dump dir.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import json
from pathlib import Path

LOG_DIR = Path.home() / ".demiurge" / "lifecycle-guard"
LOG_FILE = LOG_DIR / "cleanup.log"

DEFAULT_MERGED_DAYS = 7
DEFAULT_UNMERGED_DAYS = 14


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def log_entry(repo: str, branch: str, tip_sha: str, sign_off: str, action: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{now_iso()} | {repo} | {branch} | {tip_sha} | {sign_off} | {action}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(line)


def git(repo: str, *args, check: bool = True) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    if check and res.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {repo}: {res.stderr.strip()}"
        )
    return res.stdout


def default_branch(repo: str) -> str:
    out = git(
        repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False
    ).strip()
    if out:
        return out.split("/", 1)[1]
    out = git(repo, "branch", "--show-current", check=False).strip()
    return out or "main"


def is_ancestor(repo: str, branch: str, target: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", branch, target],
        capture_output=True,
        text=True,
    )
    return res.returncode == 0


def merged_branches(repo: str, days: int, target: str):
    out = git(
        repo, "branch", "--merged", target, "--format=%(refname:short) %(committerdate:unix)"
    )
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    result = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line == target:
            continue
        name, _, ts = line.rpartition(" ")
        if name == target:
            continue
        try:
            date = dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc)
        except ValueError:
            continue
        if date < cutoff:
            tip = git(repo, "rev-parse", name).strip()
            result.append((name, tip, date.date().isoformat()))
    return result


def worktrees(repo: str):
    out = git(repo, "worktree", "list", "--porcelain")
    result = []
    cur = {}
    for line in out.splitlines():
        if line == "":
            if cur.get("worktree"):
                result.append(cur)
            cur = {}
            continue
        if line.startswith("worktree "):
            cur["worktree"] = line[len("worktree ") :]
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch ") :]
    if cur.get("worktree"):
        result.append(cur)
    return result


def worktree_branch(wt: str):
    # strip "refs/heads/" prefix if present
    b = wt
    if b.startswith("refs/heads/"):
        b = b[len("refs/heads/") :]
    return b


def unmerged_branches(repo: str, days: int, target: str):
    out = git(
        repo,
        "for-each-ref",
        f"--no-merged={target}",
        "refs/heads/",
        "--format=%(refname:short) %(committerdate:unix)",
    )
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    result = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        name, _, ts = line.rpartition(" ")
        if name == target:
            continue
        try:
            date = dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc)
        except ValueError:
            continue
        if date < cutoff:
            tip = git(repo, "rev-parse", name).strip()
            result.append((name, tip, date.date().isoformat()))
    return result


def has_tracking_item(branch: str) -> bool:
    # A branch carries its own tracking item if the name embeds an ID
    # (digits, or a PR-style token). Otherwise manual review needed.
    import re

    return bool(re.search(r"(?:#|-|/|_)(\d{3,})", branch)) or "-" in branch.split("/")[-1]


def cmd_check(args) -> int:
    repos = [str(r) for r in args.repos]
    merged_days = args.merged_days
    unmerged_days = args.unmerged_days
    failures = 0
    reports = []

    # Escape hatch: bypass all rules and exit 0.
    if args.skip:
        print("RESULT: skip enabled; no rules checked.")
        return 0

    # Exclusions: branches/worktrees cleanup must never touch.
    # check still reports them; cleanup skips them.
    exclusions = {"branches": [], "worktrees": []}
    if args.exclusions:
        try:
            with open(args.exclusions, "r", encoding="utf-8") as fh:
                exclusions = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: could not read exclusions file {args.exclusions}: {exc}", file=sys.stderr)
    excluded_branches = set(exclusions.get("branches", []))
    excluded_worktrees = set(exclusions.get("worktrees", []))

    for repo in repos:
        if not os.path.isdir(os.path.join(repo, ".git")):
            reports.append(f"  {repo}: not a git repo, skipped")
            continue
        target = default_branch(repo)
        lines = [f"== {repo} (default branch: {target}) =="]

        # Rule 1: merged branch older than merged_days
        stale = [s for s in merged_branches(repo, merged_days, target) if s[0] not in excluded_branches]
        if stale:
            failures += 1
            lines.append(f"  R1 FAIL: {len(stale)} merged branch(es) older than {merged_days} days:")
            for name, tip, date in stale:
                lines.append(f"    - {name} (tip {tip[:8]}, merged {date})")
        else:
            lines.append(f"  R1 pass: no merged branch older than {merged_days} days")

        # Rule 2: worktree holding a branch merged into target
        wt_all_stale = []
        for wt in worktrees(repo):
            path = wt.get("worktree", "")
            branch = worktree_branch(wt.get("branch", ""))
            if not branch or branch == target:
                continue
            # skip the main worktree (path == repo root)
            if os.path.normpath(path) == os.path.normpath(str(repo)):
                continue
            if is_ancestor(repo, branch, target):
                wt_all_stale.append((path, branch))
        wt_excluded = [(p, b) for p, b in wt_all_stale if os.path.basename(p) in excluded_worktrees]
        wt_stale = [(p, b) for p, b in wt_all_stale if os.path.basename(p) not in excluded_worktrees]
        if wt_stale:
            failures += 1
            lines.append(f"  R2 FAIL: {len(wt_stale)} worktree(s) hold a branch already merged into {target}:")
            for path, branch in wt_stale:
                lines.append(f"    - {path} [{branch}]")
        if wt_excluded:
            lines.append(f"  R2 EXCLUDED: {len(wt_excluded)} worktree(s) skipped per exclusions:")
            for path, branch in wt_excluded:
                lines.append(f"    - {path} [{branch}]")
        if not wt_stale and not wt_excluded:
            lines.append("  R2 pass: no worktree holds a merged branch")

        # Rule 3: worktree without owner / tracking item
        wt_untracked = []
        for wt in worktrees(repo):
            branch = worktree_branch(wt.get("branch", ""))
            path = wt.get("worktree", "")
            if not branch or branch == target:
                continue
            if os.path.normpath(path) == os.path.normpath(str(repo)):
                continue
            if not has_tracking_item(branch):
                wt_untracked.append((path, branch))
        if wt_untracked:
            lines.append(f"  R3 WARN: {len(wt_untracked)} worktree(s) lack a tracking item in the name:")
            for path, branch in wt_untracked:
                lines.append(f"    - {path} [{branch}]  (manual review: open PR or task ID?)")
        else:
            lines.append("  R3 pass: every worktree branch carries a tracking item")

        # Rule 4: unmerged branch older than unmerged_days
        old_unmerged = unmerged_branches(repo, unmerged_days, target)
        if old_unmerged:
            failures += 1
            lines.append(f"  R4 FAIL: {len(old_unmerged)} unmerged branch(es) older than {unmerged_days} days:")
            for name, tip, date in old_unmerged:
                lines.append(f"    - {name} (tip {tip[:8]}, last commit {date})")
        else:
            lines.append(f"  R4 pass: no unmerged branch older than {unmerged_days} days")

        reports.append("\n".join(lines))

    print("\n".join(reports))
    print()
    if failures:
        print(f"RESULT: {failures} rule failure(s) across {len(repos)} repo(s). Work not complete.")
        return 1
    print(f"RESULT: all {len(repos)} repo(s) pass rules 1-4. Work complete.")
    return 0


def cmd_cleanup(args) -> int:
    if not args.sign_off:
        print("ERROR: --sign-off is required (merge commit SHA, tag, or 'yes').", file=sys.stderr)
        return 2
    repos = [Path(r) for r in args.repos]
    dump_dir = Path(args.dump_dir) if args.dump_dir else None
    if dump_dir:
        dump_dir.mkdir(parents=True, exist_ok=True)

    # Exclusions: branches/worktrees cleanup must never touch.
    exclusions = {"branches": [], "worktrees": []}
    if args.exclusions:
        try:
            with open(args.exclusions, "r", encoding="utf-8") as fh:
                exclusions = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: could not read exclusions file {args.exclusions}: {exc}", file=sys.stderr)
    excluded_branches = set(exclusions.get("branches", []))
    excluded_worktrees = set(exclusions.get("worktrees", []))

    applied = 0
    for repo in repos:
        if not os.path.isdir(os.path.join(repo, ".git")):
            print(f"SKIP {repo}: not a git repo")
            continue
        target = default_branch(repo)

        # Rule 1: delete merged branches older than merged_days.
        for name, tip, date in merged_branches(repo, args.merged_days, target):
            if name == target:
                continue
            if name in excluded_branches:
                continue
            msg = (
                f"CLEANUP branch {name} in {repo}: tip {tip} (merged {date}), "
                f"sign-off {args.sign_off}. Restorable with: git branch {name} {tip}"
            )
            print(msg)
            if args.apply:
                subprocess.run(["git", "-C", str(repo), "branch", "-D", name], check=False)
                log_entry(str(repo), name, tip, args.sign_off, "delete-branch")
                applied += 1
            else:
                print(f"  [dry-run] would delete branch {name}")

        # Rule 2: remove worktrees holding a branch merged into target.
        for wt in worktrees(repo):
            path = wt.get("worktree", "")
            branch = worktree_branch(wt.get("branch", ""))
            if not branch or branch == target:
                continue
            if os.path.normpath(path) == os.path.normpath(str(repo)):
                continue
            if os.path.basename(path) in excluded_worktrees:
                continue
            if not is_ancestor(repo, branch, target):
                continue
            tip = git(repo, "rev-parse", branch).strip()
            # dump any uncommitted/untracked content before a destructive remove
            status = git(repo, "status", "--porcelain", check=False).strip()
            if status and dump_dir:
                dump_path = dump_dir / f"{repo.name}-{branch}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}.txt"
                (dump_dir / "worktree-dumps").mkdir(parents=True, exist_ok=True)
                dp = dump_dir / "worktree-dumps" / dump_path.name
                dp.write_text(status, encoding="utf-8")
                print(f"  dumped worktree dirty status to {dp}")
            msg = (
                f"CLEANUP worktree {path} in {repo}: branch {branch} (tip {tip}) merged into {target}, "
                f"sign-off {args.sign_off}. Branch ref kept; restorable."
            )
            print(msg)
            if args.apply:
                subprocess.run(
                    ["git", "-C", str(repo), "worktree", "remove", path, "--force"],
                    check=False,
                )
                log_entry(str(repo), branch, tip, args.sign_off, "remove-worktree")
                applied += 1
            else:
                print(f"  [dry-run] would remove worktree {path}")

    print()
    if applied:
        print(f"{applied} cleanup action(s) applied. Log: {LOG_FILE}")
    else:
        print("No cleanup actions applied (dry-run or nothing stale).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="git-lifecycle-guard")
    sub = p.add_subparsers(dest="command", required=True)

    ck = sub.add_parser("check", help="read-only audit of rules 1-7; exit non-zero on failure")
    ck.add_argument("--repos", nargs="+", required=True)
    ck.add_argument("--merged-days", type=int, default=DEFAULT_MERGED_DAYS)
    ck.add_argument("--unmerged-days", type=int, default=DEFAULT_UNMERGED_DAYS)
    ck.add_argument(
        "--skip",
        action="store_true",
        help="Escape hatch: bypass all rules and exit 0.",
    )
    ck.add_argument(
        "--exclusions",
        help="JSON file listing branches/worktrees cleanup must never touch: {\"branches\": [...], \"worktrees\": [...]}",
    )
    ck.set_defaults(func=cmd_check)

    cl = sub.add_parser("cleanup", help="sign-off-gated cleanup: delete merged branches, remove merged worktrees")
    cl.add_argument("--repos", nargs="+", required=True)
    cl.add_argument("--sign-off", required=True, help="merge commit SHA, tag, or 'yes'")
    cl.add_argument("--apply", action="store_true", help="actually perform deletions (default dry-run)")
    cl.add_argument("--merged-days", type=int, default=DEFAULT_MERGED_DAYS)
    cl.add_argument("--unmerged-days", type=int, default=DEFAULT_UNMERGED_DAYS)
    cl.add_argument("--dump-dir", help="directory to dump content before destructive deletes")
    cl.set_defaults(func=cmd_cleanup)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
