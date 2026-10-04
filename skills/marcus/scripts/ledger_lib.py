#!/usr/bin/env python3
"""Run ledger: schema, locked append, reads, skill hashing and small-sample statistics.

Imported by eval_runner.py, modify_skill.py and the repo's scripts/ledger tools. It has no
command line of its own.

The ledger is metadata-only JSONL kept outside every repository, one file per UTC month:

    $DEMIURGE_LEDGER_DIR/runs-YYYY-MM.jsonl   (default ~/.demiurge/ledger/)

Rows never hold prompt text, response text or a raw session id. `session` is a hash made by
hash_session(). Every append holds `ledger.lock` in the ledger directory (msvcrt.locking on
Windows, fcntl.flock elsewhere) with a 1-second timeout, and raises LedgerLockTimeout rather
than wait longer.

Ledger counts never gate, score or rank a skill or a harness. See docs/RUN_LEDGER.md.
Stdlib only. No network access.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

SCHEMA_VERSION = "ledger.v0"
LEDGER_ENV = "DEMIURGE_LEDGER_DIR"
LOCK_NAME = "ledger.lock"
LOCK_TIMEOUT = 1.0
NOTE_MAX = 120
MONTH_FILE = re.compile(r"^runs-(\d{4})-(\d{2})\.jsonl$")

KINDS = ("invoke", "verdict")
ORIGINS = ("organic", "replay")
TRIGGERS = ("slash", "model", "eval")
ARMS = ("baseline", "treated")
LABELS = ("ok", "bad", "unknown", "dismissed")
SOURCES = ("user", "deterministic", "judge", "proxy")
FAILURE_CLASSES = (
    "misroute",       # the wrong skill ran, or the right one did not
    "wrong_output",   # the skill ran and produced an incorrect result
    "incomplete",     # the skill stopped before the task was done
    "ignored_rule",   # the skill broke one of its own stated rules
    "unsafe",         # the skill took or proposed a harmful or unapproved action
    "tool_error",     # a tool call the skill made failed
    "infra",          # the harness or runner failed; not a skill failure
    "other",
)

_HEX = re.compile(r"^[0-9a-f]{16,64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_ts(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _is_note(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= NOTE_MAX


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


# Each field maps to (required, check, description). Nested objects use a dict in place of
# the check and are validated the same way. A key missing from SCHEMA is rejected.
SCHEMA: Dict[str, Any] = {
    "schema": (True, lambda v: v == SCHEMA_VERSION, f"must be {SCHEMA_VERSION!r}"),
    "run_id": (True, _is_str, "non-empty string"),
    "ts": (True, _is_ts, "UTC ISO-8601 timestamp ending in Z"),
    "kind": (True, lambda v: v in KINDS, f"one of {KINDS}"),
    "origin": (True, lambda v: v in ORIGINS, f"one of {ORIGINS}"),
    "skill": (True, _is_str, "non-empty string"),
    "trigger": (False, lambda v: v in TRIGGERS, f"one of {TRIGGERS}"),
    "session": (False, lambda v: isinstance(v, str) and bool(_HEX.match(v)),
                "hex digest from hash_session(), never a raw session id"),
    "skill_sha": (False, lambda v: isinstance(v, str) and bool(_SHA256.match(v)),
                  "sha256 hex digest from skill_sha()"),
    "harness": (False, _is_str, "non-empty string"),
    "model_id": (False, _is_str, "non-empty string"),
    "version": (False, _is_str, "non-empty string"),
    "arm": (False, lambda v: v in ARMS, f"one of {ARMS}"),
    "case_id": (False, _is_str, "non-empty string"),
    "attempt": (False, _is_count, "non-negative integer"),
    "duration_ms": (False, _is_count, "non-negative integer"),
    "outcome": (False, {
        "label": (True, lambda v: v in LABELS, f"one of {LABELS}"),
        "source": (True, lambda v: v in SOURCES, f"one of {SOURCES}"),
        "failure_class": (False, lambda v: v in FAILURE_CLASSES, f"one of {FAILURE_CLASSES}"),
        "note": (False, _is_note, f"string of at most {NOTE_MAX} characters"),
    }, "object"),
    "refs": (False, {
        "promoted_to": (False, _is_str, "non-empty string"),
        "evals_sha256": (False, lambda v: isinstance(v, str) and bool(_SHA256.match(v)),
                         "sha256 hex digest"),
    }, "object"),
}


class LedgerError(ValueError):
    """A row failed validation."""


class LedgerLockTimeout(TimeoutError):
    """The ledger lock was not acquired within the timeout."""


def _validate(obj: Any, schema: Dict[str, Any], prefix: str) -> List[str]:
    if not isinstance(obj, dict):
        return [f"{prefix or 'row'}: must be an object"]
    errors: List[str] = []
    for key in sorted(set(obj) - set(schema)):
        errors.append(f"{prefix}{key}: unknown key")
    for key, (required, check, why) in schema.items():
        name = f"{prefix}{key}"
        if key not in obj:
            if required:
                errors.append(f"{name}: required")
            continue
        value = obj[key]
        if isinstance(check, dict):
            errors.extend(_validate(value, check, f"{name}."))
        elif not check(value):
            errors.append(f"{name}: {why}")
    return errors


def validate(row: Any) -> List[str]:
    """Return every schema error in a row; an empty list means it is valid."""
    errors = _validate(row, SCHEMA, "")
    if errors or not isinstance(row, dict):
        return errors
    if row["kind"] == "verdict" and "outcome" not in row:
        errors.append("outcome: required on a verdict row")
    return errors


def ledger_dir() -> Path:
    """The ledger directory: $DEMIURGE_LEDGER_DIR, else ~/.demiurge/ledger. Not created."""
    override = os.environ.get(LEDGER_ENV, "").strip()
    return Path(override) if override else Path.home() / ".demiurge" / "ledger"


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_run_id() -> str:
    return uuid.uuid4().hex


def hash_session(session_id: str) -> str:
    """Hash a session id so the raw id never reaches the ledger."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]


