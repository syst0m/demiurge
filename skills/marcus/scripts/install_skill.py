#!/usr/bin/env python3
"""Install a skill at one scope: a project, the global library, or staging only.

Run it; do not read it.

    python install_skill.py <skill-dir> --describe [--json]
    python install_skill.py <skill-dir> --scope project --project <dir> [--harness claude-code,antigravity]
                            [--antigravity-all-tools] [--yes]
    python install_skill.py <skill-dir> --scope global [--library <dir>] [--i-know] [--trust-provenance] [--yes]
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

Refused: global below T1, where the tier counts as recorded only when PROVENANCE.md is committed
in this script's own repository (a tier the skill declares about itself needs --trust-provenance);
global with a PreToolUse hook covering MCP tools, Bash or PowerShell, or with a frontmatter
'hooks:' block this script cannot read (unless --i-know); project for an unread (T4) skill; a skill
name that is not lowercase letters, digits and single hyphens; a linked PROVENANCE.md or sidecar;
an Antigravity hook with a Claude Code matcher (Antigravity tool names differ) unless
--antigravity-all-tools, or on an event Antigravity does not have; any write outside the target
project or library; a link path that already exists and is not ours.

Every applied install or removal is recorded twice: one line in the local sidecar
~/.demiurge/installs.jsonl ($DEMIURGE_INSTALLS_FILE or --installs-file), which holds absolute
paths and the exact entries --remove takes out again, and an append-only 'install:' block in the
skill's PROVENANCE.md (paths relative to the skill's git working tree, or hashed when outside it,
because PROVENANCE files in a working tree get committed; absolute otherwise). If either record
cannot be written, the install is rolled back.

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

# A PreToolUse matcher that covers any of these blocks a whole tool class. Each class has probe
# tool names the matcher is tested against, so "Bash|Write" covers Bash and an exact
# "mcp__gmail__send_message" covers no class. MCP probes vary the server name (with and without
# underscores or a connector UUID) and the tool verb; a matcher covers MCP tools when it matches
# MCP_MIN_PROBES of them, or when any alternative starts with mcp__ and holds a regex wildcard,
# since that reaches tools its author never saw: the reach Rule G-13 keeps out of the global scope.
TOOL_CLASS_PROBES: Dict[str, Tuple[str, ...]] = {
    "MCP tools": (
        "mcp__probe_server__probe_tool", "mcp__probe__probe", "mcp__gmail__send_message",
        "mcp__claude_ai_Gmail__create_draft", "mcp__github__create_pull_request",
        "mcp__slack__post_message", "mcp__filesystem__write_file", "mcp__calendar__create_event",
        "mcp__f1fa7737-2b02-4aac-81b0-1cc00295da83__send_message",
    ),
    "Bash": ("Bash",),
    "PowerShell": ("PowerShell",),
}
MCP_MIN_PROBES = 2
REGEX_WILDCARD = re.compile(r"[.*+?\[\](){}\\]")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")      # validate_skill.py NAME_PATTERN
NAME_MAX = 64

# Antigravity workspace hooks (antigravity.google/docs/hooks): tool events hold
# {matcher, hooks: [{type, command, timeout}]} entries; the other events hold the
# {type, command, timeout} handlers directly. Its tool names (run_command, write_to_file, ...)
# are not Claude Code's, so a Claude Code matcher cannot be carried over.
ANTIGRAVITY_TOOL_EVENTS = ("PreToolUse", "PostToolUse")
ANTIGRAVITY_EVENTS = ANTIGRAVITY_TOOL_EVENTS + ("PreInvocation", "PostInvocation", "Stop")
FRONTMATTER_HOOK_KEYS = {"matcher", "hooks", "type", "command", "timeout"}
UNPARSED_EVENT = "(unreadable hooks block)"

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
    unparsed: bool = False           # a frontmatter block this script could not read

    def classes(self) -> List[str]:
        if self.unparsed and self.event in ("PreToolUse", UNPARSED_EVENT):
            return list(TOOL_CLASS_PROBES)  # unreadable: assume it blocks everything
        return covered_classes(self.matcher) if self.event == "PreToolUse" else []


def covered_classes(matcher: Any) -> List[str]:
    """Tool classes a matcher covers. An absent, empty or '*' matcher covers every tool."""
    if matcher is None or (isinstance(matcher, str) and matcher.strip() in ("", "*")):
        return list(TOOL_CLASS_PROBES)
    if not isinstance(matcher, str):
        return list(TOOL_CLASS_PROBES)      # not a matcher string: assume the worst
    try:
        pattern = re.compile(matcher)
    except re.error:
        return list(TOOL_CLASS_PROBES)      # unreadable matcher: assume the worst
    out = [name for name, probes in TOOL_CLASS_PROBES.items()
           if sum(1 for probe in probes if pattern.fullmatch(probe))
           >= (MCP_MIN_PROBES if name == "MCP tools" else 1)]
    if "MCP tools" not in out and any(
            part.strip().lstrip("^(").startswith("mcp__") and REGEX_WILDCARD.search(part)
            for part in matcher.split("|")):
        out.insert(0, "MCP tools")
    return out


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


def unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text


EMPTY_YAML = ("", "[]", "{}", "null", "~")


def frontmatter_hooks(skill_dir: Path) -> List[Hook]:
    """Event, matcher and commands from a SKILL.md frontmatter 'hooks:' block.

    Reads only the documented block shape (event -> list of {matcher, hooks: [{type, command}]}),
    by indentation, so no YAML library is needed. It fails closed: anything else under 'hooks:'
    (flow style, a path, an unknown key) becomes an unparsed hook that counts as blocking every
    tool class, so an unreadable block can never pass as no hooks at all.
    """
    lines = frontmatter_text(skill_dir / "SKILL.md").splitlines()
    hooks: List[Hook] = []
    unparsed: List[str] = []
    in_hooks = False
    event_indent: Optional[int] = None
    entry_indent: Optional[int] = None
    event: Optional[str] = None
    current: Optional[Hook] = None

    def flag(name: Optional[str]) -> None:
        name = name or UNPARSED_EVENT
        if name not in unparsed:
            unparsed.append(name)

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0:
            key, _, value = stripped.partition(":")
            in_hooks = unquote(key) == "hooks"
            event_indent = entry_indent = None
            event, current = None, None
            if in_hooks and value.strip() not in EMPTY_YAML:
                flag(None)                   # inline or flow-style value
            continue
        if not in_hooks:
            continue
        if event_indent is None:
            event_indent = indent
        if indent <= event_indent:           # an event line
            key, sep, value = stripped.partition(":")
            event, current, entry_indent = (unquote(key) if sep else None), None, None
            if indent < event_indent or not sep or stripped.startswith(("-", "{", "[")):
                flag(event if not stripped.startswith(("-", "{", "[")) else None)
            elif value.strip() not in EMPTY_YAML:
                flag(event)
            continue
        if event is None:
            flag(None)
            continue
        if entry_indent is None:
            entry_indent = indent
        if indent < entry_indent:
            flag(event)
            continue
        if indent == entry_indent:
            if not stripped.startswith("-"):
                flag(event)
                continue
            current = None                   # a new entry under this event
        item = stripped[1:].strip() if stripped.startswith("-") else stripped
        if not item:
            continue
        if item.startswith(("{", "[")):
            flag(event)
            continue
        key, sep, value = item.partition(":")
        key, value = unquote(key), unquote(value)
        if not sep or key not in FRONTMATTER_HOOK_KEYS:
            flag(event)
            continue
        if key == "hooks":
            if value not in EMPTY_YAML:
                flag(event)
        elif key == "matcher":
            if current is None:
                current = Hook("frontmatter", event, value)
                hooks.append(current)
            else:
                current.matcher = value
        elif key == "command":
            if current is None:
                current = Hook("frontmatter", event, None)
                hooks.append(current)
            current.commands.append(value)
    hooks.extend(Hook("frontmatter", name, None, unparsed=True) for name in unparsed)
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
    return tier_in(path.read_text(encoding="utf-8", errors="replace"))


def tier_in(text: str) -> str:
    tiers: List[str] = []
    for block in YAML_FENCE_RE.findall(text):
        tiers.extend(TIER_RE.findall(block))
    return tiers[-1] if tiers else "T4"


def own_repo() -> Optional[Path]:
    """The git working tree holding this script: the Marcus repository."""
    return git_root(Path(__file__).resolve().parent)


def committed_tier(skill_dir: Path) -> Optional[str]:
    """trust_tier from PROVENANCE.md as committed at HEAD in the Marcus repository, or None.

    A skill outside that repository records its own tier, so a third party can ship
    'trust_tier: T1'. Only a committed record in this repository went through its review gates;
    uncommitted edits, including the install blocks this script appends, do not count.
    """
    repo = own_repo()
    path = skill_dir / "PROVENANCE.md"
    if repo is None or not path.is_file() or not inside(path, repo):
        return None
    rel = Path(os.path.relpath(absolute(path), absolute(repo))).as_posix()
    try:
        shown = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{rel}"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", check=False)
    except OSError:
        return None
    return tier_in(shown.stdout) if shown.returncode == 0 else None


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
    if hook.unparsed:
        where = "" if hook.event == UNPARSED_EVENT else f" under {hook.event}"
        return (f"SKILL.md frontmatter hooks{where} are in a shape this script cannot read, so "
                "they count as blocking every tool class: "
                + ", ".join(hook.classes() or ["none (not a PreToolUse event)"]) + ".")
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


def refusals(name: str, tier: str, scope: str, hooks: Sequence[Hook], i_know: bool,
             committed: Optional[str] = None, trust: bool = False) -> List[str]:
    """Why an install is refused. committed is the tier at HEAD in the Marcus repository (None
    when the skill is outside it); trust is --trust-provenance for a self-declared tier."""
    out: List[str] = []
    blocking = [h for h in hooks if h.classes()]
    effective = committed if committed is not None else tier
    source = "as committed in the Marcus repository" if committed is not None else "self-declared"
    if scope == "global" and base_tier(effective) != "T1":
        out.append(f"global install needs T1; {name} is {effective} ({source}; Rule G-13). "
                   "Use --scope project for operator testing, or --scope staging")
    elif scope == "global" and committed is None and not trust:
        out.append(f"{name}'s {tier} is self-declared: its PROVENANCE.md is not committed in the "
                   "Marcus repository, and a skill's author can write any tier there (Rule G-13). "
                   "Check that Marcus recorded it at G5, then pass --trust-provenance")
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
        # The allowed file itself is not followed: a PROVENANCE.md or sidecar that is a link
        # resolves elsewhere and fails check().
        self.real_files = {real_parent(f) for f in files}

    def allow_file(self, path: Path) -> None:
        self.files.add(norm(path))
        self.real_files.add(real_parent(path))

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
    # Windows without Developer Mode: a directory junction needs no privilege. It is made with
    # the Win32 call itself, never through cmd.exe, so no character in a path is a shell operator.
    try:
        import _winapi
        create = _winapi.CreateJunction
    except (ImportError, AttributeError) as exc:
        raise OSError(f"could not link {link}: no symlink privilege and no junction API") from exc
    create(absolute(target), absolute(link))
    if not os.path.lexists(str(link)):
        raise OSError(f"could not link {link}: the junction was not created")


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


def antigravity_handler(hook: Dict[str, Any], skill_dir: Path) -> Dict[str, Any]:
    entry = {"type": hook.get("type", "command"),
             "command": substitute(hook.get("command", ""), skill_dir)}
    if hook.get("timeout") is not None:
        entry["timeout"] = hook["timeout"]
    return entry


def antigravity_entries(fragment: Dict[str, Any], skill_dir: Path,
                        all_tools: bool) -> List[Tuple[str, Dict[str, Any]]]:
    """Antigravity workspace shape under the skill's group name (antigravity.google/docs/hooks).

    PreToolUse and PostToolUse hold {matcher, hooks: [{type, command, timeout}]} entries; the
    other events hold {type, command, timeout} handlers directly, with no 'hooks' wrapper.
    A Claude Code matcher names Claude Code tools (Bash, mcp__...), which Antigravity does not
    have, so it is refused rather than dropped: dropping it would widen the hook to every tool.
    all_tools (--antigravity-all-tools) writes matcher '*' instead, on the operator's say-so.
    """
    out: List[Tuple[str, Dict[str, Any]]] = []
    for event, groups in fragment.get("hooks", {}).items():
        if event not in ANTIGRAVITY_EVENTS:
            raise Refusal(f"Antigravity has no {event} hook event (it has "
                          f"{', '.join(ANTIGRAVITY_EVENTS)}); install with --harness claude-code")
        for group in groups:
            handlers = [antigravity_handler(h, skill_dir) for h in group.get("hooks", [])
                        if isinstance(h, dict)]
            if event not in ANTIGRAVITY_TOOL_EVENTS:
                out.extend((event, handler) for handler in handlers)
                continue
            matcher = group.get("matcher")
            if matcher not in (None, "", "*") and not all_tools:
                raise Refusal(f"the {event} hook's matcher {json.dumps(matcher)} names Claude Code "
                              "tools; Antigravity's tools are named differently (run_command, "
                              "write_to_file, ...), so it cannot be carried over. Install with "
                              "--harness claude-code, or pass --antigravity-all-tools to run it on "
                              "every Antigravity tool call (matcher '*')")
            out.append((event, {"matcher": "*", "hooks": handlers}))
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


def backup_state(path: Path) -> Optional[Dict[str, Any]]:
    """A backup's parsed content, or None when it cannot be read as a JSON object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    antigravity_all_tools: bool = False
    notes: List[str] = field(default_factory=list)


