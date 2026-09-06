#!/usr/bin/env python3
"""Syncs the executive gist of skills/marcus/human-only/demiurge-brief.html into README.md.

Usage:
    python scripts/sync_brief_summary.py [--check]

Extracts headline metrics and findings from the HTML brief and embeds them
between '<!-- BEGIN DEMIURGE BRIEF GIST -->' and '<!-- END DEMIURGE BRIEF GIST -->'
in README.md.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


START_MARKER = "<!-- BEGIN DEMIURGE BRIEF GIST -->"
END_MARKER = "<!-- END DEMIURGE BRIEF GIST -->"


def generate_gist_markdown(html_content: str) -> str:
    """Extract headline metrics and synthesize the graphical dashboard preview and gist."""
    # Extract figures if present
    fig_matches = re.findall(
        r'<div class="n">([^<]+)</div>\s*<div class="l">([^<]+(?:<strong>[^<]+</strong>[^<]*)*)</div>',
        html_content,
    )

    clean_figs = []
    for num, label in fig_matches[:4]:
        clean_num = num.replace("&times;", "×").replace("&ndash;", "–").strip()
        clean_label = re.sub(r"<[^>]+>", "", label).replace("&mdash;", "—").strip()
        clean_figs.append((clean_num, clean_label))

    lines = [
        START_MARKER,
        "```mermaid",
        "flowchart TD",
        "    subgraph Dashboard[\"DEMIURGE VISUAL DASHBOARD PREVIEW\"]",
        "        direction TB",
        "        subgraph S1[\"§01 Four Empirical Constants\"]",
        "            direction LR",
        "            N1[\"<b>7,560 Runs</b><br/>0% Skill Lift\"]",
        "            N2[\"<b>2.12× Risk</b><br/>Script Flaws\"]",
        "            N3[\"<b>~15,000 Scale</b><br/>Break-Even\"]",
        "            N4[\"<b>7–33% Unsafe</b><br/>Action Rate\"]",
        "        end",
        "        subgraph S2[\"§02 Graded Evidence Base\"]",
        "            direction LR",
        "            E1[\"<b>[SETTLED]</b><br/>Harness > Model<br/>Gates > Prompts<br/>Safety ⟂ Success\"]",
        "            E2[\"<b>[CONTESTED]</b><br/>Rejection > Generation<br/>Curation > Automation\"]",
        "            E3[\"<b>[EMERGING]</b><br/>Self-Harness Loops<br/>Regression Gating\"]",
        "        end",
        "        subgraph S3[\"§03 Mechanical Gate Pipeline\"]",
        "            direction LR",
        "            G0[\"G0: Intake\"] --> G1[\"G1: Base\"] --> G2[\"G2: Contrast\"] --> G3[\"G3: Draft\"] --> G4[\"G4: Validate\"] --> G5[\"G5: Prove\"] --> G6[\"G6: Register\"]",
        "        end",
        "        subgraph S4[\"§04–05 Invariant Verification & Limits\"]",
        "            direction LR",
        "            V1[\"<b>Verification</b><br/>14/14 Gate Tests<br/>0 Blocking Issues\"]",
        "            V2[\"<b>Honest Limits</b><br/>No Unmeasured Lift<br/>Automated Design Ceiling\"]",
        "        end",
        "        S1 --> S2 --> S3 --> S4",
        "    end",
        "```",
        "",
    ]

    if clean_figs:
        lines.append("#### Four Empirical Constants That Shaped the Design")
        lines.append("")
        for num, label in clean_figs:
            lines.append(f"- **{num}**: {label}")
        lines.append("")

    lines.extend([
        "#### Core Architectural Takeaways",
        "",
        "- **Rejection Outweighs Generation:** Methods that achieve real performance lift (e.g., SkillCAT +49.7%) succeed by ruthlessly discarding candidates through contrastive test replay, not through speculative prompt generation.",
        "- **The Harness Dominates the Model:** Model×harness pairing varies completion and efficiency dramatically across execution trajectories—enough to invert raw model leaderboard rankings.",
        "- **Capability and Safety Are Orthogonal:** Unsafe-action rates (7–33%) do not track task success rates (39–64%). Scaling capability without mechanical write-gates amplifies vulnerability.",
        "- **Four-Tier Trust Model ($T_0$ to $T_3$):** Strict mechanical progression from untrusted intake to isolated baseline contrast before any skill or harness is accepted.",
        END_MARKER,
    ])

    return "\n".join(lines)



def update_readme(repo_root: Path, check_only: bool = False) -> int:
    brief_path = repo_root / "skills" / "marcus" / "human-only" / "demiurge-brief.html"
    readme_path = repo_root / "README.md"

    if not brief_path.is_file():
        print(f"Error: {brief_path} not found.", file=sys.stderr)
        return 1

    if not readme_path.is_file():
        print(f"Error: {readme_path} not found.", file=sys.stderr)
        return 1

    html_content = brief_path.read_text(encoding="utf-8")
    readme_content = readme_path.read_text(encoding="utf-8")

    if START_MARKER not in readme_content or END_MARKER not in readme_content:
        print(
            f"Error: Markers {START_MARKER} and {END_MARKER} missing in README.md",
            file=sys.stderr,
        )
        return 1

    new_gist = generate_gist_markdown(html_content)

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    updated_readme = pattern.sub(new_gist, readme_content)

    if check_only:
        if updated_readme != readme_content:
            print("README.md executive brief gist is out of date with demiurge-brief.html.")
            return 1
        print("README.md executive brief gist is up to date.")
        return 0

    if updated_readme != readme_content:
        readme_path.write_text(updated_readme, encoding="utf-8")
        print("Updated README.md with the latest brief gist from demiurge-brief.html.")
    else:
        print("README.md is already up to date.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync brief summary into README.md")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if README.md gist is up to date without modifying",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    return update_readme(repo_root, check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
