#!/usr/bin/env python3
"""Claude Code hook that writes run-ledger rows.

Usage (from a hooks entry in the harness settings):
    python ledger_hook.py --event post-tool   # PostToolUse, matcher "Skill"
    python ledger_hook.py --event prompt      # UserPromptSubmit

The hook reads the harness event JSON on stdin and never blocks the user:

- ``--event prompt`` reads stdin and exits 0 before any import unless the prompt starts with
  ``::`` or ``/``. ``::bad [<class>] [...]`` and ``::ok`` record a verdict on the session's
  last invoke row and block the prompt, so the capture never reaches the model. ``/<name>``
  naming an installed skill records an invoke row with ``trigger: slash`` and passes through.
- ``--event post-tool`` records an invoke row with ``trigger: model`` for a Skill tool call,
  unless the session's last row is the same skill with ``trigger: slash`` from the last 60
  seconds.

No prompt text is ever stored. Text after a ``::bad`` class is accepted and dropped.
Every import sits inside one top-level try. Any failure writes ``ts, event, exception type``
to ``hook-errors.log`` in the ledger directory, and the hook still exits 0. A lock timeout
drops the row the same way. No network access.

The installed copy lives next to ledger_lib.py (see ``ledger.py install-hook``). In the repo,
ledger_lib.py is found under skills/marcus/scripts.
"""

import sys

PROMPT_KEY = '"prompt"'


def _event(argv):
    for index, arg in enumerate(argv):
        if arg == "--event" and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("--event="):
            return arg[len("--event="):]
    return ""


def _ordinary_prompt(raw):
    """True only when the prompt value is found and starts with neither '::' nor '/'.

    Uses str methods alone so the fast path imports nothing. When the key cannot be found,
    the full path runs and reports malformed input.
    """
    start = 0
    while True:
        at = raw.find(PROMPT_KEY, start)
        if at < 0:
            return False
        start = at + len(PROMPT_KEY)
        if at > 0 and raw[at - 1] == "\\":
            continue
        rest = raw[start:].lstrip(" \t\r\n")
        if not rest.startswith(":"):
            continue
        rest = rest[1:].lstrip(" \t\r\n")
        if not rest.startswith('"'):
            return False
        value = rest[1:]
        return not (value.startswith("::") or value.startswith("/"))


