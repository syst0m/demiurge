#!/usr/bin/env python3
"""
research_lib.py - Shared parsing and validation for the claims ledger.

``research/RESEARCH.md`` holds the prose. Each graded claim line carries an
inline anchor (``<!-- claim:<id> -->``) and each rule a rule anchor
(``<!-- rule:<id> -->``). ``research/sources.yaml`` is the sidecar that records
grades and sources per anchor. This module loads and dumps the sidecar, parses
the anchors and grade markers out of the prose, hashes claims and checks that
prose and sidecar agree. The scripts under ``scripts/research/`` build on it.

The sidecar carries no YAML comments, because ``yaml.safe_dump`` would drop
them on the next write; ``check_no_comments`` rejects them.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required: python -m pip install -r requirements-dev.txt", file=sys.stderr)
    sys.exit(2)

SOURCES_SCHEMA = "demiurge.sources.v1"

GRADE_RANK: Dict[str, int] = {"SETTLED": 4, "CONTESTED": 3, "EMERGING": 2, "VENDOR": 1}
GRADES = tuple(GRADE_RANK)

CLAIM_ID_RE = re.compile(r"^[a-z]+\.[a-z0-9-]+$")
RULE_ID_RE = re.compile(r"^R-[A-Z]+-\d+$")

KINDS = ("prose", "bullet", "table_row", "header")
SOURCE_TYPES = ("peer", "preprint", "spec", "vendor", "practitioner", "aggregator", "none")
SUPPORTS = ("confirms", "contrasts", "mentions")
BASES = ("evidence", "design", None)
POLARITIES = ("affirm", "negate")

EVIDENCE_REASONS = ("contrasting_source", "retracted_source", "vendor_gt1", "vendor_only")
DEBT_REASONS = (
    "no_countable_sources",
    "aggregator_unresolved",
    "lt3_independent",
    "lt2_primary",
    "independence_unset",
    "reception_unchecked",
    "unretrieved_source",
)
REASONS = EVIDENCE_REASONS + DEBT_REASONS

MAX_QUOTE_WORDS = 25

CLAIM_ANCHOR_RE = re.compile(r"<!-- claim:([^\s>]*) -->")
RULE_ANCHOR_RE = re.compile(r"<!-- rule:([^\s>]*) -->")
ANY_ANCHOR_RE = re.compile(r"<!-- (?:claim|rule):[^>]* --> ?")
MARKER_RE = re.compile(
    r"`\[(?P<grade>SETTLED|CONTESTED|EMERGING|VENDOR)(?::\s*(?P<qualifier>[^\]`]+))?\]`"
    r"(?P<flag> ?`\[UNVERIFIED\]`)?"
)
SOURCE_TAG_PREFIX_RE = re.compile(r"\]\([^)]*\)\s*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CHANGELOG_HEADING_RE = re.compile(r"^#{1,6}\s+Change log\s*$", re.IGNORECASE)


class SourcesError(ValueError):
    """Raised when the sidecar cannot be loaded as a mapping."""


@dataclass
class Marker:
    """One grade marker on an anchored line, in reading order."""

    grade: str
    qualifier: Optional[str]
    unverified: bool
    start: int
    end: int


@dataclass
class ClaimAnchor:
    id: str
    line_no: int
    text: str
    markers: List[Marker]


@dataclass
class RuleAnchor:
    id: str
    line_no: int
    end_line_no: int
    text: str


@dataclass
class ParsedResearch:
    claims: List[ClaimAnchor] = field(default_factory=list)
    rules: List[RuleAnchor] = field(default_factory=list)
    changelog_rows: List[str] = field(default_factory=list)
    unanchored_marker_lines: List[int] = field(default_factory=list)
    multi_anchor_lines: List[int] = field(default_factory=list)

    def claim_map(self) -> Dict[str, ClaimAnchor]:
        """First anchor per id; duplicates are reported by ``validate``."""
        out: Dict[str, ClaimAnchor] = {}
        for claim in self.claims:
            out.setdefault(claim.id, claim)
        return out

    def rule_map(self) -> Dict[str, RuleAnchor]:
        out: Dict[str, RuleAnchor] = {}
        for rule in self.rules:
            out.setdefault(rule.id, rule)
        return out


# --------------------------------------------------------------------------- #
# Sidecar I/O
# --------------------------------------------------------------------------- #

def load_sources(path: Union[str, Path]) -> Dict[str, Any]:
    """Load ``sources.yaml`` with ``yaml.safe_load``; the top level must be a mapping."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SourcesError(f"{path}: top level is not a mapping")
    return data


