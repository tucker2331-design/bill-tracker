#!/usr/bin/env python3
"""Bills die on the clock, so measure the clock: when a room acts, and what silence means at each week.

WHY. [[failures/assumptions_audit]] #136 is the deepest result in this project -- when identical bill text
is filed in both chambers and the minority copy dies, it dies ON THE CLOCK 69% of the time and on a VOTE
31%. Every measure we aimed at the roll call came back empty because the roll call is not where bills die.
This aims at the calendar instead.

THE FINDING. Silence is not one thing. For a majority patron in a long session, a bill still unheard is
worth about its base rate in week 2 and almost nothing by week 5:

    long session (even year)   base 63%   wk2 58%   wk3 53%   wk4 35%   wk5  3%
    short session (odd year)   base 65%   wk2 66%   wk3 46%   wk4  0%

**The action list shows the absence; it cannot tell you what the absence means.** That is the whole product
case -- a volunteer looking at an empty history in week 2 and in week 4 sees the same screen.

THE CLIFF MOVES WITH THE SESSION, so a fixed week number would be wrong by a week every odd year. Median
day of first-chamber passage: 27, 15, 28, 22, 29, 22, 27 for 2020-2026 -- long sessions cluster near day 28,
short ones near day 20. Standard #1: derive the deadline from the session, never hardcode a week.

THE ROOM-LEVEL VERSION, which is what a War Room can show before anything has happened:

    never acted on at all      H Rules 23%   ...   H the Judiciary 0%
    median day of first action H the Judiciary 7   ...   S Rules 22

SCOPE: 2020-2026 only. [[failures/openstates_committee_gap]] -- the corpus has NO committee-stage actions
before 2020 and fails silently, so the early years would contribute bills that look permanently unheard.
Bills referred more than 21 days in are excluded: they start a different race.

Run:  python3 tools/calibration/clock.py
"""
from __future__ import annotations
import sys, os, re, datetime, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load
from bill_states import FIRST_GOOD_YEAR

REF = re.compile(r"^referred to committee on (.+)$", re.I)
ACT = re.compile(r"^(reported from|subcommittee recommends|tabled in|passed by indefinitely in|"
                 r"failed to report|continued to|stricken from)", re.I)
LATE_FILING = 21        # referred after this many days -- a different race, excluded


def _start(year):
    """Session convenes the second Wednesday of January -- derived, not a table of dates."""
    jan = datetime.date(year, 1, 1)
    return jan + datetime.timedelta(days=(2 - jan.weekday()) % 7 + 7)


def rows():
    out = []
    for r in load()["bills"]:
        if r["year"] < FIRST_GOOD_YEAR or r["session"] == "2027" or not r["standing"]:
            continue
        s = _start(r["year"])
        ref = com = None
        for d, t, _c in r["actions"]:
            m = REF.match(t.strip())
            if m:
                com, ref = m.group(1).strip().rstrip("."), d
                break
        if not ref:
            continue
        try:
            rd = (datetime.date.fromisoformat(ref) - s).days
        except ValueError:
            continue
        if rd > LATE_FILING:
            continue
        a = next((d for d, t, _c in r["actions"] if ACT.match(t.strip())), None)
        try:
            ad = (datetime.date.fromisoformat(a) - s).days if a else None
        except ValueError:
            ad = None
        out.append({"year": r["year"], "long": r["year"] % 2 == 0, "standing": r["standing"],
                    "chamber": r["chamber"], "room": com, "acted_day": ad, "passed": r["passed"]})
    return out


def survival(rs):
    """"It is week W and my bill has not been heard." Of those bills, how many were ever reported?

    NOT circular: the condition is knowable at week W and the outcome comes later."""
    out = {}
    for lng in (True, False):
        for st in ("majority", "minority"):
            pool0 = [r for r in rs if r["long"] is lng and r["standing"] == st]
            if not pool0:
                continue
            row = {"base": (sum(r["passed"] for r in pool0) / len(pool0), len(pool0))}
            for w in range(2, 7):
                p = [r for r in pool0 if r["acted_day"] is None or r["acted_day"] >= w * 7]
                if len(p) >= 40:
                    row[w] = (sum(r["passed"] for r in p) / len(p), len(p))
            out[("long" if lng else "short", st)] = row
    return out


def by_room(rs, min_n=60):
    a = collections.defaultdict(list)
    for r in rs:
        a[(r["chamber"], r["room"])].append(r["acted_day"])
    out = []
    for (ch, nm), v in a.items():
        got = [x for x in v if x is not None]
        if len(v) < min_n or len(got) < 40:
            continue
        out.append({"chamber": ch, "room": nm, "n": len(v), "median_day": statistics.median(got),
                    "never": (len(v) - len(got)) / len(v)})
    return sorted(out, key=lambda r: -r["never"])


def main():
    rs = rows()
    print(f"{len(rs)} bills, {FIRST_GOOD_YEAR}-2026, referred within {LATE_FILING} days of convening\n")
    print('SILENCE, PRICED BY WEEK -- share of still-unheard bills that were EVER reported')
    sv = survival(rs)
    for k, row in sv.items():
        b, bn = row["base"]
        cells = " ".join(f"wk{w} {row[w][0]:4.0%}" for w in range(2, 7) if w in row)
        print(f"  {k[0]:5s} session, {k[1]:8s}  base {b:4.0%} (n={bn:5d}) | {cells}")
    print("\nPER ROOM -- how often it never acts at all, and how long it sits")
    print(f"  {'room':44s} {'bills':>6s} {'never acted':>12s} {'median day':>11s}")
    for r in by_room(rs):
        print(f"  {r['chamber']} {r['room'][:41]:42s} {r['n']:6d} {r['never']:11.0%} {r['median_day']:11.0f}")


if __name__ == "__main__":
    main()
