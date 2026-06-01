"""
PR-C7.1b realignment probe — does LIS's OWN semantic type field
(ReferenceType / VoteTally / IsPassed) cleanly route meeting-vs-admin,
killing the need for any dictionary?

Owner direction (2026-05-31): LIS knows what each action means and
serves it correctly. We should consume LIS's source-of-truth signals,
not build/maintain a dictionary. This probe MEASURES whether that
holds before we commit (no more asserting — assert-twice-wrong lesson).

Fetches a sample of bills fresh from LIS (ReferenceType is NOT in our
persisted cache, so a fresh fetch is required), and for every event
records: ReferenceType, ReferenceTypeID, VoteTally-present, IsPassed,
EventDate-has-real-time, EventCode, Description + the current text
classifier's verdict. Aggregates by ReferenceType.

The decisive question: do the known false positives (H5601/S5601 "Bill
text as passed", G7210 "Governor's recommendation received") carry a
DIFFERENT ReferenceType than genuine meetings (votes, committee
actions)? If yes → ReferenceType is the dictionary-free router.

Read-only. LIS API only. No Sheets, no writes.
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict

import requests

LIS_HEADERS = {"WebAPIKey": "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"}
SESSION = "20261"
VURL = "https://lis.virginia.gov/LegislationVersion/api/GetLegislationVersionbyBillNumberAsync"
EURL = "https://lis.virginia.gov/LegislationEvent/api/GetPublicLegislationEventHistoryListAsync"

SAMPLE = ([f"HB{n}" for n in range(1, 26)] + [f"SB{n}" for n in range(1, 11)]
          + ["HB1450", "SB106"])

# text classifier (verbatim subset for the cross-tab)
MEETING = ["reported", "recommends", "recommend", "passed", "failed", "defeated",
           "agreed to", "rejected", "offered", "stricken", "tabled", "continued",
           "read first", "read second", "read third", "rules suspended",
           "block vote", "concurred", "withdrawn", "amended"]
ADMINOVR = ["substitute printed", "prefiled and ordered printed"]


def s(v):
    return "" if v is None else str(v).strip()


def has_time(raw):
    x = s(raw)
    if "T" not in x:
        return False
    t = x.split("T", 1)[1][:8]
    return bool(t) and t not in ("00:00:00", "00:00")


def text_meeting(desc):
    d = s(desc).lower()
    if any(p in d for p in ADMINOVR):
        return False
    return any(p in d for p in MEETING)


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
    print("=== ReferenceType router probe ===\n")
    # aggregate by ReferenceType
    by_rt = defaultdict(lambda: {"n": 0, "rt_time": 0, "votetally": 0, "ispassed": 0,
                                 "text_meet": 0, "samples": [], "codes": Counter()})
    total = 0
    # also isolate the known false-positive codes
    fp_codes = {"H5601", "S5601", "G7210"}
    fp_rows = []
    for bill in SAMPLE:
        for e in fetch(bill):
            if not isinstance(e, dict):
                continue
            total += 1
            rt = s(e.get("ReferenceType")) or "<blank>"
            d = by_rt[rt]
            d["n"] += 1
            if has_time(e.get("EventDate")):
                d["rt_time"] += 1
            vt = e.get("VoteTally")
            if vt not in (None, "", [], {}):
                d["votetally"] += 1
            if e.get("IsPassed") is True:
                d["ispassed"] += 1
            if text_meeting(e.get("Description")):
                d["text_meet"] += 1
            code = s(e.get("EventCode"))
            d["codes"][code] += 1
            if len(d["samples"]) < 3:
                d["samples"].append(f"{code}:{s(e.get('Description'))[:45]}")
            if code in fp_codes:
                fp_rows.append((code, rt, s(e.get("ReferenceType")),
                                "VT" if vt not in (None, "", [], {}) else "-",
                                s(e.get("Description"))[:40]))
        time.sleep(0.25)

    print(f"total events: {total}\n")
    print(f"{'ReferenceType':<20} {'n':>5} {'realtime':>9} {'voteTally':>10} {'isPassed':>9} {'textMeet':>9}")
    for rt, d in sorted(by_rt.items(), key=lambda kv: -kv[1]["n"]):
        print(f"{rt:<20} {d['n']:>5} {d['rt_time']:>9} {d['votetally']:>10} {d['ispassed']:>9} {d['text_meet']:>9}")
    print()
    for rt, d in sorted(by_rt.items(), key=lambda kv: -kv[1]["n"]):
        print(f"[{rt}] top codes: {', '.join(f'{c}({n})' for c, n in d['codes'].most_common(6))}")
        for smp in d["samples"]:
            print(f"     e.g. {smp}")
    print()
    print("=== KNOWN FALSE-POSITIVE CODES — what ReferenceType does LIS give them? ===")
    seen = set()
    for code, rt, rtraw, vt, desc in fp_rows:
        key = (code, rt)
        if key in seen:
            continue
        seen.add(key)
        print(f"  {code:<7} ReferenceType={rtraw or '<blank>':<16} {vt:<3} {desc}")


if __name__ == "__main__":
    main()
