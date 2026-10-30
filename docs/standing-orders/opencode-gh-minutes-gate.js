// OpenCode plugin: blocks PR and workflow commands when GitHub Actions minutes are unavailable.
// Install: copy to ~/.config/opencode/plugins/gh-minutes-gate.js. Set GH_MINUTES_GATE_SCRIPT if your
// checkout is not at ~/Documents/code/demiurge.
// The decision lives in demiurge/scripts/gh_minutes_gate.py so every harness shares one rule.
import { spawnSync } from "node:child_process"
import { homedir } from "node:os"

const GATE = process.env.GH_MINUTES_GATE_SCRIPT
  || `${homedir()}/Documents/code/demiurge/scripts/gh_minutes_gate.py`

export const GhMinutesGate = async () => ({
  "tool.execute.before": async (input, output) => {
    if (input.tool !== "bash") return
    const command = output.args?.command
    if (typeof command !== "string") return
    const run = spawnSync("python", [GATE, "--command", command], { encoding: "utf8", timeout: 60000 })
    if (run.status === 2) throw new Error(run.stderr.trim())
  },
})
