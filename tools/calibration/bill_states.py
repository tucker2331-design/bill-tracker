#!/usr/bin/env python3
"""The tag vocabulary: every state a bill can be recorded in, and whether the record ever leaves it.

WHY THIS EXISTS. Owner, 2026-09-18, on a mockup carrying two hand-written footnotes: *"how possibly could
we compute this much text instantly for every scenario it needs to be simplified... is there any other tags
that should go in the spot of the continued notification"*. Exactly right. A tag written for one bill is a
caption; a tag is only a product if ONE template fills for all 2,326 bills. So: enumerate the states,
measure each, and let the vocabulary be the finite list rather than my judgement of the interesting case.

    a bill that was EVER...        bills   later got a floor passage vote
    Reported to the floor           8,859   7,968   89.9%   <- grey
    Re-referred                     2,363   1,467   62.1%   <- grey
    Failed to report                  245       6    2.4%   <- amber
    Tabled                          1,303      13    1.0%   <- amber
    Continued to next session       1,367      12    0.9%   <- amber
    Stricken from the docket          287       0    0.0%   <- amber
    Incorporated into another         672       0    0.0%   <- grey + pointer: the TEXT survives elsewhere
    Left in committee               6,739       0    0.0%   <- grey, terminal: LIS's own end-of-session mark

THE TAG RULE, stated once so no page has to argue it: amber means the record shows bills rarely leave this
state. Grey means they do. Every bill carries exactly one; amber fires on 588 of the 2,366 bills of 2026
(24.9%). This is a statement about the record, never a prediction (Standard #3).

THE CIRCULARITY THAT ATE THE FIRST VERSION. The natural framing is "bills whose LAST committee action is a
continuance" -- and that returns 0 of 1,352, which is TAUTOLOGICAL: a continued bill that was later reported
has "Reported" as its last action, so it leaves the bucket by succeeding. Measured on an EVER-in-this-state
basis instead, the same question returns 12 of 1,367. Both numbers are "true"; only the second is an answer.

THE SPECIAL-SESSION GUARD. "Continued to 2021 Sp. Sess. 1 in Education and Health" matches any reasonable
carryover pattern and is not a carryover -- it moves the bill to a session convening DAYS later. There are
340 of them and they pass, which drags the continuance recovery rate from 0.9% to 13.3%. Excluded by name.

DEDUPLICATION. A carried-over bill has a record in BOTH sessions (2024 and 2025), so counting session-rows
double-counts 1,548 bills. Keyed on (identifier, title), longest history wins: 22,659 rows -> 21,111 bills.

Run:  python3 tools/calibration/bill_states.py
"""
from __future__ import annotations
import sys, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load

SPSESS = re.compile(r"sp\.?\s*sess", re.I)

# Ordered so that a bill carrying several over its life shows the one from its LAST matching action.
# Every pattern is an LIS action description -- structural, never a reading of the bill's subject.
STATES = [
    ("Reported to the floor",     "grey",  r"^reported from\b"),
    ("Re-referred",               "grey",  r"^rereferred to\b"),
    ("Left in committee",         "grey",  r"^left in\b"),
    ("Incorporated",              "grey",  r"^incorporated by\b"),
    ("Failed to report",          "amber", r"^failed to report"),
    ("Tabled",                    "amber", r"^tabled in\b|laying on the table.*\bin\b|"
                                           r"^passed by indefinitely in\b"),
    ("Continued",                 "amber", r"^continued to (?:\d{4}|next session)\b.*\bin\b"),
    ("Stricken",                  "amber", r"stricken from (the )?docket"),
]
PATS = [(lbl, col, re.compile(p, re.I)) for lbl, col, p in STATES]


def _hit(label, pat, text):
    """One match test, with the one exclusion that is not expressible in the pattern."""
    if not pat.search(text):
        return False
    return not (label == "Continued" and SPSESS.search(text))


def distinct_bills(c):
    """One row per bill. A carryover appears in two sessions; the longer history is the real one."""
    best = {}
    for r in c["bills"]:
        k = (r["bill"], r["title"])
        if k not in best or len(r["actions"]) > len(best[k]["actions"]):
            best[k] = r
    return list(best.values())


def recovery(bills):
    """EVER in this state -> did a floor passage vote come AFTER the first time it did?

    Not 'last action is this state', which answers itself. See the module docstring."""
    out = {}
    for lbl, col, pat in PATS:
        n = s = 0
        for r in bills:
            i = [j for j, x in enumerate(r["actions"]) if _hit(lbl, pat, x[1].strip())]
            if not i:
                continue
            n += 1
            if any("'passage'" in (x[2] or "") for x in r["actions"][i[0] + 1:]):
                s += 1
        out[lbl] = (col, n, s)
    return out


def coverage(c, session="2026"):
    """What every bill of one session would carry. Must total the session exactly -- a vocabulary with a
    hole in it is a vocabulary that renders a blank tag on a real bill."""
    cnt = collections.Counter()
    rows = [r for r in c["bills"] if r["session"] == session]
    for r in rows:
        hits = [lbl for x in r["actions"] for lbl, _c, p in PATS if _hit(lbl, p, x[1].strip())]
        cnt[hits[-1] if hits else "(no committee action yet)"] += 1
    assert sum(cnt.values()) == len(rows), f"vocabulary does not cover {session}"
    return cnt, len(rows)


def main():
    c = load()
    bills = distinct_bills(c)
    rec = recovery(bills)
    cnt, n26 = coverage(c)
    print(f"{len(c['bills'])} session-records -> {len(bills)} distinct bills\n")
    print(f"{'a bill that was EVER...':26s} {'colour':>7s} {'bills':>7s} {'later passed':>13s} "
          f"{'2026':>7s} {'share':>7s}")
    for lbl, col, _p in PATS:
        _c, n, s = rec[lbl]
        print(f"{lbl:26s} {col:>7s} {n:7d} {s:6d} {s/max(1,n):6.1%} {cnt[lbl]:7d} {cnt[lbl]/n26:7.1%}")
    nc = cnt["(no committee action yet)"]
    print(f"{'(no committee action yet)':26s} {'grey':>7s} {'':7s} {'':13s} {nc:7d} {nc/n26:7.1%}")
    amber = sum(cnt[l] for l, col, _p in PATS if col == "amber")
    print(f"\namber fires on {amber} of {n26} bills = {amber/n26:.1%}")


if __name__ == "__main__":
    main()
