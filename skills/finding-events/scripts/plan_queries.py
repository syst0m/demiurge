#!/usr/bin/env python3
"""Turn an event brief into a resolved date window and a concrete query plan.

Run it; do not read it.

    python plan_queries.py --where London --when "this weekend" \
        --interest film-making --interest dating --access neurodivergent

    python plan_queries.py --where Manchester --when "next 2 weeks" \
        --interest "board games" --json

Why this is a script and not a judgement call: relative dates are the fragile part of this
task. "This weekend" on a Sunday, "next weekend" on a Friday, and "this week" on a Saturday
all have answers people disagree about, and getting one wrong sends the whole search at the
wrong dates without anything downstream noticing. The rules below are written down, applied
the same way every time, and printed with the output so a wrong assumption is visible rather
than buried.

Everything else - which results are any good, whether an event is real, whether it suits the
person asking - is judgement, and stays with the agent.

Stdlib only. No network. Reads nothing, writes nothing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys

# Weekend = Saturday and Sunday. Friday evening counts as weekend for events, because
# listings do, so a "weekend" window opens Friday.
FRIDAY, SATURDAY, SUNDAY = 4, 5, 6

# Query templates by source category. These build searches; they are not a directory.
# Verify anything a search returns - see references/sources.md.
LISTING_QUERIES = [
    '{interest} events {where} {daterange}',
    '"{interest}" {where} tickets {month_year}',
    '{where} what\'s on {daterange} {interest}',
]
COMMUNITY_QUERIES = [
    '{interest} meetup {where}',
    '{interest} group {where} monthly',
    '{where} {interest} community events',
]
NICHE_QUERIES = [
    '{interest} {where} site:eventbrite.co.uk',
    '{interest} {where} site:meetup.com',
    '{interest} {where} site:lu.ma',
]
ACCESS_QUERIES = {
    "neurodivergent": [
        'neurodivergent friendly {interest} events {where}',
        'autistic led {interest} {where}',
        'relaxed OR quiet OR "sensory friendly" {interest} {where}',
        'ADHD OR autistic social {where} {daterange}',
    ],
    "wheelchair": [
        'step free access {interest} {where}',
        'wheelchair accessible venue {interest} {where}',
    ],
    "sober": [
        'alcohol free OR sober {interest} events {where}',
        'daytime {interest} {where}',
    ],
    "low-cost": [
        'free {interest} events {where} {daterange}',
        'pay what you can {interest} {where}',
    ],
}


def parse_when(phrase: str, today: dt.date) -> tuple[dt.date, dt.date, str]:
    """Return (start, end, how it was read). Inclusive of both ends."""
    p = phrase.strip().lower()
    dow = today.weekday()

    if p in {"today", "tonight"}:
        return today, today, "today"
    if p == "tomorrow":
        d = today + dt.timedelta(days=1)
        return d, d, "tomorrow"

    if p in {"this weekend", "the weekend", "weekend"}:
        if dow in (SATURDAY, SUNDAY):
            # Already in it. The weekend that is happening, not the next one.
            start = today - dt.timedelta(days=dow - SATURDAY)
            return start, start + dt.timedelta(days=1), \
                "already in the weekend, so the current one (Sat-Sun)"
        start = today + dt.timedelta(days=(FRIDAY - dow) % 7)
        return start, start + dt.timedelta(days=2), "the coming Fri-Sun"

    if p == "next weekend":
        # The weekend after the coming one. On Sat/Sun, that is 7 days on.
        if dow in (SATURDAY, SUNDAY):
            start = today - dt.timedelta(days=dow - SATURDAY) + dt.timedelta(days=7)
        else:
            start = today + dt.timedelta(days=(FRIDAY - dow) % 7 + 7)
        return start, start + dt.timedelta(days=2), "the weekend after the coming one"

    if p in {"this week", "rest of the week"}:
        return today, today + dt.timedelta(days=6 - dow), "today to Sunday"
    if p == "next week":
        start = today + dt.timedelta(days=7 - dow)
        return start, start + dt.timedelta(days=6), "Monday to Sunday of next week"

    if match := re.match(r"next (\d+) (day|week|month)s?", p):
        n, unit = int(match.group(1)), match.group(2)
        days = {"day": n, "week": n * 7, "month": n * 30}[unit]
        return today, today + dt.timedelta(days=days), f"today plus {days} days"

    if match := re.match(r"(\d{4}-\d{2}-\d{2})(?:\s*(?:to|\.\.)\s*(\d{4}-\d{2}-\d{2}))?$", p):
        start = dt.date.fromisoformat(match.group(1))
        end = dt.date.fromisoformat(match.group(2)) if match.group(2) else start
        return start, end, "explicit dates"

    # Unrecognised. Do not guess a window - say so, and default to a fortnight.
    return today, today + dt.timedelta(days=14), \
        f"NOT UNDERSTOOD ({phrase!r}) - defaulted to the next 14 days. Confirm with the user."


def build_queries(where: str, interests: list[str], access: list[str],
                  start: dt.date, end: dt.date) -> list[dict]:
    daterange = f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"
    month_year = start.strftime("%B %Y")
    plan: list[dict] = []

    def add(category: str, templates: list[str], interest: str) -> None:
        for template in templates:
            plan.append({
                "category": category,
                "interest": interest,
                "query": template.format(interest=interest, where=where,
                                         daterange=daterange, month_year=month_year),
            })

    for interest in interests or ["events"]:
        add("listings", LISTING_QUERIES, interest)
        add("community", COMMUNITY_QUERIES, interest)
        add("niche", NICHE_QUERIES, interest)
        for need in access:
            if templates := ACCESS_QUERIES.get(need.lower()):
                add(f"access:{need.lower()}", templates, interest)

    # Access needs matter even with no interest attached to them.
    for need in access:
        if need.lower() not in ACCESS_QUERIES:
            plan.append({"category": f"access:{need.lower()}", "interest": "",
                         "query": f'{need} friendly events {where} {daterange}'})
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve dates and build an event query plan.")
    parser.add_argument("--where", required=True, help="city, area or 'online'")
    parser.add_argument("--when", default="next 2 weeks", help='e.g. "this weekend", "2026-09-12"')
    parser.add_argument("--interest", action="append", default=[], help="repeatable")
    parser.add_argument("--access", action="append", default=[],
                        help="repeatable: neurodivergent, wheelchair, sober, low-cost, or free text")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    start, end, reading = parse_when(args.when, today)
    queries = build_queries(args.where, args.interest, args.access, start, end)
    unclear = reading.startswith("NOT UNDERSTOOD")

    payload = {
        "where": args.where,
        "asked_for": args.when,
        "today": today.isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat(),
                   "days": (end - start).days + 1},
        "date_reading": reading,
        "needs_confirmation": unclear,
        "interests": args.interest,
        "access_needs": args.access,
        "queries": queries,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Today is {today.isoformat()} ({today.strftime('%A')}).")
        print(f"{args.when!r} read as: {reading}")
        print(f"Window: {start.isoformat()} to {end.isoformat()} "
              f"({payload['window']['days']} days)")
        print(f"Where: {args.where}"
              + (f"   Interests: {', '.join(args.interest)}" if args.interest else "")
              + (f"   Access: {', '.join(args.access)}" if args.access else ""))
        print("-" * 72)
        current = None
        for row in queries:
            if row["category"] != current:
                current = row["category"]
                print(f"\n[{current}]")
            print(f"  {row['query']}")
        print("-" * 72)
        print(f"{len(queries)} queries. Run them, then vet every result against "
              "references/vetting.md before showing it to anyone.")

    if unclear:
        print("\nThe date phrase was not understood. Confirm the window with the user "
              "before searching - a wrong window wastes the whole search.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
