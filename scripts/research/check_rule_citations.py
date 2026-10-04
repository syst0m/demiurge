#!/usr/bin/env python3
"""
check_rule_citations.py - Check the citation token on every AGENT_ARCHITECTURE.md rule.

Every ``**Rule X-n.**`` in AGENT_ARCHITECTURE.md carries exactly one citation
token, written in backticks:

    [<GRADE> §<n>[,§<m>...] · <claim-id>[, <claim-id>...]]   RESEARCH.md claims
    [<GRADE> EVIDENCE §<n>[,§<m>...]]                          G-rules, references/EVIDENCE.md
    [DESIGN]                                                   specification or practice only

A claim token must name claim ids that exist in ``claims.json``, list exactly
the RESEARCH.md sections those claims sit in, and cite a grade no higher than
the lowest effective grade among them. G-rules cite EVIDENCE.md, which carries
no claim ids, so they use the EVIDENCE form or ``[DESIGN]``. Nothing derives
from ``[VENDOR]``, so no token may cite it.

``--report`` also lists, per claim-citing rule, the cited claims still flagged
``[UNVERIFIED]``. Those are the rules to reword when ``enforced`` becomes true.

Stdlib only: it reads the compiled claims.json, never sources.yaml.

Usage:
    python scripts/research/check_rule_citations.py
    python scripts/research/check_rule_citations.py --report
    python scripts/research/check_rule_citations.py --arch <path> --claims <path>

Path flags resolve against --repo, which defaults to this checkout.

Exit codes:
    0  every rule carries one valid token
    1  one or more violations
    2  usage error, or an input file is missing or unreadable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ARCH = "skills/marcus/AGENT_ARCHITECTURE.md"
DEFAULT_CLAIMS = "skills/marcus/references/claims.json"

GRADE_RANK: Dict[str, int] = {"SETTLED": 4, "CONTESTED": 3, "EMERGING": 2, "VENDOR": 1}
GRADE_ALT = "|".join(GRADE_RANK)

RULE_RE = re.compile(r"^\*\*Rule ([A-Z])-(\d+)\.\*\*")
BLOCK_END_RE = re.compile(r"^(#|---|```|~~~)")
TOKEN_RE = re.compile(r"`\[((?:%s|DESIGN)\b[^\]`]*)\]`" % GRADE_ALT)
SECTIONS = r"§\d+(?:\s*,\s*§\d+)*"
CLAIM_ID = r"[a-z]+\.[a-z0-9-]+"
DESIGN_RE = re.compile(r"^DESIGN$")
EVIDENCE_RE = re.compile(r"^(%s) EVIDENCE (%s)$" % (GRADE_ALT, SECTIONS))
CLAIMS_TOKEN_RE = re.compile(r"^(%s) (%s)\s*·\s*(%s(?:\s*,\s*%s)*)$" % (GRADE_ALT, SECTIONS, CLAIM_ID, CLAIM_ID))


@dataclass
class Token:
    kind: str
    grade: Optional[str] = None
    sections: List[int] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)


@dataclass
class Rule:
    rule_id: str
    line: int
    text: str


@dataclass
class Claim:
    section: int
    grade: str
    unverified: bool


def find_rules(text: str) -> List[Rule]:
    """Each rule's text runs from its header to the next rule, heading, rule line or fence."""
    rules: List[Rule] = []
    current: Optional[Rule] = None
    for number, line in enumerate(text.splitlines(), start=1):
        match = RULE_RE.match(line)
        if match:
            current = Rule(f"{match.group(1)}-{match.group(2)}", number, line)
            rules.append(current)
        elif current is not None and BLOCK_END_RE.match(line):
            current = None
        elif current is not None:
            current.text += "\n" + line
    return rules


def _sections(value: str) -> List[int]:
    return [int(part.strip().lstrip("§")) for part in value.split(",")]


def parse_token(body: str) -> Optional[Token]:
    """Parse the text between the brackets of a citation token, or None when malformed."""
    body = body.strip()
    if DESIGN_RE.match(body):
        return Token("design")
    match = EVIDENCE_RE.match(body)
    if match:
        return Token("evidence", match.group(1), _sections(match.group(2)))
    match = CLAIMS_TOKEN_RE.match(body)
    if match:
        claims = [part.strip() for part in match.group(3).split(",")]
        return Token("claims", match.group(1), _sections(match.group(2)), claims)
    return None


def load_claims(compiled: Mapping[str, Any]) -> Dict[str, Claim]:
    """Map each claim id to its section, its lowest effective grade and its UNVERIFIED flag."""
    claims: Dict[str, Claim] = {}
    for entry in compiled.get("claims", []):
        grades = entry.get("grades") or []
        effective = [grade["effective"] for grade in grades if grade.get("effective") in GRADE_RANK]
        if not effective:
            continue
        lowest = min(effective, key=GRADE_RANK.__getitem__)
        unverified = any(grade.get("unverified") for grade in grades)
        claims[entry["id"]] = Claim(int(entry["section"]), lowest, unverified)
    return claims


def ledger_minimum(token: Token, claims: Mapping[str, Claim]) -> Optional[str]:
    grades = [claims[claim_id].grade for claim_id in token.claims if claim_id in claims]
    return min(grades, key=GRADE_RANK.__getitem__) if grades else None


