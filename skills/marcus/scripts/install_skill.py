#!/usr/bin/env python3
"""Install a skill at one scope: a project, the global library, or staging only.

Run it; do not read it.

    python install_skill.py <skill-dir> --describe [--json]
    python install_skill.py <skill-dir> --scope project --project <dir> [--harness claude-code,antigravity] [--yes]
    python install_skill.py <skill-dir> --scope global [--library <dir>] [--i-know] [--yes]
    python install_skill.py <skill-dir> --scope staging [--yes]
    python install_skill.py <skill-dir> --remove --scope <scope> [--project <dir> | --library <dir>] [--yes]

Every mode is a dry run until --yes. Scopes (references/SPEC.md section 6.1, Rule G-13):

    project  links <dir>/.claude/skills/<name> and/or <dir>/.agents/skills/<name> to the
             skill's canonical source, backs up and merges the skill's settings.fragment.json
             hooks into <dir>/.claude/settings.json and <dir>/.agents/hooks.json as new array
             entries, and merges its permissions.deny entries into <dir>/.claude/settings.json.
    global   links <library>/<name> (default ~/.claude/skills). Hooks reach a global install
             only through SKILL.md frontmatter 'hooks:'. This script never writes
             ~/.claude/settings.json or ~/.gemini/config/hooks.json; it prints what would be needed.
    staging  links nothing; the canonical source is the only copy.

Refused: global below T1; global with a PreToolUse hook covering MCP tools, Bash or PowerShell
(unless --i-know); project for an unread (T4) skill; any write outside the target project or
library; a link path that already exists and is not ours.

Every applied install or removal is recorded twice: an append-only 'install:' block in the
skill's PROVENANCE.md (paths relative to the skill's git working tree, or hashed when outside
it, because PROVENANCE files in a working tree get committed; absolute otherwise), and one line
in the local sidecar ~/.demiurge/installs.jsonl ($DEMIURGE_INSTALLS_FILE or --installs-file),
which holds absolute paths and the exact entries --remove takes out again.

Exit codes:
    0  planned (dry run), applied, or already installed
    2  refused, or a usage error

Stdlib only. No network.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

FRAGMENT_NAME = "settings.fragment.json"
SCOPES = ("project", "global", "staging")
HARNESSES: Dict[str, Dict[str, str]] = {
    "claude-code": {"skills": ".claude/skills", "hooks": ".claude/settings.json"},
    "antigravity": {"skills": ".agents/skills", "hooks": ".agents/hooks.json"},
}
DEFAULT_HARNESS = "claude-code"
DEFAULT_LIBRARY = "~/.claude/skills"
INSTALLS_ENV = "DEMIURGE_INSTALLS_FILE"

# A PreToolUse matcher that covers any of these blocks a whole tool class. Each probe is a tool
# name the matcher is tested against, so "Bash|Write" covers Bash and "mcp__gmail__send" covers
# no class.
TOOL_CLASS_PROBES: Dict[str, str] = {
    "MCP tools": "mcp__probe_server__probe_tool",
    "Bash": "Bash",
    "PowerShell": "PowerShell",
}

EVENT_WORDS: Dict[str, str] = {
    "PreToolUse": "runs before every {tools} call and can block it",
    "PostToolUse": "runs after every {tools} call; it can report but cannot undo the call",
    "UserPromptSubmit": "runs on every prompt you send and can block it",
    "Stop": "runs when a turn is about to end and can force a revision",
    "SessionStart": "runs when a session starts",
    "PermissionRequest": "runs when a {tools} call asks for permission and can deny it",
}

TIER_RE = re.compile(r"^\s*trust_tier:\s*['\"]?(T[1-4](?:-conditional)?)\b", re.MULTILINE)
YAML_FENCE_RE = re.compile(r"^```\s*ya?ml\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL | re.IGNORECASE)
INSTALL_HEADING_RE = re.compile(r"^## Install \d+\b", re.MULTILINE)


class Refusal(Exception):
    """A refused install. The message says which rule refused it."""


# --------------------------------------------------------------------------- #
# Reading the skill
# --------------------------------------------------------------------------- #

@dataclass
class Hook:
    source: str                      # "fragment" or "frontmatter"
    event: str
    matcher: Optional[str]
    commands: List[str] = field(default_factory=list)

    def classes(self) -> List[str]:
        return covered_classes(self.matcher) if self.event == "PreToolUse" else []


def covered_classes(matcher: Optional[str]) -> List[str]:
    """Tool classes a matcher covers. An absent, empty or '*' matcher covers every tool."""
    if matcher is None or matcher.strip() in ("", "*"):
        return list(TOOL_CLASS_PROBES)
    try:
        pattern = re.compile(matcher)
    except re.error:
        return list(TOOL_CLASS_PROBES)      # unreadable matcher: assume the worst
    return [name for name, probe in TOOL_CLASS_PROBES.items() if pattern.fullmatch(probe)]


def frontmatter_text(skill_md: Path) -> str:
    if not skill_md.is_file():
        return ""
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def frontmatter_name(skill_dir: Path) -> Optional[str]:
    match = re.search(r"^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$",
                      frontmatter_text(skill_dir / "SKILL.md"), re.MULTILINE)
    return match.group(1) if match else None


def frontmatter_hooks(skill_dir: Path) -> List[Hook]:
    """Event, matcher and commands from a SKILL.md frontmatter 'hooks:' block.

    Reads only the documented shape (event -> list of {matcher, hooks: [{type, command}]}),
    by indentation, so no YAML library is needed.
    """
    lines = frontmatter_text(skill_dir / "SKILL.md").splitlines()
    hooks: List[Hook] = []
    inside = False
    event_indent: Optional[int] = None
    event: Optional[str] = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            inside = line.split(":", 1)[0].strip() == "hooks"
            event_indent = None
            continue
        if not inside:
            continue
        if event_indent is None:
            event_indent = indent
        stripped = line.strip().lstrip("- ").strip()
        if indent == event_indent and stripped.endswith(":"):
            event = stripped[:-1].strip()
            continue
        if event is None:
            continue
        key, _, value = stripped.partition(":")
        value = value.strip().strip("'\"")
        if key.strip() == "matcher":
            hooks.append(Hook("frontmatter", event, value))
        elif key.strip() == "command":
            if not hooks or hooks[-1].event != event:
                hooks.append(Hook("frontmatter", event, None))
            hooks[-1].commands.append(value)
    return hooks


def load_fragment(skill_dir: Path) -> Dict[str, Any]:
    """The skill's settings.fragment.json (Claude Code settings shape), or {} when absent."""
    path = skill_dir / FRAGMENT_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Refusal(f"{FRAGMENT_NAME} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise Refusal(f"{FRAGMENT_NAME} must hold a JSON object")
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict) or not all(isinstance(v, list) for v in hooks.values()):
        raise Refusal(f"{FRAGMENT_NAME} 'hooks' must map each event to a list of entries")
    deny = data.get("permissions", {}).get("deny", []) if isinstance(data.get("permissions"), dict) else []
    if not isinstance(deny, list) or not all(isinstance(d, str) for d in deny):
        raise Refusal(f"{FRAGMENT_NAME} 'permissions.deny' must be a list of strings")
    return {"hooks": hooks, "deny": deny}


