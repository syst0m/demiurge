#!/usr/bin/env python3
"""
ledger.py - Read, label, stage and prune the metadata-only run ledger.

The ledger lives at $DEMIURGE_LEDGER_DIR, else ~/.demiurge/ledger/, one
runs-YYYY-MM.jsonl file per UTC month. Rows are written by the pinned hook,
by eval_runner.py --ledger and by this tool. The schema and the locking live in
skills/marcus/scripts/ledger_lib.py.

A run's label is the label of its latest verdict row. A run with no verdict row
is unlabeled.

    failures <skill> [--last 10] [--source user,deterministic] [--json]
        Runs of <skill> whose latest verdict is `bad` from one of the sources.

    verdict <run_id> --label ok|bad|unknown [--class <failure_class>] [--note]
        Appends a user verdict row. `bad` needs --class.

    promote <run_id> --skill <name> [--transcript <file>] [--transcripts <dir>]
        Stages the run's triggering user message, redacted, as a regression eval
        case at <ledger>/promoted/<skill>/<run_id>.json and appends a verdict row
        whose refs.promoted_to names that file. It never writes into a skill
        directory and has no --yes: a person reads the staged case and copies
        it into evals.json by hand.

    dismiss <run_id> --reason <text>
        Appends a `dismissed` verdict row.

    inventory [--by skill|harness|failure_class] [--days 90] [--min-n 20]
        Organic runs per group. Below --min-n labeled runs it prints counts only.
        At --min-n and above it adds a 95% Wilson interval. It never prints a
        bare rate.

    purge --older-than 180
        Rewrites closed month files older than the cutoff under ledger.lock,
        keeping the rows of unpromoted `bad` runs. Temp file, then atomic rename.

    check-kill --installed YYYY-MM-DD [--today YYYY-MM-DD]
        Evaluates kill criteria 1-4 from docs/RUN_LEDGER.md and prints PASS or KILL.

    install-hook --dest <dir>
        Copies ledger_hook.py and ledger_lib.py to <dir> and prints the settings
        snippet. It never edits a settings file.

Ledger counts never gate, score or rank a skill or a harness. See docs/RUN_LEDGER.md.
Stdlib only. No network access.

Exit codes:
    0  success, or check-kill printed PASS
    1  refused (unknown run, existing staged case, no user message), or KILL
    2  usage error, or the ledger lock timed out
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
MARCUS_SCRIPTS = REPO_ROOT / "skills" / "marcus" / "scripts"
sys.path.insert(0, str(MARCUS_SCRIPTS))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import ledger_lib  # noqa: E402
from scan_security_and_pii import PII_PATH_PATTERNS, SECRET_PATTERNS  # noqa: E402

HOOK_SOURCE = Path(__file__).resolve().parent / "ledger_hook.py"
LIB_SOURCE = MARCUS_SCRIPTS / "ledger_lib.py"
TRANSCRIPTS_ENV = "DEMIURGE_TRANSCRIPTS_DIR"
PROMOTED_DIR = "promoted"
HOOK_ERRORS = "hook-errors.log"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

REVIEW_DAYS = 56          # kill review 8 weeks after install
MIN_PROMOTED = 3          # criterion 1
MAX_UNKNOWN_SHARE = 0.80  # criterion 2
MIN_LABELED_FAILURES = 10  # criterion 2
MAX_SILENT_DAYS = 14      # criterion 4

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
ABS_PATHS = (
    re.compile(r"\b[A-Za-z]:[\\/][^\s\"'<>|]*"),
    re.compile(r"\\\\[^\s\\\"'<>|]+\\[^\s\"'<>|]*"),
    re.compile(r"(?<![\w.~/-])~[\\/][^\s\"'<>|]*"),
    re.compile(r"(?<![\w.~/:-])/(?:[\w.@-]+/)+[\w.@-]*"),
)
COMMAND_NAME = re.compile(r"<command-name>\s*(.*?)\s*</command-name>", re.S)
COMMAND_ARGS = re.compile(r"<command-args>\s*(.*?)\s*</command-args>", re.S)


class Refused(Exception):
    """A guard refused the command."""


# --- reading the ledger ------------------------------------------------------

def parse_ts(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts[:-1] + "+00:00" if ts.endswith("Z") else ts)


def collect_runs(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group rows by run_id into {invoke, verdicts, label, source, failure_class, promoted_to}."""
    runs: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        run = runs.setdefault(row["run_id"], {"run_id": row["run_id"], "invoke": None,
                                              "verdicts": [], "promoted_to": None})
        if row["kind"] == "invoke":
            if run["invoke"] is None:
                run["invoke"] = row
            continue
        run["verdicts"].append(row)
        promoted = row.get("refs", {}).get("promoted_to")
        if promoted:
            run["promoted_to"] = promoted
    for run in runs.values():
        latest = run["verdicts"][-1]["outcome"] if run["verdicts"] else None
        run["label"] = latest["label"] if latest else None
        run["source"] = latest["source"] if latest else None
        run["failure_class"] = latest.get("failure_class") if latest else None
        run["note"] = latest.get("note") if latest else None
        first = run["invoke"] or run["verdicts"][0]
        run["skill"] = first["skill"]
        run["origin"] = first["origin"]
        run["harness"] = first.get("harness")
        run["ts"] = first["ts"]
    return runs


