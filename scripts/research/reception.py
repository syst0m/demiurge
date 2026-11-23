"""Scholarly connector reception checks via stdio MCP.

scite reception returns {checked, retracted, supporting, contrasting} for a
source URL. Undermind/Consensus search return [{url, title, snippet}] for
source discovery. Connector commands/tool names are placeholders -- confirm
exact values against each vendor's MCP docs before enabling on CI.
"""
from __future__ import annotations

import os
from typing import Any

from scripts.research import mcp_client

# Connector commands / tool names. Confirm exact values against each vendor's
# MCP docs before enabling on CI.
SCITE_COMMAND = "npx"
SCITE_ARGS = ["-y", "scite-mcp@latest"]
SCITE_SMART_CITATIONS_TOOL = "scite/smart-citations"

UNDERMIND_COMMAND = "npx"
UNDERMIND_ARGS = ["-y", "undermind-mcp@latest"]

CONSENSUS_COMMAND = "npx"
CONSENSUS_ARGS = ["-y", "consensus-mcp@latest"]


def scite_reception(url: str, api_key: str) -> dict[str, Any]:
    """Return reception metadata for a source URL via scite Smart Citations."""
    env = dict(os.environ, SCITE_API_KEY=api_key)
    proc = mcp_client.start_server(SCITE_COMMAND, SCITE_ARGS, env=env)
    try:
        mcp_client.initialize(proc)
        result = mcp_client.tools_call(
            proc, SCITE_SMART_CITATIONS_TOOL, {"url": url}
        )
        return {
            "checked": True,
            "retracted": bool(result.get("retracted")),
            "supporting": result.get("supporting"),
            "contrasting": result.get("contrasting"),
        }
    finally:
        mcp_client.close(proc)


def undermind_search(query: str, api_key: str) -> list[dict]:
    """Return [{url, title, snippet}] source-discovery results from Undermind."""
    env = dict(os.environ, UNDERMIND_API_KEY=api_key)
    proc = mcp_client.start_server(UNDERMIND_COMMAND, UNDERMIND_ARGS, env=env)
    try:
        mcp_client.initialize(proc)
        raw = mcp_client.tools_call(proc, "undermind/search", {"query": query})
        return raw if isinstance(raw, list) else []
    finally:
        mcp_client.close(proc)


def consensus_search(query: str, api_key: str) -> list[dict]:
    """Return [{url, title, snippet}] source-discovery results from Consensus."""
    env = dict(os.environ, CONSENSUS_API_KEY=api_key)
    proc = mcp_client.start_server(CONSENSUS_COMMAND, CONSENSUS_ARGS, env=env)
    try:
        mcp_client.initialize(proc)
        raw = mcp_client.tools_call(proc, "consensus/search", {"query": query})
        return raw if isinstance(raw, list) else []
    finally:
        mcp_client.close(proc)
