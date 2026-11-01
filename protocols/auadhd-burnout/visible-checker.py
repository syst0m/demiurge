#!/usr/bin/env python3
"""Visible-checks verifier: encode V1-V6 as assertions against the protocol."""
import sys

path = "protocols/auadhd-burnout/protocol.md"
text = open(path).read().lower()
fails = []

# V1: all four factors
for kw in ["dexamphetamine", "emotional trauma", "overcommitment", "burnout"]:
    if kw not in text:
        fails.append("V1 missing factor: " + kw)

# V2: safety & scope
if "not medical advice" not in text:
    fails.append("V2 missing disclaimer")
if "crisis" not in text or "emergency" not in text:
    fails.append("V2 missing crisis gate")

# V3: evidence tagging + RESEARCH.md claim ids
tags = ["my judgement", "settled", "contest", "vendor", "emerging"]
if not any(t in text for t in tags):
    fails.append("V3 missing evidence tags")
claims = ["fail.self-eval", "eval.judge-bias", "eval.visible-heldout-gap",
          "fail.reward-hacking", "fail.escalation-channel", "fail.pressure-exploit"]
if not any(c in text for c in claims):
    fails.append("V3 missing research claims")

# V4: daily-OS modules
for kw in ["energy", "dex timing", "sensory", "trauma pacing", "overcommitment guardrail"]:
    if kw not in text:
        fails.append("V4 missing module: " + kw)

# V5: weekly cycle + buffer
if "weekly" not in text:
    fails.append("V5 missing weekly cycle")
if "buffer" not in text:
    fails.append("V5 missing buffer")

# V6: edge handling
if "crash day" not in text:
    fails.append("V6 missing crash-day rule")
if "decline" not in text:
    fails.append("V6 missing overcommitment response")

print("visible exit", 1 if fails else 0)
for f in fails:
    print(" -", f)
sys.exit(1 if fails else 0)
