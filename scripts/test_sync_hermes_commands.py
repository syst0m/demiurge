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
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
