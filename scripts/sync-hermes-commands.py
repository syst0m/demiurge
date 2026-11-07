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
        f"provides_hooks:\n  - pre_gateway_dispatch\n  - pre_llm_call\n  - on_session_end\n"
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
    if not PLUGIN_YAML.exists() or PLUGIN_YAML.read_text(encoding="utf-8") != yaml_text:
        drift = True
        if not args.check:
            PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
            PLUGIN_YAML.write_text(yaml_text, encoding="utf-8")
            print(f"WRITE {PLUGIN_YAML}")

    # commands/*.toml
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    # __init__.py marks the plugin dir as a Python package (required by the
    # Hermes plugin loader); keep it in sync too.
    init_py = PLUGIN_DIR / "__init__.py"
    init_text = '''"""Hermes plugin for demiurge skills: /niccolo, /marcus and /imhotep slash commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
COMMANDS_DIR = ROOT / "commands"
LEDGER_HOOK = ROOT.parent.parent / "demiurge-ledger" / "ledger_hook.py"


def _ledger(*args: str) -> None:
    """Write one run-ledger row through the pinned hook. Fail-open: never raises."""
    try:
        if LEDGER_HOOK.is_file():
            subprocess.run([sys.executable, str(LEDGER_HOOK), "--event", "record",
                            "--harness", "hermes", *args],
                           timeout=3, capture_output=True, check=False)
    except Exception:
        pass


def _cheatsheet() -> str:
    """The ledger cheat-sheet text from the pinned hook, or '' when it is missing."""
    try:
        if LEDGER_HOOK.is_file():
            done = subprocess.run([sys.executable, str(LEDGER_HOOK), "--event", "help"],
                                  timeout=3, capture_output=True, text=True, check=False)
            return done.stdout.strip()
    except Exception:
        pass
    return ""


def block_help_prompt(user_message: Any = None, **_: Any) -> dict[str, str] | None:
    """Answer ::help with zero model calls; pre_gateway_dispatch never fires on Desktop."""
    text = user_message if isinstance(user_message, str) else ""
    if text.strip() != "::help":
        return None
    sheet = _cheatsheet()
    if not sheet:
        return None
    return {"action": "block", "message": "```\\n" + sheet + "\\n```"}


def record_session_end(completed: Any = None, failed: Any = None, **_: Any) -> None:
    """Hermes on_session_end fires at each turn finalization: one harness row per turn.

    A failed turn is bad (infra); a completed one is ok; an interrupted one stays unlabeled.
    """
    if failed:
        _ledger("--subject-type", "harness", "--subject", "hermes", "--label", "bad", "--class", "infra")
    elif completed:
        _ledger("--subject-type", "harness", "--subject", "hermes", "--label", "ok")
    else:
        _ledger("--subject-type", "harness", "--subject", "hermes")


def _read_toml_command(path: Path) -> tuple[str, str, str] | None:
    """Parse a minimal commands/*.toml: description and prompt on lines 1-2."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    description = prompt = ""
    for ln in lines:
        if ln.startswith("description ="):
            description = ln.split("=", 1)[1].strip().strip('"')
        elif ln.startswith("prompt ="):
            prompt = ln.split("=", 1)[1].strip().strip('"')
    if not description or not prompt:
        return None
    return path.stem, description, prompt


def _skill_prompt(command: str, args: str = "") -> str:
    tail = args.strip()
    target = f"\\n\\nUser arguments: {tail}" if tail else ""
    for path in sorted(COMMANDS_DIR.glob("*.toml")):
        parsed = _read_toml_command(path)
        if parsed and parsed[0] == command:
            desc = parsed[1]
            return f"Load and follow the Hermes plugin skill `demiurge-skills:{command}`. {desc}{target}"
    return f"Run the {command} skill from the demiurge repo.{target}"


def _slash_access_denied(event: Any, gateway: Any, command: str) -> bool:
    if gateway is None or event is None:
        return False
    checker = getattr(gateway, "_check_slash_access", None)
    source = getattr(event, "source", None)
    if checker is None or source is None:
        return False
    try:
        return checker(source, command) is not None
    except Exception:
        return True


def rewrite_gateway_command(event: Any = None, gateway: Any = None, **_: Any) -> dict[str, str] | None:
    """Rewrite authorized gateway /niccolo, /marcus and /imhotep commands into skill prompts."""
    text = str(getattr(event, "text", "") or "").strip()
    if not text.startswith("/"):
        return None
    head, _, rest = text[1:].partition(" ")
    command = head.replace("_", "-").lower()
    if not any(p.stem == command for p in COMMANDS_DIR.glob("*.toml")):
        return None
    if _slash_access_denied(event, gateway, command):
        return None
    _ledger("--subject-type", "skill", "--subject", command, "--trigger", "slash")
    return {"action": "rewrite", "text": _skill_prompt(command, rest)}


def register(ctx: Any) -> None:
    """Register the hooks that expose /niccolo, /marcus, /imhotep and ::help."""
    ctx.register_hook("pre_gateway_dispatch", rewrite_gateway_command)
    ctx.register_hook("pre_llm_call", block_help_prompt)
    try:
        ctx.register_hook("on_session_end", record_session_end)
    except Exception:
        pass  # an unknown hook name must never break the slash commands
'''
    if not init_py.exists() or init_py.read_text(encoding="utf-8") != init_text:
        drift = True
        if not args.check:
            init_py.write_text(init_text, encoding="utf-8")
            print(f"WRITE {init_py}")
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