def load_runs() -> Dict[str, Dict[str, Any]]:
    return collect_runs(ledger_lib.iter_rows())


def require_run(run_id: str) -> Dict[str, Any]:
    run = load_runs().get(run_id)
    if run is None:
        raise Refused(f"no ledger row for run_id {run_id!r}")
    return run


def verdict_row(run: Dict[str, Any], outcome: Dict[str, Any],
                refs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    row: Dict[str, Any] = {"run_id": run["run_id"], "kind": "verdict", "origin": run["origin"],
                           "skill": run["skill"], "outcome": outcome}
    invoke = run["invoke"] or {}
    for key in ("session", "harness", "model_id", "version", "skill_sha"):
        if key in invoke:
            row[key] = invoke[key]
    if refs:
        row["refs"] = refs
    return row


# --- failures, verdict, dismiss ----------------------------------------------

def cmd_failures(args: argparse.Namespace) -> int:
    sources = [s.strip() for s in args.source.split(",") if s.strip()]
    unknown = sorted(set(sources) - set(ledger_lib.SOURCES))
    if unknown:
        print(f"ERROR: unknown source {', '.join(unknown)}; one of {ledger_lib.SOURCES}",
              file=sys.stderr)
        return 2
    runs = [run for run in load_runs().values()
            if run["skill"] == args.skill and run["label"] == "bad" and run["source"] in sources]
    runs.sort(key=lambda run: run["ts"])
    runs = runs[-args.last:] if args.last > 0 else []
    fields = ("run_id", "ts", "harness", "source", "failure_class", "note", "promoted_to")
    if args.json:
        print(json.dumps([{key: run[key] for key in fields} for run in runs], indent=2))
        return 0
    if not runs:
        print(f"no failures for {args.skill} from {','.join(sources)}")
        return 0
    for run in runs:
        staged = " staged" if run["promoted_to"] else ""
        note = f"  {run['note']}" if run["note"] else ""
        print(f"{run['run_id']}  {run['ts'][:19]}  {run['failure_class'] or 'unclassified'}"
              f"  {run['source']}  {run['harness'] or '-'}{staged}{note}")
    return 0


def cmd_verdict(args: argparse.Namespace) -> int:
    if args.label == "bad" and not args.failure_class:
        print("ERROR: --label bad needs --class", file=sys.stderr)
        return 2
    if args.label != "bad" and args.failure_class:
        print("ERROR: --class applies only to --label bad", file=sys.stderr)
        return 2
    run = require_run(args.run_id)
    outcome: Dict[str, Any] = {"label": args.label, "source": "user"}
    if args.failure_class:
        outcome["failure_class"] = args.failure_class
    if args.note:
        outcome["note"] = args.note
    ledger_lib.append(verdict_row(run, outcome))
    print(f"recorded {args.label} for {run['skill']} run {args.run_id}")
    return 0


def cmd_dismiss(args: argparse.Namespace) -> int:
    run = require_run(args.run_id)
    ledger_lib.append(verdict_row(run, {"label": "dismissed", "source": "user",
                                        "note": args.reason}))
    print(f"dismissed {run['skill']} run {args.run_id}")
    return 0


# --- promote -----------------------------------------------------------------

def redact(text: str) -> str:
    """Mask secrets, user paths, emails and absolute paths. Free-text personal content stays."""
    patterns = [p for p, _ in SECRET_PATTERNS] + [p for p, _ in PII_PATH_PATTERNS]
    patterns += [EMAIL, *ABS_PATHS]
    for pattern in patterns:
        text = pattern.sub("[REDACTED]", text)
    return text


def transcripts_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    override = os.environ.get(TRANSCRIPTS_ENV, "").strip()
    return Path(override) if override else Path.home() / ".claude" / "projects"


def find_transcript(session: str, root: Path) -> Optional[Path]:
    """The transcript whose file stem hashes to the row's session value."""
    if not root.is_dir():
        return None
    for path in root.rglob("*.jsonl"):
        if ledger_lib.hash_session(path.stem) == session:
            return path
    return None


def user_text(entry: Dict[str, Any]) -> Optional[str]:
    """The typed text of a user transcript entry, or None for tool results and meta entries."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return None
    content = entry.get("message", {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        content = "\n".join(b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str):
        return None
    name = COMMAND_NAME.search(content)
    if name:
        args = COMMAND_ARGS.search(content)
        content = f"{name.group(1)} {args.group(1) if args else ''}"
    content = content.strip()
    if not content or content.startswith("::"):
        return None
    return content


def triggering_message(transcript: Path, before: dt.datetime) -> Optional[str]:
    """The last user-typed message at or before `before`."""
    found: Optional[str] = None
    with open(transcript, encoding="utf-8") as handle:
        for raw in handle:
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            stamp = entry.get("timestamp")
            if not isinstance(stamp, str):
                continue
            try:
                when = parse_ts(stamp)
            except ValueError:
                continue
            if when > before:
                break
            text = user_text(entry)
            if text is not None:
                found = text
    return found


def cmd_promote(args: argparse.Namespace) -> int:
    for label, value in (("--skill", args.skill), ("run_id", args.run_id)):
        if not SAFE_NAME.match(value):
            print(f"ERROR: {label} must match {SAFE_NAME.pattern}", file=sys.stderr)
            return 2
    run = require_run(args.run_id)
    if run["skill"] != args.skill:
        raise Refused(f"run {args.run_id} belongs to {run['skill']!r}, not {args.skill!r}")
    invoke = run["invoke"]
    if invoke is None:
        raise Refused(f"run {args.run_id} has no invoke row")
    if args.transcript:
        transcript: Optional[Path] = Path(args.transcript)
    elif invoke.get("session"):
        transcript = find_transcript(invoke["session"], transcripts_root(args.transcripts))
    else:
        raise Refused(f"run {args.run_id} has no session; pass --transcript")
    if transcript is None or not transcript.is_file():
        raise Refused(f"no transcript found for run {args.run_id}; pass --transcript")
    message = triggering_message(transcript, parse_ts(invoke["ts"]))
    if message is None:
        raise Refused(f"no user message before run {args.run_id} in {transcript.name}")

    staging = ledger_lib.ledger_dir() / PROMOTED_DIR / args.skill
    target = staging / f"{args.run_id}.json"
    if target.exists():
        raise Refused(f"{target} already exists; review or delete it first")
    case = {
        "id": f"ledger-{args.run_id[:12]}",
        "suite": "regression",
        "query": redact(message),
        "expected_behavior": "",
        "needs_expected_behavior": True,
        "provenance": f"ledger:{args.run_id}",
    }
    staging.mkdir(parents=True, exist_ok=True)
    with open(target, "x", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps(case, indent=2, ensure_ascii=False) + "\n")
    outcome: Dict[str, Any] = {"label": run["label"] or "bad", "source": run["source"] or "user"}
    if run["failure_class"] and outcome["label"] == "bad":
        outcome["failure_class"] = run["failure_class"]
    ledger_lib.append(verdict_row(run, outcome, {"promoted_to": str(target)}))
    print(f"staged: {target}")
    print("Regex redaction misses free-text personal content. Read the case, write its "
          "expected_behavior, then copy it into the skill's evals.json by hand.")
    return 0


# --- inventory ---------------------------------------------------------------

def _interval(bad: int, labeled: int) -> str:
    low, high = ledger_lib.wilson(bad, labeled)
    return f"bad 95% Wilson [{low:.2f}, {high:.2f}]"


def cmd_inventory(args: argparse.Namespace) -> int:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)
    runs = [run for run in load_runs().values()
            if run["origin"] == "organic" and run["invoke"] is not None
            and parse_ts(run["ts"]) >= cutoff]
    print(f"organic runs in the last {args.days} days, by {args.by}; "
          f"counts only below {args.min_n} labeled")
    if args.by == "failure_class":
        failures = [run for run in runs if run["label"] == "bad"]
        classes = Counter(run["failure_class"] or "unclassified" for run in failures)
        total = len(failures)
        for name, count in sorted(classes.items(), key=lambda kv: (-kv[1], kv[0])):
            line = f"{name}: failures={count}"
            if total >= args.min_n:
                low, high = ledger_lib.wilson(count, total)
                line += f"  share of {total} failures 95% Wilson [{low:.2f}, {high:.2f}]"
            print(line)
        if not classes:
            print("no failures")
        return 0
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for run in runs:
        groups[run[args.by] or "unknown"].append(run)
    for name in sorted(groups):
        labels = Counter(run["label"] or "unlabeled" for run in groups[name])
        ok, bad = labels["ok"], labels["bad"]
        labeled = ok + bad
        line = (f"{name}: n={len(groups[name])} ok={ok} bad={bad} "
                f"dismissed={labels['dismissed']} "
                f"unlabeled={labels['unlabeled'] + labels['unknown']}")
        if labeled >= args.min_n:
            line += f"  {_interval(bad, labeled)} over {labeled} labeled"
        print(line)
    if not groups:
        print("no runs")
    return 0


# --- purge -------------------------------------------------------------------

def _month_end(year: int, month: int) -> dt.datetime:
    last = calendar.monthrange(year, month)[1]
    return dt.datetime(year, month, last, 23, 59, 59, 999999, tzinfo=dt.timezone.utc)


def _keep_run(run: Optional[Dict[str, Any]]) -> bool:
    return run is not None and run["label"] == "bad" and not run["promoted_to"]


def cmd_purge(args: argparse.Namespace) -> int:
    if args.older_than < 1:
        print("ERROR: --older-than must be at least 1", file=sys.stderr)
        return 2
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=args.older_than)
    removed = kept = 0
    with ledger_lib.locked() as base:
        runs = collect_runs(ledger_lib.iter_rows(base))
        for path in ledger_lib.month_files(base):
            match = ledger_lib.MONTH_FILE.match(path.name)
            year, month = int(match.group(1)), int(match.group(2))
            if (year, month) >= (now.year, now.month) or _month_end(year, month) >= cutoff:
                continue
            lines_out: List[str] = []
            file_removed = 0
            with open(path, encoding="utf-8") as handle:
                for raw in handle:
                    if not raw.strip():
                        continue
                    try:
                        row = json.loads(raw)
                        run_id = row["run_id"]
                    except (json.JSONDecodeError, KeyError, TypeError):
                        lines_out.append(raw if raw.endswith("\n") else raw + "\n")
                        continue
                    if _keep_run(runs.get(run_id)):
                        lines_out.append(raw if raw.endswith("\n") else raw + "\n")
                    else:
                        file_removed += 1
            if not file_removed:
                kept += len(lines_out)
                continue
            fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=base)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
                out.writelines(lines_out)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, path)
            removed += file_removed
            kept += len(lines_out)
            print(f"{path.name}: removed {file_removed}, kept {len(lines_out)}")
    print(f"purge: removed {removed} rows from closed months ending before "
          f"{cutoff.date().isoformat()}, kept {kept} in those months")
    return 0


# --- check-kill --------------------------------------------------------------

def _date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def longest_silence(stamps: List[dt.datetime], start: dt.datetime,
                    end: dt.datetime) -> Tuple[float, dt.datetime]:
    """Longest gap in days with no row between start and end, and where it began."""
    points = [start] + sorted(s for s in stamps if start <= s <= end) + [end]
    best, begin = 0.0, start
    for earlier, later in zip(points, points[1:]):
        gap = (later - earlier).total_seconds() / 86400
        if gap > best:
            best, begin = gap, earlier
    return best, begin


def evaluate_kill(installed: dt.date, today: dt.date) -> List[Tuple[int, bool, str]]:
    start = dt.datetime.combine(installed, dt.time.min, tzinfo=dt.timezone.utc)
    end = dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc)
    rows = [row for row in ledger_lib.iter_rows()
            if row["origin"] == "organic" and start <= parse_ts(row["ts"]) <= end]
    runs = collect_runs(rows)
    results: List[Tuple[int, bool, str]] = []

    promoted = sum(1 for run in runs.values() if run["promoted_to"])
    results.append((1, promoted >= MIN_PROMOTED,
                    f"{promoted} failures staged by promote (need {MIN_PROMOTED})"))

    invoked = [run for run in runs.values() if run["invoke"] is not None]
    unknown = sum(1 for run in invoked if run["label"] in (None, "unknown"))
    labeled_failures = sum(1 for run in runs.values() if run["label"] == "bad"
                           and run["source"] in ("user", "deterministic"))
    if invoked:
        share_unknown = unknown / len(invoked)
        killed = share_unknown > MAX_UNKNOWN_SHARE and labeled_failures < MIN_LABELED_FAILURES
        results.append((2, not killed,
                        f"{unknown} of {len(invoked)} invoke runs unlabeled, "
                        f"{labeled_failures} user or deterministic failures "
                        f"(kill above {MAX_UNKNOWN_SHARE:.0%} unlabeled with fewer than "
                        f"{MIN_LABELED_FAILURES} failures)"))
    else:
        results.append((2, False, "no invoke runs since install"))

    proxy = [row for row in rows if row.get("outcome", {}).get("source") == "proxy"]
    if not proxy:
        results.append((3, True, "not applicable: nothing writes proxy labels"))
    else:
        results.append((3, False, f"{len(proxy)} proxy-labeled rows found; enrich was cut, "
                                  "so audit where they came from"))

    stamps = [parse_ts(row["ts"]) for row in rows]
    gap, began = longest_silence(stamps, start, min(end, dt.datetime.now(dt.timezone.utc)))
    errors = 0
    log = ledger_lib.ledger_dir() / HOOK_ERRORS
    if log.is_file():
        with open(log, encoding="utf-8", errors="replace") as handle:
            errors = sum(1 for line in handle if line.strip())
    results.append((4, gap < MAX_SILENT_DAYS,
                    f"longest stretch with no rows {gap:.1f} days from "
                    f"{began.date().isoformat()} (kill at {MAX_SILENT_DAYS}); "
                    f"{errors} lines in {HOOK_ERRORS}"))
    return results


def cmd_check_kill(args: argparse.Namespace) -> int:
    today = args.today or dt.datetime.now(dt.timezone.utc).date()
    if today < args.installed:
        print("ERROR: --today is before --installed", file=sys.stderr)
        return 2
    review = args.installed + dt.timedelta(days=REVIEW_DAYS)
    if today < review:
        print(f"note: review date is {review.isoformat()}; this is an early check")
    results = evaluate_kill(args.installed, today)
    for number, passed, detail in results:
        print(f"criterion {number}: {'PASS' if passed else 'KILL'}  {detail}")
    verdict = all(passed for _, passed, _ in results)
    print("PASS" if verdict else "KILL")
    return 0 if verdict else 1


# --- install-hook ------------------------------------------------------------

def cmd_install_hook(args: argparse.Namespace) -> int:
    missing = [p.name for p in (HOOK_SOURCE, LIB_SOURCE) if not p.is_file()]
    if missing:
        print(f"ERROR: missing source files: {', '.join(missing)}", file=sys.stderr)
        return 2
    dest = Path(args.dest).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    for source in (HOOK_SOURCE, LIB_SOURCE):
        shutil.copy2(source, dest / source.name)
        print(f"copied {source.name} -> {dest / source.name}")
    hook = (dest / HOOK_SOURCE.name).as_posix()
    snippet = {"hooks": {
        "PostToolUse": [{"matcher": "Skill", "hooks": [{
            "type": "command", "timeout": 2,
            "command": f'python "{hook}" --event post-tool || true'}]}],
        "UserPromptSubmit": [{"hooks": [{
            "type": "command", "timeout": 2,
            "command": f'python "{hook}" --event prompt || true'}]}],
    }}
    print("Add each entry below as a new element of the existing hooks arrays in your "
          "settings file. Keep every existing hook:")
    print(json.dumps(snippet, indent=2))
    return 0


# --- command line ------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0].strip())
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("failures", help="list a skill's labeled failures")
    p.add_argument("skill")
    p.add_argument("--last", type=int, default=10)
    p.add_argument("--source", default="user,deterministic")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_failures)

    p = sub.add_parser("verdict", help="record a user verdict for a run")
    p.add_argument("run_id")
    p.add_argument("--label", required=True, choices=("ok", "bad", "unknown"))
    p.add_argument("--class", dest="failure_class", choices=ledger_lib.FAILURE_CLASSES)
    p.add_argument("--note")
    p.set_defaults(func=cmd_verdict)

    p = sub.add_parser("promote", help="stage a run as a regression eval case")
    p.add_argument("run_id")
    p.add_argument("--skill", required=True)
    p.add_argument("--transcript", help="transcript JSONL to read instead of searching")
    p.add_argument("--transcripts", help=f"transcript root (default ${TRANSCRIPTS_ENV} "
                                         "or ~/.claude/projects)")
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("dismiss", help="mark a run as dismissed")
    p.add_argument("run_id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_dismiss)

    p = sub.add_parser("inventory", help="counts per skill, harness or failure class")
    p.add_argument("--by", choices=("skill", "harness", "failure_class"), default="skill")
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--min-n", type=int, default=20)
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("purge", help="drop old rows from closed months")
    p.add_argument("--older-than", type=int, required=True, metavar="DAYS")
    p.set_defaults(func=cmd_purge)

    p = sub.add_parser("check-kill", help="evaluate kill criteria 1-4")
    p.add_argument("--installed", type=_date, required=True)
    p.add_argument("--today", type=_date)
    p.set_defaults(func=cmd_check_kill)

    p = sub.add_parser("install-hook", help="copy the hook to a pinned directory")
    p.add_argument("--dest", required=True)
    p.set_defaults(func=cmd_install_hook)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    except ledger_lib.LedgerError as exc:
        print(f"ERROR: invalid row: {exc}", file=sys.stderr)
        return 2
    except ledger_lib.LedgerLockTimeout as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
