#!/usr/bin/env python3
"""Materialize skill bundles into each harness's native plugin shape.

A bundle is a manifest (`bundles/<name>/bundle.json`) naming skills. Skill bodies are never
copied; each harness gets symlinks (or copies, where symlinks are unavailable) into the skill
library.

Verified targets — each harness's own load path, not a guess:

  antigravity  <root>/.agents/plugins/<bundle>/plugin.json + skills/
               Workspace plugins activate for that project (Antigravity docs, "Plugins").
  claude-code  <root>/.claude/skills/<skill>            (project skill scope)
               <root>/.claude/settings.json hooks.Stop    (the gate)
               Claude Code does NOT auto-load .claude/plugins/<name>/ without a marketplace
               install record, so there is no bundle directory for it.
  hermes       %LOCALAPPDATA%/hermes/plugins/<bundle>/    (user scope, always)
               plus plugins.enabled in config.yaml.
               The desktop gateway never loads ./.hermes/plugins (gateway/session_local.py,
               project_plugins_warning); that path is CLI-only, so --scope project still
               targets the user dir for Hermes and says so.

Guards:
  * a bundle skill missing from every library is a hard error
  * a target holding different real content is refused, never overwritten
  * `--check` writes nothing and exits 1 on drift

Usage:
  python scripts/sync_bundles.py --apply                 # all bundles, this repo
  python scripts/sync_bundles.py --check
  python scripts/sync_bundles.py --bundle baseline-coding --project ~/code/app --apply
  python scripts/sync_bundles.py --scope global --apply

Exit codes: 0 clean, 1 drift or refused, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parent.parent
BUNDLES_DIR = REPO / "bundles"
if not BUNDLES_DIR.is_dir():
    for _c in [REPO.parent / "agent-skills" / "bundles", Path.home() / "Documents" / "code" / "agent-skills" / "bundles"]:
        if _c.is_dir():
            BUNDLES_DIR = _c
            break
GATE_SCRIPT = REPO / "scripts" / "testing_matrix_gate.py"

HARNESSES = ("antigravity", "claude-code", "hermes")
GLOBAL_ROOTS = {
    "antigravity": Path.home() / ".gemini" / "config",
    "claude-code": Path.home() / ".claude",
    "hermes": Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "hermes",
}


def default_libraries() -> List[Path]:
    """Skill libraries, searched in order. First hit wins."""
    here = os.environ.get("DEMIURGE_SKILL_LIBRARY", "")
    roots: List[Path] = []
    if here:
        roots += [Path(p) for p in here.split(os.pathsep) if p]
    roots += [
        REPO.parent / "agent-skills" / "skills",
        Path.home() / "Documents" / "code" / "agent-skills" / "skills",
        Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "hermes" / "skills",
        Path.home() / ".agents" / "skills",
    ]
    seen: set = set()
    out: List[Path] = []
    for r in roots:
        if r.is_dir() and r.resolve() not in seen:
            seen.add(r.resolve())
            out.append(r)
    return out


def resolve_skill(roots: Sequence[Path], name: str) -> Optional[Path]:
    """Find <name>/SKILL.md in a flat library or one category level down."""
    for root in roots:
        direct = root / name / "SKILL.md"
        if direct.is_file():
            return root / name
        if not root.is_dir():
            continue
        # A categorized library (Hermes: skills/<category>/<skill>/) as well as a flat one.
        for cat in sorted(root.iterdir()):
            if cat.is_dir() and (cat / name / "SKILL.md").is_file():
                return cat / name
    return None


def load_bundles(bundles_dir: Path, names: Sequence[str]) -> List[dict]:
    bundles = []
    for entry in sorted(bundles_dir.iterdir()):
        manifest = entry / "bundle.json"
        if not manifest.is_file():
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if names and data["name"] not in names:
            continue
        data["dir"] = entry
        bundles.append(data)
    if names:
        found = {b["name"] for b in bundles}
        missing = [n for n in names if n not in found]
        if missing:
            raise SystemExit(f"ERROR: unknown bundle(s): {', '.join(missing)}")
    return bundles


# ---------------------------------------------------------------- guards

def link_or_copy(src: Path, dst: Path) -> str:
    """Point dst at src. Prefers a symlink, falls back to a recursive copy."""
    if dst.is_symlink() or dst.exists():
        dst.unlink() if dst.is_symlink() else shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        dst.symlink_to(src.resolve(), target_is_directory=True)
        return "link"
    except OSError:
        shutil.copytree(src, dst)
        return "copy"


def skill_link(dst: Path, src: Path) -> Tuple[str, str]:
    """Compare dst against src. Returns (state, detail)."""
    if dst.is_symlink():
        try:
            target = dst.resolve()
        except OSError:
            target = None
        if target == src.resolve():
            return "ok", "link"
        return "drift", f"-> {target}"
    if not dst.exists():
        return "missing", "not installed"
    if dst.is_dir():
        rels = sorted(p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file())
        have = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file())
        if rels != have:
            return "conflict", "real directory with different content"
        same = all(
            (src / rel).read_bytes().replace(b"\r\n", b"\n")
            == (dst / rel).read_bytes().replace(b"\r\n", b"\n")
            for rel in rels
        )
        # Same shape, different bytes: a stale copy from a previous copy-fallback deploy.
        return ("ok", "copy") if same else ("drift", "stale copy")
    return "conflict", "real file in place of a skill link"


# ---------------------------------------------------------------- manifests

def write_manifest(path: Path, body: str, apply: bool) -> Tuple[str, str]:
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    if old == body:
        return "ok", "current"
    if not apply:
        return "drift", "stale" if old is not None else "missing"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return "synced", "written"


HERMES_GATE_INIT = '''"""Hermes hook: a source change with no test change is not a complete task.

