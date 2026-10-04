"""Tests for scripts/ledger/ledger_hook.py."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE / "ledger_hook.py"
REPO_ROOT = HERE.parents[1]
LEDGER_LIB = REPO_ROOT / "skills" / "marcus" / "scripts" / "ledger_lib.py"
sys.path.insert(0, str(LEDGER_LIB.parent))

import ledger_lib  # noqa: E402

WSL_REFUSED = "bash not found (WSL bash refused)"
SESSION = "session-under-test"

# Runs the hook's code with builtins.__import__ patched and writes every imported module
# name to argv[2]. argv[1] is the hook path.
IMPORT_PROBE = """
import builtins, json, sys
hook, out = sys.argv[1], sys.argv[2]
seen = []
real = builtins.__import__
def probe(name, *args, **kwargs):
    seen.append(name)
    return real(name, *args, **kwargs)
code = compile(open(hook, encoding="utf-8").read(), hook, "exec")
sys.argv = [hook, "--event", "prompt"]
builtins.__import__ = probe
try:
    exec(code, {"__name__": "__main__", "__file__": hook})
except SystemExit as exc:
    rc = exc.code
else:
    rc = None
finally:
    builtins.__import__ = real
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"rc": rc, "imports": seen}, handle)
"""


def _refuse_wsl(candidate: str | None) -> str | None:
    if not candidate:
        return None
    if "system32" in str(Path(candidate)).lower():
        return None
    return candidate


def resolve_bash() -> str | None:
    """Resolve bash: DEMIURGE_BASH, then Git for Windows bash next to git, then PATH."""
    override = os.environ.get("DEMIURGE_BASH")
    if override:
        return _refuse_wsl(override)
    git = shutil.which("git")
    if git:
        git_dir = Path(git).resolve().parent
        for candidate in (
            git_dir / "bash.exe",
            git_dir.parent / "bin" / "bash.exe",
            git_dir.parent.parent / "bin" / "bash.exe",
        ):
            if candidate.is_file():
                return _refuse_wsl(str(candidate))
    return _refuse_wsl(shutil.which("bash"))


BASH = resolve_bash()


class HookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.ledger = self.root / "ledger"
        self.home = self.root / "home"
        skill = self.home / ".claude" / "skills" / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
        self.transcript = self.root / "transcript.jsonl"
        entries = [
            {"type": "user", "version": "9.9.1", "message": {"role": "user"}},
            {"type": "assistant", "version": "9.9.2",
             "message": {"role": "assistant", "model": "model-under-test"}},
            {"type": "system", "subtype": "note"},
        ]
        self.transcript.write_text("".join(json.dumps(e) + "\n" for e in entries),
                                   encoding="utf-8")
        self.env = dict(os.environ)
        self.env.update({ledger_lib.LEDGER_ENV: str(self.ledger), "HOME": str(self.home),
                         "USERPROFILE": str(self.home)})
        self.env.pop("PYTHONPATH", None)

    def payload(self, **extra) -> str:
        data = {"session_id": SESSION, "transcript_path": str(self.transcript),
                "cwd": str(self.root / "project")}
        data.update(extra)
        return json.dumps(data)

    def run_hook(self, event: str, stdin: str, hook: Path = HOOK
                 ) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(hook), "--event", event],
                              input=stdin.encode("utf-8"), capture_output=True,
                              env=self.env, timeout=30, check=False)

    def rows(self) -> list:
        return list(ledger_lib.iter_rows(self.ledger, strict=True))

    def error_log(self) -> list:
        path = self.ledger / "hook-errors.log"
        if not path.is_file():
            return []
        return path.read_text(encoding="utf-8").splitlines()

    def post_tool(self, skill: str = "demo") -> subprocess.CompletedProcess:
        return self.run_hook("post-tool", self.payload(
            hook_event_name="PostToolUse", tool_name="Skill", tool_input={"skill": skill}))

    def prompt(self, text: str) -> subprocess.CompletedProcess:
        return self.run_hook("prompt", self.payload(
            hook_event_name="UserPromptSubmit", prompt=text))


class TestPostTool(HookTestCase):
    def test_post_tool_row_written(self) -> None:
        result = self.post_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["kind"], row["origin"], row["skill"], row["trigger"]),
                         ("invoke", "organic", "demo", "model"))
        self.assertEqual(row["model_id"], "model-under-test")
        self.assertEqual(row["version"], "9.9.2")
        self.assertEqual(row["session"], ledger_lib.hash_session(SESSION))
        self.assertEqual(row["skill_sha"],
                         ledger_lib.skill_sha(self.home / ".claude" / "skills" / "demo"))
        self.assertNotIn(SESSION, json.dumps(row))
        self.assertEqual(self.error_log(), [])

    def test_skill_name_falls_back_to_name_then_unknown(self) -> None:
        self.run_hook("post-tool", self.payload(tool_name="Skill",
                                                tool_input={"name": "other"}))
        self.run_hook("post-tool", self.payload(tool_name="Skill", tool_input={}))
        self.assertEqual([row["skill"] for row in self.rows()], ["other", "unknown"])
        self.assertTrue(all("skill_sha" not in row for row in self.rows()))

    def test_slash_then_tool_call_is_deduped(self) -> None:
        self.assertEqual(self.prompt("/demo do the thing").returncode, 0)
        self.assertEqual(self.post_tool().returncode, 0)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trigger"], "slash")

    def test_other_skill_after_slash_is_not_deduped(self) -> None:
        self.prompt("/demo")
        self.post_tool("other")
        self.assertEqual([row["skill"] for row in self.rows()], ["demo", "other"])

    def test_old_slash_row_is_not_deduped(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(seconds=120)
        ts = old.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        path = ledger_lib.month_file(ts, self.ledger)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "schema": ledger_lib.SCHEMA_VERSION, "run_id": "old", "ts": ts, "kind": "invoke",
            "origin": "organic", "skill": "demo", "trigger": "slash",
            "session": ledger_lib.hash_session(SESSION)}) + "\n", encoding="utf-8")
        self.post_tool()
        self.assertEqual([row["trigger"] for row in self.rows()], ["slash", "model"])


class TestPrompt(HookTestCase):
    def test_bad_with_class_records_verdict_and_blocks(self) -> None:
        self.post_tool()
        invoke = self.rows()[0]
        result = self.prompt("::bad misroute x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout),
                         {"decision": "block", "reason": "ledger: recorded bad for demo"})
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        verdict = rows[1]
        self.assertEqual(verdict["kind"], "verdict")
        self.assertEqual(verdict["run_id"], invoke["run_id"])
        self.assertEqual(verdict["outcome"],
                         {"label": "bad", "source": "user", "failure_class": "misroute"})
        self.assertNotIn(" x", json.dumps(verdict))

    def test_ok_records_verdict(self) -> None:
        self.post_tool()
        result = self.prompt("::ok")
        self.assertEqual(json.loads(result.stdout)["reason"], "ledger: recorded ok for demo")
        self.assertEqual(self.rows()[1]["outcome"], {"label": "ok", "source": "user"})

    def test_bad_with_unknown_word_has_no_class(self) -> None:
        self.post_tool()
        self.prompt("::bad this was wrong")
        self.assertEqual(self.rows()[1]["outcome"], {"label": "bad", "source": "user"})

    def test_verdict_without_invoke_blocks_without_row(self) -> None:
        result = self.prompt("::bad")
        self.assertEqual(json.loads(result.stdout)["decision"], "block")
        self.assertEqual(self.rows(), [])

    def test_slash_for_installed_skill_writes_row_and_passes(self) -> None:
        result = self.prompt("/demo some private words")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        rows = self.rows()
        self.assertEqual([(r["skill"], r["trigger"]) for r in rows], [("demo", "slash")])
        self.assertNotIn("private", json.dumps(rows))

    def test_slash_for_unknown_name_writes_nothing(self) -> None:
        self.assertEqual(self.prompt("/clear").returncode, 0)
        self.assertEqual(self.rows(), [])

    def test_ordinary_prompt_writes_nothing_and_imports_nothing(self) -> None:
        stdin = self.payload(hook_event_name="UserPromptSubmit",
                             prompt='please "prompt": "::bad" fix /demo')
        out = self.root / "imports.json"
        started = time.monotonic()
        result = subprocess.run([sys.executable, "-c", IMPORT_PROBE, str(HOOK), str(out)],
                                input=stdin.encode("utf-8"), capture_output=True,
                                env=self.env, timeout=30, check=False)
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        probe = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(probe["rc"], 0)
        self.assertEqual(set(probe["imports"]) - {"sys"}, set())
        self.assertLess(elapsed, 2.0)
        self.assertFalse(self.ledger.exists())

    def test_capture_prompt_goes_past_the_fast_path(self) -> None:
        self.post_tool()
        out = self.root / "imports.json"
        stdin = self.payload(hook_event_name="UserPromptSubmit", prompt="::ok")
        subprocess.run([sys.executable, "-c", IMPORT_PROBE, str(HOOK), str(out)],
                       input=stdin.encode("utf-8"), capture_output=True, env=self.env,
                       timeout=30, check=False)
        self.assertIn("ledger_lib", json.loads(out.read_text(encoding="utf-8"))["imports"])


class TestFailOpen(HookTestCase):
    def test_malformed_stdin_exits_zero_and_logs(self) -> None:
        for event in ("prompt", "post-tool"):
            result = self.run_hook(event, "{not json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
        log = self.error_log()
        self.assertEqual(len(log), 2)
        self.assertEqual([line.split("\t")[1:] for line in log],
                         [["prompt", "JSONDecodeError"], ["post-tool", "JSONDecodeError"]])
        self.assertEqual(self.rows(), [])

    def test_missing_ledger_lib_exits_zero_and_logs(self) -> None:
        lonely = self.root / "bin" / "ledger_hook.py"
        lonely.parent.mkdir()
        shutil.copy2(HOOK, lonely)
        result = self.run_hook("post-tool", self.payload(tool_name="Skill",
                                                         tool_input={"skill": "demo"}),
                               hook=lonely)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.error_log()[0].split("\t")[1:],
                         ["post-tool", "ModuleNotFoundError"])

    def test_pinned_copy_imports_sibling_ledger_lib(self) -> None:
        pinned = self.root / "bin"
        pinned.mkdir()
        shutil.copy2(HOOK, pinned / "ledger_hook.py")
        shutil.copy2(LEDGER_LIB, pinned / "ledger_lib.py")
        result = self.run_hook("post-tool", self.payload(tool_name="Skill",
                                                         tool_input={"skill": "demo"}),
                               hook=pinned / "ledger_hook.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.error_log(), [])

    def test_lock_timeout_drops_row_and_logs(self) -> None:
        with ledger_lib.locked(self.ledger, timeout=1.0):
            started = time.monotonic()
            result = self.post_tool()
            elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 5.0)
        self.assertEqual(self.error_log()[0].split("\t")[1:],
                         ["post-tool", "LedgerLockTimeout"])
        self.assertEqual(self.rows(), [])

    def test_lock_timeout_on_bad_still_blocks(self) -> None:
        self.post_tool()
        with ledger_lib.locked(self.ledger, timeout=1.0):
            result = self.prompt("::bad misroute private words")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout),
                         {"decision": "block", "reason": "ledger: not recorded (error logged)"})
        self.assertEqual(self.error_log()[0].split("\t")[1:], ["prompt", "LedgerLockTimeout"])
        self.assertEqual(len(self.rows()), 1)

    def test_oversized_skill_row_has_no_skill_sha(self) -> None:
        skill = self.home / ".claude" / "skills" / "demo"
        for index in range(ledger_lib.HOOK_MAX_FILES + 1):
            (skill / f"f{index}.md").write_text("x", encoding="utf-8")
        result = self.post_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertNotIn("skill_sha", rows[0])
        self.assertEqual(self.error_log(), [])

    @unittest.skipIf(BASH is None, WSL_REFUSED)
    def test_installed_command_exits_zero_when_script_deleted(self) -> None:
        pinned = self.root / "bin"
        pinned.mkdir()
        script = pinned / "ledger_hook.py"
        shutil.copy2(HOOK, script)
        script.unlink()
        python = Path(sys.executable).as_posix()
        command = f'"{python}" "{script.as_posix()}" --event prompt || true'
        result = subprocess.run([BASH, "-c", command],
                                input=self.payload(prompt="::bad").encode("utf-8"),
                                capture_output=True, env=self.env, timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
