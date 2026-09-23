#!/usr/bin/env python3
"""The second chamber: what carries a bill across the building, measured on every member's floor vote.

RESULT (docs/testing/second_chamber.md): one asymmetry. When the patron's party RUNS chamber 2, cross-party
support in chamber 1 is worth nothing (86/89/86/87% across the range, coef +0.01 p=0.97). When it does NOT,
the other party's chamber-1 support swings chamber 2 from 24% to 80% (p=3e-13) -- but the headline vote total
already carries almost all of it (AUC 0.756 vs 0.775) and nearly the whole effect is 2023's split control.

THE DATA TRAP: the member-level floor file misses most SECOND-chamber passages (997 false negatives; a true
83.6% read as 49%). Outcome comes from the action record; the vote file is used only for the chamber-1 split.
Scope: 2023-2026, the four sessions with member-level floor roll calls (committee_votes).
"""
from __future__ import annotations
import sys, os, re, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV
from corpus import load, _party_lookup, CONTROL

# BOTH wording regimes: legacy 2023/24 House "H VOTE: Passage" / "H VOTE: Block Vote Passage";
# 2025+ House and all-years Senate "Read third time and passed House" / "Passed Senate (with substitute)".
# Conference "Adoption", "REJECTED", "Constitutional reading dispensed" and concurrences are NOT passage.
PASS = re.compile(r"VOTE:\s*(?:Block Vote\s+)?Passage|\bpassed (?:the )?(?:House|Senate)\b", re.I)
NOT = re.compile(r"reconsider|defeated|rejected|failed", re.I)
PARTIES = ("Democratic", "Republican")

# THE OUTCOME COMES FROM THE ACTION RECORD, NOT THE FLOOR-VOTE FILE. The member-level floor file is missing
# most second-chamber passages: validated against the action text it produced 997 FALSE NEGATIVES out of
# 2,410 real passages (HB 1595 of 2023 was enacted as Chapter 772 and the vote file said it died), which
# turned a true ~84% second-chamber pass rate into 49%. The vote file is still the right source for the
# chamber-1 PARTY SPLIT -- that is what it is for -- just not for whether chamber 2 acted.
# Deliberately NOT matched: "senate.*passed" -- it catches "Passed by indefinitely", which is a KILL.
CH2_PASSED = {
    "H": re.compile(r"\bpassed senate\b|signed by (?:the )?president|signed by (?:the )?speaker|"
                    r"approved by governor|vetoed by governor|\benacted\b|chapter \d", re.I),
    "S": re.compile(r"\bpassed house\b|signed by (?:the )?speaker|signed by (?:the )?president|"
                    r"approved by governor|vetoed by governor|\benacted\b|chapter \d", re.I),
}


def _yr(date):
    m = re.search(r"/(\d{2,4})$", date or "")
    if not m:
        return None
    y = m.group(1)
    return int("20" + y) if len(y) == 2 else int(y)


def _bill_key(b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return f"{m.group(1)} {int(m.group(2))}" if m else None


def build():
    """One row per bill that passed its chamber of origin on a recorded floor vote."""
    party, _person = _party_lookup()
    d = CV.load()
    corpus = {(r["session"], r["bill"]): r for r in load()["bills"]}
    ballots = collections.defaultdict(list)
    for v in d["votes"]:
        if v["venue"] == "floor":
            ballots[(v["session"], v["vote_id"])].append((v["name"], v["opt"]))
    ev = collections.defaultdict(list)          # (session, bill) -> [(chamber, date, vote_id, desc)]
    for (_yr_, vid), e in d["events"].items():
        if e["venue"] != "floor" or not PASS.search(e["desc"]) or NOT.search(e["desc"]):
            continue
        if _yr(e.get("date")) != int(e["session"]):        # biennium carryover rows -- see the log
            continue
        k = _bill_key(e.get("bill"))
        if k:
            ev[(e["session"], k)].append((e["chamber"], e.get("date") or "", vid, e["desc"]))
    rows = []
    for (s, b), es in ev.items():
        r = corpus.get((s, b))
        if not r or r["chief_party"] not in PARTIES:
            continue
        ch1 = b[0]
        mine = sorted([x for x in es if x[0] == ch1], key=lambda x: x[1])
        if not mine:
            continue
        vid = mine[-1][2]
        tally = {p: [0, 0] for p in PARTIES}           # party -> [yes, voting]
        for nm, opt in ballots.get((s, vid), []):
            p = party(nm)
            if p in tally:
                tally[p][1] += 1
                tally[p][0] += opt == "yes"
        pat = r["chief_party"]
        opp = PARTIES[1] if pat == PARTIES[0] else PARTIES[0]
        if tally[pat][1] < 5 or tally[opp][1] < 5:
            continue                                   # too few resolved ballots to read the split
        yr = int(s)
        ch2 = "S" if ch1 == "H" else "H"
        ch2_major = CONTROL[yr][0 if ch2 == "H" else 1]
        tot_yes = tally[pat][0] + tally[opp][0]
        tot = tally[pat][1] + tally[opp][1]
        rows.append({
            "session": s, "bill": b, "year": yr, "ch1": ch1, "patron_party": pat,
            "aligned_ch2": pat == ch2_major,          # patron's party runs the chamber it is going to
            "split_control": CONTROL[yr][0] != CONTROL[yr][1],
            "opp_yes": tally[opp][0] / tally[opp][1],  # share of the OTHER party that voted yes
            "own_yes": tally[pat][0] / tally[pat][1],
            "no_share": 1 - tot_yes / tot,
            "passed_ch2": any(CH2_PASSED[ch1].search(t) for _d, t, _c in r["actions"]),
            "cops_opp": sum(1 for cp in r["cop_parties"] if cp == opp),
        })
    return rows


if __name__ == "__main__":
    rows = build()
    print(f"{len(rows)} bills that passed their chamber of origin on a recorded floor vote, 2023-2026")
    c = collections.Counter((r["session"], r["ch1"]) for r in rows)
    print("  by session x origin chamber:", dict(sorted(c.items())))
    print(f"  passed the second chamber: {sum(r['passed_ch2'] for r in rows)} "
          f"({sum(r['passed_ch2'] for r in rows)/len(rows):.1%})")
