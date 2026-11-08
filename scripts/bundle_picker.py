#!/usr/bin/env python3
"""Interactive picker: choose skills from bundles to install or sync into a harness.

Reads bundle manifests from `bundles/`, lets the user pick a harness, then bundles,
then per-bundle skills in a numbered checkbox menu. Applies the selection through
the existing `scripts/sync_bundles.py` materializer (symlink/copy into each
harness's native plugin shape). Re-running later re-syncs idempotently.

stdlib only — no dependencies, following the ponytail lazy principle.

Usage:
  python scripts/bundle_picker.py                 # interactive flow
  python scripts/bundle_picker.py --list          # print bundles and skills, exit
  python scripts/bundle_picker.py --bundles-dir <dir>
  python scripts/bundle_picker.py --apply-all     # sync every skill in every bundle into every harness
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_bundles import (  # noqa: E402
    GLOBAL_ROOTS,
    HARNESSES,
    default_libraries,
    load_bundles as _sync_load_bundles,
    resolve_skill,
    skill_link,
)

SCRIPT = Path(__file__).resolve()
REPO = SCRIPT.parent.parent
DEFAULT_BUNDLES_DIR = REPO / "bundles"
SYNC_BUNDLES = SCRIPT.parent / "sync_bundles.py"

CLEAR = "\033[2J\033[H"  # ANSI home+clear; falls back gracefully on dumb terminals

HARNESS_CHOICES = [
    ("hermes", "Hermes desktop (TUI)", "user plugin dir — %LOCALAPPDATA%/hermes/plugins/<bundle>/skills"),
    ("opencode", "OpenCode (CLI)", "~/.config/opencode/skills/<skill>"),
    ("antigravity", "Antigravity (IDE)", "<root>/.agents/plugins/<bundle>/skills"),
    ("claude-code", "Claude Code", "<root>/.claude/skills/<skill>"),
]


def supports_color() -> bool:
    if os.name == "nt":
        return bool(os.environ.get("WT_SESSION") or os.environ.get("ConEmuANSI") == "ON")
    return True


C = (
    {
        "bold": "\033[1m",
        "dim": "\033[2m",
        "reset": "\033[0m",
        "cyan": "\033[36m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "gray": "\033[90m",
    }
    if supports_color()
    else {k: "" for k in ("bold", "dim", "reset", "cyan", "green", "yellow", "red", "gray")}
)


def load_bundles(bundles_dir: Path) -> List[dict]:
    bundles = []
    for entry in sorted(bundles_dir.iterdir()):
        manifest = entry / "bundle.json"
        if not manifest.is_file():
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["dir"] = entry
        bundles.append(data)
    return bundles


def skill_target_dir(harness: str, bundle_name: str, skill: str) -> Path:
    """Where sync_bundles would place this skill for this harness."""
    root = Path.cwd()  # default scope is project
    if harness == "hermes":
        return GLOBAL_ROOTS["hermes"] / "plugins" / bundle_name / "skills" / skill
    if harness == "claude-code":
        return root / ".claude" / "skills" / skill
    if harness == "antigravity":
        return root / ".agents" / "plugins" / bundle_name / "skills" / skill
    if harness == "opencode":
        return Path.home() / ".config" / "opencode" / "skills" / skill
    raise ValueError(harness)


def install_state(harness: str, bundle: dict, skill: str) -> str:
    """'installed' | 'in library' | 'not found' for the chosen harness target."""
    src = resolve_skill(default_libraries(), skill)
    if src is None:
        return "not found"
    dst = skill_target_dir(harness, bundle["name"], skill)
    state, _ = skill_link(dst, src)
    if state == "ok":
        return "installed"
    return "in library"


def status_text(harness: str, bundle: dict, skill: str) -> str:
    state = install_state(harness, bundle, skill)
    if state == "installed":
        return f"{C['green']}installed{C['reset']}"
    if state == "in library":
        return f"{C['yellow']}in library{C['reset']}"
    return f"{C['red']}not found{C['reset']}"


def render(bundles: List[dict], choices: Dict[str, set], harness: str,
           active: int | None = None) -> None:
    """Draw the picker screen. Re-printing each turn keeps it TTY-agnostic."""
    print(CLEAR, end="")
    print(f"{C['bold']}Skill bundle picker{C['reset']} — harness: {C['cyan']}{harness}{C['reset']}")
    print(f"Commands: <number> toggle  ·  a = all  ·  n = none  ·  d = done  ·  q = quit")
    print()
    for i, bundle in enumerate(bundles):
        name = bundle["name"]
        skills = bundle["skills"]
        selected = choices.get(name, set())
        marker = "▶" if active == i else " "
        desc = bundle.get("description", "")
        installed = sum(1 for s in skills if install_state(harness, bundle, s) == "installed")
        print(
            f"{marker} [{i+1}] {C['cyan']}{name}{C['reset']} — {desc}"
            f"  {C['dim']}({installed}/{len(skills)} installed){C['reset']}"
        )
        if not skills:
            print(f"    {C['dim']}(no skills){C['reset']}")
            continue
        for j, skill in enumerate(skills):
            on = "x" if skill in selected else " "
            on_color = C["green"] if on == "x" else C["gray"]
            print(
                f"    [{on_color}{on}{C['reset']}] {j+1}:{skill:40s}"
                f"  {C['dim']}status:{C['reset']} {status_text(harness, bundle, skill)}"
            )
        print()
    print(f"Selection applied on 'd'. 'q' abandons unsaved changes.")


def choose_one(options: List[Tuple], prompt: str, title: str = "") -> Optional[int]:
    """Single-select menu: press a number to choose and advance immediately."""
    while True:
        if title:
            print(title)
        for i, option in enumerate(options):
            print(f"  [{i+1}] {option[1]}")
        print()
        try:
            cmd = input(f"{prompt} > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not cmd:
            continue
        if cmd == "q":
            return None
        try:
            idx = int(cmd) - 1
        except ValueError:
            print(f"  {C['red']}unknown command{C['reset']}")
            continue
        if 0 <= idx < len(options):
            return idx
        print(f"  {C['red']}out of range{C['reset']}")


def choose_from(options: List[Tuple], prompt: str, title: str = "",
                preselected: Optional[set] = None) -> List[int]:
    """Generic multi-toggle menu. Returns indices of chosen options."""
    chosen: set = set(preselected or set())
    while True:
        if title:
            print(title)
        for i, option in enumerate(options):
            label = option[1]
            marker = "x" if i in chosen else " "
            print(f"  [{C['green'] if i in chosen else C['gray']}{marker}{C['reset']}] {i+1}: {label}")
        print()
        try:
            cmd = input(f"{prompt} > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return []
        if not cmd:
            continue
        if cmd == "q":
            return []
        if cmd == "d":
            return sorted(chosen)
        if cmd == "a":
            chosen = set(range(len(options)))
            continue
        if cmd == "n":
            chosen = set()
            continue
        try:
            idx = int(cmd) - 1
        except ValueError:
            print(f"  {C['red']}unknown command{C['reset']}")
            continue
        if 0 <= idx < len(options):
            if idx in chosen:
                chosen.discard(idx)
            else:
                chosen.add(idx)
        else:
            print(f"  {C['red']}out of range{C['reset']}")


def pick_skills(bundle: dict, harness: str) -> set:
    """Interactive checkbox menu for one bundle. Returns the selected skill set."""
    name = bundle["name"]
    skills = list(bundle["skills"])
    # Default: pre-select skills already installed in this harness; user toggles add/remove.
    selected: set = {s for s in skills if install_state(harness, bundle, s) == "installed"}
    while True:
        render([bundle], {name: selected}, harness, active=0)
        try:
            cmd = input(f"  {name} > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return selected
        if not cmd:
            continue
        if cmd == "q":
            return selected
        if cmd == "d":
            return selected
        if cmd == "a":
            selected = set(skills)
            continue
        if cmd == "n":
            selected = set()
            continue
        try:
            idx = int(cmd) - 1
        except ValueError:
            print(f"  {C['red']}unknown command{C['reset']}")
            continue
        if 0 <= idx < len(skills):
            skill = skills[idx]
            if skill in selected:
                selected.discard(skill)
            else:
                selected.add(skill)
        else:
            print(f"  {C['red']}out of range{C['reset']}")


def write_filtered_manifests(bundles: List[dict], picks: Dict[int, set], tmpdir: Path) -> List[dict]:
    """Write one manifest per chosen bundle containing only selected skills."""
    written = []
    for idx, sel in picks.items():
        bundle = bundles[idx]
        data = {
            "name": bundle["name"],
            "description": bundle.get("description", ""),
            "skills": sorted(sel),
        }
        out = tmpdir / bundle["name"] / "bundle.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        written.append(data)
    return written


def apply_selection(bundles: List[dict], picks: Dict[int, set], harnesses: List[str],
                    apply: bool) -> int:
    if not picks or not harnesses:
        print("Nothing selected.")
        return 0
    summary = []
    for idx in sorted(picks):
        bundle = bundles[idx]
        summary.append(
            f"  {bundle['name']}: {len(picks[idx])} skill(s) — "
            f"{', '.join(sorted(picks[idx])) or '(none)'}"
        )
    print("Plan:")
    print("\n".join(summary))
    print(f"Harnesses: {', '.join(harnesses)}")
    if not apply:
        try:
            confirm = input("\nApply this selection? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if confirm != "y":
            print("Aborted.")
            return 1

    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        write_filtered_manifests(bundles, picks, tmpdir)
        cmd = [
            sys.executable, str(SYNC_BUNDLES),
            "--bundles-dir", str(tmpdir),
            "--apply",
        ]
        for h in harnesses:
            cmd += ["--harness", h]
        print(f"Running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=str(REPO))
        return proc.returncode


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Interactively pick skills from bundles to install or sync into a harness.")
    p.add_argument("--bundles-dir", type=Path, default=DEFAULT_BUNDLES_DIR,
                   help="bundle manifest directory (default: repo's bundles/)")
    p.add_argument("--list", action="store_true", help="print bundles and skills, then exit")
    p.add_argument("--apply-all", action="store_true", help="sync every skill in every bundle into every harness without prompting")
    args = p.parse_args(argv)

    bundles = load_bundles(args.bundles_dir)
    if not bundles:
        print(f"No bundles found in {args.bundles_dir}")
        return 1
    if args.list:
        for b in bundles:
            print(f"{b['name']}: {', '.join(b['skills']) or '(none)'}")
        return 0

    if args.apply_all:
        harness_idxs = [i for i, o in enumerate(HARNESS_CHOICES) if o[0] in HARNESSES]
        harnesses = [HARNESS_CHOICES[i][0] for i in harness_idxs]
        picks = {i: set(b["skills"]) for i, b in enumerate(bundles)}
    else:
        # 1. Choose harness (single select, advances immediately)
        harness_idx = choose_one(HARNESS_CHOICES, "Select harness", "Harnesses:")
        if harness_idx is None:
            print("No harness chosen.")
            return 0
        harnesses = [HARNESS_CHOICES[harness_idx][0]]

        # 2. Choose bundles — pre-select bundles that already have a skill installed
        bundle_options = [(b["name"], b.get("description", "")) for b in bundles]
        preselected = {i for i, b in enumerate(bundles)
                       if any(install_state(harnesses[0], b, s) == "installed"
                              for s in b["skills"])}
        idxs = choose_from(bundle_options, "Select bundle", "Bundles:", preselected)
        if not idxs:
            print("No bundles chosen.")
            return 0

        # 3. Per-bundle skills (uses chosen harness for status display)
        picks: Dict[int, set] = {}
        for i in idxs:
            picks[i] = pick_skills(bundles[i], harnesses[0])

    return apply_selection(bundles, picks, harnesses, apply=True)


if __name__ == "__main__":
    sys.exit(main())