def fragment_hooks(fragment: Dict[str, Any]) -> List[Hook]:
    out: List[Hook] = []
    for event, entries in fragment.get("hooks", {}).items():
        for entry in entries:
            if not isinstance(entry, dict):
                raise Refusal(f"{FRAGMENT_NAME} has a non-object entry under {event}")
            commands = [h.get("command", "") for h in entry.get("hooks", []) if isinstance(h, dict)]
            out.append(Hook("fragment", event, entry.get("matcher"), commands))
    return out


def read_tier(skill_dir: Path) -> str:
    """Latest trust_tier in PROVENANCE.md's YAML blocks; T4 when none is recorded."""
    path = skill_dir / "PROVENANCE.md"
    if not path.is_file():
        return "T4"
    tiers: List[str] = []
    for block in YAML_FENCE_RE.findall(path.read_text(encoding="utf-8", errors="replace")):
        tiers.extend(TIER_RE.findall(block))
    return tiers[-1] if tiers else "T4"


def base_tier(tier: str) -> str:
    return tier.split("-", 1)[0]


# --------------------------------------------------------------------------- #
# Plain words, recommendation and refusal rules
# --------------------------------------------------------------------------- #

def script_name(command: str) -> str:
    names = re.findall(r"[\w.-]+\.(?:py|sh|ps1|js|bash)\b", command)
    return names[-1] if names else command.strip()[:60]


def tool_words(matcher: Optional[str]) -> str:
    if matcher is None or matcher.strip() in ("", "*"):
        return "tool"
    words = []
    for part in matcher.split("|"):
        part = part.strip()
        words.append("MCP tool" if part in ("mcp__.*", "mcp__.+", "mcp__*") else part)
    return ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else words[0]


def describe_hook(hook: Hook) -> str:
    phrase = EVENT_WORDS.get(hook.event, "runs on " + hook.event).format(tools=tool_words(hook.matcher))
    scripts = ", ".join(sorted({script_name(c) for c in hook.commands})) or "(no command)"
    text = f"{hook.event} hook {scripts} {phrase}."
    if hook.classes():
        text += " Blocks whole tool classes: " + ", ".join(hook.classes()) + "."
    return text


def recommend(tier: str, blocking: bool) -> Tuple[str, str]:
    tier = base_tier(tier)
    if tier == "T4":
        return "staging", "T4 (unread third party) is never installed; keep the canonical source only"
    if tier in ("T2", "T3"):
        return "staging", (f"{tier} has not been accepted at G5; install into a project only "
                           "while the operator tests it")
    if blocking:
        return "project", ("a hook blocks a whole tool class; Rule G-13 keeps it out of every "
                           "other session")
    return "global", "T1 with no tool-class-blocking hook"


