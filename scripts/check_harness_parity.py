#!/usr/bin/env python3
"""Gate: every skill in this repo is deployed, and current, in every installed harness.

Harness libraries checked (a harness whose home directory does not exist is skipped, as
scripts/sync-skills.sh skips it):

  claude-code   ~/.claude/skills
  antigravity   ~/.gemini/config/skills
  opencode      ~/.config/opencode/skills
  hermes        ~/.hermes/skills/agent-skills

Plugins: with --plugin or --profile, a skill that an installed plugin provides (plugins/registry.json)
is "covered" when no standalone copy exists, and "duplicate" (a failure) when one does.

Exit codes: 0 every installed harness holds a current copy of every skill, 1 a copy is missing,
stale or duplicated. A library that resolves to the same directory as an earlier one is reported once.
The fix for a failure is the user's step: scripts/sync-skills.sh with no flags.

Usage: check_harness_parity.py [--repo <dir>] [--json]
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plugin_registry as plugreg  # noqa: E402

HARNESS_LIBRARIES = {
    "claude-code": (".claude", "skills"),
    "antigravity": (".gemini/config", "skills"),
    "opencode": (".config/opencode", "skills"),
    "hermes": (".hermes", "skills/agent-skills"),  # on Windows: %LOCALAPPDATA%/hermes (see hermes_home)
}
IGNORED = ("__pycache__", "*.pyc", "results-*.json", "transcripts-*.json", "last_run.json")


def tree(root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or any(fnmatch.fnmatch(part, pat) for part in rel.parts for pat in IGNORED):
            continue
        out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def plugin_provided(plugins: Iterable[str]) -> Dict[str, set]:
    """Per harness, the skills that an installed plugin provides. Empty when no plugins are named."""
    names = list(plugins)
    if not names:
        return {}
    registry = plugreg.load_registry()
    out: Dict[str, set] = {}
    for harness in plugreg.HARNESSES:
        rows = plugreg.plan(harness, names, registry)
        out[harness] = plugreg.exclusions(rows, registry)
    return out


def hermes_home(home: Path) -> Path:
    """Hermes keeps its skills under %LOCALAPPDATA%/hermes on Windows, not under ~/.hermes."""
    import os
    local = os.environ.get("LOCALAPPDATA")
    if local and home == Path.home() and (Path(local) / "hermes").is_dir():
        return Path(local) / "hermes"
    return home / ".hermes"


def check(repo: Path, home: Path, provided: Optional[Dict[str, set]] = None) -> List[Dict[str, str]]:
    """provided: harness -> skills an installed plugin supplies. Those skills must NOT also be
    deployed standalone (DUPLICATE). A missing one is covered, not MISSING."""
    provided = provided or {}
    findings: List[Dict[str, str]] = []
    seen: Dict[Path, str] = {}
    skills = sorted(p for p in (repo / "skills").iterdir() if p.is_dir())
    for harness, (harness_home, sub) in HARNESS_LIBRARIES.items():
        base = hermes_home(home) if harness == "hermes" else home / harness_home
        if not base.is_dir():
            findings.append({"harness": harness, "skill": "*", "state": "skipped", "detail": "harness not installed"})
            continue
        library = base / sub
        real = library.resolve()
        if real in seen:
            findings.append({"harness": harness, "skill": "*", "state": "skipped",
                             "detail": f"same directory as {seen[real]}"})
            continue
        seen[real] = harness
        covered = provided.get(harness, set())
        for skill in skills:
            deployed = library / skill.name
            if skill.name in covered:
                if deployed.exists():
                    findings.append({"harness": harness, "skill": skill.name, "state": "duplicate",
                                     "detail": f"{deployed} (a plugin also provides it)"})
                else:
                    findings.append({"harness": harness, "skill": skill.name, "state": "covered",
                                     "detail": "provided by an installed plugin"})
            elif not deployed.is_dir():
                findings.append({"harness": harness, "skill": skill.name, "state": "missing", "detail": str(deployed)})
            elif tree(skill) != tree(deployed):
                findings.append({"harness": harness, "skill": skill.name, "state": "stale", "detail": str(deployed)})
            else:
                findings.append({"harness": harness, "skill": skill.name, "state": "ok", "detail": str(deployed)})
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--plugin", action="append", default=[],
                        help="registry plugin name counted as installed where its harness supports it; repeatable")
    parser.add_argument("--profile", type=Path, action="append", default=[],
                        help="profile JSON whose plugins count as installed; repeatable")
    args = parser.parse_args(argv)
    names = list(args.plugin)
    for prof in args.profile:
        names += json.loads(prof.read_text(encoding="utf-8")).get("plugins", [])
    findings = check(args.repo.resolve(), args.home, plugin_provided(names))
    failed = [f for f in findings if f["state"] in ("missing", "stale", "duplicate")]
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"{f['state'].upper():8} {f['harness']:12} {f['skill']}  {f['detail'] if f['state'] != 'ok' else ''}".rstrip())
        if failed:
            print("\nHarness parity failed. Deploy with: bash scripts/sync-skills.sh (the user's step; "
                  "agents run only --check --repo-only).", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
