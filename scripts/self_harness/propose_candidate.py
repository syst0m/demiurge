#!/usr/bin/env python3
"""Build a proposer prompt from a diagnosis brief, or parse its reply into a proposal.

Marcus stays fully offline and deterministic (docs/INSTALLATION.md, §5): this script
never calls a model API. In build mode it assembles a prompt an operator runs inside a
supervised Marcus/Claude Code session. In parse mode it validates that session's
structured JSON reply and writes a proposal_bundle.json for materialize_candidate.py.

A candidate changes exactly one declared harness surface (the same constraint the
Self-Harness template enforces on its own virtual hooks, proposer/src/self_harness_
proposer/hooks.py: "mechanism-diverse candidates must change exactly one virtual
hook").
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

FORMAT = "demiurge.self_harness.proposal_bundle.v0"
REQUIRED_NARRATIVE_FIELDS = ("summary", "why_distinct", "net_gain_hypothesis", "regression_guard")


def parse_surface_args(raw_surfaces: list[str]) -> dict[str, Path]:
    surfaces: dict[str, Path] = {}
    for raw in raw_surfaces:
        if "=" not in raw:
            raise ValueError(f"--surface must be name=path, got: {raw!r}")
        name, _, path_str = raw.partition("=")
        name = name.strip()
        if not name:
            raise ValueError(f"--surface has an empty name: {raw!r}")
        surfaces[name] = Path(path_str.strip())
    return surfaces


def build_prompt(diagnosis: dict[str, Any], surfaces: dict[str, Path]) -> str:
    lines = [
        "# Self-Harness Proposer Prompt",
        "",
        "Read the diagnosis below, then propose exactly one bounded edit to exactly one of "
        "the declared surfaces. Do not touch any other file.",
        "",
        "## Diagnosis Summary",
        "",
        f"- Failing tasks: `{diagnosis.get('failing_demiurge_tasks', 0)}` "
        f"of `{diagnosis.get('total_demiurge_tasks', 0)}` inspected",
    ]
    clusters = diagnosis.get("clusters", [])
    if not clusters:
        lines.append("- No failure clusters. A no-op reply is the correct reply.")
    for cluster in clusters:
        lines.append(
            f"- `{cluster['cluster_id']}` (`{cluster['count']}` tasks): {cluster['signature']}"
        )
    lines.extend(["", "## Declared Surfaces", ""])
    for name, path in sorted(surfaces.items()):
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines.append(f"### `{name}` — `{path.as_posix()}`")
        lines.append("")
        lines.append("```")
        lines.append(content)
        lines.append("```")
        lines.append("")
    lines.extend(
        [
            "## Required Reply Shape",
            "",
            "Save a JSON object with these fields to a file, then re-run this script with "
            "`--response <that file> --output proposal_bundle.json`:",
            "",
            "```json",
            json.dumps(
                {
                    "proposal_id": "short-slug",
                    "title": "One-line description",
                    "surface": "<one name from Declared Surfaces above>",
                    "value": "<the full new content of that surface file>",
                    "summary": "What changed and why, tied to a named cluster above.",
                    "why_distinct": "Why this edit differs from other candidates considered.",
                    "net_gain_hypothesis": "What measurable improvement this predicts.",
                    "regression_guard": "What this edit must not break.",
                },
                indent=2,
            ),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_and_build_bundle(response: dict[str, Any], surfaces: dict[str, Path]) -> dict[str, Any]:
    proposal_id = str(response.get("proposal_id") or "").strip()
    if not proposal_id:
        raise ValueError("response is missing a non-empty 'proposal_id'")

    surface_name = str(response.get("surface") or "").strip()
    if surface_name not in surfaces:
        raise ValueError(
            f"response targets surface {surface_name!r}, which is not one of the declared "
            f"surfaces: {sorted(surfaces)}"
        )

    for field in REQUIRED_NARRATIVE_FIELDS:
        if not str(response.get(field) or "").strip():
            raise ValueError(f"response is missing a non-empty {field!r}")

    new_value = response.get("value")
    if not isinstance(new_value, str) or not new_value.strip():
        raise ValueError("response is missing a non-empty 'value'")

    surface_path = surfaces[surface_name]
    current_value = surface_path.read_text(encoding="utf-8") if surface_path.is_file() else ""
    if new_value == current_value:
        raise ValueError(
            f"response value for surface {surface_name!r} is identical to the current file "
            "content; this is a no-op proposal, not a candidate"
        )

    return {
        "format": FORMAT,
        "proposal_id": proposal_id,
        "title": str(response.get("title") or proposal_id),
        "surface": surface_name,
        "surface_path": surface_path.as_posix(),
        "value": new_value,
        "summary": response["summary"],
        "why_distinct": response["why_distinct"],
        "net_gain_hypothesis": response["net_gain_hypothesis"],
        "regression_guard": response["regression_guard"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or parse a self-harness proposer turn.")
    parser.add_argument("--surface", action="append", required=True, help="name=path, repeatable.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnosis", type=Path, help="diagnosis.json, required in build mode.")
    parser.add_argument("--response", type=Path, help="Proposer reply JSON. Switches to parse mode.")
    args = parser.parse_args(argv)

    surfaces = parse_surface_args(args.surface)

    if args.response is None:
        if args.diagnosis is None:
            raise ValueError("--diagnosis is required in build mode")
        diagnosis = json.loads(args.diagnosis.read_text(encoding="utf-8"))
        prompt = build_prompt(diagnosis, surfaces)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(prompt, encoding="utf-8")
        print(f"Proposer prompt written to: {args.output}")
        print(
            "Next step: run this prompt inside a supervised Marcus/Claude Code session, save "
            "its JSON reply to a file, then re-run with --response <file> --output "
            "proposal_bundle.json"
        )
        return 0

    response = json.loads(args.response.read_text(encoding="utf-8"))
    bundle = validate_and_build_bundle(response, surfaces)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    print(f"Proposal bundle written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