def allowed_scopes(tier: str, blocking: bool) -> List[str]:
    tier = base_tier(tier)
    scopes = ["staging"]
    if tier != "T4":
        scopes.insert(0, "project")
    if tier == "T1" and not blocking:
        scopes.insert(0, "global")
    return scopes


def refusals(name: str, tier: str, scope: str, hooks: Sequence[Hook], i_know: bool) -> List[str]:
    out: List[str] = []
    blocking = [h for h in hooks if h.classes()]
    if scope == "global" and base_tier(tier) != "T1":
        out.append(f"global install needs T1; {name} is {tier} (Rule G-13). "
                   "Use --scope project for operator testing, or --scope staging")
    if scope == "global" and blocking and not i_know:
        classes = [c for c in TOOL_CLASS_PROBES if any(c in h.classes() for h in blocking)]
        out.append(f"{name} has a PreToolUse hook that blocks {', '.join(classes)} in every "
                   "session it loads into (Rule G-13). Use --scope project, or pass --i-know")
    if scope == "project" and base_tier(tier) == "T4":
        out.append(f"{name} is T4 (unread third party) and is not installed, at any scope "
                   "(references/SPEC.md section 6). Read every bundled file and record a tier first")
    return out


# --------------------------------------------------------------------------- #
# Paths, links and the write guard
# --------------------------------------------------------------------------- #

def absolute(path: Path) -> str:
    return os.path.abspath(str(path))


def norm(path: Path) -> str:
    return os.path.normcase(absolute(path))


def real(path: Path) -> str:
    return os.path.normcase(os.path.realpath(str(path)))


def real_parent(path: Path) -> str:
    """The path with every link above it resolved; the last component itself is not followed."""
    full = Path(absolute(path))
    return os.path.normcase(os.path.join(os.path.realpath(str(full.parent)), full.name))


