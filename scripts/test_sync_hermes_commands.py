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


BAD = "This is a pipeline rework, not a bug fix."


class TropeRewriteTest(unittest.TestCase):
    def _hook(self, stub, text):
        with tempfile.TemporaryDirectory() as tmp:
            module = _load(_build_plugin(Path(tmp)))
            calls = []

            def wrapped(lines):
                calls.append(list(lines))
                return stub(lines, len(calls))

            setattr(module, "_llm_rewrite", wrapped)
            return module, module.trope_gate_transform_llm_output(response_text=text), calls

    def test_clean_reply_returns_none(self):
        _, out, calls = self._hook(lambda lines, n: lines, "All plain.")
        self.assertIsNone(out)
        self.assertEqual(calls, [])

    def test_flagged_line_is_rewritten_and_others_untouched(self):
        _, out, calls = self._hook(
            lambda lines, n: ["This is a pipeline rework."], "Intro.\n" + BAD + "\nEnd."
        )
        self.assertEqual(out, "Intro.\nThis is a pipeline rework.\nEnd.")
        self.assertEqual(calls[0], [BAD])

    def test_still_flagged_after_three_tries_is_kept_and_flagged(self):
        module, out, calls = self._hook(lambda lines, n: lines, "Intro.\n" + BAD)
        self.assertEqual(len(calls), 3)
        self.assertEqual(out, "Intro.\n" + BAD + module.TROPE_FLAG)
        self.assertNotIn("withheld", out)

    def test_second_try_succeeds_stops_early(self):
        module, out, calls = self._hook(
            lambda lines, n: lines if n == 1 else ["This is a pipeline rework."], BAD
        )
        self.assertEqual(len(calls), 2)
        self.assertNotIn(module.TROPE_FLAG, out)

    def test_rewriter_exception_keeps_and_flags(self):
        def boom(lines, n):
            raise RuntimeError("down")

        module, out, calls = self._hook(boom, BAD)
        self.assertEqual(out, BAD + module.TROPE_FLAG)
        self.assertEqual(len(calls), 1)

    def test_wrong_line_count_counts_as_failed_try(self):
        module, out, calls = self._hook(lambda lines, n: ["x"], BAD + "\n" + BAD)
        self.assertEqual(len(calls), 3)
        self.assertEqual(out, "\n".join([BAD + module.TROPE_FLAG] * 2))

    def test_inline_code_line_splices_original_text(self):
        line = "Use `foo(a, not b)` here, not there."
        fixed = "Use `foo(a, not b)` here."
        _, out, _ = self._hook(lambda lines, n: [fixed], line)
        self.assertEqual(out, fixed)

    def test_flag_suffix_does_not_trip_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = _load(_build_plugin(Path(tmp)))
            self.assertEqual(module._trope_hits("x" + module.TROPE_FLAG), [])

    def test_slow_rewriter_hits_budget_and_flags(self):
        import time

        def slow(lines, n):
            time.sleep(3)
            return ["fixed"]

        with tempfile.TemporaryDirectory() as tmp:
            module = _load(_build_plugin(Path(tmp)))
            module.BUDGET_SECONDS = 0.5
            setattr(module, "_llm_rewrite", lambda lines: slow(lines, 1))
            t0 = time.monotonic()
            out = module.trope_gate_transform_llm_output(response_text=BAD)
            self.assertLess(time.monotonic() - t0, 2)
            self.assertEqual(out, BAD + module.TROPE_FLAG)
            self.assertNotIn("withheld", out)

    def test_nested_list_item_keeps_indent_and_marker(self):
        text = "- top\n    - It is a rework, not a fix.\n- end"
        _, out, calls = self._hook(lambda lines, n: ["It is a rework."], text)
        self.assertEqual(calls[0], ["It is a rework, not a fix."])
        self.assertEqual(out, "- top\n    - It is a rework.\n- end")

    def test_marker_echoed_by_model_gives_one_marker(self):
        text = "- top\n    - It is a rework, not a fix.\n- end"
        _, out, _ = self._hook(lambda lines, n: ["- It is a rework."], text)
        self.assertEqual(out, "- top\n    - It is a rework.\n- end")

    def test_numbered_list_prefix_is_kept(self):
        _, out, _ = self._hook(lambda lines, n: ["It is a rework."], "3. It is a rework, not a fix.")
        self.assertEqual(out, "3. It is a rework.")

    def test_crlf_text_keeps_crlf(self):
        text = "a\r\nIt is a rework, not a fix.\r\nb\r\n"
        _, out, _ = self._hook(lambda lines, n: ["It is a rework."], text)
        self.assertEqual(out, "a\r\nIt is a rework.\r\nb\r\n")
        module, out, _ = self._hook(lambda lines, n: lines, text)
        self.assertEqual(out, "a\r\nIt is a rework, not a fix." + module.TROPE_FLAG + "\r\nb\r\n")
        self.assertNotIn("\n", out.replace("\r\n", ""))

    def test_rewrite_that_is_a_fence_or_quote_marker_fails_the_try(self):
        flagged = "It is a rework, not a fix."
        text = flagged + "\n\n```\ncode sample\n```\nEnd."
        for bad in ("```", "> It is a rework."):
            module, out, calls = self._hook(lambda lines, n, bad=bad: [bad], text)
            self.assertEqual(len(calls), 3)
            self.assertEqual(out, flagged + module.TROPE_FLAG + "\n\n```\ncode sample\n```\nEnd.")

    def test_fenced_code_is_exempt(self):
        _, out, _ = self._hook(lambda lines, n: lines, "```\n" + BAD + "\n```")
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