def month_file(ts: str, directory: Optional[Path] = None) -> Path:
    base = directory if directory is not None else ledger_dir()
    return base / f"runs-{ts[:4]}-{ts[5:7]}.jsonl"


def _try_lock(handle: Any) -> bool:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle: Any) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def locked(directory: Optional[Path] = None, timeout: float = LOCK_TIMEOUT) -> Iterator[Path]:
    """Hold ledger.lock for the block and yield the ledger directory.

    Raises LedgerLockTimeout when the lock is still held elsewhere after `timeout` seconds.
    Purge and every append run inside this.
    """
    base = directory if directory is not None else ledger_dir()
    base.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    with open(base / LOCK_NAME, "a+b") as handle:
        while not _try_lock(handle):
            if time.monotonic() >= deadline:
                raise LedgerLockTimeout(f"{LOCK_NAME} held for more than {timeout:g}s")
            time.sleep(0.002)
        try:
            yield base
        finally:
            _unlock(handle)


def append(row: Dict[str, Any], directory: Optional[Path] = None,
           timeout: float = LOCK_TIMEOUT) -> Dict[str, Any]:
    """Validate a row and append it to its month file under the lock.

    `schema` and `ts` are filled in when absent. Returns the row as written.
    Raises LedgerError on an invalid row and LedgerLockTimeout when the lock times out.
    """
    if not isinstance(row, dict):
        raise LedgerError("row: must be an object")
    full = {"schema": SCHEMA_VERSION, "ts": now_ts(), **row}
    errors = validate(full)
    if errors:
        raise LedgerError("; ".join(errors))
    line = json.dumps(full, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with locked(directory, timeout) as base:
        with open(month_file(full["ts"], base), "a", encoding="utf-8", newline="\n") as out:
            out.write(line)
            out.flush()
            os.fsync(out.fileno())
    return full


def month_files(directory: Optional[Path] = None) -> List[Path]:
    """Month files in the ledger directory, oldest first."""
    base = directory if directory is not None else ledger_dir()
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_file() and MONTH_FILE.match(p.name))


def iter_rows(directory: Optional[Path] = None, strict: bool = False) -> Iterator[Dict[str, Any]]:
    """Yield rows oldest file first, in append order.

    A line that is not a JSON object, or fails validation, is skipped. With strict=True it
    raises LedgerError naming the file and line instead.
    """
    for path in month_files(directory):
        with open(path, encoding="utf-8") as handle:
            for number, raw in enumerate(handle, 1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    if strict:
                        raise LedgerError(f"{path.name}:{number}: {exc.msg}") from exc
                    continue
                errors = validate(row)
                if errors:
                    if strict:
                        raise LedgerError(f"{path.name}:{number}: {'; '.join(errors)}")
                    continue
                yield row


def find(run_id: str, directory: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every row for one run_id: its invoke row and any verdict rows, in append order."""
    return [row for row in iter_rows(directory) if row["run_id"] == run_id]


SKIP_PARTS = {"__pycache__", "node_modules", ".git"}
# Written into evals/ by eval_runner.py after every measurement; they describe a run, not the skill.
EVAL_OUTPUT_RE = re.compile(r"^(?:results-.+|transcripts-.+|last_run)\.json$")
HOOK_MAX_FILES = 500
HOOK_MAX_BYTES = 8 * 1024 * 1024


class SkillShaBudgetExceeded(Exception):
    """The bundle holds more files or bytes than the caller allowed."""


def _bundle_files(root: Path) -> Iterator[Tuple[Path, str]]:
    """(path, bundle-relative posix path) for every hashed file. Skipped trees are never entered."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS and not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(root)
        for name in filenames:
            if name.startswith("."):
                continue
            if rel_dir.parts == ("evals",) and EVAL_OUTPUT_RE.match(name):
                continue
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            yield path, (rel_dir / name).as_posix()


def skill_sha(skill_dir: Path, max_files: Optional[int] = None, max_bytes: Optional[int] = None) -> str:
    """sha256 over a skill bundle's files, independent of directory listing order.

    Each file contributes its path relative to the bundle and the sha256 of its bytes, in
    sorted path order. Caches, dot-directories, dotfiles and the eval outputs in ``evals/``
    (``results-*.json``, ``transcripts-*.json``, ``last_run.json``) are left out, so a
    measurement does not change the hash of the skill it measured. With ``max_files`` or
    ``max_bytes`` set, raises SkillShaBudgetExceeded as soon as the bundle passes either limit.
    """
    root = Path(skill_dir)
    entries: List[Tuple[str, str]] = []
    total = 0
    for path, rel in _bundle_files(root):
        if max_files is not None and len(entries) >= max_files:
            raise SkillShaBudgetExceeded(f"more than {max_files} files")
        data = path.read_bytes()
        total += len(data)
        if max_bytes is not None and total > max_bytes:
            raise SkillShaBudgetExceeded(f"more than {max_bytes} bytes")
        entries.append((rel, hashlib.sha256(data).hexdigest()))
    digest = hashlib.sha256()
    for rel, file_hash in sorted(entries):
        digest.update(f"{rel}\0{file_hash}\n".encode("utf-8"))
    return digest.hexdigest()


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion; (0.0, 1.0) when n is 0."""
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("need 0 <= successes <= n")
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value over discordant pairs b and c; 1.0 when both are 0."""
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)