def inside(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([norm(path), norm(root)]) == norm(root)
    except ValueError:                       # different drives
        return False


def is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def link_state(link: Path, target: Path) -> str:
    """'absent', 'ours' (a link to target, or target itself) or 'foreign'."""
    if not os.path.lexists(str(link)):
        return "absent"
    if real(link) == real(target):
        return "ours"
    return "foreign"


def git_root(path: Path) -> Optional[Path]:
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def forbidden_paths() -> List[Path]:
    home = Path.home()
    return [home / ".claude" / "settings.json", home / ".gemini" / "config" / "hooks.json"]


class Guard:
    """Every write goes through check(); anything outside the allowed set is refused.

    A path passes only when it is allowed both as written and with its links resolved, so a
    junction or symlink planted inside the project (say .claude pointing at the real home)
    cannot carry a write out of it. Pass link=True for a path that is itself the link being
    made or removed: then only the directories above it are resolved.
    """

    def __init__(self, roots: Sequence[Path], files: Sequence[Path]):
        self.roots = list(roots)
        self.real_roots = [real(r) for r in self.roots]
        self.files = {norm(f) for f in files}
        self.real_files = {real(f) for f in files}

    def allow_file(self, path: Path) -> None:
        self.files.add(norm(path))
        self.real_files.add(real(path))

    def check(self, path: Path, link: bool = False) -> None:
        resolved = real_parent(path) if link else real(path)
        for forbidden in forbidden_paths():
            if norm(path) == norm(forbidden) or resolved in (real(forbidden), real_parent(forbidden)):
                raise Refusal(f"{path} holds global hooks; this script never writes it")
        literal = norm(path) in self.files or any(inside(path, r) for r in self.roots)
        resolved_ok = resolved in self.real_files or any(
            under(resolved, r) for r in self.real_roots)
        if literal and resolved_ok:
            return
        if literal:
            raise Refusal(f"write refused: {path} resolves through a link to {resolved}, "
                          "outside the target")
        raise Refusal(f"write outside the target refused: {path}")


def under(resolved: str, root: str) -> bool:
    try:
        return os.path.commonpath([resolved, root]) == root
    except ValueError:                       # different drives
        return False


def missing_dirs(directory: Path) -> List[Path]:
    """Directories mkdir(parents=True) would create, outermost first."""
    out: List[Path] = []
    current = directory
    while not current.exists():
        out.append(current)
        current = current.parent
    return list(reversed(out))


def make_link(link: Path, target: Path) -> None:
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return
    except OSError:
        if os.name != "nt":
            raise
    # Windows without Developer Mode: a directory junction needs no privilege.
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0 or not os.path.lexists(str(link)):
        raise OSError(f"could not link {link}: {(result.stdout + result.stderr).strip()}")


def remove_link(link: Path) -> None:
    """Remove a symlink or junction itself. Never recurses into what it points at."""
    if not is_link(link):
        raise Refusal(f"{link} is no longer a link; left in place")
    try:
        os.unlink(str(link))
    except OSError:
        os.rmdir(str(link))                  # a Windows directory link or junction


# --------------------------------------------------------------------------- #
# Settings merges
# --------------------------------------------------------------------------- #

def substitute(value: Any, skill_dir: Path) -> Any:
    if isinstance(value, str):
        return (value.replace("{SKILL}", skill_dir.as_posix())
                .replace("{PYTHON}", Path(sys.executable).as_posix()))
    if isinstance(value, list):
        return [substitute(v, skill_dir) for v in value]
    if isinstance(value, dict):
        return {k: substitute(v, skill_dir) for k, v in value.items()}
    return value


def antigravity_entries(fragment: Dict[str, Any], skill_dir: Path) -> List[Tuple[str, Dict[str, Any]]]:
    """Antigravity workspace shape: event -> [{type, command, timeout}], no 'hooks' wrapper."""
    out: List[Tuple[str, Dict[str, Any]]] = []
    for event, groups in fragment.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                entry = {"type": hook.get("type", "command"),
                         "command": substitute(hook.get("command", ""), skill_dir)}
                if hook.get("timeout") is not None:
                    entry["timeout"] = hook["timeout"]
                out.append((event, entry))
    return out


def claude_entries(fragment: Dict[str, Any], skill_dir: Path) -> List[Tuple[str, Dict[str, Any]]]:
    return [(event, substitute(copy.deepcopy(group), skill_dir))
            for event, groups in fragment.get("hooks", {}).items() for group in groups]


def read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise Refusal(f"{path} is not valid JSON ({exc}); fix it by hand first") from exc
    if not isinstance(data, dict):
        raise Refusal(f"{path} must hold a JSON object")
    return data


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def container(data: Dict[str, Any], keys: Sequence[str], kind: type, created: List[str]) -> Any:
    """Walk keys, creating missing containers and recording each one created."""
    node: Any = data
    for depth, key in enumerate(keys):
        want = kind if depth == len(keys) - 1 else dict
        if key not in node:
            node[key] = want()
            created.append(".".join(keys[:depth + 1]))
        elif not isinstance(node[key], want):
            raise Refusal(f"'{'.'.join(keys[:depth + 1])}' is a {type(node[key]).__name__}, "
                          f"expected a {want.__name__}; fix it by hand first")
        node = node[key]
    return node


def merge(data: Dict[str, Any], harness: str, group: str,
          entries: Sequence[Tuple[str, Dict[str, Any]]], deny: Sequence[str]) -> Dict[str, Any]:
    """Append entries as new array elements; existing entries are never replaced."""
    created: List[str] = []
    added: List[Dict[str, Any]] = []
    for event, entry in entries:
        keys = ["hooks", event] if harness == "claude-code" else [group, event]
        array = container(data, keys, list, created)
        if entry not in array:
            array.append(entry)
            added.append({"keys": keys, "entry": entry})
    deny_added: List[str] = []
    if deny and harness == "claude-code":
        array = container(data, ["permissions", "deny"], list, created)
        for rule in deny:
            if rule not in array:
                array.append(rule)
                deny_added.append(rule)
    return {"created_keys": created, "entries": added, "deny": deny_added}


def unmerge(data: Dict[str, Any], record: Dict[str, Any]) -> List[str]:
    """Remove exactly the recorded entries, then any container this install created and left empty."""
    notes: List[str] = []
    for item in record.get("entries", []):
        node: Any = data
        for key in item["keys"]:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, list) and item["entry"] in node:
            node.remove(item["entry"])
        else:
            notes.append(f"hook entry under {'.'.join(item['keys'])} already gone")
    perms = data.get("permissions", {})
    deny = perms.get("deny") if isinstance(perms, dict) else None
    for rule in record.get("deny", []):
        if isinstance(deny, list) and rule in deny:
            deny.remove(rule)
        else:
            notes.append(f"deny entry {rule} already gone")
    for dotted in sorted(record.get("created_keys", []), key=lambda k: -k.count(".")):
        keys = dotted.split(".")
        parent: Any = data
        for key in keys[:-1]:
            parent = parent.get(key) if isinstance(parent, dict) else None
        if isinstance(parent, dict) and keys[-1] in parent and not parent[keys[-1]]:
            del parent[keys[-1]]
    return notes


def backup_path(path: Path) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.{stamp}.bak")
    counter = 1
    while os.path.lexists(str(candidate)):
        candidate = path.with_name(f"{path.name}.{stamp}-{counter}.bak")
        counter += 1
    return candidate


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #

def installs_file(arg: Optional[str]) -> Path:
    raw = arg or os.environ.get(INSTALLS_ENV) or str(Path.home() / ".demiurge" / "installs.jsonl")
    return Path(raw).expanduser().absolute()


