"""
PR-C7.1d follow-up — diagnose WHY the worker drops valid meeting times
that LegEvent has.

Hypothesis (from reading calendar_worker.py):
  The LegEvent recovery block is gated `if origin == "journal_default"`
  (calendar_worker.py:3289). But a FLOOR action that misses its convene
  anchor is assigned `origin = "floor_miss"` (line 3259) BEFORE that
  gate — so it never reaches LegEvent recovery. ABSOLUTE_FLOOR_VERBS
  (line 347) forces these actions to a "Floor" location (line 3072),
  routing them through the convene-anchor path (line 3239), not the
  LegEvent path.

  Net: floor votes (read 2nd/3rd, rules suspended, conference report
  agreed, agreed to, rejected, passed) whose convene anchor is missing
  show `⏱️ [NO_CONVENE_ANCHOR]` even though LegEvent has their exact
  minute-precision time. The worker structurally never asks.

This script demonstrates the MECHANISM on real LIS data — no Sheets
access needed:
  1. Fetch LegEvent events for a sample of bills.
  2. For each event: does it carry a real wall-clock time? Is its
     description an ABSOLUTE_FLOOR_VERB (worker forces it to Floor)?
  3. Count floor-type, real-timed events — the population AT RISK of
     the floor_miss dead-end.

SCOPE CAVEAT (Codex P2 review, 2026-05-31): this count is the AT-RISK
population, NOT the actually-dropped count. The worker only dead-ends a
floor action when its convene anchor is ALSO missing — if
`convene_times[date][chamber]` exists, the worker sets
`origin = "convene_anchor"` and the row gets a real time (NOT dropped).
This script does not have the worker's convene-time graph, so it cannot
tell which of the at-risk events actually missed their anchor. The
ACTUAL dropped count is the C7_1d audit's flagged genuine-meeting rows
(rows truly showing placeholder times) — a subset of this at-risk
population. This script proves the mechanism is real and the at-risk
population is non-trivial; the audit's flagged set is the authoritative
dropped count.

Read-only. No Sheets writes. LIS API only.
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from categorize import eventdate_has_real_time, safe_str  # noqa: E402

# Mirror calendar_worker.py:347 EXACTLY.
ABSOLUTE_FLOOR_VERBS = [
    "reading dispensed", "read first", "read second", "read third",
    "passed senate", "passed house", "agreed to", "rejected",
    "rules suspended", "conference report agreed",
]

LIS_HEADERS = {"WebAPIKey": "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"}
SESSION_CODE_5D = "20261"
VERSION_URL = "https://lis.virginia.gov/LegislationVersion/api/GetLegislationVersionbyBillNumberAsync"
EVENT_URL = "https://lis.virginia.gov/LegislationEvent/api/GetPublicLegislationEventHistoryListAsync"

# Sample: bills known to be in the flagged set (from the audit histogram)
# plus a spread of low-numbered bills likely to have full floor histories.
SAMPLE_BILLS = (
    [f"HB{n}" for n in (1, 2, 5, 100, 1450)]
    + [f"SB{n}" for n in (1, 5, 106, 200)]
    + [f"HB{n}" for n in (1500, 1600, 800)]
)


def fetch_events(bill):
    try:
        v = requests.get(VERSION_URL, headers=LIS_HEADERS,
                         params={"billNumber": bill, "sessionCode": SESSION_CODE_5D}, timeout=15)
        vj = v.json()
        if not isinstance(vj, dict):
            return []
        versions = vj.get("LegislationsVersion")
        if not isinstance(versions, list) or not versions:
            return []
        first = versions[0]
        if not isinstance(first, dict):
            return []
        lid = first.get("LegislationID")
        if not lid:
            return []
        e = requests.get(EVENT_URL, headers=LIS_HEADERS,
                         params={"legislationID": lid, "sessionCode": SESSION_CODE_5D}, timeout=15)
        ej = e.json()
        if not isinstance(ej, dict):
            return []
        evs = ej.get("LegislationEvents") or []
        return evs if isinstance(evs, list) else []
    except Exception as ex:
        print(f"  ⚠️ {bill}: {type(ex).__name__}: {ex}")
        return []


def is_absolute_floor(description: str) -> bool:
    """Mirror calendar_worker.py:3064 — is_absolute_floor test."""
    lower = safe_str(description).lower()
    return any(f in lower for f in ABSOLUTE_FLOOR_VERBS)


def main():
    print("=== PR-C7.1d floor-gate diagnosis ===")
    print(f"Sample: {len(SAMPLE_BILLS)} bills\n")
    floor_realtime = []          # floor-type events WITH a real time (the dropped meetings)
    floor_realtime_codes = Counter()
    nonfloor_realtime = 0
    total_realtime = 0
    total_events = 0
    for bill in SAMPLE_BILLS:
        evs = fetch_events(bill)
        time.sleep(0.3)
        for e in evs:
            if not isinstance(e, dict):
                continue
            total_events += 1
            desc = safe_str(e.get("Description"))
            code = safe_str(e.get("EventCode"))
            has_time = eventdate_has_real_time(e.get("EventDate"))
            if not has_time:
                continue
            total_realtime += 1
            if is_absolute_floor(desc):
                floor_realtime.append((bill, code, safe_str(e.get("EventDate")), desc[:60]))
                floor_realtime_codes[code] += 1
            else:
                nonfloor_realtime += 1

    print(f"Total events examined:                 {total_events}")
    print(f"Events with a real wall-clock time:    {total_realtime}")
    print(f"  ... that are ABSOLUTE_FLOOR_VERBS:   {len(floor_realtime)}  <-- AT-RISK population")
    print(f"  ... non-floor (LegEvent path OK):    {nonfloor_realtime}")
    print()
    print("FLOOR-TYPE EVENTS WITH REAL TIMES — the AT-RISK population.")
    print("Worker routes these via the convene-anchor path. Of these, ONLY the")
    print("subset whose (date,chamber) also LACKS a convene anchor becomes")
    print("origin=floor_miss → LegEvent block SKIPPED (line 3289). The rest get")
    print("origin=convene_anchor and a real time — NOT dropped. This script")
    print("cannot distinguish the two (no convene-time graph); the C7_1d audit's")
    print("flagged genuine-meeting rows are the authoritative dropped count.")
    print(f"  {'bill':<8} {'code':<8} {'eventdate':<22} description")
    for bill, code, edate, desc in floor_realtime[:40]:
        print(f"  {bill:<8} {code:<8} {edate:<22} {desc}")
    print()
    print("EventCode histogram among the AT-RISK floor-type real-timed events:")
    for code, n in floor_realtime_codes.most_common():
        print(f"  {code:<8} {n}")
    print()
    print("CONCLUSION (mechanism, not count): floor votes routinely carry a")
    print("minute-precision LegEvent time. When such an action ALSO misses its")
    print("convene anchor, the floor_miss dead-end (origin != 'journal_default')")
    print("prevents the LegEvent block from recovering that time. The fix is to")
    print("fall through floor_miss → LegEvent. The number of rows actually")
    print("affected = the C7_1d audit's flagged genuine-meeting residue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