def dump_sources(data: Mapping[str, Any], path: Optional[Union[str, Path]] = None) -> str:
    """Serialize the sidecar deterministically; write it when ``path`` is given."""
    text = yaml.safe_dump(
        dict(data),
        sort_keys=False,
        allow_unicode=True,
        width=4096,
        default_flow_style=False,
    )
    if path is not None:
        Path(path).write_text(text, encoding="utf-8", newline="\n")
    return text


def check_no_comments(text: str) -> List[str]:
    """Return one error per YAML comment in ``text``; empty when there are none.

    A ``#`` counts as a comment when no scanner token covers it, which is the
    case for full-line comments and for a ``#`` after the last token on a line.
    A ``#`` inside a scalar (a URL fragment, a quoted string) is covered.
    """
    covered = bytearray(len(text) + 1)
    for token in yaml.scan(text):
        start, end = token.start_mark.index, token.end_mark.index
        if end > start:
            covered[start:end] = b"\x01" * (end - start)
    errors: List[str] = []
    seen_lines = set()
    for match in re.finditer("#", text):
        index = match.start()
        if covered[index]:
            continue
        line_no = text.count("\n", 0, index) + 1
        if line_no in seen_lines:
            continue
        seen_lines.add(line_no)
        errors.append(f"line {line_no}: YAML comment not allowed in sources.yaml; use a notes: field")
    return errors


# --------------------------------------------------------------------------- #
# RESEARCH.md parsing
# --------------------------------------------------------------------------- #

def find_markers(line: str) -> List[Marker]:
    """Grade markers on ``line`` in order, skipping ``[VENDOR]`` source tags after ``](...)``."""
    markers: List[Marker] = []
    for match in MARKER_RE.finditer(line):
        grade = match.group("grade")
        if grade == "VENDOR" and match.group("qualifier") is None and SOURCE_TAG_PREFIX_RE.search(line[: match.start()]):
            continue
        markers.append(
            Marker(
                grade=grade,
                qualifier=match.group("qualifier"),
                unverified=bool(match.group("flag")),
                start=match.start(),
                end=match.end(),
            )
        )
    return markers


