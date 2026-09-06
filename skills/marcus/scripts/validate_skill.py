#!/usr/bin/env python3
"""G4 - deterministic format and security validation for an Agent Skill.

Run it; do not read it.

    python validate_skill.py <skill-dir> [--json] [--strict]

Exit codes:
    0  clean
    1  warnings only (or blocking issues when --strict is off and none are blocking)
    2  at least one blocking issue

Format rules come from the published Agent Skills constraints; security rules come from
the two published scans of community skills. See references/EVIDENCE.md sections 5 and 7.
Stdlib only, so it runs anywhere the skill does.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# --- Published limits. Each is a documented constraint. -------------------------------
NAME_MAX = 64
DESCRIPTION_MAX = 1024
BODY_MAX_LINES = 500          # documented threshold for optimal performance
REFERENCE_TOC_THRESHOLD = 100  # over this, partial reads miss content without a ToC
MIN_EVAL_CASES = 3            # documented minimum for eval-driven development
RESERVED_SUBSTRINGS = ("anthropic", "claude")
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
XML_TAG = re.compile(r"<[A-Za-z/][^>]*>")

BLOCKING, WARNING, INFO = "blocking", "warning", "info"


@dataclass
class Finding:
    level: str
    code: str
    message: str
    where: str = ""

    def line(self) -> str:
        loc = f" [{self.where}]" if self.where else ""
        return f"{self.level.upper():<8} {self.code:<22} {self.message}{loc}"


# --- Security patterns. Script-bundling skills are 2.12x more likely to be vulnerable, --
# --- so executable content is scanned harder than prose. --------------------------------
HIGH_RISK = [
    (r"curl[^\n|]*\|\s*(ba)?sh", "remote-pipe-shell", "pipes a download straight into a shell"),
    (r"wget[^\n|]*\|\s*(ba)?sh", "remote-pipe-shell", "pipes a download straight into a shell"),
    (r"base64[^\n]*(-d|--decode)[^\n]*\|\s*(ba)?sh", "encoded-exec", "decodes and executes"),
    (r"b64decode\s*\([^)]*\)\s*\)?\s*(?=.*\b(exec|eval)\b)", "encoded-exec", "decodes then evaluates"),
    (r"\b(exec|eval)\s*\(\s*(requests|urllib|urlopen|fetch)", "remote-exec", "evaluates fetched content"),
    (r"(id_rsa|\.ssh/|\.aws/credentials|\.npmrc|\.netrc)", "credential-path", "touches a credential path"),  # forge:allow credential-path - pattern definition regex
    (r"(?i)\b(AWS_SECRET|API_KEY|PRIVATE_KEY|BEGIN RSA PRIVATE)", "secret-literal", "references a secret"),  # forge:allow secret-literal - pattern definition regex
]

MEDIUM_RISK = [
    (r"\b(requests\.(post|put)|urllib\.request\.urlopen|httpx\.(post|put)|fetch\()",
     "network-egress", "makes an outbound network call - check it against the trifecta"),
    (r"\bos\.system\s*\(|\bsubprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True",
     "shell-invocation", "invokes a shell; prefer an argument list"),
    (r"(?i)\brm\s+-rf\b", "destructive", "destructive delete - must dump before deleting"),
]

# Instruction-shaped text inside reference files is the documented injection vector:
# 91% of confirmed malicious skill payloads used prompt injection.
INJECTION_SHAPED = [
    (r"(?i)ignore (all |any )?(previous|prior|above) instructions", "injection-shaped"),
    (r"(?i)disregard (the )?(system prompt|your instructions)", "injection-shaped"),
    (r"(?i)you are now (a|an|in) ", "injection-shaped"),
    (r"(?i)\bdo not (tell|inform|mention to) the user\b", "injection-shaped"),
]

# Conversational meta-commentary, session transcripts, and diary entries
# have no place in agent skills; comments record code invariants, not session history.
SUPERFLUOUS = [
    (r"(?i)\b(chat\s+transcript|previously\s+held\s+a\s+chat|transcript\s+describing)\b",
     "superfluous-transcript", "chat transcript reference in comments or prose"),  # forge:allow superfluous-transcript - pattern definition regex
    (r"(?i)\b(working\s+copy\s+had\s+been\s+installed|unversioned\s+and\s+would\s+be\s+displaced|displaced\s+by\s+`?pre-commit)\b",
     "superfluous-war-story", "historical migration narrative in comment"),  # forge:allow superfluous-war-story - pattern definition regex
    (r"(?i)\b(session\s+diary|diary\s+note|\d{4}-\d{2}-\d{2}\s+(incident|debugging\s+session|war\s+story))\b",
     "superfluous-diary", "session diary or developer war story in comment"),  # forge:allow superfluous-diary - pattern definition regex
]

TIME_SENSITIVE = re.compile(
    r"(?i)\b(as of (january|february|march|april|may|june|july|august|september|october|november|december|\d{4})"
    r"|before \w+ \d{4}|after \w+ \d{4}|currently, |at the time of writing|this year)\b"
)

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
BACKTICK_PATH = re.compile(r"`([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.*-]+)+)`")

# The "tool content is data" rule is stated in many shapes by skills that observe it.
# Matching only one phrasing reported two skills that DO state it as skills that do not -
# a validator that fails a compliant skill teaches people to ignore its warnings.
DATA_NOT_INSTRUCTIONS = re.compile(
    r"(?i)(data,?\s+(and\s+)?never\s+instructions"
    r"|never\s+instructions,?\s+(only\s+)?data"
    r"|(is|are)\s+data\b[^.]{0,60}\bnot\s+(a\s+)?(command|instruction)"
    r"|not\s+treat\s+\w*\s?(output|content)[^.]{0,30}as\s+(an?\s+)?instruction"
    r"|treat[^.]{0,40}as\s+data,?\s+never\s+as\s+instructions?)"
)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, list[Finding]]:
    """Minimal YAML frontmatter reader - flat key: value only, which is all the spec allows."""
    findings: list[Finding] = []
    if not text.startswith("---"):
        findings.append(Finding(BLOCKING, "frontmatter-missing",
                                "SKILL.md must open with a '---' YAML frontmatter block"))
        return {}, text, findings

    end = text.find("\n---", 3)
    if end == -1:
        findings.append(Finding(BLOCKING, "frontmatter-unclosed",
                                "frontmatter block is never closed with '---'"))
        return {}, text, findings

    raw = text[3:end]
    body = text[end + 4:]
    fields: dict[str, str] = {}
    key = None
    for raw_line in raw.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[:1] in " \t" and key:          # folded continuation
            fields[key] += " " + raw_line.strip()
            continue
        if ":" not in raw_line:
            continue
        key, _, value = raw_line.partition(":")
        key = key.strip()
        fields[key] = value.strip().strip("'\"")
    return fields, body, findings


def check_name(name: str | None) -> list[Finding]:
    if not name:
        return [Finding(BLOCKING, "name-missing", "frontmatter has no 'name' field")]
    out: list[Finding] = []
    if len(name) > NAME_MAX:
        out.append(Finding(BLOCKING, "name-too-long", f"name is {len(name)} chars, limit {NAME_MAX}"))
    if not NAME_PATTERN.match(name):
        out.append(Finding(BLOCKING, "name-charset",
                           "name must be lowercase letters, digits and single hyphens only"))
    for word in RESERVED_SUBSTRINGS:
        if word in name.lower():
            out.append(Finding(BLOCKING, "name-reserved", f"name must not contain '{word}'"))
    if XML_TAG.search(name):
        out.append(Finding(BLOCKING, "name-xml", "name must not contain XML tags"))
    return out


def check_description(desc: str | None) -> list[Finding]:
    if not desc:
        return [Finding(BLOCKING, "description-missing", "frontmatter has no 'description' field")]
    out: list[Finding] = []
    if len(desc) > DESCRIPTION_MAX:
        out.append(Finding(BLOCKING, "description-too-long",
                           f"description is {len(desc)} chars, limit {DESCRIPTION_MAX}"))
    if XML_TAG.search(desc):
        out.append(Finding(BLOCKING, "description-xml", "description must not contain XML tags"))
    # Third person: the description is injected into the system prompt, and first or second
    # person there measurably disrupts skill selection.
    if re.search(r"(?i)\b(I can|I will|I help|you can use this|use me to)\b", desc):
        out.append(Finding(WARNING, "description-person",
                           "description must be third person - drop 'I'/'you' framing"))
    # It has to say WHEN, not only what: 'when' is what the selector matches a request against.
    if not re.search(r"(?i)\b(use when|when the user|when asked|when working|use for|whenever)\b", desc):
        out.append(Finding(WARNING, "description-no-trigger",
                           "description names no triggering situation - add a 'Use when ...' clause"))
    if len(desc) < 60:
        out.append(Finding(WARNING, "description-thin",
                           "description is very short; selection accuracy degrades sharply as a library grows"))
    return out


def check_body(body: str) -> list[Finding]:
    out: list[Finding] = []
    lines = body.splitlines()
    if len(lines) > BODY_MAX_LINES:
        out.append(Finding(BLOCKING, "body-too-long",
                           f"body is {len(lines)} lines, limit {BODY_MAX_LINES} - move detail into references/"))
    elif len(lines) > BODY_MAX_LINES * 0.8:
        out.append(Finding(WARNING, "body-near-limit",
                           f"body is {len(lines)} lines, approaching the {BODY_MAX_LINES}-line limit"))
    if match := TIME_SENSITIVE.search(body):
        out.append(Finding(WARNING, "time-sensitive",
                           f"time-sensitive phrasing {match.group(0)!r} - move it to an 'Old patterns' section"))
    if not DATA_NOT_INSTRUCTIONS.search(body):
        out.append(Finding(WARNING, "no-data-not-instructions",
                           "body does not state that tool output is data, never instructions"))
    return out


def check_paths(skill_dir: Path, body: str) -> list[Finding]:
    """Backticked relative paths in SKILL.md that do not resolve.

    Markdown links are covered by check_references; these are the paths written as bare
    code spans - install steps, artefact tables, "run this script" lines. A dangling one
    sends the reader (or the agent) somewhere that does not exist, and nothing else catches
    it. Scoped to SKILL.md, because reference docs legitimately describe hypothetical trees.
    """
    out: list[Finding] = []
    for candidate in sorted(set(BACKTICK_PATH.findall(body))):
        if candidate.startswith(("~", "/", "http")) or "*" in candidate:
            continue  # home-relative, absolute, URL or glob - not ours to resolve
        if (skill_dir / candidate).exists():
            continue
        # Kept high-recall on purpose. A hit is either a genuinely broken skill-relative
        # path, or an external one written ambiguously - and both are worth fixing, so
        # neither is a false positive in the sense that matters.
        out.append(Finding(WARNING, "dangling-path",
                           f"SKILL.md refers to {candidate!r}, which does not exist inside the skill "
                           "- fix it, or write it as ~/... if it is external"))
    return out


def check_references(skill_dir: Path, body: str) -> list[Finding]:
    out: list[Finding] = []
    linked: set[Path] = set()

    for target in MD_LINK.findall(body):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if "\\" in target:
            out.append(Finding(BLOCKING, "windows-path",
                               f"link {target!r} uses backslashes - always forward slashes"))
            continue
        resolved = (skill_dir / target).resolve()
        if not resolved.exists():
            out.append(Finding(BLOCKING, "broken-reference", f"SKILL.md links to missing file {target!r}"))
            continue
        linked.add(resolved)

    # References must be one level deep: a file reached only through another referenced file
    # gets partially read (head -100) rather than read whole.
    for ref in sorted(linked):
        if ref.suffix.lower() != ".md" or not ref.is_file():
            continue
        text = ref.read_text(encoding="utf-8", errors="replace")
        line_count = len(text.splitlines())
        if line_count > REFERENCE_TOC_THRESHOLD:
            head = "\n".join(text.splitlines()[:40]).lower()
            if "contents" not in head and "table of contents" not in head:
                out.append(Finding(WARNING, "reference-no-toc",
                                   f"{line_count}-line reference has no table of contents",
                                   ref.name))
        for nested in MD_LINK.findall(text):
            if nested.startswith(("http://", "https://", "#", "mailto:")):
                continue
            nested_path = (ref.parent / nested).resolve()
            if nested_path.suffix.lower() == ".md" and nested_path not in linked and nested_path.exists():
                out.append(Finding(WARNING, "nested-reference",
                                   f"reaches {nested!r} only through another reference - link it from SKILL.md",
                                   ref.name))
    return out


# Suppressions are explicit, carry a reason, and are always printed. A scanner with silent
# exemptions is a scanner you cannot audit - which is the whole problem with skill supply
# chains. Two forms, because JSON cannot hold a comment:
#   same-line:    ... # forge:allow <code> - reason
#   .forgeignore: <relative/path>:<code> # reason
INLINE_ALLOW = re.compile(r"forge:allow\s+([a-z-]+)\s*[-:]?\s*(.*)$")


def load_forgeignore(skill_dir: Path) -> dict[tuple[str, str], str]:
    """Return {(relative_path, code): reason} from .forgeignore."""
    path = skill_dir / ".forgeignore"
    entries: dict[tuple[str, str], str] = {}
    if not path.is_file():
        return entries
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        spec, _, reason = line.partition("#")
        target, _, code = spec.strip().rpartition(":")
        if target and code:
            entries[(target.strip(), code.strip())] = reason.strip()
    return entries


def scan_file(path: Path, rel: str, executable: bool,
              ignores: dict[tuple[str, str], str]) -> list[Finding]:
    out: list[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [Finding(WARNING, "unreadable", f"could not read: {exc}", rel)]

    checks: list[tuple[str, str, str, str]] = (
        [(p, c, w, BLOCKING) for p, c, w in HIGH_RISK]
        + [(p, c, w, WARNING) for p, c, w in MEDIUM_RISK]
        + [(p, c, w, WARNING) for p, c, w in SUPERFLUOUS]
        + ([] if executable else
           [(p, c, "text is shaped like a prompt injection", BLOCKING) for p, c in INJECTION_SHAPED])
    )

    for number, line in enumerate(lines, 1):
        inline = INLINE_ALLOW.search(line)
        for pattern, code, why, level in checks:
            if not re.search(pattern, line):
                continue
            where = f"{rel}:{number}"
            if inline and inline.group(1) == code:
                reason = inline.group(2).strip()
                if reason:
                    out.append(Finding(INFO, f"allowed:{code}", f"{why} - suppressed: {reason}", where))
                elif meta := ignores.get((rel, "suppression-no-reason")):
                    out.append(Finding(INFO, "allowed:suppression-no-reason",
                                       f"{code} suppressed with no inline reason - allowed: {meta}", where))
                else:
                    out.append(Finding(WARNING, "suppression-no-reason",
                                       f"{code} suppressed with no reason given", where))
            elif (rel, code) in ignores:
                reason = ignores[(rel, code)]
                if reason:
                    out.append(Finding(INFO, f"allowed:{code}",
                                       f"{why} - suppressed in .forgeignore: {reason}", where))
                else:
                    out.append(Finding(WARNING, "suppression-no-reason",
                                       f"{code} suppressed in .forgeignore with no reason", where))
            else:
                out.append(Finding(level, code, why, where))
    return out


def check_bundle(skill_dir: Path) -> list[Finding]:
    out: list[Finding] = []
    scripts_dir = skill_dir / "scripts"
    ignores = load_forgeignore(skill_dir)

    # SKILL.md is scanned too. It is the file a malicious skill would put an injection in,
    # and it is the file most likely to be read without being audited.
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir).as_posix()
        if path.suffix.lower() in {".py", ".sh", ".bash", ".ps1", ".js", ".rb"}:
            out.extend(scan_file(path, rel, executable=True, ignores=ignores))
        elif path.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml"}:
            out.extend(scan_file(path, rel, executable=False, ignores=ignores))

    if scripts_dir.is_dir() and any(scripts_dir.iterdir()):
        provenance = skill_dir / "PROVENANCE.md"
        justified = provenance.is_file() and re.search(
            r"(?i)script", provenance.read_text(encoding="utf-8", errors="replace"))
        if not justified:
            out.append(Finding(WARNING, "scripts-unjustified",
                               "bundles executable scripts with no justification in PROVENANCE.md "
                               "- script-bundling skills are 2.12x more likely to be vulnerable"))
    return out


def extract_cases(data: object) -> list[dict]:
    """Read eval cases from either shape in use.

    Two are current: a flat {"cases": [...]} list where each case names its own suite, and a
    {"suites": {"regression": [...], "capability": [...]}} mapping where the suite is the key.
    Reading only the first reported a skill with 16 cases across both suites as having none -
    the kind of false negative that makes a gate worse than no gate.
    """
    if isinstance(data, list):
        return [c for c in data if isinstance(c, dict)]
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("cases"), list):
        return [c for c in data["cases"] if isinstance(c, dict)]

    cases: list[dict] = []
    suites = data.get("suites")
    if isinstance(suites, dict):
        for suite_name, suite in suites.items():
            rows = suite if isinstance(suite, list) else (
                suite.get("cases", []) if isinstance(suite, dict) else [])
            for row in rows:
                if isinstance(row, dict):
                    cases.append({**row, "suite": row.get("suite", suite_name)})
    return cases


def check_evals(skill_dir: Path) -> list[Finding]:
    candidates = [skill_dir / "evals" / "evals.json", skill_dir / "evals.json"]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        return [Finding(WARNING, "evals-missing",
                        "no evals/evals.json - a skill without evals has not been measured")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Finding(BLOCKING, "evals-malformed", f"evals.json is not valid JSON: {exc}")]

    cases = extract_cases(data)
    out: list[Finding] = []
    if len(cases) < MIN_EVAL_CASES:
        out.append(Finding(WARNING, "evals-too-few",
                           f"{len(cases)} eval case(s); the documented minimum is {MIN_EVAL_CASES}"))
    suites = {c.get("suite") for c in cases if isinstance(c, dict)}
    if "regression" not in suites:
        out.append(Finding(WARNING, "evals-no-regression",
                           "no regression suite - regression cases come from real failures and must hold at 100%"))
    for i, case in enumerate(cases):
        # Both key names are in use for the same thing; either makes a case gradeable.
        if isinstance(case, dict) and not (case.get("expected_behavior") or case.get("expected_output")):
            out.append(Finding(WARNING, "eval-no-expectation",
                               f"case {i} has no expected_behavior - it cannot be graded"))
    return out


def validate(skill_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [Finding(BLOCKING, "skill-md-missing", f"no SKILL.md in {skill_dir}")]

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fields, body, fm_findings = parse_frontmatter(text)
    findings.extend(fm_findings)
    if fields:
        findings.extend(check_name(fields.get("name")))
        findings.extend(check_description(fields.get("description")))
        if (name := fields.get("name")) and name != skill_dir.name:
            findings.append(Finding(WARNING, "name-dir-mismatch",
                                    f"frontmatter name {name!r} differs from directory {skill_dir.name!r}"))
    findings.extend(check_body(body))
    findings.extend(check_references(skill_dir, body))
    findings.extend(check_paths(skill_dir, body))
    findings.extend(check_bundle(skill_dir))
    findings.extend(check_evals(skill_dir))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="G4 validation for an Agent Skill.")
    parser.add_argument("skill_dir", type=Path)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true", help="treat warnings as blocking")
    args = parser.parse_args()

    skill_dir = args.skill_dir.expanduser().resolve()
    if not skill_dir.is_dir():
        print(f"error: {skill_dir} is not a directory", file=sys.stderr)
        return 2

    findings = validate(skill_dir)
    blocking = [f for f in findings if f.level == BLOCKING]
    warnings = [f for f in findings if f.level == WARNING]
    suppressed = [f for f in findings if f.level == INFO and f.code.startswith("allowed:")]

    if args.json:
        print(json.dumps({
            "skill": skill_dir.name,
            "path": skill_dir.as_posix(),
            "blocking": len(blocking),
            "warnings": len(warnings),
            "suppressed": len(suppressed),
            "gate": "G4",
            "passed": not blocking and not (args.strict and warnings),
            "findings": [asdict(f) for f in findings],
        }, indent=2))
    else:
        print(f"G4 validation: {skill_dir.name}")
        print("-" * 72)
        if not findings:
            print("clean - no findings")
        order = {BLOCKING: 0, WARNING: 1, INFO: 2}
        for finding in sorted(findings, key=lambda f: (order[f.level], f.code, f.where)):
            print(finding.line())
        print("-" * 72)
        print(f"{len(blocking)} blocking, {len(warnings)} warning(s), "
              f"{len(suppressed)} suppressed with a stated reason")
        if suppressed:
            print("Suppressions are shown above, never hidden. Read each one before trusting this pass.")
        if blocking:
            print("\nG4 FAILED. The build stops here; blocking issues are not waivable.")
        elif warnings and args.strict:
            print("\nG4 FAILED under --strict.")
        else:
            print("\nG4 passed. Next: G5 - eval_runner.py must show a positive delta before this ships.")

    if blocking or (args.strict and warnings):
        return 2
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
