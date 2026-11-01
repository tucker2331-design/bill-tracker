#!/usr/bin/env python3
"""Pennsylvania committee rosters — goldens on the REAL feeds fetched 2026-11-01 (tools/historical_cache/pa/2025_0/,
MANIFEST.json `later_fetches`): House + Senate committee assignments and session members RSS. No hand-made fixture.

GOLDEN (goldens/pa_roster_2025_0.json): a SHA-256 of every roster row + the stats, and spot rows checkable by eye
against the feed.

INVARIANTS (from the feeds themselves, independent of the golden):
  * every member has a structural memberId and a party joined on it (0 without either)
  * the party joined on memberId agrees with the "(D)"/"(R)" in the assignments title for every member — the title is
    read here ONLY as a cross-check of the structural join, never by the product
  * the one name join (committee_key) finds a roster for every bill whose export names a current committee (0 missing)
  * each committee's count of seats matches the feed's own count of <parss:Committee> elements naming it

Re-capture ONLY for an intended output change:  python3 test_pa_roster.py --write
"""
import collections
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

from states import pa_adapter as A
from states import pa_roster as R
import test_pa_intake as S

GOLDEN = os.path.join(S.HERE, "goldens", "pa_roster_2025_0.json")
FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


def raw(name):
    with open(os.path.join(S.CACHE, name), "rb") as f:
        return f.read()


fx = S.SampleFetcher()
rows, stats = R.run_roster(fx, S.PA.urls)
check("four feeds asked for, all bulk RSS", sorted(fx.asked) == sorted(
    f"https://www.palegis.us/{c}/rss/{p}" for c in ("house", "senate") for p in ("committee/assignments", "session/members")))

# --- invariants ---
check("250 members (201 House + 49 Senate), every one with a memberId and a party",
      stats["roster_members"] == 250 and stats["roster_members_without_id"] == 0 and stats["roster_members_without_party"] == 0,
      json.dumps(stats))
title_party = {}
for ch in ("house", "senate"):
    for it in ET.fromstring(raw(f"{ch}_committee_assignments.xml")).iter("item"):
        m = re.search(r"\(([A-Z])\)", it.findtext("title") or "")
        title_party[R._member_id(it)] = m.group(1) if m else ""
joined = {x["member_id"]: x["party"] for x in rows}
check("party joined on memberId == party in the title, for every member (cross-check only)",
      all(title_party.get(k) == v for k, v in joined.items()) and len(joined) == 250)
seat_counts = collections.Counter()
for ch, chamber in (("house", "House"), ("senate", "Senate")):
    for c in ET.fromstring(raw(f"{ch}_committee_assignments.xml")).iter(R.NS + "Committee"):
        seat_counts[R.committee_key(chamber, c.text or "")] += 1
check("seats per committee == the feed's own count", collections.Counter(x["key"] for x in rows) == seat_counts)

export = A.read_export(raw(S.FILES[S.PA.urls["bill_history"].format(session="2025_0")]))
meetings = []
for ch in ("house", "senate"):
    meetings += A.parse_schedule(raw(f"{ch}_committee_schedule.xml"), ch)
records, _ = A.build_records(export, meetings, S.TODAY, S.NOW)
cov = R.coverage(records, rows)
check("every bill's current committee has a roster (5,184 bills name one)",
      cov["bills_committee_without_roster"] == 0 and sum(1 for r in records if r["last_committee"]) == 5184, json.dumps(cov))

# --- the name join, unit level ---
check("committee_key maps & -> AND and case, nothing else",
      [R.committee_key("House", "Aging & Older Adult Services"), R.committee_key("Senate", "Rules & Executive Nominations"),
       R.committee_key("House", "Consumer Protection, Technology & Utilities")]
      == ["House AGING AND OLDER ADULT SERVICES", "Senate RULES AND EXECUTIVE NOMINATIONS",
          "House CONSUMER PROTECTION, TECHNOLOGY AND UTILITIES"])
check("a renamed committee is a miss, never a fuzzy match",
      R.coverage([{"last_committee": "House EDUCATION AND WORKFORCE"}], rows)["bills_committee_without_roster"] == 1)

# --- spot rows (checkable by eye against house_committee_assignments.xml) ---
edu = [x for x in rows if x["key"] == "House EDUCATION"]
check("House Education: 26 seats, the two chairs listed first, as the feed labels them",
      len(edu) == 26 and [(x["member"], x["party"], x["role"]) for x in edu[:2]]
      == [("Bryan Cutler", "R", "Chair"), ("Peter Schweyer", "D", "Chair")])
abney = [x for x in rows if x["member_id"] == "1933"]
check("Aerion Abney (memberId 1933): six committees, district 19, D",
      len(abney) == 6 and {x["district"] for x in abney} == {"19"} and {x["party"] for x in abney} == {"D"})

# --- golden ---
digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
got = {"rows_sha256": digest, "stats": stats, "spot": edu[:3]}
if "--write" in sys.argv:
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump(got, f, indent=1, sort_keys=True)
    print(f"wrote {GOLDEN}")
else:
    with open(GOLDEN, encoding="utf-8") as f:
        want = json.load(f)
    check("golden: every roster row + stats unchanged", got == want,
          "re-capture with --write ONLY for an intended output change")
sys.exit(1 if FAILS else 0)