def _table_cells(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def parse_research(text: str) -> ParsedResearch:
    """Parse anchors, markers, rules and change-log rows out of RESEARCH.md text.

    Fenced blocks, the confidence-marker legend table and the change-log table
    are skipped for anchors and markers. Change-log data rows are returned
    verbatim, header and separator excluded. Line numbers are 1-based.
    """
    parsed = ParsedResearch()
    lines = text.split("\n")
    fence: Optional[str] = None
    table_mode: Optional[str] = None
    in_changelog = False
    changelog_header_seen = False
    open_rule: Optional[RuleAnchor] = None

    for index, line in enumerate(lines):
        line_no = index + 1

        fence_match = FENCE_RE.match(line)
        if fence is not None:
            if fence_match and fence_match.group(1)[0] == fence[0] and len(fence_match.group(1)) >= len(fence):
                fence = None
            continue
        if fence_match:
            fence = fence_match.group(1)
            open_rule = None
            continue

        if not line.strip():
            open_rule = None
            table_mode = None
            if in_changelog and changelog_header_seen:
                in_changelog = False
            continue

        if line.startswith("#"):
            in_changelog = bool(CHANGELOG_HEADING_RE.match(line))
            changelog_header_seen = False
            table_mode = None

        if _is_table_line(line):
            if table_mode is None:
                cells = _table_cells(line)
                if in_changelog:
                    table_mode = "changelog"
                elif cells and cells[0] == "Marker":
                    table_mode = "legend"
                else:
                    table_mode = "table"
                if table_mode == "changelog":
                    changelog_header_seen = True
                    continue
            if table_mode == "changelog":
                if not re.fullmatch(r"\|?[\s:|-]+\|?", line.strip()):
                    parsed.changelog_rows.append(line)
                continue
            if table_mode == "legend":
                continue
        else:
            table_mode = None

        if open_rule is not None:
            open_rule.end_line_no = line_no
            open_rule.text += "\n" + line

        rule_ids = RULE_ANCHOR_RE.findall(line)
        for rule_id in rule_ids:
            rule = RuleAnchor(id=rule_id, line_no=line_no, end_line_no=line_no, text=line)
            parsed.rules.append(rule)
            open_rule = rule

        claim_ids = CLAIM_ANCHOR_RE.findall(line)
        if len(claim_ids) + len(rule_ids) > 1:
            parsed.multi_anchor_lines.append(line_no)
        markers = find_markers(line)
        if claim_ids:
            for claim_id in claim_ids:
                parsed.claims.append(ClaimAnchor(id=claim_id, line_no=line_no, text=line, markers=markers))
        elif markers:
            parsed.unanchored_marker_lines.append(line_no)

    return parsed


def strip_anchors(text: str) -> str:
    """Remove every claim and rule anchor plus the single space after it."""
    return ANY_ANCHOR_RE.sub("", text)


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #

def canonical_line(line: str) -> str:
    """Anchored line text without anchors, grade markers or UNVERIFIED flags, whitespace collapsed."""
    without_anchors = strip_anchors(line)
    pieces: List[str] = []
    cursor = 0
    for marker in find_markers(without_anchors):
        pieces.append(without_anchors[cursor : marker.start])
        cursor = marker.end
    pieces.append(without_anchors[cursor:])
    return " ".join("".join(pieces).split())


_HASH_EXCLUDED_SOURCE_KEYS = ("reception", "quote", "accessed")


def claim_sha256(claim_id: str, line: str, sources: Sequence[Mapping[str, Any]]) -> str:
    """Hash of a claim's identity: id, canonical line text and sources minus volatile fields."""
    payload = {
        "id": claim_id,
        "text": canonical_line(line),
        "sources": [
            {key: value for key, value in source.items() if key not in _HASH_EXCLUDED_SOURCE_KEYS}
            for source in sources
        ],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def lower_grade(first: str, second: str) -> str:
    """The lower-ranked of two grades."""
    return first if GRADE_RANK[first] <= GRADE_RANK[second] else second


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def _check_enum(errors: List[str], where: str, name: str, value: Any, allowed: Sequence[Any]) -> None:
    if value not in allowed:
        shown = ", ".join("null" if item is None else str(item) for item in allowed)
        errors.append(f"{where}: {name} {value!r} not in {{{shown}}}")


def _validate_grade(errors: List[str], where: str, grade: Any) -> None:
    if not isinstance(grade, dict):
        errors.append(f"{where}: grade entry is not a mapping")
        return
    _check_enum(errors, where, "asserted", grade.get("asserted"), GRADES)
    for key in ("cap", "cap_evidence"):
        if key in grade:
            _check_enum(errors, where, key, grade[key], GRADES + (None,))
    if "unverified" in grade and not isinstance(grade["unverified"], bool):
        errors.append(f"{where}: unverified must be true or false")
    reasons = grade.get("cap_reasons", [])
    if not isinstance(reasons, list):
        errors.append(f"{where}: cap_reasons must be a list")
    else:
        for reason in reasons:
            _check_enum(errors, where, "cap_reason", reason, REASONS)


def _validate_source(errors: List[str], where: str, source: Any, seen_ids: set) -> None:
    if not isinstance(source, dict):
        errors.append(f"{where}: source entry is not a mapping")
        return
    source_id = source.get("id")
    if not isinstance(source_id, str) or not source_id:
        errors.append(f"{where}: source id missing")
    elif source_id in seen_ids:
        errors.append(f"{where}: duplicate source id {source_id!r}")
    else:
        seen_ids.add(source_id)
    where = f"{where} source {source_id}"
    url = source.get("url")
    if url is not None and not isinstance(url, str):
        errors.append(f"{where}: url must be a string or null")
    _check_enum(errors, where, "type", source.get("type"), SOURCE_TYPES)
    if "resolves_to_type" in source:
        _check_enum(errors, where, "resolves_to_type", source["resolves_to_type"], SOURCE_TYPES + (None,))
    if source.get("resolves_to") and source.get("resolves_to_type") is None:
        errors.append(f"{where}: resolves_to set without resolves_to_type")
    _check_enum(errors, where, "supports", source.get("supports"), SUPPORTS)
    group = source.get("independence_group")
    if group is not None and not isinstance(group, str):
        errors.append(f"{where}: independence_group must be a string or null")
    quote = source.get("quote")
    if quote is not None:
        if not isinstance(quote, str):
            errors.append(f"{where}: quote must be a string or null")
        elif len(quote.split()) > MAX_QUOTE_WORDS:
            errors.append(f"{where}: quote has {len(quote.split())} words (max {MAX_QUOTE_WORDS})")
    reception = source.get("reception")
    if reception is not None:
        if not isinstance(reception, dict):
            errors.append(f"{where}: reception must be a mapping")
        elif "checked" in reception and not isinstance(reception["checked"], bool):
            errors.append(f"{where}: reception.checked must be true or false")


def validate(sources: Mapping[str, Any], research: Union[str, ParsedResearch]) -> List[str]:
    """Check sidecar and prose against each other; return errors, empty when clean."""
    parsed = parse_research(research) if isinstance(research, str) else research
    errors: List[str] = []

    if sources.get("schema") != SOURCES_SCHEMA:
        errors.append(f"schema must be {SOURCES_SCHEMA!r}, got {sources.get('schema')!r}")
    meta = sources.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta: missing or not a mapping")
    elif not isinstance(meta.get("enforced"), bool):
        errors.append("meta.enforced must be true or false")
    claims = sources.get("claims") or {}
    rules = sources.get("rules") or {}
    if not isinstance(claims, dict):
        errors.append("claims: not a mapping")
        claims = {}
    if not isinstance(rules, dict):
        errors.append("rules: not a mapping")
        rules = {}

    for line_no in parsed.multi_anchor_lines:
        errors.append(f"RESEARCH.md:{line_no}: more than one anchor on the line")
    for line_no in parsed.unanchored_marker_lines:
        errors.append(f"RESEARCH.md:{line_no}: grade marker without a claim anchor")

    anchor_counts: Dict[str, int] = {}
    for anchor in parsed.claims:
        anchor_counts[anchor.id] = anchor_counts.get(anchor.id, 0) + 1
    for claim_id, count in anchor_counts.items():
        if count > 1:
            errors.append(f"claim {claim_id}: anchored {count} times in RESEARCH.md")
        if not CLAIM_ID_RE.match(claim_id):
            errors.append(f"claim {claim_id!r}: anchor id does not match {CLAIM_ID_RE.pattern}")
        if claim_id not in claims:
            errors.append(f"claim {claim_id}: anchored in RESEARCH.md but missing from sources.yaml")

    rule_counts: Dict[str, int] = {}
    for anchor in parsed.rules:
        rule_counts[anchor.id] = rule_counts.get(anchor.id, 0) + 1
    for rule_id, count in rule_counts.items():
        if count > 1:
            errors.append(f"rule {rule_id}: anchored {count} times in RESEARCH.md")
        if not RULE_ID_RE.match(rule_id):
            errors.append(f"rule {rule_id!r}: anchor id does not match {RULE_ID_RE.pattern}")
        if rule_id not in rules:
            errors.append(f"rule {rule_id}: anchored in RESEARCH.md but missing from sources.yaml")

    anchors = parsed.claim_map()
    for claim_id, claim in claims.items():
        where = f"claim {claim_id}"
        if not isinstance(claim_id, str) or not CLAIM_ID_RE.match(claim_id):
            errors.append(f"claim {claim_id!r}: id does not match {CLAIM_ID_RE.pattern}")
        if claim_id not in anchors:
            errors.append(f"{where}: in sources.yaml but not anchored in RESEARCH.md")
        if not isinstance(claim, dict):
            errors.append(f"{where}: not a mapping")
            continue
        if not isinstance(claim.get("section"), int) or isinstance(claim.get("section"), bool):
            errors.append(f"{where}: section must be an integer")
        _check_enum(errors, where, "kind", claim.get("kind"), KINDS)
        _check_enum(errors, where, "polarity", claim.get("polarity"), POLARITIES)
        grades = claim.get("grades")
        if not isinstance(grades, list):
            errors.append(f"{where}: grades must be a list")
            grades = []
        for position, grade in enumerate(grades):
            _validate_grade(errors, f"{where} grade {position}", grade)
        if claim_id in anchors:
            marker_count = len(anchors[claim_id].markers)
            if marker_count != len(grades):
                errors.append(
                    f"{where}: {len(grades)} grades in sources.yaml, {marker_count} markers on RESEARCH.md:{anchors[claim_id].line_no}"
                )
        source_list = claim.get("sources")
        if not isinstance(source_list, list):
            errors.append(f"{where}: sources must be a list")
            source_list = []
        seen_ids: set = set()
        for source in source_list:
            _validate_source(errors, where, source, seen_ids)
        duplicates = claim.get("duplicates", [])
        if not isinstance(duplicates, list):
            errors.append(f"{where}: duplicates must be a list")
        else:
            for other in duplicates:
                if other not in claims:
                    errors.append(f"{where}: duplicate {other!r} is not a known claim")

    rule_anchors = parsed.rule_map()
    for rule_id, rule in rules.items():
        where = f"rule {rule_id}"
        if not isinstance(rule_id, str) or not RULE_ID_RE.match(rule_id):
            errors.append(f"rule {rule_id!r}: id does not match {RULE_ID_RE.pattern}")
        if rule_id not in rule_anchors:
            errors.append(f"{where}: in sources.yaml but not anchored in RESEARCH.md")
        if not isinstance(rule, dict):
            errors.append(f"{where}: not a mapping")
            continue
        _check_enum(errors, where, "basis", rule.get("basis"), BASES)
        cited = rule.get("claims", [])
        if not isinstance(cited, list):
            errors.append(f"{where}: claims must be a list")
        else:
            for claim_id in cited:
                if claim_id not in claims:
                    errors.append(f"{where}: cites unknown claim {claim_id!r}")

    return errors