def inspect(skill_dir: Path) -> Tuple[str, str, List[Hook], Dict[str, Any]]:
    if not (skill_dir / "SKILL.md").is_file():
        raise Refusal(f"no SKILL.md in {skill_dir}")
    name = frontmatter_name(skill_dir) or skill_dir.name
    # The name becomes a link path and an Antigravity group key, so it must be one plain path
    # component: no separators, dots, spaces or shell characters.
    if len(name) > NAME_MAX or not NAME_RE.fullmatch(name):
        raise Refusal(f"skill name {name!r} must be lowercase letters, digits and single hyphens, "
                      f"at most {NAME_MAX} characters")
    if is_link(skill_dir / "PROVENANCE.md"):
        raise Refusal(f"{skill_dir / 'PROVENANCE.md'} is a link; the tier and install records "
                      "must live in the skill's own file")
    fragment = load_fragment(skill_dir)
    hooks = fragment_hooks(fragment) + frontmatter_hooks(skill_dir)
    return name, read_tier(skill_dir), hooks, fragment


def describe(skill_dir: Path) -> Dict[str, Any]:
    name, tier, hooks, fragment = inspect(skill_dir)
    committed = committed_tier(skill_dir)
    if committed is not None:
        tier = committed
    blocking = any(h.classes() for h in hooks)
    scope, reason = recommend(tier, blocking)
    if committed is None and scope == "global":
        reason += "; the tier is self-declared, so a global install needs --trust-provenance"
    deny = fragment.get("deny", [])
    return {
        "skill": name,
        "trust_tier": tier,
        "tier_source": "committed" if committed is not None else "self-declared",
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
    print(f"{info['question']}  ({info['skill']}, {info['trust_tier']} {info['tier_source']})")
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
    links: List[Tuple[Path, str, Path]] = []
    if ctx.scope == "project":
        for harness in ctx.harnesses:
            skills_dir = ctx.target / HARNESSES[harness]["skills"]
            links.append((skills_dir / ctx.name, harness, skills_dir))
    elif ctx.scope == "global":
        links.append((ctx.target / ctx.name, "library", ctx.target))
        if real(ctx.target) != norm(ctx.target):
            ctx.notes.append(f"the library {ctx.target} is itself a link to {real(ctx.target)}; "
                             "the new link lands there")
        tree = git_root(Path(os.path.realpath(str(ctx.target))))
        if tree is not None:
            ctx.notes.append(f"the library sits inside the git working tree {tree}; the link shows "
                             "there as an untracked file. Keep it out of that tree's commits")
    plan: Dict[str, Any] = {"links": [], "settings": []}
    for link, harness, skills_dir in links:
        if norm(link.parent) != norm(skills_dir):
            raise Refusal(f"{link} is not directly inside {skills_dir}")
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
                entries = antigravity_entries(ctx.fragment, ctx.skill_dir, ctx.antigravity_all_tools)
                deny = []
                if ctx.fragment.get("deny"):
                    ctx.notes.append("Antigravity: this script knows no workspace deny-rule schema, so "
                                     "the permissions.deny entries go to .claude/settings.json only.")
                if ctx.antigravity_all_tools and any(
                        g.get("matcher") not in (None, "", "*")
                        for e, gs in ctx.fragment.get("hooks", {}).items()
                        if e in ANTIGRAVITY_TOOL_EVENTS for g in gs):
                    ctx.notes.append("--antigravity-all-tools: the Antigravity entries use matcher '*', "
                                     "so each hook script sees every tool call of its event and must "
                                     "filter by tool name itself.")
            if not entries and not deny:
                continue
            exists = path.is_file()
            data = read_json(path)
            preview = copy.deepcopy(data)
            result = merge(preview, harness, ctx.name, entries, deny)
            plan["settings"].append({"path": path, "harness": harness, "exists": exists,
                                     "backup": backup_path(path) if exists else None,
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
            print(f"BACKUP   {verb}copy {item['path']} to {item['backup'].name}")
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


def prepare_records(ctx: Context, guard: Guard, create: bool) -> List[str]:
    """Check both record paths before anything is installed; with create, make the sidecar's
    missing parents (~/.demiurge on a first install) and nothing else."""
    provenance = ctx.skill_dir / "PROVENANCE.md"
    for path in (provenance, ctx.installs):
        if is_link(path):
            raise Refusal(f"{path} is a link; records are written only to a plain file")
        if os.path.lexists(str(path)) and not path.is_file():
            raise Refusal(f"{path} exists and is not a file")
        guard.check(path)
    made: List[str] = []
    for directory in missing_dirs(ctx.installs.parent):
        guard.allow_file(directory)
        guard.check(directory)
        if create:
            directory.mkdir()
            made.append(absolute(directory))
    return made


def append_text(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def truncate_to(path: Path, size: Optional[int]) -> None:
    """Put an appended-to file back to its earlier size, or remove it if it was new."""
    if size is None:
        if path.is_file():
            path.unlink()
        return
    with path.open("r+b") as handle:
        handle.truncate(size)


def append_records(ctx: Context, guard: Guard, row: Dict[str, Any]) -> None:
    """Sidecar line first (it is what --remove reads), then the PROVENANCE.md block. If either
    write fails, both files go back to their earlier size and the error propagates."""
    provenance = ctx.skill_dir / "PROVENANCE.md"
    block = provenance_block(ctx.skill_dir, row)
    if not provenance.is_file():
        block = f"# PROVENANCE — {ctx.name}\n" + block
    guard.check(ctx.installs)
    guard.check(provenance)
    sizes = {path: (path.stat().st_size if path.is_file() else None)
             for path in (ctx.installs, provenance)}
    try:
        append_text(ctx.installs, json.dumps(row, sort_keys=True) + "\n")
        append_text(provenance, block)
    except OSError:
        for path, size in sizes.items():
            try:
                truncate_to(path, size)
            except OSError:
                pass
        raise


def make_dirs(dirs: Sequence[Path], guard: Guard, created: List[str]) -> None:
    for directory in dirs:
        guard.check(directory)
        if not directory.exists():
            directory.mkdir()
            created.append(absolute(directory))


def check_plan(plan: Dict[str, Any], guard: Guard) -> None:
    """Check every write a plan makes before making any, so a refusal leaves nothing half done."""
    for item in plan["links"]:
        guard.check(item["path"], link=True)
        for d in item["mkdirs"]:
            guard.check(d)
    for item in plan["settings"]:
        guard.check(item["path"])
        if item["backup"] is not None:
            guard.check(item["backup"])
        for d in item["mkdirs"]:
            guard.check(d)


def apply_install(ctx: Context, plan: Dict[str, Any], guard: Guard) -> Dict[str, Any]:
    check_plan(plan, guard)
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
            backup = item["backup"]
            if backup is not None:
                if os.path.lexists(str(backup)):
                    raise Refusal(f"backup {backup} appeared after planning; nothing overwritten")
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
        # When nothing else changed since the install, the file goes back byte for byte from the
        # install's backup, so the user's own formatting and characters survive.
        original = Path(row["backup"]) if row.get("backup") else None
        restore = (original is not None and original.is_file() and not is_link(original)
                   and backup_state(original) == data)
        if apply:
            if row.get("created_file") and not data:
                path.unlink()
            else:
                backup = backup_path(path)
                guard.check(backup)
                shutil.copy2(str(path), str(backup))
                if restore:
                    path.write_bytes(original.read_bytes())
                else:
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
        # Kept as written, not resolved: ~/.claude/skills may be a link into another git tree,
        # and the link and record belong at the library path the operator named. The Guard
        # still resolves every write.
        target = Path(absolute(Path(args.library or DEFAULT_LIBRARY).expanduser()))
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
    parser.add_argument("--trust-provenance", action="store_true",
                        help="accept a T1 the skill's own PROVENANCE.md declares, outside the "
                             "Marcus repository, for a global install")
    parser.add_argument("--antigravity-all-tools", action="store_true",
                        help="write an Antigravity tool hook with matcher '*' when its Claude Code "
                             "matcher cannot be carried over")
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
        ctx = Context(skill_dir, name, tier, hooks, fragment, args.scope, harnesses, target, installs,
                      antigravity_all_tools=args.antigravity_all_tools)
        roots = [target] if target else []
        guard = Guard(roots, [skill_dir / "PROVENANCE.md", installs])
        prepare_records(ctx, guard, create=False)
        rows = read_records(installs)
        existing = active_install(rows, skill_dir, args.scope, target)
        record_dirs: List[str] = []

        if args.remove:
            if existing is None:
                raise Refusal(f"no recorded {args.scope} install of {name}"
                              + (f" at {target}" if target else "") + f" in {installs}")
            if args.yes:
                record_dirs = prepare_records(ctx, guard, create=True)
            row = run_remove(ctx, existing, guard, args.yes)
        else:
            committed = committed_tier(skill_dir) if args.scope == "global" else None
            reasons = refusals(name, tier, args.scope, hooks, args.i_know,
                               committed, args.trust_provenance)
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
            check_plan(plan, guard)
            record_dirs = prepare_records(ctx, guard, create=True)
            try:
                row = apply_install(ctx, plan, guard)
            except Exception:
                rollback([], [], record_dirs)
                raise
        if not args.yes:
            print("\nDRY RUN: nothing written. Re-run with --yes to apply.")
            return 0
        try:
            append_records(ctx, guard, row)
        except OSError as exc:
            if row["action"] == "install":
                rollback(row["links"], row["settings"], [*row["created_dirs"], *record_dirs])
                raise OSError(f"could not record the install, so it was rolled back: {exc}") from exc
            raise OSError(f"removal applied but not recorded ({exc}); re-run --remove to "
                          "record it") from exc
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
