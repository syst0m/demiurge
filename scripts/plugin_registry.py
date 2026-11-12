#!/usr/bin/env python3
"""Decide which harness plugins to use, so skills are not deployed twice.

A plugin is used only where its harness supports it and it is installed there.
A plugin that the harness supports but that is not installed falls back to
standalone skills, and the install hint is printed. Sync never installs plugin code.

Status per (harness, plugin):
  use          supported and installed. Its provided skills are excluded from standalone deploy.
  fallback     supported but not installed. Standalone skills are deployed; hint printed.
  unsupported  the registry has no build of this plugin for this harness.

Registry: agent-skills/plugins/registry.json (one entry per plugin).

Usage:
  python scripts/plugin_registry.py status --harness claude-code --profile profiles/global.json
  python scripts/plugin_registry.py exclusions --harness hermes --bundle baseline-coding
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set

HARNESSES = ("antigravity", "claude-code", "hermes")


def _home() -> Path:
    return Path.home()


def hermes_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(_home() / "AppData" / "Local"))) / "hermes"


def registry_path() -> Path:
    """agent-skills/plugins/registry.json, found the same way sync_bundles finds bundles."""
    env = os.environ.get("DEMIURGE_AGENT_SKILLS")
    here = Path(__file__).resolve().parent.parent
    candidates = [Path(env)] if env else []
    candidates += [here.parent / "agent-skills", _home() / "Documents" / "code" / "agent-skills"]
    for c in candidates:
        if (c / "plugins" / "registry.json").is_file():
            return c / "plugins" / "registry.json"
    raise SystemExit("ERROR: plugins/registry.json not found; set DEMIURGE_AGENT_SKILLS")


def load_registry(path: Optional[Path] = None) -> Dict[str, dict]:
    data = json.loads((path or registry_path()).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def installed_probe(harness: str, plugin_id: str) -> bool:
    """True when the harness has this plugin on disk. Reads only; never writes."""
    if harness == "claude-code":
        f = _home() / ".claude" / "plugins" / "installed_plugins.json"
        if not f.is_file():
            return False
        data = json.loads(f.read_text(encoding="utf-8"))
        plugins = data.get("plugins", data)
        return plugin_id in plugins
    if harness == "hermes":
        return (hermes_root() / "plugins" / plugin_id / "plugin.yaml").is_file()
    if harness == "antigravity":
        return (_home() / ".gemini" / "config" / "plugins" / plugin_id).is_dir()
    return False


def hint(harness: str, name: str, plugin_id: str) -> str:
    if harness == "claude-code":
        return f"install with: /plugin install {plugin_id}"
    return f"install the '{name}' plugin in {harness}, then re-run sync"


def plan(harness: str, names: Iterable[str], registry: Dict[str, dict],
         probe: Callable[[str, str], bool] = installed_probe) -> List[dict]:
    """One row per plugin name. Unknown names are reported as unsupported."""
    rows = []
    for name in names:
        entry = registry.get(name)
        plugin_id = entry["harness"].get(harness) if entry else None
        if not plugin_id:
            rows.append({"name": name, "status": "unsupported", "id": None, "hint": ""})
            continue
        status = "use" if probe(harness, plugin_id) else "fallback"
        rows.append({"name": name, "status": status, "id": plugin_id,
                     "hint": "" if status == "use" else hint(harness, name, plugin_id)})
    return rows


def exclusions(rows: Iterable[dict], registry: Dict[str, dict]) -> Set[str]:
    """Skill names that a plugin in use already provides."""
    skills: Set[str] = set()
    for row in rows:
        if row["status"] == "use":
            skills.update(registry[row["name"]].get("provides_skills", []))
    return skills


def names_from_profile_or_bundle(profile: Optional[Path], bundle_dirs: Iterable[Path],
                                 bundles: Iterable[str]) -> List[str]:
    names: List[str] = []
    if profile:
        names += json.loads(profile.read_text(encoding="utf-8")).get("plugins", [])
    for b in bundles:
        for d in bundle_dirs:
            m = d / b / "bundle.json"
            if m.is_file():
                names += json.loads(m.read_text(encoding="utf-8")).get("plugins", [])
                break
    return list(dict.fromkeys(names))


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("status", "exclusions"):
        s = sub.add_parser(cmd)
        s.add_argument("--harness", required=True, choices=HARNESSES)
        s.add_argument("--profile", type=Path)
        s.add_argument("--bundle", action="append", default=[])
        s.add_argument("--bundles-dir", type=Path, default=None)
    args = p.parse_args(argv)

    registry = load_registry()
    bundle_dirs = [args.bundles_dir] if args.bundles_dir else [registry_path().parent.parent / "bundles"]
    names = names_from_profile_or_bundle(args.profile, bundle_dirs, args.bundle)
    rows = plan(args.harness, names, registry)

    if args.cmd == "exclusions":
        for skill in sorted(exclusions(rows, registry)):
            print(skill)
        return 0
    for row in rows:
        line = f"{row['status'].upper():12} {args.harness} {row['name']}"
        if row["id"]:
            line += f" ({row['id']})"
        print(line)
        if row["hint"]:
            print(f"             {row['hint']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
