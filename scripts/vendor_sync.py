#!/usr/bin/env python3
"""Keep vendored upstream files byte-identical to a pinned upstream commit.

A vendored project lives in ``skills/<skill>/references/<name>/`` next to an
``UPSTREAM.yaml`` that pins its repository, commit and the sha256 of every file
taken from it. Upstream text is third-party instructions (trust tier T3), so
nothing here updates a vendored file on its own: ``--fetch`` only reports, and
``--apply`` needs the exact commit the operator reviewed.

Usage:
    python scripts/vendor_sync.py --check
    python scripts/vendor_sync.py --fetch [NAME]
    python scripts/vendor_sync.py --apply COMMIT NAME

Exit codes:
    0  vendored files match their pins (--check), upstream has not moved
       (--fetch), or the update was written (--apply)
    1  a vendored file was edited by hand (--check), upstream moved (--fetch),
       or a fetch or apply failed
    2  usage error or missing dependency
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required: python -m pip install -r requirements-dev.txt", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
PIN_GLOB = "skills/*/references/*/UPSTREAM.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover(root: Path = REPO_ROOT) -> List[Path]:
    return sorted(root.glob(PIN_GLOB))


def load_pin(pin_path: Path) -> dict:
    pin = yaml.safe_load(pin_path.read_text(encoding="utf-8"))
    for key in ("repo", "commit", "files"):
        if not pin.get(key):
            raise ValueError(f"{pin_path}: missing '{key}'")
    return pin


def check(root: Path = REPO_ROOT) -> int:
    pins = discover(root)
    if not pins:
        print("OK       no vendored projects")
        return 0
    failed = False
    for pin_path in pins:
        pin = load_pin(pin_path)
        for upstream_name, entry in pin["files"].items():
            local = pin_path.parent / entry["as"]
            rel = local.relative_to(root).as_posix()
            if not local.is_file():
                print(f"MISSING  {rel} (from {upstream_name})")
                failed = True
            elif sha256(local) != entry["sha256"]:
                print(f"EDITED   {rel} differs from {pin['repo']}@{pin['commit'][:7]}")
                failed = True
            else:
                print(f"OK       {rel}")
    if failed:
        print("Vendored files are never edited by hand. Restore them, or run --fetch and --apply.")
    return 1 if failed else 0


def clone(repo: str, dest: Path, commit: Optional[str] = None) -> str:
    # autocrlf off: the pinned sha256 is of the exact upstream bytes on every platform.
    args = ["git", "-c", "core.autocrlf=false", "clone", "--quiet"] + ([] if commit else ["--depth", "1"]) + [repo, str(dest)]
    subprocess.run(args, check=True)
    if commit:
        subprocess.run(["git", "-C", str(dest), "checkout", "--quiet", commit], check=True)
    return subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def select(root: Path, name: Optional[str]) -> List[Path]:
    pins = [p for p in discover(root) if name is None or p.parent.name == name]
    if name and not pins:
        raise ValueError(f"no vendored project named '{name}'")
    return pins


def fetch(root: Path = REPO_ROOT, name: Optional[str] = None) -> int:
    moved = False
    for pin_path in select(root, name):
        pin = load_pin(pin_path)
        with tempfile.TemporaryDirectory() as tmp:
            head = clone(pin["repo"], Path(tmp) / "src")
            if head == pin["commit"]:
                print(f"CURRENT  {pin_path.parent.name} @ {head[:7]}")
                continue
            moved = True
            print(f"MOVED    {pin_path.parent.name}: {pin['commit'][:7]} -> {head[:7]}")
            for upstream_name, entry in pin["files"].items():
                new = Path(tmp) / "src" / upstream_name
                old = pin_path.parent / entry["as"]
                old_lines = old.read_text(encoding="utf-8").splitlines(keepends=True) if old.is_file() else []
                new_lines = new.read_text(encoding="utf-8").splitlines(keepends=True) if new.is_file() else []
                sys.stdout.writelines(difflib.unified_diff(old_lines, new_lines, f"pinned/{upstream_name}", f"{head[:7]}/{upstream_name}"))
            print(f"Review the diff, then: python scripts/vendor_sync.py --apply {head} {pin_path.parent.name}")
    return 1 if moved else 0


def apply(commit: str, name: str, root: Path = REPO_ROOT) -> int:
    pin_path = select(root, name)[0]
    pin = load_pin(pin_path)
    with tempfile.TemporaryDirectory() as tmp:
        head = clone(pin["repo"], Path(tmp) / "src", commit)
        for upstream_name, entry in pin["files"].items():
            data = (Path(tmp) / "src" / upstream_name).read_bytes()
            (pin_path.parent / entry["as"]).write_bytes(data)
            entry["sha256"] = hashlib.sha256(data).hexdigest()
    pin["commit"] = head
    pin["fetched"] = dt.date.today().isoformat()
    pin_path.write_text(yaml.safe_dump(pin, sort_keys=False), encoding="utf-8")
    print(f"APPLIED  {name} @ {head[:7]}. Run the skill's evals before committing.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--fetch", nargs="?", const="", metavar="NAME")
    mode.add_argument("--apply", nargs=2, metavar=("COMMIT", "NAME"))
    args = parser.parse_args(argv)
    try:
        if args.check:
            return check()
        if args.fetch is not None:
            return fetch(name=args.fetch or None)
        return apply(*args.apply)
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
