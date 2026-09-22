#!/usr/bin/env python3
"""The tag vocabulary: every state a bill can be recorded in, and whether the record ever leaves it.

WHY THIS EXISTS. Owner, 2026-09-18, on a mockup carrying two hand-written footnotes: *"how possibly could
we compute this much text instantly for every scenario it needs to be simplified... is there any other tags
that should go in the spot of the continued notification"*. Exactly right. A tag written for one bill is a
caption; a tag is only a product if ONE template fills for all 2,326 bills. So: enumerate the states,
measure each, and let the vocabulary be the finite list rather than my judgement of the interesting case.

    a bill that was EVER...        bills   later got a floor passage vote
    Reported to the floor           8,859   7,968   89.9%   <- grey
    Re-referred                     1,669   1,305   78.2%   <- grey
    Failed to report                  245       6    2.4%   <- plain
    Tabled                          1,240      12    1.0%   <- plain
    Continued to next session       1,348      12    0.9%   <- plain
    Stricken from the docket          256       0    0.0%   <- plain
    Incorporated into another         672       0    0.0%   <- grey + pointer: the TEXT survives elsewhere
    Left in committee               4,542       0    0.0%   <- grey, terminal: LIS's own end-of-session mark

THE TAG RULE, stated once so no page has to argue it: the tag always carries the count behind it. Every
bill carries exactly one and the vocabulary covers a session exactly. NO COLOUR IS SPENT -- v1 turned four
of these amber and both P20b ("arithmetic takes no marker") and the 2026-07-08 outcome-tag doctrine
("carried over = amber, still alive, just deferred") already forbade it. The number does the work.
This is a statement about the record, never a prediction (Standard #3).

THE CIRCULARITY THAT ATE THE FIRST VERSION. The natural framing is "bills whose LAST committee action is a
continuance" -- and that returns 0 of 1,352, which is TAUTOLOGICAL: a continued bill that was later reported
has "Reported" as its last action, so it leaves the bucket by succeeding. Measured on an EVER-in-this-state
basis instead, the same question returns 12 of 1,367. Both numbers are "true"; only the second is an answer.

THE SPECIAL-SESSION GUARD. "Continued to 2021 Sp. Sess. 1 in Education and Health" matches any reasonable
carryover pattern and is not a carryover -- it moves the bill to a session convening DAYS later. There are
340 of them and they pass, which drags the continuance recovery rate from 0.9% to 13.3%. Excluded by name.

DEDUPLICATION. A carried-over bill has a record in BOTH sessions (2024 and 2025), so counting session-rows
double-counts 1,548 bills. Keyed on (identifier, title), longest history wins; with the pre-2020 gap
excluded that leaves 14,533 distinct bills.

Run:  python3 tools/calibration/bill_states.py
"""
from __future__ import annotations
import sys, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load

SPSESS = re.compile(r"sp\.?\s*sess", re.I)

# THE COMMITTEE-STAGE RECORD DOES NOT EXIST BEFORE 2020 IN THIS CORPUS, and it fails SILENTLY: the bills
# are all there, the passage flag is intact, only the committee actions are missing. Measured coverage of
# "Reported from" -- 2017: 0%, 2018: 0%, 2019: 0%, then 56-65% every year after. "Failed to report" and
# "Passed by indefinitely": 0% in all three. Only "Left in committee" survives at a normal rate (28-40%),
# so the early years contribute KILLS WITHOUT REPORTS -- a one-sided sample that looks like data.
# It cost 16 points: Re-referred recovery published as 62.1% is 78.2% on the years that have the record.
# `assert_years` FAILS LOUD rather than letting a future caller widen the window back into the gap.
FIRST_GOOD_YEAR = 2020


def assert_years(bills):
    """Refuse to compute on years whose committee record is missing. See FIRST_GOOD_YEAR."""
    bad = sorted({r["year"] for r in bills if r["year"] < FIRST_GOOD_YEAR})
    if bad:
        raise SystemExit(f"committee-stage actions are absent for {bad}; "
                         f"filter to year >= {FIRST_GOOD_YEAR} before calling this")

# Ordered so that a bill carrying several over its life shows the one from its LAST matching action.
# Every pattern is an LIS action description -- structural, never a reading of the bill's subject.
STATES = [
    ("Reported to the floor",     "moves",  r"^reported from\b"),
    ("Re-referred",               "moves",  r"^rereferred to\b"),
    ("Left in committee",         "ends",  r"^left in\b"),
    ("Incorporated",              "ends",  r"^incorporated by\b"),
    ("Failed to report",          "rarely", r"^failed to report"),
    ("Tabled",                    "rarely", r"^tabled in\b|laying on the table.*\bin\b|"
                                           r"^passed by indefinitely in\b"),
    ("Continued",                 "rarely", r"^continued to (?:\d{4}|next session)\b.*\bin\b"),
    ("Stricken",                  "rarely", r"stricken from (the )?docket"),
]
PATS = [(lbl, col, re.compile(p, re.I)) for lbl, col, p in STATES]


def _hit(label, pat, text):
    """One match test, with the one exclusion that is not expressible in the pattern."""
    if not pat.search(text):
        return False
    return not (label == "Continued" and SPSESS.search(text))


def distinct_bills(c):
    """One row per bill, and only the years whose committee record exists (see FIRST_GOOD_YEAR).

    A carryover appears in two sessions; the longer history is the real one."""
    best = {}
    for r in c["bills"]:
        if r["year"] < FIRST_GOOD_YEAR:
            continue
        k = (r["bill"], r["title"])
        if k not in best or len(r["actions"]) > len(best[k]["actions"]):
            best[k] = r
    return list(best.values())


def recovery(bills):
    """See assert_years -- this refuses to run on the years with no committee record."""
    """EVER in this state -> did a floor passage vote come AFTER the first time it did?

    Not 'last action is this state', which answers itself. See the module docstring."""
    assert_years(bills)
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
    print(f"{'a bill that was EVER...':26s} {'leaves?':>8s} {'bills':>7s} {'later passed':>13s} "
          f"{'2026':>7s} {'share':>7s}")
    for lbl, col, _p in PATS:
        _c, n, s = rec[lbl]
        print(f"{lbl:26s} {col:>8s} {n:7d} {s:6d} {s/max(1,n):6.1%} {cnt[lbl]:7d} {cnt[lbl]/n26:7.1%}")
    nc = cnt["(no committee action yet)"]
    print(f"{'(no committee action yet)':26s} {'grey':>7s} {'':7s} {'':13s} {nc:7d} {nc/n26:7.1%}")
    rare = sum(cnt[l] for l, col, _p in PATS if col == "rarely")
    print(f"\nstates the record rarely leaves: {rare} of {n26} bills = {rare/n26:.1%}")


if __name__ == "__main__":
    main()
