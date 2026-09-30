#!/usr/bin/env python3
"""
check_verifications.py - Require a passing verification record for every upgraded or new claim.

A research PR that raises a grade or adds a claim needs a separate verifier to
re-retrieve that claim's sources in a fresh context. The verifier writes one
record per claim at

    research/verifications/<claim-id>/<claim_sha256[:12]>.yaml

The record is keyed on claim content, not on the head SHA, because pushing the
record changes the head. Record fields:

    claim_id: ctx.length-degradation
    claim_sha256: <64 hex, as compiled into claims.json>
    verdict: pass | fail
    proposer: <who proposed the change>
    verifier: <who re-retrieved the sources; must differ from proposer>
    verifier_session_sha256: <64 hex hash of the verifier session id>
    sources:
      - id: s1
        url: "https://..."
        url_resolves: true
        quote_found: true
        reception: {checked: true, retracted: false}
        independence_group_confirmed: true
    notes: ""

A record passes when its ``claim_sha256`` matches ``claims.json``, the verdict
is ``pass``, the verifier differs from the proposer, and every counted source
of the claim in ``sources.yaml`` appears with ``url_resolves``,
``quote_found``, ``reception.checked`` and ``independence_group_confirmed``
all true. Counted sources are the ones ``grade_cap.py`` counts.

The claims to check come from the ``claims_diff.py --json`` output. The
script reads ``needs_verification``. Without it, it falls back to
``upgraded_claims`` plus ``new_claims``, then to the ``claims`` entries whose
``status`` is ``new`` or whose ``upgrade`` is true. Entries are claim ids or
mappings with an ``id`` and optionally the head ``claim_sha256``; a diff hash
that disagrees with ``claims.json`` fails, because one of the two is stale. A
diff with none of these keys is a usage error, so a changed diff shape fails
closed instead of passing.

Removed claims have no record to check. The owner approval gate covers them.

Usage:
    python scripts/research/check_verifications.py --repo . --diff diff.json \\
        --claims skills/marcus/references/claims.json --dir research/verifications

Path flags (--claims, --sources, --dir) resolve against --repo, which defaults
to this checkout. --diff resolves against the working directory.

Exit codes:
    0  every upgraded or new claim has a passing record
    1  a record is missing or fails a check
    2  usage error, or an input is missing or malformed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import grade_cap as gc
import research_lib as rl

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CLAIMS = "skills/marcus/references/claims.json"
DEFAULT_SOURCES = "research/sources.yaml"
DEFAULT_DIR = "research/verifications"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA_PREFIX_LEN = 12

NEEDS_KEY = "needs_verification"
ID_KEYS = ("upgraded_claims", "new_claims")
CLAIMS_KEY = "claims"
SOURCE_FLAGS = ("url_resolves", "quote_found", "independence_group_confirmed")


class InputError(ValueError):
    """Raised when an input file is missing or has the wrong shape."""


# --------------------------------------------------------------------------- #
# Diff
# --------------------------------------------------------------------------- #

def _entry(entry: Any, where: str) -> Tuple[str, Optional[str]]:
    if isinstance(entry, str):
        return entry, None
    if isinstance(entry, Mapping) and isinstance(entry.get("id"), str):
        claim_sha = entry.get("claim_sha256")
        return entry["id"], claim_sha if isinstance(claim_sha, str) else None
    raise InputError(f"diff: {where} entry {entry!r} has no claim id")


def _list(diff: Mapping[str, Any], key: str) -> List[Any]:
    value = diff[key]
    if not isinstance(value, list):
        raise InputError(f"diff: {key} is not a list")
    return value


def _needs_record(entry: Any) -> bool:
    if not isinstance(entry, Mapping):
        return False
    return entry.get("status") == "new" or (entry.get("upgrade") is True and entry.get("status") != "removed")


def claims_to_verify(diff: Mapping[str, Any]) -> List[Tuple[str, Optional[str]]]:
    """(claim id, head claim_sha256 or None) for every upgraded or new claim, in first-seen order."""
    if not isinstance(diff, Mapping):
        raise InputError("diff: top level is not a JSON object")
    found: Dict[str, Optional[str]] = {}

    def add(entry: Any, where: str) -> None:
        claim_id, claim_sha = _entry(entry, where)
        if found.get(claim_id) is None:
            found[claim_id] = claim_sha

    if NEEDS_KEY in diff:
        for entry in _list(diff, NEEDS_KEY):
            add(entry, NEEDS_KEY)
    elif any(key in diff for key in ID_KEYS):
        for key in ID_KEYS:
            for entry in _list(diff, key) if key in diff else []:
                add(entry, key)
    elif CLAIMS_KEY in diff:
        for entry in _list(diff, CLAIMS_KEY):
            if _needs_record(entry):
                add(entry, CLAIMS_KEY)
    else:
        known = ", ".join((NEEDS_KEY,) + ID_KEYS + (CLAIMS_KEY,))
        raise InputError(f"diff: no claim list found; expected one of {known}")
    return list(found.items())


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #

def record_path(directory: Path, claim_id: str, claim_sha: str) -> Path:
    return directory / claim_id / f"{claim_sha[:SHA_PREFIX_LEN]}.yaml"


def _record_sources(record: Mapping[str, Any]) -> Tuple[Dict[str, Mapping[str, Any]], Dict[str, Mapping[str, Any]]]:
    by_id: Dict[str, Mapping[str, Any]] = {}
    by_url: Dict[str, Mapping[str, Any]] = {}
    for entry in record.get("sources") or []:
        if not isinstance(entry, Mapping):
            continue
        if isinstance(entry.get("id"), str):
            by_id.setdefault(entry["id"], entry)
        if isinstance(entry.get("url"), str):
            by_url.setdefault(entry["url"], entry)
    return by_id, by_url


def _same_person(first: str, second: str) -> bool:
    return first.strip().casefold() == second.strip().casefold()


def check_record(
    claim_id: str,
    record: Any,
    claim_sha: str,
    counted: Sequence[Mapping[str, Any]],
) -> List[str]:
    """Problems with one verification record; empty when it passes."""
    if not isinstance(record, Mapping):
        return ["record is not a mapping"]
    problems: List[str] = []
    recorded_id = record.get("claim_id")
    if recorded_id is not None and recorded_id != claim_id:
        problems.append(f"claim_id {recorded_id!r} does not match {claim_id!r}")
    if record.get("claim_sha256") != claim_sha:
        problems.append(f"claim_sha256 {record.get('claim_sha256')!r} does not match claims.json {claim_sha}")
    if record.get("verdict") != "pass":
        problems.append(f"verdict is {record.get('verdict')!r}, not 'pass'")
    verifier, proposer = record.get("verifier"), record.get("proposer")
    if not isinstance(verifier, str) or not verifier.strip():
        problems.append("verifier missing")
    if not isinstance(proposer, str) or not proposer.strip():
        problems.append("proposer missing")
    if isinstance(verifier, str) and isinstance(proposer, str) and verifier.strip() and _same_person(verifier, proposer):
        problems.append(f"verifier {verifier!r} is the proposer")
    session = record.get("verifier_session_sha256")
    if not isinstance(session, str) or not SHA256_RE.match(session):
        problems.append("verifier_session_sha256 is not 64 lowercase hex characters")
    if record.get("sources") is not None and not isinstance(record.get("sources"), list):
        problems.append("sources is not a list")
        return problems

    by_id, by_url = _record_sources(record)
    for source in counted:
        source_id = source.get("id")
        entry = by_id.get(source_id) if source_id else None
        if entry is None and source.get("url"):
            entry = by_url.get(source["url"])
        label = f"source {source_id}"
        if entry is None:
            problems.append(f"{label}: counted source missing from the record")
            continue
        if entry.get("url") is not None and source.get("url") and entry.get("url") != source.get("url"):
            problems.append(f"{label}: url {entry.get('url')!r} differs from sources.yaml {source.get('url')!r}")
        for flag in SOURCE_FLAGS:
            if entry.get(flag) is not True:
                problems.append(f"{label}: {flag} is not true")
        reception = entry.get("reception")
        if not isinstance(reception, Mapping) or reception.get("checked") is not True:
            problems.append(f"{label}: reception.checked is not true")
    return problems


def load_record(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    return rl.yaml.safe_load(text)


# --------------------------------------------------------------------------- #
# Check
# --------------------------------------------------------------------------- #

def check(
    diff: Mapping[str, Any],
    compiled: Mapping[str, Any],
    sources: Mapping[str, Any],
    directory: Path,
    repo: Optional[Path] = None,
) -> Tuple[List[str], List[str]]:
    """Return (claim ids checked, failure lines)."""
    wanted = claims_to_verify(diff)
    claim_ids = [claim_id for claim_id, _ in wanted]
    compiled_claims = {c.get("id"): c for c in compiled.get("claims") or [] if isinstance(c, Mapping)}
    sidecar = sources.get("claims") or {}
    failures: List[str] = []
    for claim_id, diff_sha in wanted:
        compiled_claim = compiled_claims.get(claim_id)
        if compiled_claim is None:
            failures.append(f"{claim_id}: not in claims.json")
            continue
        claim_sha = compiled_claim.get("claim_sha256")
        if not isinstance(claim_sha, str) or not SHA256_RE.match(claim_sha):
            failures.append(f"{claim_id}: claims.json has no valid claim_sha256")
            continue
        if diff_sha is not None and diff_sha != claim_sha:
            failures.append(f"{claim_id}: diff claim_sha256 {diff_sha} differs from claims.json {claim_sha}; run grade_cap.py --write")
            continue
        sidecar_claim = sidecar.get(claim_id)
        if not isinstance(sidecar_claim, Mapping):
            failures.append(f"{claim_id}: not in sources.yaml")
            continue
        path = record_path(directory, claim_id, claim_sha)
        shown = path.relative_to(repo).as_posix() if repo and path.is_relative_to(repo) else path.as_posix()
        if not path.is_file():
            failures.append(f"{claim_id}: no verification record at {shown}")
            continue
        try:
            record = load_record(path)
        except rl.yaml.YAMLError as exc:
            failures.append(f"{claim_id}: {shown} is not valid YAML ({exc})")
            continue
        counted = gc.counted_sources(sidecar_claim.get("sources") or [])
        failures.extend(f"{claim_id}: {problem}" for problem in check_record(claim_id, record, claim_sha, counted))
    return claim_ids, failures


def _read_json(path: Path, name: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(f"{name}: {path.as_posix()} not found") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{name}: {path.as_posix()} is not valid JSON ({exc})") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Require passing verification records for upgraded or new claims.")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="checkout root; --claims, --sources and --dir resolve against it")
    parser.add_argument("--diff", required=True, help="claims_diff.py --json output")
    parser.add_argument("--claims", default=DEFAULT_CLAIMS, help="compiled claims.json at the head")
    parser.add_argument("--sources", default=DEFAULT_SOURCES, help="sources.yaml at the head")
    parser.add_argument("--dir", default=DEFAULT_DIR, help="verification record directory")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()

    def under_repo(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo / path

    try:
        diff = _read_json(Path(args.diff), "diff")
        compiled = _read_json(under_repo(args.claims), "claims")
        if not isinstance(compiled, Mapping):
            raise InputError("claims: top level is not a JSON object")
        sources = rl.load_sources(under_repo(args.sources))
        claim_ids, failures = check(diff, compiled, sources, under_repo(args.dir), repo)
    except InputError as exc:
        print(f"ERROR: {exc}")
        return 2
    except FileNotFoundError as exc:
        print(f"ERROR: {exc.filename}: not found")
        return 2
    except (rl.SourcesError, rl.yaml.YAMLError) as exc:
        print(f"ERROR: {exc}")
        return 2

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        print(f"{len(failures)} problem(s) across {len(claim_ids)} upgraded or new claim(s)")
        return 1
    print(f"OK: {len(claim_ids)} upgraded or new claim(s) verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
