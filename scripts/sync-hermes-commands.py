#!/usr/bin/env python3
"""Sync demiurge skills into Hermes plugin commands.

Reads each skill's SKILL.md frontmatter (name, description) from
$DEMIURGE_REPO/skills/*/SKILL.md and writes:

  %LOCALAPPDATA%/hermes/plugins/demiurge-skills/plugin.yaml
  %LOCALAPPDATA%/hermes/plugins/demiurge-skills/commands/<name>.toml

Usage:  python scripts/sync-hermes-commands.py [--check]
  (no flags)   apply: write plugin.yaml + commands/*.toml
  --check      report drift, write nothing (exit 1 if drift)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expandvars(r"%LOCALAPPDATA%\hermes")))
PLUGIN_DIR = HERMES_HOME / "plugins" / "demiurge-skills"
COMMANDS_DIR = PLUGIN_DIR / "commands"
PLUGIN_YAML = PLUGIN_DIR / "plugin.yaml"

FRONTMATTER_RE = re.compile(r"---\s*\n(.*?)\n---", re.DOTALL)
FIELD_RE = re.compile(r'^(\w+):\s*(.*)$', re.MULTILINE)


def parse_skill(skill_dir: Path) -> dict[str, str] | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    text = skill_md.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.search(text)
    if not m:
        return None
    fields = dict(FIELD_RE.findall(m.group(1)))
    name = fields.get("name")
    description = fields.get("description", "")
    if not name:
        return None
    return {"name": name, "description": description}


def command_toml(name: str, description: str) -> str:
    return (
        f'description = "{description}"\n'
        f'prompt = "Use the {name} skill from the demiurge repo. {description} '
        f'Load the {name} skill via skill_view and apply it to the user\'s request. '
        f'Every command runs from the root of the demiurge checkout (read from $DEMIURGE_REPO)."\n'
    )


def plugin_yaml(names: list[str]) -> str:
    commands = "\n".join(f"  - {n}" for n in names)
    return (
        f"name: demiurge-skills\n"
        f"version: 1.0.0\n"
        f"description: Hermes slash commands for demiurge skills ({', '.join(names)}). Synced from scripts/sync-hermes-commands.py — do not edit by hand.\n"
        f"provides_commands:\n{commands}\n"
        f"provides_skills:\n{commands}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift, write nothing (exit 1 if drift)")
    args = parser.parse_args(argv)

    skills = sorted(
        (s for s in (p for p in SKILLS_DIR.iterdir() if p.is_dir())),
        key=lambda p: p.name,
    )
    parsed: list[dict[str, str]] = []
    for s in skills:
        info = parse_skill(s)
        if info:
            parsed.append(info)

    names = [p["name"] for p in parsed]
    yaml_text = plugin_yaml(names)

    drift = False

    # plugin.yaml
    if PLUGIN_YAML.exists() and PLUGIN_YAML.read_text(encoding="utf-8") != yaml_text:
        drift = True
        if not args.check:
            PLUGIN_YAML.write_text(yaml_text, encoding="utf-8")
            print(f"WRITE {PLUGIN_YAML}")

    # commands/*.toml
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    for p in parsed:
        expected.add(p["name"] + ".toml")
        toml_text = command_toml(p["name"], p["description"])
        path = COMMANDS_DIR / (p["name"] + ".toml")
        if path.exists() and path.read_text(encoding="utf-8") != toml_text:
            drift = True
            if not args.check:
                path.write_text(toml_text, encoding="utf-8")
                print(f"WRITE {path}")
        elif not path.exists():
            drift = True
            if not args.check:
                path.write_text(toml_text, encoding="utf-8")
                print(f"WRITE {path}")

    # remove stale commands (skills that no longer exist)
    for f in COMMANDS_DIR.glob("*.toml"):
        if f.name not in expected:
            drift = True
            if not args.check:
                f.unlink()
                print(f"REMOVE {f}")

    if drift:
        print("Drift detected" + (" (would write)" if args.check else ""))
        return 1
    print("In sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
