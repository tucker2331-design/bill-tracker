#!/usr/bin/env python3
"""Committees remember ideas. The verdict a room gave an idea last time is the verdict it gives again --
even when a different legislator carries it, and more strongly than the same idea sent to another room.

WHY THIS IS NOT SURFACE. Owner's test (2026-09-22): a finding has to tell you something the bill's own
action list does not already say. A bill's history starts at its own filing. This is the history BEFORE
that -- what this committee did with this idea the last time it saw it -- which a veteran lobbyist carries
in their head and a volunteer cannot see anywhere.

    SAME idea, SAME first committee, patron's party held fixed
    match rule        died there before -> dies again    cleared before -> dies    odds ratio
    exact title            79.7%  (n=227)                   26.4%  (n=148)         10.8 [6.7-17.6]
    subject clause         58.3%  (n=1,033)                 35.3%  (n=1,342)        2.6 [2.2-3.0]

THE CONFOUND THAT HAD TO BE BEATEN: bad ideas are bad everywhere. If that were the whole story, the room
would not matter. Exact title, same standing:

    SAME first committee        OR 15.2  [9.3-25.0]   n=440
    DIFFERENT first committee   OR  5.5  [3.0-10.3]   n=204     difference z=+2.49, p=0.013

Both are true: idea quality persists (5.5x), and the ROOM roughly triples it. Stable across eras
(OR 12.9 in 2020-22, 16.1 in 2023-26). And a new carrier of the same party still meets it: OR 3.6, p=0.003.

THE ASYMMETRY (the part a lobbyist would not guess). Once a room has killed an idea, moving it to another
room barely helps -- 85% vs 81% die again. What the room adds is mostly on the YES side: an idea it cleared
before clears again 73%, against 57% if you send it somewhere else. What DOES break a room's no is a change
of carrier standing ([[failures/assumptions_audit]] #129: minority -> majority carrier, 6% -> 41%).

WHY THE DOSE-RESPONSE MATTERS. The tighter the idea match, the stronger the memory (exact 10.8 > subject
2.6). Noise does not do that. It is the best single piece of evidence that the mechanism is real.

MATCHING AND STANDARD #3. Exact title EQUALITY compares two values of an official LIS field -- identity,
like comparing bill numbers -- and is the only form proposed for the lobbyist path. The subject-clause rule
splits the title string, which is text parsing: INTERNAL ONLY. Coverage on 2026: exact 280 bills (11.8%),
199 of them in the same first committee (8.4%); subject clause 1,083 (45.8%).

SCOPE: 2020-2026 only ([[failures/openstates_committee_gap]]). "Cleared" = reached a first-chamber floor
passage, i.e. got out of the first committee. Biennium carryover twins (same number, same title,
consecutive years) are one bill, not a refile.

Run:  python3 tools/calibration/room_memory.py
"""
from __future__ import annotations
import sys, os, re, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load, norm
from bill_states import FIRST_GOOD_YEAR

REF = re.compile(r"^referred to committee (?:on|for) (.+?)\.?$", re.I)
P1 = {"H": re.compile(r"passed house|read third time and passed house", re.I),
      "S": re.compile(r"passed senate", re.I)}


def first_room(r):
    for _d, t, _c in r["actions"]:
        m = REF.match(t.strip())
        if m:
            return (r["chamber"], m.group(1))
    return None


def cleared(r):
    return any(P1[r["chamber"]].search(t) for _d, t, _c in r["actions"])


def subj(t):
    return norm((t or "").split(";")[0])


def odds(pairs):
    """pairs of (prev_cleared, next_cleared). Haldane-corrected OR with a 95% CI."""
    a = sum(1 for p, n in pairs if not p and not n)
    b = sum(1 for p, n in pairs if not p and n)
    c = sum(1 for p, n in pairs if p and not n)
    d = sum(1 for p, n in pairs if p and n)
    orr = ((a + .5) * (d + .5)) / ((b + .5) * (c + .5))
    se = math.sqrt(1 / (a + .5) + 1 / (b + .5) + 1 / (c + .5) + 1 / (d + .5))
    return {"die_after_die": a / max(1, a + b), "die_after_clear": c / max(1, c + d), "or": orr, "se": se,
            "lo": math.exp(math.log(orr) - 1.96 * se), "hi": math.exp(math.log(orr) + 1.96 * se),
            "n": len(pairs), "n_died": a + b, "n_cleared": c + d}


def attempt_pairs(bills, key):
    """Consecutive attempts of the same idea under `key`, carryover twins collapsed."""
    idx = collections.defaultdict(list)
    for r in bills:
        idx[key(r)].append(r)
    out = []
    for rs in idx.values():
        rs = sorted(rs, key=lambda r: (r["year"], r["session"]))
        uniq = []
        for r in rs:
            if uniq and uniq[-1]["bill"] == r["bill"] and r["year"] - uniq[-1]["year"] <= 1:
                continue
            uniq.append(r)
        by_y = {}
        for r in uniq:
            by_y.setdefault(r["year"], r)
        ys = sorted(by_y)
        out += [(by_y[a], by_y[b]) for a, b in zip(ys, ys[1:])]
    return out


def main():
    c = load()
    bills = [r for r in c["bills"] if r["year"] >= FIRST_GOOD_YEAR and r["session"] != "2027"
             and r["title"] and first_room(r)]
    ex = attempt_pairs(bills, lambda r: norm(r["title"]))
    same_st = [(A, B) for A, B in ex if A["standing"] == B["standing"]]
    print(f"{len(ex)} consecutive attempts of an exact-title idea, {FIRST_GOOD_YEAR}-2026\n")
    for lbl, f in (("SAME first committee", lambda A, B: first_room(A) == first_room(B)),
                   ("DIFFERENT first committee", lambda A, B: first_room(A) != first_room(B))):
        o = odds([(cleared(A), cleared(B)) for A, B in same_st if f(A, B)])
        print(f"  {lbl:26s} n={o['n']:4d}  died before -> dies {o['die_after_die']:5.1%}  "
              f"cleared before -> dies {o['die_after_clear']:5.1%}  OR {o['or']:5.1f} [{o['lo']:.1f}-{o['hi']:.1f}]")
    s = odds([(cleared(A), cleared(B)) for A, B in same_st if first_room(A) == first_room(B)])
    d = odds([(cleared(A), cleared(B)) for A, B in same_st if first_room(A) != first_room(B)])
    z = (math.log(s["or"]) - math.log(d["or"])) / math.sqrt(s["se"] ** 2 + d["se"] ** 2)
    print(f"  same room vs different room: z = {z:+.2f}, p = {math.erfc(abs(z)/math.sqrt(2)):.2g}\n")
    diff_pat = [(A, B) for A, B in same_st if first_room(A) == first_room(B)
                and (A["chief_key"] or A["chief"]) != (B["chief_key"] or B["chief"])]
    o = odds([(cleared(A), cleared(B)) for A, B in diff_pat])
    print(f"  NEW carrier, same party, same room: n={o['n']}  {o['die_after_die']:.1%} vs "
          f"{o['die_after_clear']:.1%}  OR {o['or']:.1f} [{o['lo']:.1f}-{o['hi']:.1f}]")


if __name__ == "__main__":
    main()
