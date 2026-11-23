"""Tests for scripts.research.reception (scholarly connector reception)."""
from __future__ import annotations

import unittest

from unittest.mock import MagicMock, patch

from scripts.research import mcp_client, reception


class SciteReceptionTest(unittest.TestCase):
    def test_uses_mcp_client(self):
        calls = []

        def fake_tools_call(proc, name, args):
            calls.append((name, args))
            return {
                "checked": True,
                "retracted": False,
                "supporting": 3,
                "contrasting": 1,
            }

        fake_proc = MagicMock()
        with (
            patch.object(mcp_client, "start_server", return_value=fake_proc),
            patch.object(mcp_client, "initialize", return_value={}),
            patch.object(mcp_client, "tools_call", side_effect=fake_tools_call),
            patch.object(mcp_client, "close"),
        ):
            result = reception.scite_reception(
                "https://arxiv.org/abs/2509.09677", "key"
            )

        self.assertEqual(
            result,
            {
                "checked": True,
                "retracted": False,
                "supporting": 3,
                "contrasting": 1,
            },
        )
        self.assertEqual(calls[0][0], "scite/smart-citations")
        self.assertEqual(calls[0][1]["url"], "https://arxiv.org/abs/2509.09677")
