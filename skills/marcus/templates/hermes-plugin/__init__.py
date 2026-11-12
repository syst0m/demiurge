"""{{HOOK_NAME}}: veto the turn before any inference request.

Contract (agent/turn_context.py:_collect_pre_llm_call_context): a pre_llm_call callback vetoes
the turn by returning {"action": "block", "message": "<non-empty string>"}. A block without a
message is ignored. The turn then ends with no inference request at all.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parent / "hooks" / "gate.py"


def register(ctx):
    def _check(event, payload):
        repo = os.environ.get("DEMIURGE_REPO") or os.getcwd()
        proc = subprocess.run(
            [sys.executable, str(GATE), "--repo", repo, "--json"],
            capture_output=True, text=True)
        try:
            data = json.loads(proc.stdout)
        except Exception:
            return None
        if data.get("decision") == "block":
            message = str(data.get("reason") or "policy gate blocked this turn").strip()
            if not message:
                return None
            print(message)
            return {"action": "block", "message": message}
        return None
    ctx.register_hook("pre_llm_call", _check)
