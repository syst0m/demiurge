#!/usr/bin/env python3
"""
test_sync_hermes_commands.py - Unit tests for the generated demiurge-skills Hermes plugin.

The sync script writes into $HERMES_HOME/plugins/demiurge-skills. Each test runs it
against a temporary HERMES_HOME, then imports the generated __init__.py and exercises
the ::help hook. No real plugin directory is touched.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "sync-hermes-commands.py"


def _build_plugin(home: Path) -> Path:
    """Run the sync script against a temporary HERMES_HOME and return the plugin dir."""
    env = dict(os.environ, HERMES_HOME=str(home))
    subprocess.run(
        [sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )
    plugin_dir = home / "plugins" / "demiurge-skills"
    if not (plugin_dir / "__init__.py").is_file():
        raise AssertionError("sync-hermes-commands.py wrote no plugin __init__.py")
    return plugin_dir


def _load(plugin_dir: Path):
    spec = importlib.util.spec_from_file_location(
        "demiurge_skills_under_test", plugin_dir / "__init__.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HelpPromptTest(unittest.TestCase):
    def test_help_blocks_with_the_cheat_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = _load(_build_plugin(Path(tmp)))
            setattr(module, "_cheatsheet", lambda: "SHEET")
            self.assertEqual(
                module.block_help_prompt("::help"),
                {"action": "block", "message": "SHEET  "},
            )

    def test_help_keeps_lines_and_backticks_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = _load(_build_plugin(Path(tmp)))
            setattr(module, "_cheatsheet", lambda: "A <b> c\n\nD")
            self.assertEqual(
                module.block_help_prompt("::help"),
                {"action": "block", "message": "A `<b>` c  \n\nD  "},
            )

    def test_other_prompts_pass_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = _load(_build_plugin(Path(tmp)))
            setattr(module, "_cheatsheet", lambda: "SHEET")
            self.assertIsNone(module.block_help_prompt("hello"))
            self.assertIsNone(module.block_help_prompt("  "))
            self.assertIsNone(module.block_help_prompt(["::help"]))  # multimodal turn

    def test_missing_hook_fails_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = _load(_build_plugin(Path(tmp)))
            self.assertIsNone(module.block_help_prompt("::help"))

    def test_plugin_manifest_declares_the_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _build_plugin(Path(tmp))
            manifest = (plugin_dir / "plugin.yaml").read_text(encoding="utf-8")
            self.assertIn("pre_llm_call", manifest)


BAD = "This is a pipeline rework, not a bug fix."


class TropeHooksTest(unittest.TestCase):
    """Single-output design: the rule rides in as context, the reply is never rewritten."""

    def _module(self, tmp):
        return _load(_build_plugin(Path(tmp)))

    def test_pre_llm_call_adds_rule_as_context_and_never_vetoes(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._module(tmp)
            out = module.trope_gate_pre_llm_call(payload={"user_message": BAD})
            self.assertIn("context", out)
            self.assertNotIn("action", out)
            self.assertIn("negative parallelism", out["context"])

    def test_reply_is_never_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._module(tmp)
            self.assertIsNone(module.trope_gate_log_llm_output(response_text=BAD))
            self.assertIsNone(module.trope_gate_log_llm_output(response_text="Plain line."))

    def test_each_flagged_line_is_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._module(tmp)
            module.trope_gate_log_llm_output(response_text="Plain.\n" + BAD + "\n")
            log = Path(tmp) / "logs" / "trope-gate-hits.log"
            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("line 2", lines[0])

    def test_quoted_example_writes_no_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._module(tmp)
            module.trope_gate_log_llm_output(response_text='The rule bans "' + BAD + '" here.')
            self.assertFalse((Path(tmp) / "logs" / "trope-gate-hits.log").exists())

    def test_clean_reply_writes_no_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._module(tmp)
            module.trope_gate_log_llm_output(response_text="Plain statement.")
            self.assertFalse((Path(tmp) / "logs" / "trope-gate-hits.log").exists())

    def test_rewrite_machinery_is_gone(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._module(tmp)
            for name in ("_llm_rewrite", "_rewrite_flagged", "trope_gate_transform_llm_output"):
                self.assertFalse(hasattr(module, name), name)

    def test_logging_failure_fails_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._module(tmp)
            with mock.patch.object(module, "_trope_hits", side_effect=RuntimeError("boom")):
                self.assertIsNone(module.trope_gate_log_llm_output(response_text=BAD))


class TropeOpenItemsTest(unittest.TestCase):
    def test_outer_source_has_no_invalid_escape_warning(self):
        import warnings
        src = (Path(__file__).parent / "sync-hermes-commands.py").read_text(encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            compile(src, "sync-hermes-commands.py", "exec")  # must not raise


if __name__ == "__main__":
    unittest.main()
