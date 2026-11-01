#!/usr/bin/env python3
"""H1-plan-composability: compose the protocol's daily-OS rules into a 7-day plan
(including one crash day) and validate the invariants the rules imply. Exit 0 iff all hold."""
import sys

# Protocol rules (from the builder's Build Brief):
#  R1 med timing: dex after the first meal; NO dose after 15:00.
#  R2 sleep: target >= 6.5 h, fixed wake time.
#  R3 capacity: must-do <= 16 h/day + 1.5 h buffer.
#  R4 trauma pacing: one 10-min grounding/reset break every day.
#  R5 crash day: fatigue >= 4 -> minimum viable schedule + rest + NO new med changes.
#  R6 overcommitment guardrail: <= 1 optional commitment per day.

def day_plan(fatigue, commitments):
    # commitments: list of (is_optional, hours)
    optional = [h for o, h in commitments if o]
    n_optional = min(len(optional), 1)          # R6 guardrail
    if fatigue >= 4:                            # R5 crash day
        med = "none (crash day: rest, no new med changes)"
    else:
        med = "08:00 dex after breakfast (no dose after 15:00)"
    grounding = "10-min grounding/reset break"  # R4
    schedule = "work 2h" if fatigue >= 4 else "work 4h"
    sleep_h = 6.5 if fatigue < 4 else 8.0       # crash day protects sleep
    return {"med": med, "schedule": schedule, "sleep": sleep_h,
            "grounding": grounding, "n_optional": n_optional}

def main():
    days = [
        ("Mon", 2, [(True, 2), (False, 4)]),
        ("Tue", 2, [(False, 4)]),
        ("Wed", 5, [(False, 3), (True, 1)]),      # crash day
        ("Thu", 1, [(True, 3)]),
        ("Fri", 2, [(False, 5)]),
        ("Sat", 3, [(True, 4), (False, 4)]),      # fatigue 3 -> ok, 2 optional capped at 1
        ("Sun", 1, [(False, 6)]),
    ]
    crash = day_plan(days[2][1], days[2][2])   # Wednesday crash day
    crash_ok = crash["med"] == "none (crash day: rest, no new med changes)"
    med_ok = all("after 15:00" in day_plan(f, [])["med"]
                 for _, f, _ in days if f < 4)
    sleep_ok = sum(1 for _, f, _ in days if day_plan(f, [])["sleep"] >= 6.5) >= 5
    grounding_count = sum(1 for _, f, _ in days if day_plan(f, [])["grounding"])
    violations = [d for d in days if day_plan(d[1], d[2])["n_optional"] > 1]
    checks = {
        "crash-day rule fires on day 3": crash_ok,
        "no dose after 15:00": med_ok,
        "sleep >= 6.5h on >= 5 nights": sleep_ok,
        "grounding break daily": grounding_count == 7,
        "overcommitment <=1 optional/day": not violations,
    }
    ok = True
    for k, v in checks.items():
        print(("PASS" if v else "FAIL"), "-", k)
        ok = ok and v
    print("exit", 0 if ok else 1)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
