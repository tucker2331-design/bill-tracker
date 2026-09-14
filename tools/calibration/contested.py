#!/usr/bin/env python3
"""Routine bills and contested bills are two different populations. Every earlier stat pooled them.

THE OBJECTION (owner, 2026-09-14): "make sure you are distinguishing between resolutions and bi partisan
day to day passage vs real bills, ie commending resolution vs actual change to the law bc they have diff
stats."

RESOLUTIONS were already out: `corpus.build()` keeps only `^[HS]B `, so HJ/SJ/HR/SR (commendations,
memorials, celebrations -- 1,271 of 3,637 identifiers in 2026 alone) never entered any finding.

THE REAL PROBLEM IS INSIDE HB/SB: charter amendments, technical corrections and uncontested code cleanups
pass near-universally and drag every average toward "everything passes".

THE MEASURE is structural, not textual: **what share of the room voted against the bill on the FIRST roll
call it ever received.** First, so it is fixed before the outcome. Share, not count, so an 8-seat
subcommittee and a 100-seat floor are comparable.

MOTION DIRECTION IS THE WHOLE TRICK. A motion to table carried 8-0 means the room unanimously opposed the
bill while recording ZERO "no" votes. Counting raw no-votes marks that bill "unopposed" -- exactly
backwards. Opposition = the NO count on a favourable motion, the YES count on a fatal one. "Failed to
recommend reporting" is a FAVOURABLE motion that lost, so it is not in the fatal list.

Run:  python3 tools/calibration/contested.py
"""
from __future__ import annotations
import sys, os, re, collections, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV, votes as V
from corpus import load

FATAL_DIR = ("laying on the table", "lay on the table", "passed by indefinitely", "striking from",
             "strike from", "continued to", "tabled in", "rejected", "defeated")


def is_fatal(t):
    t = (t or "").lower()
    if "failed to recommend" in t or "failed to report" in t:
        return False                       # the motion WAS to report; it lost
    return any(f in t for f in FATAL_DIR)


def _bk(s, b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return (s, f"{m.group(1)} {int(m.group(2))}") if m else None


def _date(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(s[:10], f).date()
        except Exception:
            pass
    return None


def first_opposition():
    """Opposition share on each bill's earliest dated roll call, from both vote corpora."""
    cb = {(r["session"], r["bill"]): r for r in load()["bills"]}
    rolls = collections.defaultdict(list)
    for e in CV.load()["events"].values():
        k = _bk(e["session"], e.get("bill"))
        y, n = e.get("yes") or 0, e.get("no") or 0
        if k and k in cb and y + n >= 3:
            rolls[k].append((_date(e.get("date")), (y if is_fatal(e.get("desc")) else n) / (y + n)))
    for e in V.load()["events"].values():
        k = _bk(e["session"], e.get("bill"))
        y, n = e.get("yes") or 0, e.get("no") or 0
        if k and k in cb and y + n >= 3:
            rolls[k].append((_date(e.get("date")), (y if is_fatal(e.get("motion")) else n) / (y + n)))
    out = {}
    for k, v in rolls.items():
        v = [x for x in v if x[0]]
        if v:
            out[k] = min(v)[1]
    return cb, out


def main():
    cb, first = first_opposition()
    B = [r for r in cb.values() if r["standing"] and (r["session"], r["bill"]) in first]
    allb = [r for r in cb.values() if r["standing"]]
    print("=" * 74)
    print("ROUTINE BILLS AND CONTESTED BILLS ARE TWO DIFFERENT POPULATIONS")
    print("=" * 74)
    print(f"\n  resolutions (HJ/SJ/HR/SR) were never in the corpus: prefixes present are "
          f"{sorted({r['bill'].split()[0] for r in allb})}")
    print(f"  bills with a dated roll call and standing resolved: {len(B):,} of {len(allb):,}"
          f" ({len(B) / len(allb):.0%})")

    def rate(g):
        return sum(1 for r in g if r["passed"]) / len(g) if g else 0.0
    bands = [("nobody against", lambda s: s == 0), ("1-10%", lambda s: 0 < s <= .10),
             ("10-25%", lambda s: .10 < s <= .25), ("25-40%", lambda s: .25 < s <= .40),
             ("over 40%", lambda s: s > .40)]
    print(f"\n  OPPOSITION ON THE FIRST ROLL CALL (fixed before the outcome)")
    print(f"  {'':<24}{'bills':>8}{'share':>8}{'majority':>16}{'minority':>16}{'gap':>7}")
    for lbl, f in bands:
        g = [r for r in B if f(first[(r["session"], r["bill"])])]
        a = [r for r in g if r["standing"] == "majority"]
        b = [r for r in g if r["standing"] == "minority"]
        cells = (f"{rate(a):>10.0%} ({len(a):>4,}){rate(b):>10.0%} ({len(b):>4,})"
                 f"{(rate(a) - rate(b)) * 100:>+7.0f}") if len(a) >= 50 and len(b) >= 50 else \
                f"{'thin':>16}{f'({len(a)},{len(b)})':>16}"
        print(f"  {lbl:<24}{len(g):>8,}{len(g) / len(B):>8.0%}{cells}")
    con = [r for r in B if first[(r["session"], r["bill"])] == 0]
    ctd = [r for r in B if first[(r["session"], r["bill"])] > 0]
    print(f"\n  CONSENSUS  {len(con):,} bills ({len(con) / len(B):.0%}) pass {rate(con):.0%}")
    print(f"  CONTESTED  {len(ctd):,} bills ({len(ctd) / len(B):.0%}) pass {rate(ctd):.0%}")
    a = [r for r in con if r["standing"] == "majority"]; b = [r for r in con if r["standing"] == "minority"]
    print(f"\n  THE HEADLINE NUMBER SPLITS IN TWO:")
    print(f"    on CONSENSUS bills the majority advantage is {(rate(a) - rate(b)) * 100:+.0f} points")
    a = [r for r in B if .10 < first[(r["session"], r["bill"])] <= .40 and r["standing"] == "majority"]
    b = [r for r in B if .10 < first[(r["session"], r["bill"])] <= .40 and r["standing"] == "minority"]
    print(f"    on CONTESTED-but-alive bills (10-40% against) it is "
          f"{(rate(a) - rate(b)) * 100:+.0f} points")
    print(f"\n  The pooled '+26 points' is an average over these. Quote it split, never pooled.")
    print(f"\n  CAUTION: the 'over 40%' band is not a harder version of the same thing -- a first roll")
    print(f"  call that lopsided usually IS the kill, so that band selects on the outcome.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
