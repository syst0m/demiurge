#!/usr/bin/env python3
"""resolve_config.py - Resolves skill configuration for Marcus with Demiurge project overrides.

Pattern: Configurable Agent Skills (Without Forking).
Reads `config.default.yaml` from the skill directory, searches for `.agents/skills.config.yaml`,
`.agents/config.yaml`, `.agent/skills.config.yaml`, or `skills.config.yaml` in current or ancestor
directories, and deep-merges user/project overrides over skill defaults.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return override


def find_project_config(start_dir: Path) -> Path | None:
    current = start_dir.resolve()
    for directory in [current, *current.parents]:
        candidates = [
            directory / ".agents" / "skills.config.yaml",
            directory / ".agents" / "config.yaml",
            directory / ".agent" / "skills.config.yaml",
            directory / "skills.config.yaml",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    return None


def parse_yaml_or_json(content: str) -> Dict[str, Any]:
    if HAVE_YAML:
        return yaml.safe_load(content) or {}
    try:
        return json.loads(content)
    except Exception:
        data: Dict[str, Any] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            v = v.strip()
            if v.lower() == "true":
                val = True
            elif v.lower() == "false":
                val = False
            else:
                try:
                    val = float(v) if "." in v else int(v)
                except ValueError:
                    val = v.strip("\"'")
            data[k.strip()] = val
        return data


def resolve(skill_name: str, skill_dir: Path, project_root: Path) -> Dict[str, Any]:
    default_config_path = skill_dir / "config.default.yaml"
    defaults: Dict[str, Any] = {}
    if default_config_path.is_file():
        defaults = parse_yaml_or_json(default_config_path.read_text(encoding="utf-8"))

    user_config_path = find_project_config(project_root)
    user_overrides: Dict[str, Any] = {}
    if user_config_path and user_config_path.is_file():
        full_user_config = parse_yaml_or_json(user_config_path.read_text(encoding="utf-8"))
        if isinstance(full_user_config, dict):
            user_overrides = full_user_config.get(skill_name, {}) or {}

    return deep_merge(defaults, user_overrides)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve Marcus skill configuration.")
    parser.add_argument("skill_name", nargs="?", default="marcus", help="Name of the skill")
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parent.parent, help="Directory containing config.default.yaml")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Root directory of the user project")
    parser.add_argument("--json", action="store_true", help="Output resolved configuration as JSON")
    parser.add_argument("--key", type=str, help="Output only a specific configuration key value")

    args = parser.parse_args()
    resolved = resolve(args.skill_name, args.skill_dir, args.project_root)

    if args.key:
        val = resolved.get(args.key)
        if val is None:
            sys.exit(1)
        print(val)
        return

    if args.json or not HAVE_YAML:
        print(json.dumps(resolved, indent=2))
    else:
        print(yaml.dump(resolved, default_flow_style=False))


if __name__ == "__main__":
    main()
