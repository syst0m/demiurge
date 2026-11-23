"""stdio MCP client for scholarly connectors.

Starts each connector (scite, Undermind, Consensus) as a stdio subprocess,
speaks JSON-RPC over its pipes, and shuts it down when done. Standard
library only -- no new dependencies.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any


class MCPError(RuntimeError):
    """The MCP server returned an error or a malformed response."""


_id_counter = 0


def _next_id() -> int:
    global _id_counter
    _id_counter += 1
    return _id_counter


def start_server(
    command: str, args: list[str], env: dict[str, str] | None = None
) -> subprocess.Popen:
    """Start an MCP server as a stdio subprocess and return its Popen handle."""
    return subprocess.Popen(
        [command, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    )


def send(proc: subprocess.Popen, req: dict[str, Any]) -> None:
    """Write one JSON-RPC request to the server's stdin."""
    assert proc.stdin is not None, "MCP server stdin is closed"
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()


def read_response(proc: subprocess.Popen) -> dict[str, Any]:
    """Read one JSON-RPC response line from the server's stdout."""
    assert proc.stdout is not None, "MCP server stdout is closed"
    line = proc.stdout.readline()
    if not line:
        raise MCPError("MCP server closed stdout")
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        raise MCPError(f"invalid JSON from MCP server: {exc}") from exc


def _request(proc: subprocess.Popen, method: str, params: dict[str, Any]) -> dict[str, Any]:
    send(proc, {"jsonrpc": "2.0", "id": _next_id(), "method": method, "params": params})
    resp = read_response(proc)
    if isinstance(resp, dict) and "error" in resp:
        raise MCPError(str(resp["error"]))
    return resp


def initialize(proc: subprocess.Popen) -> dict[str, Any]:
    return _request(proc, "initialize", {}).get("result", {})


def tools_list(proc: subprocess.Popen) -> list[dict[str, Any]]:
    return _request(proc, "tools/list", {}).get("result", {}).get("tools", [])


def tools_call(
    proc: subprocess.Popen, name: str, args: dict[str, Any]
) -> dict[str, Any]:
    return _request(proc, "tools/call", {"name": name, "arguments": args}).get(
        "result", {}
    )


def close(proc: subprocess.Popen) -> None:
    """Tell the server to exit, then terminate/kill it with a timeout."""
    try:
        if proc.stdin is not None and not proc.stdin.closed:
            send(proc, {"jsonrpc": "2.0", "method": "exit", "params": {}})
            proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