def _log_error(event, exc):
    """Append one line to hook-errors.log. A failure to log is reported on stderr."""
    try:
        import os
        from datetime import datetime, timezone
        override = os.environ.get("DEMIURGE_LEDGER_DIR", "").strip()
        base = override or os.path.join(os.path.expanduser("~"), ".demiurge", "ledger")
        os.makedirs(base, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(os.path.join(base, "hook-errors.log"), "a", encoding="utf-8") as out:
            out.write(f"{ts}\t{event or '-'}\t{type(exc).__name__}\n")
    except OSError as log_exc:
        sys.stderr.write(f"ledger hook: {type(exc).__name__}; log failed: "
                         f"{type(log_exc).__name__}\n")


def main():
    event = _event(sys.argv)
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        if event == "prompt" and _ordinary_prompt(raw):
            return 0
        _run(event, raw)
    except Exception as exc:  # the hook's single top-level catch: it logs and exits 0
        _log_error(event, exc)
    return 0


def _run(event, raw):
    import json
    import os
    import re
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "..", "..", "skills", "marcus", "scripts"), here):
        if path not in sys.path:
            sys.path.insert(0, path)
    import ledger_lib

    harness = "claude-code"
    dedupe_seconds = 60
    tail_bytes = 256 * 1024
    bad_re = re.compile(r"^::bad(?:\s+(\S+))?(?:\s+.*)?$", re.DOTALL)
    ok_re = re.compile(r"^::ok(?:\s+.*)?$", re.DOTALL)
    slash_re = re.compile(r"^/([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\s|$)")
    name_re = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("hook input is not a JSON object")

    def tail_lines(path):
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - tail_bytes))
            data = handle.read()
        lines = data.decode("utf-8", "replace").splitlines()
        if size > tail_bytes and lines:
            lines = lines[1:]
        return lines

    def transcript_meta():
        """model_id and version from the newest transcript entries that carry them."""
        found = {}
        path = payload.get("transcript_path")
        if not isinstance(path, str) or not os.path.isfile(path):
            return found
        for line in reversed(tail_lines(path)):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            message = entry.get("message")
            model = message.get("model") if isinstance(message, dict) else None
            if "model_id" not in found and isinstance(model, str) and model.strip() \
                    and not model.startswith("<"):
                found["model_id"] = model
            version = entry.get("version")
            if "version" not in found and isinstance(version, str) and version.strip():
                found["version"] = version
            if len(found) == 2:
                break
        return found

    def skill_dir(name):
        """The installed skill directory for a bare skill name, or None."""
        if not name_re.match(name):
            return None
        roots = []
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd:
            roots.append(Path(cwd) / ".claude" / "skills")
        roots.append(Path.home() / ".claude" / "skills")
        for root in roots:
            candidate = root / name
            if (candidate / "SKILL.md").is_file():
                return candidate
        return None

    def session_rows(session):
        """This session's rows from the current and previous month files, newest first."""
        base = ledger_lib.ledger_dir()
        now = datetime.now(timezone.utc)
        prev = now.replace(day=1) - timedelta(days=1)
        files = [base / f"runs-{prev.year:04d}-{prev.month:02d}.jsonl",
                 base / f"runs-{now.year:04d}-{now.month:02d}.jsonl"]
        rows = []
        for path in files:
            if not path.is_file():
                continue
            for line in tail_lines(path):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("session") == session \
                        and not ledger_lib.validate(row):
                    rows.append(row)
        rows.sort(key=lambda row: row["ts"])
        return list(reversed(rows))

    def parse_ts(ts):
        return datetime.fromisoformat(ts[:-1] + "+00:00")

    def invoke_row(name, trigger, session):
        row = {"run_id": ledger_lib.new_run_id(), "kind": "invoke", "origin": "organic",
               "skill": name, "trigger": trigger, "harness": harness}
        if session:
            row["session"] = session
        directory = skill_dir(name)
        if directory is not None:
            row["skill_sha"] = ledger_lib.skill_sha(directory)
        row.update(transcript_meta())
        return row

    session_id = payload.get("session_id")
    session = ledger_lib.hash_session(session_id) \
        if isinstance(session_id, str) and session_id else None

    if event == "post-tool":
        if payload.get("tool_name", "Skill") != "Skill":
            return
        tool_input = payload.get("tool_input")
        tool_input = tool_input if isinstance(tool_input, dict) else {}
        name = "unknown"
        for key in ("skill", "name"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                name = value.strip().lstrip("/")
                break
        if session:
            recent = session_rows(session)
            if recent:
                last = recent[0]
                age = (datetime.now(timezone.utc) - parse_ts(last["ts"])).total_seconds()
                if last["skill"] == name and last.get("trigger") == "slash" \
                        and 0 <= age <= dedupe_seconds:
                    return
        ledger_lib.append(invoke_row(name, "model", session))
        return

    if event != "prompt":
        raise ValueError("unknown --event")

    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        raise ValueError("prompt missing")

    bad = bad_re.match(prompt)
    ok = ok_re.match(prompt)
    if bad or ok:
        label = "bad" if bad else "ok"
        outcome = {"label": label, "source": "user"}
        if bad and bad.group(1) and bad.group(1).lower() in ledger_lib.FAILURE_CLASSES:
            outcome["failure_class"] = bad.group(1).lower()
        last = None
        if session:
            last = next((row for row in session_rows(session) if row["kind"] == "invoke"),
                        None)
        if last is None:
            reason = "ledger: no skill run in this session to label"
        else:
            verdict = {"run_id": last["run_id"], "kind": "verdict", "origin": "organic",
                       "skill": last["skill"], "session": session, "harness": harness,
                       "outcome": outcome}
            ledger_lib.append(verdict)
            reason = f"ledger: recorded {label} for {last['skill']}"
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
        return

    slash = slash_re.match(prompt)
    if slash and skill_dir(slash.group(1)) is not None:
        ledger_lib.append(invoke_row(slash.group(1), "slash", session))


if __name__ == "__main__":
    sys.exit(main())
