"""Tests for scripts.research.reception (scholarly connector reception)."""
from __future__ import annotations

import unittest

from unittest.mock import MagicMock, patch

from scripts.research import reception


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
            patch("mcp_client.start_server", return_value=fake_proc),
            patch("mcp_client.initialize", return_value={}),
            patch("mcp_client.tools_call", side_effect=fake_tools_call),
            patch("mcp_client.close"),
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