def _check_claims_token(rule_id: str, token: Token, claims: Mapping[str, Claim]) -> List[str]:
    errors: List[str] = []
    if len(set(token.claims)) != len(token.claims):
        errors.append(f"{rule_id}: a claim id is cited twice")
    if len(set(token.sections)) != len(token.sections):
        errors.append(f"{rule_id}: a section is listed twice")
    unknown = [claim_id for claim_id in token.claims if claim_id not in claims]
    for claim_id in unknown:
        errors.append(f"{rule_id}: unknown claim id {claim_id}")
    known = [claim_id for claim_id in token.claims if claim_id in claims]
    cited_sections = {claims[claim_id].section for claim_id in known}
    for claim_id in known:
        section = claims[claim_id].section
        if section not in token.sections:
            errors.append(f"{rule_id}: {claim_id} is in §{section}, which the token does not list")
    for section in token.sections:
        if not unknown and section not in cited_sections:
            errors.append(f"{rule_id}: §{section} is listed but no cited claim is in it")
    lowest = ledger_minimum(token, claims)
    if lowest is not None and GRADE_RANK[token.grade] > GRADE_RANK[lowest]:
        errors.append(f"{rule_id}: cites {token.grade}, above the ledger minimum {lowest}")
    return errors


def check_rule(rule: Rule, claims: Mapping[str, Claim]) -> Tuple[Optional[Token], List[str]]:
    """Return the rule's parsed token (None if it has no single valid one) and its violations."""
    bodies = TOKEN_RE.findall(rule.text)
    if not bodies:
        return None, [f"{rule.rule_id}: no citation token"]
    if len(bodies) > 1:
        return None, [f"{rule.rule_id}: {len(bodies)} citation tokens, expected exactly one"]
    token = parse_token(bodies[0])
    if token is None:
        return None, [f"{rule.rule_id}: malformed token [{bodies[0]}]"]
    errors: List[str] = []
    is_gate = rule.rule_id.startswith("G-")
    if token.grade == "VENDOR":
        errors.append(f"{rule.rule_id}: cites VENDOR; nothing derives from [VENDOR]")
    if is_gate and token.kind == "claims":
        errors.append(f"{rule.rule_id}: G-rules cite EVIDENCE.md as [<GRADE> EVIDENCE §n] or [DESIGN]")
    elif not is_gate and token.kind == "evidence":
        errors.append(f"{rule.rule_id}: EVIDENCE tokens are for G-rules; cite claim ids")
    if token.kind == "claims":
        errors += _check_claims_token(rule.rule_id, token, claims)
    return token, errors


def check(arch_text: str, compiled: Mapping[str, Any]) -> Tuple[List[Rule], Dict[str, Token], List[str]]:
    claims = load_claims(compiled)
    rules = find_rules(arch_text)
    tokens: Dict[str, Token] = {}
    errors: List[str] = []
    seen: Dict[str, int] = {}
    for rule in rules:
        if rule.rule_id in seen:
            errors.append(f"{rule.rule_id}: defined at lines {seen[rule.rule_id]} and {rule.line}")
            continue
        seen[rule.rule_id] = rule.line
        token, rule_errors = check_rule(rule, claims)
        errors += rule_errors
        if token is not None:
            tokens[rule.rule_id] = token
    return rules, tokens, errors


def report_lines(rules: Sequence[Rule], tokens: Mapping[str, Token], compiled: Mapping[str, Any]) -> List[str]:
    """One line per rule: its token kind and grade, the ledger minimum and any UNVERIFIED claims."""
    claims = load_claims(compiled)
    lines = [f"enforced={str(bool(compiled.get('enforced'))).lower()}"]
    for rule in rules:
        token = tokens.get(rule.rule_id)
        if token is None:
            lines.append(f"{rule.rule_id}\tinvalid")
            continue
        if token.kind == "design":
            lines.append(f"{rule.rule_id}\tDESIGN")
            continue
        if token.kind == "evidence":
            lines.append(f"{rule.rule_id}\t{token.grade} EVIDENCE")
            continue
        lowest = ledger_minimum(token, claims)
        pending = [claim_id for claim_id in token.claims if claim_id in claims and claims[claim_id].unverified]
        line = f"{rule.rule_id}\t{token.grade}\tledger={lowest}"
        if pending:
            line += "\tunverified=" + ",".join(pending) + "\treword if these drop when enforced"
        lines.append(line)
    return lines


def resolve(repo: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo / path


def use_utf8_output() -> None:
    """Print § and · as UTF-8 even where the console default is a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check the citation token on every AGENT_ARCHITECTURE.md rule.")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="checkout root; path flags resolve against it")
    parser.add_argument("--arch", default=DEFAULT_ARCH, help="AGENT_ARCHITECTURE.md")
    parser.add_argument("--claims", default=DEFAULT_CLAIMS, help="compiled claims.json")
    parser.add_argument("--report", action="store_true", help="also list each rule's grade against the ledger")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    use_utf8_output()
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    arch_path = resolve(repo, args.arch)
    claims_path = resolve(repo, args.claims)
    try:
        arch_text = arch_path.read_text(encoding="utf-8")
        compiled = json.loads(claims_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc.filename}: not found")
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: {claims_path.name}: {exc}")
        return 2
    rules, tokens, errors = check(arch_text, compiled)
    if not rules:
        print(f"ERROR: {arch_path.name}: no **Rule X-n.** headers found")
        return 1
    if args.report:
        for line in report_lines(rules, tokens, compiled):
            print(line)
    for error in errors:
        print(f"ERROR: {error}")
    status = "FAIL" if errors else "OK"
    print(f"{status}: {len(rules)} rules, {len(errors)} violations")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
