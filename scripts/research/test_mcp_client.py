"""Tests for scripts.research.mcp_client (stdio MCP client)."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

from scripts.research.mcp_client import (
    MCPError,
    close,
    initialize,
    read_response,
    send,
    start_server,
    tools_call,
    tools_list,
)

_STUB = r"""import json
import sys

while True:
    line = sys.stdin.readline()
    if not line:
        break
    req = json.loads(line)
    rid = req.get("id")
    sys.stdout.write(
        json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"ok": True}}) + "\n"
    )
    sys.stdout.flush()
"""


def start_stub() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", _STUB],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )


class McpClientRoundTrip(unittest.TestCase):
    def test_tools_call_echoes_result(self):
        proc = start_stub()
        self.addCleanup(close, proc)
        resp = tools_call(proc, "test/tool", {"a": 1})
        self.assertEqual(resp, {"ok": True})

    def test_initialize_and_tools_list(self):
        proc = start_stub()
        self.addCleanup(close, proc)
        self.assertEqual(initialize(proc), {"ok": True})
        self.assertEqual(tools_list(proc), [])

    def test_mcp_error_on_error_response(self):
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                'import json,sys;sys.stdout.write(json.dumps({"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"method not found"}})+"\\n");sys.stdout.flush()',
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(close, proc)
        with self.assertRaises(MCPError):
            tools_call(proc, "no/such", {})
