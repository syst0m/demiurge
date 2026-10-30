#!/usr/bin/env python3
"""Decide whether GitHub Actions can run for this repo, and block PR/CI actions when it cannot.

Modes:
  GITHUB  Actions can run (or the repo is public). GitHub PRs and workflows are preferred.
  LOCAL   Actions minutes are exhausted, or cannot be shown to exist. Use local test, merge, tag and
          release. PR and workflow commands are blocked.

An undetermined state is LOCAL: failing open is how agents end up opening a PR that never runs.

Usage:
  gh_minutes_gate.py --status [--refresh] [--json]
  gh_minutes_gate.py --hook                  # hook JSON on stdin; exit 2 blocks (Claude Code, Antigravity)
  gh_minutes_gate.py --command "<shell cmd>" # same decision for one command (OpenCode plugin)

Evidence order: GH_MINUTES_MODE override, 15-minute cache, public repo, the legacy quota endpoint,
then the repo's own recent Actions runs (billing-failure annotation means LOCAL, a recent success
means GITHUB). The billing usage-summary endpoint needs the `user` token scope and reports no
remaining quota, so it is not used.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CACHE_TTL_SECONDS = 15 * 60
GH_TIMEOUT_SECONDS = 15
RECENT_SUCCESS_SECONDS = 48 * 3600
MODES = ("github", "local")

BLOCKED = (
    re.compile(r"\bgh(?:\.exe)?\b.*?\bpr\b.*?\b(create|merge)\b", re.I),
    re.compile(r"\bgh(?:\.exe)?\b.*?\bworkflow\b.*?\brun\b", re.I),
    re.compile(r"\bgh(?:\.exe)?\b.*?\brun\b.*?\b(watch|rerun)\b", re.I),
)
BILLING_TEXT = re.compile(r"payments have failed|spending limit|minutes? (have been )?(used|exhausted)", re.I)

LOCAL_GUIDANCE = (
    "GitHub Actions minutes are unavailable ({reason}). Do not open PRs or rely on GitHub Actions.\n"
    "Use the local flow instead: run the repo's local checks, merge locally "
    "(git checkout main && git merge --no-ff <branch>), tag locally (git tag vX.Y.Z), and run the "
    "local release/deploy script.\n"
    "{repo_flow}"
    "Re-check with: python {script} --status --refresh. Override with GH_MINUTES_MODE=github|local."
)


def cache_path() -> Path:
    base = os.environ.get("GH_MINUTES_CACHE_DIR")
    root = Path(base) if base else Path.home() / ".cache" / "gh-minutes"
    return root / "state.json"


def run_gh(args: List[str], timeout: int = GH_TIMEOUT_SECONDS, **kwargs) -> Optional[Any]:
    """Run gh and return parsed JSON, or None on any failure, timeout or non-JSON output."""
    cwd = kwargs.get("cwd")
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout, cwd=str(cwd) if cwd else None)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def read_cache(key: str, now: float) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = data.get(key)
    if isinstance(entry, dict) and now - float(entry.get("at", 0)) < CACHE_TTL_SECONDS \
            and entry.get("mode") in MODES:
        return entry
    return None


def write_cache(key: str, mode: str, reason: str, now: float) -> None:
    path = cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[key] = {"mode": mode, "reason": reason, "at": now}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def _call_run_gh(args: List[str], cwd: Optional[Path | str] = None) -> Optional[Any]:
    if cwd is not None:
        try:
            return run_gh(args, cwd=cwd)
        except TypeError:
            return run_gh(args)
    return run_gh(args)


def quota_signal(owner: str, cwd: Optional[Path | str] = None) -> Optional[Tuple[str, str]]:
    """Legacy quota endpoint: authoritative when it answers, absent for many accounts."""
    for path in (f"/users/{owner}/settings/billing/actions", f"/orgs/{owner}/settings/billing/actions"):
        data = _call_run_gh(["api", path], cwd=cwd)
        if isinstance(data, dict) and "included_minutes" in data and "total_minutes_used" in data:
            left = float(data["included_minutes"]) - float(data["total_minutes_used"])
            if left <= 0:
                return "local", "quota endpoint reports 0 included minutes left"
            return "github", f"quota endpoint reports {left:.0f} minutes left"
    return None


def run_evidence(repo: str, cwd: Optional[Path | str] = None) -> Optional[Tuple[str, str]]:
    runs = _call_run_gh(["run", "list", "--repo", repo, "--limit", "3",
                        "--json", "databaseId,conclusion,createdAt"], cwd=cwd)
    if not isinstance(runs, list) or not runs:
        return None
    latest = runs[0]
    if latest.get("conclusion") == "failure":
        jobs = _call_run_gh(["api", f"repos/{repo}/actions/runs/{latest['databaseId']}/jobs"], cwd=cwd)
        for job in (jobs or {}).get("jobs", []):
            notes = _call_run_gh(["api", f"repos/{repo}/check-runs/{job['id']}/annotations"], cwd=cwd) or []
            if any(BILLING_TEXT.search(str(n.get("message", ""))) for n in notes):
                return "local", "latest Actions run failed with a billing annotation"
    for item in runs:
        if item.get("conclusion") == "success":
            stamp = item.get("createdAt", "")
            try:
                age = time.time() - calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
            except ValueError:
                continue
            if age < RECENT_SUCCESS_SECONDS:
                return "github", "an Actions run succeeded in the last 48 hours"
    return None


def detect(refresh: bool = False, now: Optional[float] = None, cwd: Optional[Path | str] = None) -> Dict[str, str]:
    now = time.time() if now is None else now
    forced = os.environ.get("GH_MINUTES_MODE", "").strip().lower()
    if forced in MODES:
        return {"mode": forced, "reason": "GH_MINUTES_MODE override", "source": "env"}
    info = _call_run_gh(["repo", "view", "--json", "nameWithOwner,isPrivate"], cwd=cwd)
    if not isinstance(info, dict) or "nameWithOwner" not in info:
        return {"mode": "local", "reason": "no GitHub repo or gh unavailable (fail closed)", "source": "default"}
    repo = info["nameWithOwner"]
    if not refresh:
        hit = read_cache(repo, now)
        if hit:
            return {"mode": hit["mode"], "reason": hit["reason"], "source": "cache"}
    if info.get("isPrivate") is False:
        found: Optional[Tuple[str, str]] = ("github", "public repo: Actions minutes are free")
    else:
        found = quota_signal(repo.split("/")[0], cwd=cwd) or run_evidence(repo, cwd=cwd)
    mode, reason = found or ("local", "could not confirm minutes (fail closed)")
    write_cache(repo, mode, reason, now)
    return {"mode": mode, "reason": reason, "source": "live"}


def blocked_command(command: str) -> bool:
    if not command:
        return False
    for part in re.split(r"&&|\|\||[;\n|]", command):
        if any(p.search(part) for p in BLOCKED):
            return True
    return False


def command_from_hook(payload: Dict[str, Any]) -> str:
    tool_call = payload.get("toolCall") or {}
    args = tool_call.get("args") or payload.get("tool_input") or payload.get("toolInput") or payload.get("args") or {}
    if isinstance(args, str):
        return args
    if isinstance(args, dict):
        for key in ("CommandLine", "commandLine", "command", "cmd"):
            val = args.get(key)
            if isinstance(val, str):
                return val
    return ""


def repo_flow(cwd: Optional[Path | str] = None) -> str:
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             timeout=5, cwd=str(cwd) if cwd else None).stdout.strip()
        spec = json.loads((Path(top) / ".agents" / "local-ci.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ""
    lines = [f"  {k}: {v}" for k, v in spec.items() if isinstance(v, str)]
    return "This repo's local flow (.agents/local-ci.json):\n" + "\n".join(lines) + "\n" if lines else ""


def decide(command: str, cwd: Optional[Path | str] = None) -> Tuple[int, str]:
    """Return (exit_code, message). Only blocked commands cost a detect() call."""
    if not command or not blocked_command(command):
        return 0, ""
    state = detect(cwd=cwd)
    if state["mode"] == "github":
        return 0, ""
    return 2, LOCAL_GUIDANCE.format(reason=state["reason"], repo_flow=repo_flow(cwd=cwd), script=Path(__file__).resolve())


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--command")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.status:
        state = detect(refresh=args.refresh)
        print(json.dumps(state) if args.json else f"{state['mode'].upper()}: {state['reason']} [{state['source']}]")
        return 0
    command = args.command if args.command is not None else ""
    is_antigravity = False
    cwd = None
    if args.hook:
        try:
            if hasattr(sys.stdin, "buffer"):
                raw = sys.stdin.buffer.read().decode("utf-8-sig", "replace")
            else:
                raw = sys.stdin.read().lstrip("\ufeff")
            payload = json.loads(raw or "{}")
            is_antigravity = bool(payload.get("toolCall") or payload.get("conversationId"))
            command = command_from_hook(payload)
            ws_paths = payload.get("workspacePaths") or []
            if ws_paths:
                cwd = ws_paths[0]
        except ValueError:
            if is_antigravity:
                print(json.dumps({"decision": "allow"}))
            return 0
    code, message = decide(command, cwd=cwd)
    if is_antigravity:
        if code != 0:
            print(json.dumps({"decision": "deny", "reason": message}))
        else:
            print(json.dumps({"decision": "allow"}))
        return 0
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