def read_records(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def same(stored: Optional[str], path: Optional[Path]) -> bool:
    return stored is not None and path is not None and os.path.normcase(stored) == norm(path)


def active_install(rows: Sequence[Dict[str, Any]], skill_dir: Path, scope: str,
                   target: Optional[Path]) -> Optional[Dict[str, Any]]:
    removed = {r.get("removes") for r in rows if r.get("action") == "remove"}
    for row in reversed(rows):
        if (row.get("action") == "install" and row.get("id") not in removed
                and same(row.get("skill_dir"), skill_dir) and row.get("scope") == scope
                and (same(row.get("target"), target) if target else row.get("target") is None)):
            return row
    return None


def committed_path(path: Path, skill_dir: Path) -> str:
    """How a path is written into PROVENANCE.md.

    A PROVENANCE.md inside a git working tree gets committed, and the repo scanners refuse
    absolute user paths there: the path is relative to that tree when it sits inside it,
    and a sha256 prefix of the absolute path otherwise. Outside any tree it stays absolute.
    """
    root = git_root(skill_dir)
    if root is None:
        return path.as_posix()
    if inside(path, root):
        rel = Path(os.path.relpath(str(path), str(root))).as_posix()
        return "." if rel == "." else rel
    return "sha256:" + hashlib.sha256(norm(path).encode("utf-8")).hexdigest()[:16]


def provenance_block(skill_dir: Path, row: Dict[str, Any]) -> str:
    text = ""
    path = skill_dir / "PROVENANCE.md"
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    number = len(INSTALL_HEADING_RE.findall(text)) + 1
    label = row["scope"] if row["action"] == "install" else f"remove {row['scope']}"
    target = row.get("target")
    fields: List[Tuple[str, Any]] = [
        ("id", row["id"]), ("action", row["action"]), ("scope", row["scope"]),
        ("harnesses", row.get("harnesses", [])),
        ("target", committed_path(Path(target), skill_dir) if target else None),
        ("links", row.get("links_rel", [])),
        ("hook_entries", row.get("hook_count", 0)),
        ("deny_entries", row.get("deny_count", 0)),
        ("date", row["date"]),
    ]
    if row["action"] == "remove":
        fields.insert(2, ("removes", row["removes"]))
    body = "\n".join(f"  {key}: {json.dumps(value)}" for key, value in fields)
    rule = ("Install blocks are append-only: every install and removal adds one, and none is "
            "edited.\n\n") if number == 1 else ""
    return (f"\n## Install {number}: {label} ({row['date']})\n\n{rule}"
            f"```yaml\ninstall:\n{body}\n```\n")


# --------------------------------------------------------------------------- #
# Planning and applying
# --------------------------------------------------------------------------- #

@dataclass
class Context:
    skill_dir: Path
    name: str
    tier: str
    hooks: List[Hook]
    fragment: Dict[str, Any]
    scope: str
    harnesses: List[str]
    target: Optional[Path]
    installs: Path
    notes: List[str] = field(default_factory=list)


def inspect(skill_dir: Path) -> Tuple[str, str, List[Hook], Dict[str, Any]]:
    if not (skill_dir / "SKILL.md").is_file():
        raise Refusal(f"no SKILL.md in {skill_dir}")
    name = frontmatter_name(skill_dir) or skill_dir.name
    fragment = load_fragment(skill_dir)
    hooks = fragment_hooks(fragment) + frontmatter_hooks(skill_dir)
    return name, read_tier(skill_dir), hooks, fragment


def describe(skill_dir: Path) -> Dict[str, Any]:
    name, tier, hooks, fragment = inspect(skill_dir)
    blocking = any(h.classes() for h in hooks)
    scope, reason = recommend(tier, blocking)
    deny = fragment.get("deny", [])
    return {
        "skill": name,
        "trust_tier": tier,
        "question": f"Where should {name} and its hooks live?",
        "hooks": [{"source": h.source, "event": h.event, "matcher": h.matcher,
                   "blocks_classes": h.classes(), "plain": describe_hook(h)} for h in hooks],
        "deny": {"count": len(deny), "examples": deny[:3]},
        "options": ["project", "global", "staging"],
        "allowed": allowed_scopes(tier, blocking),
        "recommended": scope,
        "reason": reason,
    }


def print_description(info: Dict[str, Any]) -> None:
    print(f"{info['question']}  ({info['skill']}, {info['trust_tier']})")
    print("-" * 72)
    if info["hooks"]:
        for number, hook in enumerate(info["hooks"], 1):
            print(f"{number}. {hook['plain']}  [{hook['source']}]")
    else:
        print("No hooks.")
    if info["deny"]["count"]:
        print(f"Deny rules: {info['deny']['count']} tool patterns refused outright, e.g. "
              + ", ".join(info["deny"]["examples"]))
    print("-" * 72)
    labels = {"project": "Project (choose folder)", "global": "Global", "staging": "Staging"}
    for option in info["options"]:
        flags = []
        if option == info["recommended"]:
            flags.append("recommended")
        if option not in info["allowed"]:
            flags.append("refused")
        print(f"  {labels[option]}" + (f"  [{', '.join(flags)}]" if flags else ""))
    print(f"Recommended: {info['recommended']} - {info['reason']}")


def global_hook_notes(ctx: Context) -> List[str]:
    notes = []
    fm = [h for h in ctx.hooks if h.source == "frontmatter"]
    frag = [h for h in ctx.hooks if h.source == "fragment"]
    if frag:
        snippet = ["hooks:"]
        for event, group in claude_entries(ctx.fragment, ctx.skill_dir):
            snippet.append(f"  {event}:")
            snippet.append(f"    - matcher: {json.dumps(group.get('matcher', ''))}")
            snippet.append("      hooks:")
            for hook in group.get("hooks", []):
                snippet.append(f"        - type: {hook.get('type', 'command')}")
                snippet.append(f"          command: {json.dumps(hook.get('command', ''))}")
                if hook.get("timeout") is not None:
                    snippet.append(f"          timeout: {hook['timeout']}")
        notes.append(f"{FRAGMENT_NAME} hooks are not installed globally. This script never writes "
                     "~/.claude/settings.json or ~/.gemini/config/hooks.json. To carry them with "
                     "the skill, the SKILL.md frontmatter would need:\n" + "\n".join(snippet))
    if ctx.fragment.get("deny"):
        notes.append(f"{len(ctx.fragment['deny'])} permissions.deny entries cannot be set from "
                     "frontmatter; a global install leaves them out. Use --scope project to apply them.")
    if frag or fm:
        notes.append("Antigravity has no skill-level hooks: only global, workspace "
                     "(.agents/hooks.json) and plugin hooks. Use --scope project for Antigravity.")
    return notes


def plan_install(ctx: Context) -> Dict[str, Any]:
    links: List[Tuple[Path, str]] = []
    if ctx.scope == "project":
        for harness in ctx.harnesses:
            links.append((ctx.target / HARNESSES[harness]["skills"] / ctx.name, harness))
    elif ctx.scope == "global":
        links.append((ctx.target / ctx.name, "library"))
    plan: Dict[str, Any] = {"links": [], "settings": []}
    for link, harness in links:
        if inside(link, ctx.skill_dir):
            raise Refusal(f"{link} would sit inside the skill's own source")
        state = link_state(link, ctx.skill_dir)
        if state == "foreign":
            raise Refusal(f"{link} already exists and is not a link to {ctx.skill_dir}; left untouched")
        plan["links"].append({"path": link, "harness": harness, "state": state,
                              "mkdirs": missing_dirs(link.parent) if state == "absent" else []})
    if any(h.source == "frontmatter" for h in ctx.hooks):
        ctx.notes.append("SKILL.md frontmatter hooks register when the skill is invoked and stay "
                         "for the rest of that session; this script does not copy them anywhere.")
    if ctx.scope == "project" and (ctx.fragment.get("hooks") or ctx.fragment.get("deny")):
        for harness in ctx.harnesses:
            path = ctx.target / HARNESSES[harness]["hooks"]
            if harness == "claude-code":
                entries = claude_entries(ctx.fragment, ctx.skill_dir)
                deny = ctx.fragment.get("deny", [])
            else:
                entries = antigravity_entries(ctx.fragment, ctx.skill_dir)
                deny = []
                if ctx.fragment.get("deny"):
                    ctx.notes.append("Antigravity: this script knows no workspace deny-rule schema, so "
                                     "the permissions.deny entries go to .claude/settings.json only.")
                if any(g.get("matcher") for gs in ctx.fragment.get("hooks", {}).values() for g in gs):
                    ctx.notes.append("Antigravity entries carry no matcher; each hook script sees every "
                                     "call of its event and must filter by tool name itself.")
            if not entries and not deny:
                continue
            data = read_json(path)
            preview = copy.deepcopy(data)
            result = merge(preview, harness, ctx.name, entries, deny)
            plan["settings"].append({"path": path, "harness": harness, "exists": path.is_file(),
                                     "mkdirs": missing_dirs(path.parent), "result": result,
                                     "data": preview})
    if ctx.scope == "global":
        ctx.notes.extend(global_hook_notes(ctx))
    return plan


def print_plan(ctx: Context, plan: Dict[str, Any], applying: bool) -> None:
    verb = "" if applying else "would "
    print(f"install {ctx.name} ({ctx.tier}) scope={ctx.scope}"
          + (f" harness={','.join(ctx.harnesses)}" if ctx.scope == "project" else ""))
    print("-" * 72)
    for item in plan["links"]:
        if item["state"] == "ours":
            print(f"LINK     {item['path']} already points at the source; {verb}leave it")
        else:
            print(f"LINK     {verb}link {item['path']} -> {ctx.skill_dir}")
    for item in plan["settings"]:
        if item["exists"]:
            print(f"BACKUP   {verb}copy {item['path']} to a .bak beside it")
        for added in item["result"]["entries"]:
            print(f"HOOK     {verb}append to {'.'.join(added['keys'])} in {item['path']}: "
                  f"{json.dumps(added['entry'])}")
        if item["result"]["deny"]:
            print(f"DENY     {verb}append {len(item['result']['deny'])} entries to permissions.deny "
                  f"in {item['path']}")
        if not item["result"]["entries"] and not item["result"]["deny"]:
            print(f"SETTINGS {item['path']} already holds every entry")
    if ctx.scope == "staging":
        print(f"STAGING  nothing linked; the canonical source stays at {ctx.skill_dir}")
    print(f"RECORD   {verb}append to {ctx.skill_dir / 'PROVENANCE.md'} and {ctx.installs}")
    for note in ctx.notes:
        print(f"NOTE     {note}")


def new_id(*parts: str) -> str:
    seed = "|".join(parts) + dt.datetime.now(dt.timezone.utc).isoformat()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def append_records(ctx: Context, guard: Guard, row: Dict[str, Any]) -> None:
    provenance = ctx.skill_dir / "PROVENANCE.md"
    block = provenance_block(ctx.skill_dir, row)
    guard.check(provenance)
    if not provenance.is_file():
        block = f"# PROVENANCE — {ctx.name}\n" + block
    with provenance.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(block)
    guard.check(ctx.installs)
    # The sidecar's own missing parents (~/.demiurge on a first install) and nothing else.
    for directory in missing_dirs(ctx.installs.parent):
        guard.allow_file(directory)
        guard.check(directory)
    ctx.installs.parent.mkdir(parents=True, exist_ok=True)
    with ctx.installs.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def make_dirs(dirs: Sequence[Path], guard: Guard, created: List[str]) -> None:
    for directory in dirs:
        guard.check(directory)
        if not directory.exists():
            directory.mkdir()
            created.append(absolute(directory))


def apply_install(ctx: Context, plan: Dict[str, Any], guard: Guard) -> Dict[str, Any]:
    # Check every write before making any, so a refusal leaves nothing half done.
    for item in plan["links"]:
        guard.check(item["path"], link=True)
        for d in item["mkdirs"]:
            guard.check(d)
    for item in plan["settings"]:
        guard.check(item["path"])
        guard.check(backup_path(item["path"]))
        for d in item["mkdirs"]:
            guard.check(d)
    created_dirs: List[str] = []
    links_made: List[str] = []
    settings_rows: List[Dict[str, Any]] = []
    try:
        for item in plan["links"]:
            if item["state"] == "absent":
                make_dirs(item["mkdirs"], guard, created_dirs)
                make_link(item["path"], ctx.skill_dir)
                links_made.append(absolute(item["path"]))
        for item in plan["settings"]:
            result = item["result"]
            if not result["entries"] and not result["deny"]:
                continue
            make_dirs(item["mkdirs"], guard, created_dirs)
            backup = None
            if item["exists"]:
                backup = backup_path(item["path"])
                shutil.copy2(str(item["path"]), str(backup))
            settings_rows.append({"file": absolute(item["path"]), "harness": item["harness"],
                                  "created_file": not item["exists"],
                                  "backup": absolute(backup) if backup else None, **result})
            write_json(item["path"], item["data"])
    except Exception:
        rollback(links_made, settings_rows, created_dirs)
        raise
    rel = [Path(os.path.relpath(p, absolute(ctx.target))).as_posix() for p in links_made] if ctx.target else []
    return {
        "id": new_id(norm(ctx.skill_dir), ctx.scope, norm(ctx.target) if ctx.target else ""),
        "action": "install",
        "skill": ctx.name,
        "skill_dir": absolute(ctx.skill_dir),
        "scope": ctx.scope,
        "harnesses": ctx.harnesses if ctx.scope == "project" else [],
        "target": absolute(ctx.target) if ctx.target else None,
        "links": links_made,
        "links_rel": rel,
        "created_dirs": created_dirs,
        "settings": settings_rows,
        "hook_count": sum(len(s["entries"]) for s in settings_rows),
        "deny_count": sum(len(s["deny"]) for s in settings_rows),
        "date": dt.date.today().isoformat(),
    }


def rollback(links: Sequence[str], settings: Sequence[Dict[str, Any]], dirs: Sequence[str]) -> None:
    """Undo a failed apply: settings back from their backups, links and new directories removed."""
    for row in settings:
        path = Path(row["file"])
        if row["backup"]:
            shutil.copy2(row["backup"], str(path))
        elif path.is_file():
            path.unlink()
    for link in links:
        if is_link(Path(link)):
            remove_link(Path(link))
    for directory in reversed(dirs):
        path = Path(directory)
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def run_remove(ctx: Context, record: Dict[str, Any], guard: Guard, apply: bool) -> Dict[str, Any]:
    verb = "" if apply else "would "
    print(f"remove {ctx.name} scope={ctx.scope} (install {record['id']})")
    print("-" * 72)
    for link in record.get("links", []):
        path = Path(link)
        guard.check(path, link=True)
        if not os.path.lexists(link):
            print(f"LINK     {link} already gone")
        elif not is_link(path) or real(path) != real(ctx.skill_dir):
            print(f"LINK     {link} is no longer our link; {verb}leave it")
        else:
            print(f"UNLINK   {verb}unlink {link}")
            if apply:
                remove_link(path)
    for row in record.get("settings", []):
        path = Path(row["file"])
        guard.check(path)
        if not path.is_file():
            print(f"SETTINGS {path} already gone")
            continue
        data = read_json(path)
        notes = unmerge(data, row)
        print(f"HOOK     {verb}take {len(row['entries'])} hook and {len(row['deny'])} deny entries "
              f"out of {path}")
        for note in notes:
            print(f"NOTE     {note}")
        if apply:
            if row.get("created_file") and not data:
                path.unlink()
            else:
                backup = backup_path(path)
                guard.check(backup)
                shutil.copy2(str(path), str(backup))
                write_json(path, data)
    for directory in reversed(record.get("created_dirs", [])):
        path = Path(directory)
        guard.check(path)
        if apply and path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    print(f"RECORD   {verb}append the removal to {ctx.skill_dir / 'PROVENANCE.md'} and {ctx.installs}")
    return {
        "id": new_id(record["id"], "remove"),
        "action": "remove",
        "removes": record["id"],
        "skill": ctx.name,
        "skill_dir": absolute(ctx.skill_dir),
        "scope": ctx.scope,
        "harnesses": record.get("harnesses", []),
        "target": record.get("target"),
        "links_rel": record.get("links_rel", []),
        "hook_count": record.get("hook_count", 0),
        "deny_count": record.get("deny_count", 0),
        "date": dt.date.today().isoformat(),
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def parse_harnesses(raw: str) -> List[str]:
    names = [part.strip() for part in raw.split(",") if part.strip()]
    unknown = [n for n in names if n not in HARNESSES]
    if unknown or not names:
        raise Refusal(f"unknown harness {', '.join(unknown) or raw!r}; choose from {', '.join(HARNESSES)}")
    return list(dict.fromkeys(names))


def resolve_target(args: argparse.Namespace) -> Optional[Path]:
    if args.scope == "project":
        if not args.project:
            raise Refusal("--scope project needs --project <dir>")
        target = Path(args.project).expanduser().resolve()
        if not target.is_dir():
            raise Refusal(f"project {target} is not a directory")
        if norm(target) == norm(Path.home()):
            raise Refusal("the home directory is the global scope, not a project; use --scope global")
        return target
    if args.scope == "global":
        target = Path(args.library or DEFAULT_LIBRARY).expanduser().resolve()
        if not target.is_dir():
            raise Refusal(f"library {target} does not exist; create it first")
        return target
    return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("skill_dir", type=Path)
    parser.add_argument("--scope", choices=SCOPES)
    parser.add_argument("--project", help="project root for --scope project")
    parser.add_argument("--harness", default=DEFAULT_HARNESS,
                        help="comma-separated: claude-code, antigravity (project scope)")
    parser.add_argument("--library", help=f"skill library for --scope global (default {DEFAULT_LIBRARY})")
    parser.add_argument("--remove", action="store_true", help="undo the recorded install")
    parser.add_argument("--describe", action="store_true",
                        help="list hooks in plain words and the recommended scope, then exit")
    parser.add_argument("--i-know", action="store_true",
                        help="allow a global install whose hook blocks a whole tool class")
    parser.add_argument("--installs-file", help=f"install sidecar (default ${INSTALLS_ENV} or "
                                                "~/.demiurge/installs.jsonl)")
    parser.add_argument("--yes", action="store_true", help="apply; without it nothing is written")
    parser.add_argument("--json", action="store_true", help="machine-readable --describe output")
    args = parser.parse_args(argv)

    skill_dir = args.skill_dir.expanduser().resolve()
    try:
        if args.describe:
            info = describe(skill_dir)
            if args.json:
                print(json.dumps(info, indent=2))
            else:
                print_description(info)
            return 0
        if not args.scope:
            raise Refusal("--scope is required (project, global or staging), or use --describe")
        name, tier, hooks, fragment = inspect(skill_dir)
        harnesses = parse_harnesses(args.harness)
        target = resolve_target(args)
        installs = installs_file(args.installs_file)
        if git_root(installs.parent) is not None:
            raise Refusal(f"{installs} sits inside a git working tree; the sidecar holds absolute "
                          "paths and stays out of every checkout")
        ctx = Context(skill_dir, name, tier, hooks, fragment, args.scope, harnesses, target, installs)
        roots = [target] if target else []
        guard = Guard(roots, [skill_dir / "PROVENANCE.md", installs])
        rows = read_records(installs)
        existing = active_install(rows, skill_dir, args.scope, target)

        if args.remove:
            if existing is None:
                raise Refusal(f"no recorded {args.scope} install of {name}"
                              + (f" at {target}" if target else "") + f" in {installs}")
            row = run_remove(ctx, existing, guard, args.yes)
        else:
            reasons = refusals(name, tier, args.scope, hooks, args.i_know)
            if reasons:
                raise Refusal("; ".join(reasons))
            if existing is not None:
                print(f"ALREADY INSTALLED: {name} scope={args.scope} (install {existing['id']}). "
                      "Nothing to do; --remove first to change it.")
                return 0
            plan = plan_install(ctx)
            print_plan(ctx, plan, args.yes)
            if not args.yes:
                print("\nDRY RUN: nothing written. Re-run with --yes to apply.")
                return 0
            row = apply_install(ctx, plan, guard)
        if not args.yes:
            print("\nDRY RUN: nothing written. Re-run with --yes to apply.")
            return 0
        append_records(ctx, guard, row)
        print(f"\nDONE: {row['action']} {row['id']} recorded.")
        return 0
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
