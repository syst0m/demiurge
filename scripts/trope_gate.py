#!/usr/bin/env python3
"""Negative-parallelism gate, shared by the Stop hook, the pre-save hook and the file gate.

Modes (stdlib only, no network):
  trope_gate.py [FILE ...]     scan files; no FILE scans every tracked *.md. Exit 1 on a hit.
  trope_gate.py --stop-hook    Claude Code Stop hook. Reads hook JSON on stdin.
                               Exit 2 with the reason on stderr blocks the stop.
  trope_gate.py --pretool      Claude Code PreToolUse hook for Write/Edit/MultiEdit on *.md.
                               Exit 2 blocks the tool call.

Patterns live in trope_patterns.txt beside this file. Prose only: fenced code,
inline code and block quotes are removed before matching.

Fails open on unreadable input. A gate must not block on its own parse failure.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATTERN_FILE = HERE / "trope_patterns.txt"
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")


def load_patterns(path: Path = PATTERN_FILE) -> list[tuple[str, re.Pattern]]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        name, _, regex = raw.partition("\t")
        out.append((name.strip(), re.compile(regex.strip(), re.IGNORECASE)))
    return out


PATTERNS = load_patterns()


def prose_lines(text: str):
    """Yield (lineno, prose) with fenced code, block quotes and inline code blanked."""
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or line.lstrip().startswith(">"):
            continue
        yield n, INLINE_CODE_RE.sub(" ", line)


def scan_text(text: str) -> list[tuple[int, str, str]]:
    hits = []
    for n, prose in prose_lines(text):
        for name, pat in PATTERNS:
            if pat.search(prose):
                hits.append((n, name, prose.strip()))
                break
    return hits


def format_hits(hits, label: str = "") -> str:
    head = f"{label}:" if label else ""
    lines = [f"{head}{n}: [{name}] {snip}" for n, name, snip in hits]
    return "\n".join(lines)


REASON = (
    "Negative parallelism or compressed contrast detected (i-have-adhd rule 11). "
    "Ban: \"it's not X, it's Y\", \"not because X, but because Y\", \"not just X, but Y\", "
    "and \"X, not Y\". Rewrite each flagged sentence as the one plain statement meant, then continue."
)


def tracked_markdown() -> list[str]:
    res = subprocess.run(["git", "ls-files", "*.md"], capture_output=True, text=True)
    return [p for p in res.stdout.splitlines() if p.strip()]


def run_files(args: list[str]) -> int:
    files = args or tracked_markdown()
    if not files:
        print("No Markdown files to scan.")
        return 0
    found = []
    for f in files:
        p = Path(f)
        if not p.is_file():
            continue
        found.append(format_hits(scan_text(p.read_text(encoding="utf-8", errors="ignore")), f))
    found = [x for x in found if x]
    if found:
        print("\n".join(found))
        print("\nError: negative parallelism or compressed contrast detected in the lines above.")
        return 1
    print("No AI tropes detected.")
    return 0


def _last_assistant_text(transcript: str) -> str:
    last = ""
    for line in Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        msg = rec.get("message") if isinstance(rec.get("message"), dict) else rec
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(b.get("text", "") for b in content
                             if isinstance(b, dict) and b.get("type") == "text")
        else:
            text = ""
        if text.strip():
            last = text
    return last


def run_stop_hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("stop_hook_active") is True:
        return 0  # loop guard: this hook already blocked once this turn
    text = payload.get("last_assistant_message") or ""
    transcript = payload.get("transcript_path") or payload.get("transcriptPath")
    if not text and transcript and Path(transcript).is_file():
        try:
            text = _last_assistant_text(transcript)
        except Exception:
            return 0
    if not text:
        return 0  # nothing to check is not a match
    hits = scan_text(text)
    if not hits:
        return 0
    print(REASON + "\n" + format_hits(hits), file=sys.stderr)
    return 2


def run_pretool() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    path = str(tool_input.get("file_path") or "")
    if not path.lower().endswith(".md"):
        return 0
    chunks = []
    if isinstance(tool_input.get("content"), str):
        chunks.append(tool_input["content"])
    if isinstance(tool_input.get("new_string"), str):
        chunks.append(tool_input["new_string"])
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
            chunks.append(edit["new_string"])
    hits = [h for c in chunks for h in scan_text(c)]
    if not hits:
        return 0
    print(REASON + f"\nFile: {path}\n" + format_hits(hits), file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    # Windows consoles default to cp1252; a snippet with a non-Latin symbol would crash the report.
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    if argv and argv[0] == "--stop-hook":
        return run_stop_hook()
    if argv and argv[0] == "--pretool":
        return run_pretool()
    return run_files(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
