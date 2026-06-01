"""
PR-C7.1b — validate the structural router against live LIS data.

Fetches a bill sample fresh (capturing the fields the router needs:
ReferenceType, VoteTally, ActorType, EventCode, EventDate, Description),
applies structural_router.route_event(), and reports:
  - verdict × reason distribution
  - samples per (route, reason) bucket for eyeball validation
  - the RISKY buckets surfaced for inspection: timed_action (rule 5,
    meeting-by-time) and untimed (rule 6, admin-by-default) — where a
    misroute is most likely
  - cross-check vs the text classifier on the known false-positive codes

Read-only, LIS API only. Run with output captured to a FILE
(lesson from assumptions_audit #57 — never transcribe a corrupting
terminal).
"""
from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict

import requests

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from structural_router import route_event, _s  # noqa: E402

LIS_HEADERS = {"WebAPIKey": "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"}
SESSION = "20261"
VURL = "https://lis.virginia.gov/LegislationVersion/api/GetLegislationVersionbyBillNumberAsync"
EURL = "https://lis.virginia.gov/LegislationEvent/api/GetPublicLegislationEventHistoryListAsync"
SAMPLE = ([f"HB{n}" for n in range(1, 26)] + [f"SB{n}" for n in range(1, 11)]
          + ["HB1450", "SB106"])


def fetch(bill):
    try:
        v = requests.get(VURL, headers=LIS_HEADERS,
                         params={"billNumber": bill, "sessionCode": SESSION}, timeout=15).json()
        if not isinstance(v, dict):
            return []
        vs = v.get("LegislationsVersion")
        if not isinstance(vs, list) or not vs or not isinstance(vs[0], dict):
            return []
        lid = vs[0].get("LegislationID")
        if not lid:
            return []
        e = requests.get(EURL, headers=LIS_HEADERS,
                         params={"legislationID": lid, "sessionCode": SESSION}, timeout=15).json()
        if not isinstance(e, dict):
            return []
        ev = e.get("LegislationEvents") or []
        return ev if isinstance(ev, list) else []
    except Exception as ex:
        print(f"  warn {bill}: {type(ex).__name__}")
        return []


def main():
    verdict_reason = Counter()
    samples = defaultdict(list)
    total = 0
    fp_codes = {"H5601", "S5601", "G7210"}
    fp_results = []
    for bill in SAMPLE:
        for e in fetch(bill):
            if not isinstance(e, dict):
                continue
            total += 1
            v = route_event(e)
            key = (v.route, v.reason)
            verdict_reason[key] += 1
            if len(samples[key]) < 5:
                samples[key].append(f"{_s(e.get('EventCode')):<7}{_s(e.get('Description'))[:55]}")
            if _s(e.get("EventCode")) in fp_codes:
                fp_results.append((_s(e.get("EventCode")), v.route, v.reason))
        time.sleep(0.25)

    meet = sum(n for (r, _), n in verdict_reason.items() if r == "meeting")
    adm = sum(n for (r, _), n in verdict_reason.items() if r == "admin")
    print(f"=== STRUCTURAL ROUTER validation — {total} events ===")
    print(f"  meeting: {meet}   admin: {adm}\n")
    print(f"  {'route':<8} {'reason':<20} {'n':>5}")
    for (route, reason), n in sorted(verdict_reason.items(), key=lambda kv: -kv[1]):
        print(f"  {route:<8} {reason:<20} {n:>5}")
    print()
    for key in sorted(samples, key=lambda k: -verdict_reason[k]):
        print(f"[{key[0]}/{key[1]}] ({verdict_reason[key]})")
        for smp in samples[key]:
            print(f"    {smp}")
    print()
    print("=== KNOWN FALSE-POSITIVE CODES — does the router collapse them to admin? ===")
    seen = set()
    for code, route, reason in fp_results:
        if code in seen:
            continue
        seen.add(code)
        flag = "✅" if route == "admin" else "❌ STILL MEETING"
        print(f"  {code:<7} → {route}/{reason}  {flag}")


if __name__ == "__main__":
    main()
