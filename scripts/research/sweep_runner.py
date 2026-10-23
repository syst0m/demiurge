"""Weekend runner for the Buckminster research sweep.

Windows Task Scheduler starts this script at six weekend slots (Saturday and Sunday,
09:00, 14:00 and 20:00), at logon, and when a missed slot becomes available. The script
decides what to do from the state file, so extra starts are harmless:

- A weekend that already succeeded is skipped.
- Each attempt runs the sweep headless with `claude -p` and reads its SWEEP_RESULT line.
- Success always notifies (PR opened, action required, or no change).
- Saturday: when the evening slot has passed with no success, notify once and retry Sunday.
- Sunday: when the evening slot has passed with no success, notify once (weekend failed).
- A later start that finds a weekend slot with no attempt reports it as missed (PC off).
- The first start of each day checks the claude and gws logins and reports a broken one.

Notifications: a Windows toast plus an email to the owner through `gws gmail +send`. The
owner is SWEEP_NOTIFY_EMAIL, else the gws login user. An email that fails raises its own
toast and stays in outbox.json, and each start sends the outbox again.

Installed copy: ~/.demiurge/sweep/sweep_runner.py, which the Task Scheduler task starts.
Tests: scripts/research/test_sweep_runner.py.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("DEMIURGE_SWEEP_HOME", Path.home() / ".demiurge" / "sweep"))
STATE = HOME / "state.json"
LOCK = HOME / "running.lock"
LOGS = HOME / "logs"
PROMPT = HOME / "prompt.md"
REPO = Path(os.environ.get("DEMIURGE_REPO", Path.home() / "Documents" / "code" / "demiurge"))
OUTBOX = HOME / "outbox.json"
CLAUDE = os.environ.get("SWEEP_CLAUDE", "claude")
GWS = os.environ.get("SWEEP_GWS", "gws")
RUN_TIMEOUT_S = 3 * 3600
LOCK_STALE_S = RUN_TIMEOUT_S + 600
EVENING_HOUR = 20
SLOTS = [9, 14, 20]
GMAIL_SEND_SCOPES = {"https://mail.google.com/", "https://www.googleapis.com/auth/gmail.send",
                     "https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/gmail.modify"}

ALLOWED_TOOLS = [
    "Bash(git:*)", "Bash(python:*)", "Bash(python3:*)", "Bash(bash scripts/sync-skills.sh:*)",
    "Bash(gh pr create:*)", "Bash(gh pr view:*)", "Bash(gh pr list:*)", "Bash(gh api:*)",
    "Bash(cd:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(test:*)", "Bash(pwd:*)", "Bash(case:*)",
    "Read", "Edit", "Write", "Glob", "Grep", "WebSearch", "WebFetch", "Skill", "TodoWrite",
    "mcp__082ce661-00b0-4a0f-b69b-da3ff0aab91c", "mcp__8ec6ab15-27d6-47fe-86b4-6e3f363dee6e",
    "mcp__d85faa48-b615-43cd-bb28-b1c2d9f112e7",
]
DENIED_TOOLS = ["Bash(git push origin main:*)", "Bash(gh pr merge:*)", "Bash(gh pr comment:*)",
                "Bash(gh pr review:*)", "Bash(gh pr edit:*)", "Bash(gws:*)"]

RESULT_RE = re.compile(r"^SWEEP_RESULT\s+(\{.*\})\s*$", re.MULTILINE)


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"weekends": {}}


def save_state(state: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE)


def weekend_key(day: dt.date) -> str:
    """The Saturday that starts the weekend `day` belongs to, or the latest past Saturday."""
    back = (day.weekday() - 5) % 7
    return (day - dt.timedelta(days=back)).isoformat()


def notify(title: str, body: str) -> None:
    log(f"NOTIFY {title}: {body}")
    toast(title, body)
    error = send_email(title, body)
    if error:
        queue_email(title, body)
        toast("Research sweep email failed",
              f"{title}: {error[:120]}. Fix: run gws auth login. The email is kept and sent at the next start.")


def toast(title: str, body: str) -> None:
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
        "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$x = $t.GetElementsByTagName('text');"
        f"$x.Item(0).AppendChild($t.CreateTextNode({ps_quote(title)})) > $null;"
        f"$x.Item(1).AppendChild($t.CreateTextNode({ps_quote(body[:250])})) > $null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Research sweep').Show([Windows.UI.Notifications.ToastNotification]::new($t))"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       timeout=30, capture_output=True)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"toast failed: {exc!r}")


def send_email(title: str, body: str) -> str:
    """Send one email; return "" on success, else the reason it failed."""
    to = owner_email()
    if not to:
        error = "no owner address: set SWEEP_NOTIFY_EMAIL or log in to gws"
    else:
        try:
            r = subprocess.run([GWS, "gmail", "+send", "--to", to, "--subject", f"[Research sweep] {title}",
                                "--body", body], timeout=120, capture_output=True, text=True)
            error = "" if r.returncode == 0 else f"rc={r.returncode}: {(r.stderr or '').strip().splitlines()[-1:]}"
        except (OSError, subprocess.SubprocessError) as exc:
            error = repr(exc)
    if error:
        log(f"email failed: {error}")
    return error


def queue_email(title: str, body: str) -> None:
    queued = load_outbox()
    queued.append({"title": title, "body": body})
    OUTBOX.write_text(json.dumps(queued, indent=2), encoding="utf-8")


def load_outbox() -> list:
    try:
        return json.loads(OUTBOX.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def flush_outbox() -> None:
    """Send each queued email again; keep the ones that still fail."""
    queued = load_outbox()
    if not queued:
        return
    kept = [m for m in queued if send_email(m["title"], m["body"])]
    if kept:
        OUTBOX.write_text(json.dumps(kept, indent=2), encoding="utf-8")
    else:
        OUTBOX.unlink(missing_ok=True)
    log(f"outbox: sent {len(queued) - len(kept)}, kept {len(kept)}")


def gws_status() -> dict:
    try:
        r = subprocess.run([GWS, "auth", "status"], timeout=60, capture_output=True, text=True)
        out = r.stdout or ""
        return json.loads(out[out.index("{"):])
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def owner_email() -> str:
    return os.environ.get("SWEEP_NOTIFY_EMAIL") or gws_status().get("user", "")


def login_problems() -> list[str]:
    """Each broken login the sweep depends on, as "name: problem. Fix: action"."""
    problems = []
    try:
        r = subprocess.run([CLAUDE, "auth", "status"], timeout=60, capture_output=True, text=True)
        logged_in = r.returncode == 0 and json.loads(r.stdout or "{}").get("loggedIn") is True
    except (OSError, subprocess.SubprocessError, ValueError):
        logged_in = False
    if not logged_in:
        problems.append("claude: not logged in. Fix: run claude in a terminal and type /login")
    gws = gws_status()
    if not gws.get("token_valid"):
        problems.append("gws: no valid token. Fix: run gws auth login")
    elif not GMAIL_SEND_SCOPES & set(gws.get("scopes", [])):
        problems.append("gws: token has no Gmail send scope. Fix: run gws auth login and include Gmail")
    return problems


def check_logins(state: dict, today: dt.date) -> None:
    """Run the login check at the first start of each day and report a broken login."""
    if state.get("login_check") == today.isoformat():
        return
    state["login_check"] = today.isoformat()
    save_state(state)
    problems = login_problems()
    if problems:
        names = ", ".join(p.split(":")[0] for p in problems)
        notify(f"Login check failed: {names}",
               "The sweep cannot run or email you until this is fixed. " + " ".join(problems))


def ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def log(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    with (LOGS / "runner.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {msg}\n")


def acquire_lock() -> bool:
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < LOCK_STALE_S:
        return False
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def run_sweep(now: dt.datetime) -> dict:
    LOGS.mkdir(parents=True, exist_ok=True)
    out_path = LOGS / f"sweep-{now:%Y%m%d-%H%M}.log"
    cmd = [CLAUDE, "-p", PROMPT.read_text(encoding="utf-8"), "--model", "claude-opus-5-5",
           "--allowedTools", *ALLOWED_TOOLS, "--disallowedTools", *DENIED_TOOLS]
    env = dict(os.environ, DEMIURGE_REPO=str(REPO).replace("\\", "/"))
    try:
        r = subprocess.run(cmd, cwd=REPO, env=env, timeout=RUN_TIMEOUT_S,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        text = (r.stdout or "") + "\n" + (r.stderr or "")
        rc = r.returncode
    except subprocess.TimeoutExpired as exc:
        text, rc = f"timeout after {RUN_TIMEOUT_S}s\n{exc.stdout or ''}", -1
    except OSError as exc:
        text, rc = f"could not start claude: {exc!r}", -2
    out_path.write_text(text, encoding="utf-8")
    matches = RESULT_RE.findall(text)
    if matches:
        try:
            result = json.loads(matches[-1])
        except ValueError:
            result = {"status": "failed", "summary": "SWEEP_RESULT line was not valid JSON"}
    else:
        tail = " ".join(text.strip().splitlines()[-3:])[:300]
        result = {"status": "failed", "summary": f"no SWEEP_RESULT line (exit {rc}): {tail}"}
    result["log"] = str(out_path)
    return result


def missed_slots(day_iso: str, attempts: list, now: dt.datetime) -> list[str]:
    day = dt.date.fromisoformat(day_iso)
    tried = {dt.datetime.fromisoformat(a["at"]) for a in attempts}
    missed = []
    for hour in SLOTS:
        slot = dt.datetime.combine(day, dt.time(hour))
        if slot > now:
            continue
        window_end = slot + dt.timedelta(hours=5)
        if not any(slot - dt.timedelta(minutes=30) <= t < window_end for t in tried):
            missed.append(f"{slot:%a %H:%M}")
    return missed


def describe_attempts(attempts: list) -> str:
    if not attempts:
        return "no attempts ran"
    return "; ".join(f"{a['at'][5:16]} {a['result'].get('status')}: {a['result'].get('summary', '')[:120]}"
                     for a in attempts)


def main() -> int:
    now = dt.datetime.fromisoformat(os.environ["SWEEP_NOW"]) if os.environ.get("SWEEP_NOW") else dt.datetime.now()
    today = now.date()
    state = load_state()
    flush_outbox()
    check_logins(state, today)
    key = weekend_key(today)
    wk = state["weekends"].setdefault(key, {"attempts": [], "success": False, "notified": []})
    sat = dt.date.fromisoformat(key)
    sun = sat + dt.timedelta(days=1)

    if today.weekday() < 5:
        # A weekday start (logon or a missed slot fired late): report an unfinished weekend once.
        if not wk["success"] and "final" not in wk["notified"]:
            missed = missed_slots(sat.isoformat(), wk["attempts"], now) + missed_slots(sun.isoformat(), wk["attempts"], now)
            notify("Weekend sweep did not complete",
                   f"Weekend of {key}: {describe_attempts(wk['attempts'])}. Missed slots (PC off or asleep): "
                   f"{', '.join(missed) or 'none'}. Run it by hand: python \"{Path(__file__)}\" --force")
            wk["notified"].append("final")
            save_state(state)
        if "--force" not in sys.argv:
            return 0

    if wk["success"]:
        return 0

    if today == sun and "saturday" not in wk["notified"]:
        sat_attempts = [a for a in wk["attempts"] if a["at"].startswith(sat.isoformat())]
        missed = missed_slots(sat.isoformat(), sat_attempts, now)
        notify("Saturday sweep did not complete; retrying Sunday",
               f"Saturday {key}: {describe_attempts(sat_attempts)}. Missed slots: {', '.join(missed) or 'none'}.")
        wk["notified"].append("saturday")
        save_state(state)

    if not acquire_lock():
        log("another attempt is running; exit")
        return 0
    try:
        log(f"attempt for weekend {key}")
        result = run_sweep(now)
        wk["attempts"].append({"at": now.isoformat(timespec="seconds"), "result": result})
        status = result.get("status")
        if status in ("pr_opened", "no_change", "action_required"):
            wk["success"] = True
            titles = {"pr_opened": "PR opened: review it",
                      "no_change": "No changes this week",
                      "action_required": "Action required"}
            body = result.get("summary", "")
            if result.get("pr_url"):
                body += f"\nPR: {result['pr_url']}"
            if result.get("action"):
                body += f"\nNext: {result['action']}"
            body += f"\nLog: {result['log']}"
            notify(titles[status], body)
        else:
            evening_passed = now.hour >= EVENING_HOUR
            if today == sat and evening_passed and "saturday" not in wk["notified"]:
                notify("Saturday sweep failed; retrying Sunday",
                       f"{describe_attempts([a for a in wk['attempts'] if a['at'].startswith(key)])}. Log: {result['log']}")
                wk["notified"].append("saturday")
            elif today == sun and evening_passed and "final" not in wk["notified"]:
                notify("Weekend sweep failed",
                       f"All weekend attempts failed: {describe_attempts(wk['attempts'])}. Log: {result['log']}")
                wk["notified"].append("final")
        save_state(state)
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
