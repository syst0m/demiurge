// OpenCode plugin: records skill tool calls in the run ledger. Fail-open: it never blocks a tool.
// Install: copy to ~/.config/opencode/plugins/demiurge-ledger.js. Set LEDGER_HOOK if the pinned
// hook is not at ~/.demiurge/bin/ledger_hook.py (see docs/RUN_LEDGER.md section 4).
// Shape follows docs/standing-orders/opencode-gh-minutes-gate.js (tool.execute.before, input.tool,
// output.args). The tool name "skill" and its "name" argument are NOT verified in a live session.
import { spawnSync } from "node:child_process"
import { homedir } from "node:os"

const HOOK = process.env.LEDGER_HOOK || `${homedir()}/.demiurge/bin/ledger_hook.py`

export const DemiurgeLedger = async () => ({
  "tool.execute.before": async (input, output) => {
    try {
      const name = output.args?.name
      if (input.tool !== "skill" || typeof name !== "string") return
      spawnSync("python", [HOOK, "--event", "record", "--harness", "opencode",
        "--subject-type", "skill", "--subject", name, "--trigger", "model"],
        { encoding: "utf8", timeout: 3000 })
    } catch {
      // a ledger fault must never reach the user's tool call
    }
  },
})
