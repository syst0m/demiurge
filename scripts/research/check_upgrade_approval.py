#!/usr/bin/env python3
"""
check_upgrade_approval.py - Require an owner approval bound to the PR head SHA.

A research PR whose ``claims_diff.py`` class is ``upgrade`` passes only when a
PR comment carries the owner's approval for the exact head commit. The script
reads every issue comment on the PR with

    gh api repos/<repository>/issues/<pr>/comments --paginate

and passes when one comment meets all of these:

  - ``user.login`` equals ``--owner``
  - ``user.type`` is ``User``
  - ``user.login`` differs from ``--deny-login`` (the routine's bot login)
  - a line of the body matches ``^/approve-upgrade ([0-9a-f]{40})$`` and the
    SHA equals ``--head-sha``

A new push changes the head SHA, so it voids every earlier approval. No
timestamps are involved. The order is: the verifier pushes its records, the
owner comments ``/approve-upgrade <final head SHA>``, then the owner re-runs
the failed job.

The ``gh`` command comes from ``DEMIURGE_GH``, split with shlex, default
``gh``. The repository comes from ``--repository``, then
``GITHUB_REPOSITORY``, then the ``{owner}/{repo}`` placeholder that ``gh``
fills from the current checkout. Stdlib only; every subprocess call takes a
list of arguments.

Usage:
    python scripts/research/check_upgrade_approval.py --pr 42 \\
        --head-sha <40 hex> --owner <login> [--deny-login <bot login>]

An empty --deny-login denies nothing, so the check still requires the owner.

Exit codes:
    0  an owner comment approves the head SHA
    1  no comment approves the head SHA
    2  usage error, or the gh call failed or returned malformed JSON
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from typing import Any, Iterable, List, Mapping, Optional, Sequence

APPROVE_RE = re.compile(r"^/approve-upgrade ([0-9a-f]{40})$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USER_TYPE = "User"
REPO_PLACEHOLDER = "{owner}/{repo}"


class GhError(RuntimeError):
    """The gh call failed or returned something other than comment arrays."""


def gh_command() -> List[str]:
    raw = os.environ.get("DEMIURGE_GH", "").strip()
    return shlex.split(raw) if raw else ["gh"]


def parse_pages(text: str) -> List[Mapping[str, Any]]:
    """Parse ``gh api --paginate`` output: one JSON array per page, back to back."""
    decoder = json.JSONDecoder()
    comments: List[Mapping[str, Any]] = []
    pos = 0
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            return comments
        try:
            page, pos = decoder.raw_decode(text, pos)
        except json.JSONDecodeError as exc:
            raise GhError(f"gh api returned malformed JSON: {exc}") from exc
        if not isinstance(page, list):
            raise GhError(f"gh api returned a {type(page).__name__}, expected a list of comments")
        for item in page:
            if not isinstance(item, dict):
                raise GhError("gh api returned a comment that is not an object")
            comments.append(item)


def fetch_comments(repository: str, pr: int) -> List[Mapping[str, Any]]:
    cmd = [*gh_command(), "api", f"repos/{repository}/issues/{pr}/comments", "--paginate"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise GhError(f"{shlex.join(cmd)} exited {proc.returncode}: {detail}")
    return parse_pages(proc.stdout)


def approved_shas(body: str) -> List[str]:
    shas = []
    for line in body.splitlines():
        match = APPROVE_RE.match(line.strip())
        if match:
            shas.append(match.group(1))
    return shas


def find_approval(
    comments: Iterable[Mapping[str, Any]],
    head_sha: str,
    owner: str,
    deny_login: str = "",
) -> Optional[Mapping[str, Any]]:
    """Return the first comment that approves ``head_sha``, or None."""
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict):
            continue
        login = user.get("login")
        if login != owner or user.get("type") != USER_TYPE:
            continue
        if deny_login and login == deny_login:
            continue
        body = comment.get("body")
        if isinstance(body, str) and head_sha in approved_shas(body):
            return comment
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Require an owner /approve-upgrade comment for the PR head SHA.")
    parser.add_argument("--pr", required=True, type=int, help="pull request number")
    parser.add_argument("--head-sha", required=True, help="PR head commit, 40 lowercase hex")
    parser.add_argument("--owner", required=True, help="login whose approval counts")
    parser.add_argument("--deny-login", default="", help="login that never counts, such as the routine bot")
    parser.add_argument("--repository", help="OWNER/NAME (default: GITHUB_REPOSITORY, then the current checkout)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    head_sha = args.head_sha.strip()
    owner = args.owner.strip()
    deny_login = args.deny_login.strip()
    if not SHA_RE.match(head_sha):
        print(f"ERROR: --head-sha must be 40 lowercase hex characters, got {args.head_sha!r}")
        return 2
    if not owner:
        print("ERROR: --owner is empty")
        return 2
    repository = args.repository or os.environ.get("GITHUB_REPOSITORY", "").strip() or REPO_PLACEHOLDER
    try:
        comments = fetch_comments(repository, args.pr)
    except GhError as exc:
        print(f"ERROR: {exc}")
        return 2
    except OSError as exc:
        print(f"ERROR: could not run gh: {exc}")
        return 2
    approval = find_approval(comments, head_sha, owner, deny_login)
    if approval is None:
        print(f"FAIL: no /approve-upgrade {head_sha} comment from {owner} on PR #{args.pr}.")
        print(f"The owner comments '/approve-upgrade {head_sha}' after the last push, then re-runs this job.")
        return 1
    where = approval.get("html_url") or f"comment {approval.get('id', '?')}"
    print(f"OK: {owner} approved upgrade at {head_sha} ({where}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