Contract (agent/turn_context.py:_collect_pre_llm_call_context): a pre_llm_call callback vetoes
the turn by returning {"action": "block", "message": "<non-empty string>"}. A block without a
message is ignored. The turn then ends with no inference request at all.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parent / "hooks" / "testing_matrix_gate.py"


def register(ctx):
    def _check(event=None, payload=None, **kwargs):
        repo = os.environ.get("DEMIURGE_REPO") or os.getcwd()
        proc = subprocess.run(
            [sys.executable, str(GATE), "--repo", repo, "--json"],
            capture_output=True, text=True)
        try:
            data = json.loads(proc.stdout)
        except Exception:
            return None
        if data.get("decision") == "block":
            message = str(data.get("reason") or "testing matrix gate blocked this turn").strip()
            if not message:
                return None
            print(message)
            return {"action": "block", "message": message}
        return None
    ctx.register_hook("pre_llm_call", _check)
'''


def gate_wiring(harness: str) -> Dict[str, str]:
    """Each harness's native hook dialect. The block decisions genuinely differ:
    Claude Code stops on {"decision":"block"}, Antigravity on {"decision":"continue"}."""
    if harness == "antigravity":
        cmd = f"python {GATE_SCRIPT} --json --hook-format antigravity"
        return {"hooks.json": json.dumps(
            {"testing-matrix": {"enabled": True,
                                "Stop": [{"type": "command", "command": cmd, "timeout": 30}]}},
            indent=2) + "\n"}
    if harness == "claude-code":
        cmd = f"python {GATE_SCRIPT} --json --hook-format claude-code"
        return {"__settings__": json.dumps(
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": cmd, "timeout": 30}]}]}},
            indent=2)}
    cmd = f"python {GATE_SCRIPT} --json"
    return {
        "__init__.py": HERMES_GATE_INIT,
        "hooks/testing_matrix_gate.py": GATE_SCRIPT.read_text(encoding="utf-8"),
    }


def apply_gate(harness: str, plugin_dir: Path, project: Path, apply: bool) -> bool:
    """Write the gate wiring. Claude Code's settings file is merged, never replaced."""
    drift = False
    for rel, body in gate_wiring(harness).items():
        if rel == "__settings__":
            settings = project / ".claude" / "settings.json"
            data = json.loads(settings.read_text(encoding="utf-8")) if settings.is_file() else {}
            stop = data.setdefault("hooks", {}).setdefault("Stop", [])
            entry = json.loads(body)["hooks"]["Stop"][0]
            commands = [h.get("command") for group in stop for h in group.get("hooks", [])]
            if entry["hooks"][0]["command"] in commands:
                continue
            if not apply:
                drift = True
                print(f"  DRIFT    {harness} Stop hook not registered")
                continue
            stop.append(entry)
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"  SYNCED  {harness} Stop hook -> {settings}")
            continue
        dst = plugin_dir / rel
        old = dst.read_text(encoding="utf-8") if dst.is_file() else None
        if old == body:
            continue
        if not apply:
            drift = True
            print(f"  DRIFT    {harness} gate wiring: {rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(body, encoding="utf-8")
        print(f"  SYNCED  {harness} gate wiring: {rel}")
    return drift


def plugin_manifests(bundle: dict) -> Dict[str, str]:
    name, desc = bundle["name"], bundle["description"]
    return {
        "antigravity": json.dumps(
            {"name": name, "version": "1.0.0", "description": desc}, indent=2) + "\n",
        "hermes": "\n".join([
            f"name: {name}",
            'version: "1.0.0"',
            f'description: "{desc}"',
            *(["provides_hooks:", "  - pre_llm_call"] if bundle.get("hooks") else []),
            "provides_skills:",
            *[f"  - {s}" for s in bundle["skills"]],
            "",
        ]),
    }


def manifest_path(harness: str, plugin_dir: Path) -> Path:
    return plugin_dir / ("plugin.json" if harness == "antigravity" else "plugin.yaml")


def enable_hermes_plugin(name: str, apply: bool) -> bool:
    """Add *name* to plugins.enabled in the Hermes config.yaml (line-based; no PyYAML)."""
    cfg = GLOBAL_ROOTS["hermes"] / "config.yaml"
    if not cfg.is_file():
        return False
    lines = cfg.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.rstrip() == "plugins:")
        enabled = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "enabled:")
    except StopIteration:
        print(f"  WARN     {cfg} has no plugins.enabled list; add '{name}' by hand")
        return False
    base = len(lines[enabled]) - len(lines[enabled].lstrip())
    j = enabled + 1
    while j < len(lines):
        line = lines[j]
        if not line.strip():
            break
        if len(line) - len(line.lstrip()) <= base:
            break  # a sibling key (`disabled:`, `mcp_servers:`), not a list item
        if line.strip().lstrip("- ").strip() == name:
            return False
        j += 1
    if not apply:
        return True
    lines.insert(j, " " * (base + 2) + f"- {name}")
    cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  SYNCED  hermes plugins.enabled += {name}")
    return False


# ---------------------------------------------------------------- driver

def sync_one(harness: str, skill: str, src: Path, dst: Path, apply: bool) -> int:
    state, detail = skill_link(dst, src)
    if state == "ok":
        return 0
    if state == "conflict":
        print(f"  REFUSE  {harness} skill {skill}: {detail}")
        return 1
    if not apply:
        print(f"  {state.upper():8} {harness} skill {skill} ({detail})")
        return 1
    how = link_or_copy(src, dst)
    print(f"  SYNCED  {harness} skill {skill} ({how})")
    return 0


def materialize_claude(bundle: dict, sources: Dict[str, Path], project: Path,
                       scope: str, apply: bool) -> int:
    """Claude Code: project skills under .claude/skills/, hooks in .claude/settings.json.

    There is no bundle directory: Claude Code does not load .claude/plugins/<name>/ without a
    marketplace install record.
    """
    drift = 0
    base = project if scope == "project" else GLOBAL_ROOTS["claude-code"]
    for skill in bundle["skills"]:
        drift |= sync_one("claude-code", skill, sources[skill],
                          base / ".claude" / "skills" / skill, apply)
    if bundle.get("hooks"):
        drift |= apply_gate("claude-code", base / ".claude", project, apply)
    return drift


def run(bundles: Sequence[dict], roots: Sequence[Path], project: Path,
        scope: str, apply: bool, harnesses: Sequence[str]) -> int:
    drift = 0
    for bundle in bundles:
        print(f"=== {bundle['name']} ({len(bundle['skills'])} skills)")
        sources: Dict[str, Path] = {}
        for skill in bundle["skills"]:
            found = resolve_skill(roots, skill)
            if found is None:
                print(f"  ERROR  skill '{skill}' is not in any library")
                drift = 1
            else:
                sources[skill] = found
        if len(sources) != len(bundle["skills"]):
            continue

        for harness in harnesses:
            if harness == "claude-code":
                drift |= materialize_claude(bundle, sources, project, scope, apply)
                continue

            if harness == "hermes":
                if scope == "project":
                    print("  NOTE    hermes: the desktop gateway never loads ./.hermes/plugins; "
                          "using the user plugin dir")
                plugin_dir = GLOBAL_ROOTS["hermes"] / "plugins" / bundle["name"]
            else:
                base = project if scope == "project" else GLOBAL_ROOTS[harness]
                plugin_dir = base / ".agents" / "plugins" / bundle["name"]

            state, detail = write_manifest(
                manifest_path(harness, plugin_dir), plugin_manifests(bundle)[harness], apply)
            print(f"  {state.upper():8} {harness} manifest ({detail})")
            # "synced" means the write landed; only a stale/missing manifest in check mode is drift.
            drift |= state not in ("ok", "synced")

            for skill in bundle["skills"]:
                drift |= sync_one(harness, skill, sources[skill],
                                  plugin_dir / "skills" / skill, apply)

            if bundle.get("hooks"):
                drift |= apply_gate(harness, plugin_dir, project, apply)

            if harness == "hermes":
                drift |= enable_hermes_plugin(bundle["name"], apply)

    if drift and not apply:
        print("\nDrift detected. Re-run with --apply to materialize.")
    return 1 if drift else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bundle", action="append", default=[],
                   help="bundle name; repeatable (default: all)")
    p.add_argument("--bundles-dir", type=Path, default=BUNDLES_DIR,
                   help="bundle manifest directory (default: the repo's bundles/)")
    p.add_argument("--project", type=Path, default=REPO,
                   help="project root (default: the demiurge checkout)")
    p.add_argument("--scope", choices=["project", "global"], default="project")
    p.add_argument("--harness", action="append", default=[],
                   help="harness name; repeatable (default: all three)")
    p.add_argument("--library", action="append", default=[],
                   help="skill library dir; repeatable")
    p.add_argument("--apply", action="store_true", help="write (default: report only)")
    p.add_argument("--check", action="store_true", help="report drift, exit 1 (default behaviour)")
    args = p.parse_args(argv)

    roots = [Path(x) for x in args.library] if args.library else default_libraries()
    if not roots:
        print("NOTE: no skill library found; nothing to materialize or check", file=sys.stderr)
        return 0
    harnesses = args.harness or list(HARNESSES)
    bad = [h for h in harnesses if h not in HARNESSES]
    if bad:
        print(f"ERROR: unknown harness(es): {', '.join(bad)}", file=sys.stderr)
        return 2

    try:
        bundles = load_bundles(args.bundles_dir, args.bundle)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2

    return run(bundles, roots, args.project.resolve(), args.scope,
               args.apply, harnesses)


if __name__ == "__main__":
    sys.exit(main())
