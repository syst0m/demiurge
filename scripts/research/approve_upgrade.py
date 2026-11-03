#!/usr/bin/env python3
"""
approve_upgrade.py - Post the owner's /approve-upgrade comment after a human confirms.

Shows the pull request, its head SHA and the changed files, asks for one
confirmation, posts ``/approve-upgrade <head SHA>`` and re-runs the failed
``research-approval`` job. It works only for a person:

  - stdin and stdout must be a terminal, so an agent or a pipe cannot answer
  - the signed-in ``gh`` user must be the approver (``--approver``, default the
    repository owner), so another account cannot approve
  - the head SHA is read again after the confirmation, and a push in between
    cancels the approval

The comment is the one ``check_upgrade_approval.py`` looks for. Run it from the
Terminal panel and answer ``y``.

Usage:
    python scripts/research/approve_upgrade.py <pr> [--approver <login>]

Exit codes:
    0  approved and the job re-run (or no failed job to re-run)
    1  the person declined, or the head moved
    2  not a terminal, wrong user, pull request not open, or a gh call failed
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Callable, List, Optional, Sequence, Tuple

from check_upgrade_approval import gh_command

APPROVAL_JOB = "research-approval"
RUN_ID_RE = re.compile(r"/runs/(\d+)")
MAX_FILES = 30

Gh = Callable[[Sequence[str]], Tuple[int, str]]


def run_gh(args: Sequence[str]) -> Tuple[int, str]:
    proc = subprocess.run([*gh_command(), *args], capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, proc.stdout if proc.returncode == 0 or proc.stdout else proc.stderr


def gh_json(gh: Gh, args: Sequence[str], *, allow_failure: bool = False):
    code, out = gh(args)
    if code != 0 and not allow_failure:
        raise RuntimeError(f"gh {' '.join(args)} exited {code}: {out.strip()}")
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh {' '.join(args)} returned malformed JSON: {exc}") from exc


def head_sha(gh: Gh, pr: str) -> str:
    return gh_json(gh, ["pr", "view", pr, "--json", "headRefOid"])["headRefOid"]


def failed_job_run_id(gh: Gh, pr: str) -> Optional[str]:
    # gh pr checks exits non-zero while a check fails, and still prints the JSON.
    checks = gh_json(gh, ["pr", "checks", pr, "--json", "name,bucket,link"], allow_failure=True)
    for check in checks:
        if check.get("name") == APPROVAL_JOB and check.get("bucket") == "fail":
            match = RUN_ID_RE.search(check.get("link", ""))
            return match.group(1) if match else None
    return None


def run(
    pr: str,
    approver: str,
    *,
    gh: Gh = run_gh,
    ask: Callable[[str], str] = input,
    interactive: bool,
    out=print,
) -> int:
    if not interactive:
        out("Refused: run this from a terminal. An agent or a pipe cannot approve.")
        return 2
    try:
        info = gh_json(gh, ["pr", "view", pr, "--json", "state,title,url,headRefOid,files"])
        if info["state"] != "OPEN":
            out(f"Refused: PR {pr} is {info['state']}, not OPEN.")
            return 2
        who = gh_json(gh, ["api", "user"])["login"]
        approver = approver or gh_json(gh, ["repo", "view", "--json", "owner"])["owner"]["login"]
        if who != approver:
            out(f"Refused: signed in as {who}, but the approver is {approver}.")
            return 2

        sha = info["headRefOid"]
        files: List[str] = [f["path"] for f in info["files"]]
        out(f"\n{info['title']}\n{info['url']}\nhead {sha}\n{len(files)} changed file(s):")
        out("\n".join(f"  {p}" for p in files[:MAX_FILES]))
        if len(files) > MAX_FILES:
            out(f"  ... and {len(files) - MAX_FILES} more")
        if ask(f"\nPost /approve-upgrade for {sha[:7]} as {who}? [y/N] ").strip().lower() != "y":
            out("Cancelled. Nothing posted.")
            return 1
        if head_sha(gh, pr) != sha:
            out("Cancelled: the head changed after you read the diff. Run this again.")
            return 1

        code, text = gh(["pr", "comment", pr, "--body", f"/approve-upgrade {sha}"])
        if code != 0:
            raise RuntimeError(f"gh pr comment exited {code}: {text.strip()}")
        out(f"Posted /approve-upgrade {sha}")

        run_id = failed_job_run_id(gh, pr)
        if run_id is None:
            out(f"No failed {APPROVAL_JOB} job to re-run.")
            return 0
        code, text = gh(["run", "rerun", run_id, "--failed"])
        if code != 0:
            raise RuntimeError(f"gh run rerun exited {code}: {text.strip()}")
        out(f"Re-running {APPROVAL_JOB} (run {run_id}).")
        return 0
    except (RuntimeError, KeyError) as exc:
        out(f"Error: {exc}")
        return 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Post the owner's /approve-upgrade comment.")
    parser.add_argument("pr", help="pull request number")
    parser.add_argument("--approver", default="", help="login allowed to approve (default: repository owner)")
    args = parser.parse_args(argv)
    return run(args.pr, args.approver, interactive=sys.stdin.isatty() and sys.stdout.isatty())


if __name__ == "__main__":
    sys.exit(main())
