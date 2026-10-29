#!/usr/bin/env python3
"""Does what is SAID in committee tell us anything? (transcripts.py segments, Internet Archive captions)

  1. SAME MEETING  -- debate length, speaker turns, public speakers and stated opposition vs how the room voted at that
                      meeting's recorded vote (unanimous / split / party-line / mixed). Descriptive: the vote happens at
                      the end of the debate, so this is not a forecast.
  2. NEXT STAGES   -- for bills REPORTED by that meeting: did the debate foreshadow what happened later (passing the full
                      chamber; becoming law)? This IS forward-looking: the debate is over before the later votes.
  3. WHO SPOKE     -- legislators named in a bill's debate ("Senator X", "Delegate X") vs their own vote at that meeting:
                      do the ones who engage break from their party more often?
Coverage is whatever the Internet Archive holds (mostly Senate 2023-2025, House 2026) -- reported with every number.
"""
from __future__ import annotations
import sys, os, re, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV
from corpus import load

SEG = os.path.join(HERE, "..", "historical_cache", "va_transcripts", "segments.json")
LAW = re.compile(r"approved by governor|^acts of assembly chapter|^governor.?s action.*approved", re.I)   # corpus "passed" = had a passage vote, NOT law
PASS_CH = re.compile(r"^(read third time and )?passed (house|senate)\b", re.I)


def shape(ballots, patron_party):
    yes = np.mean([s for _w, _p, s in ballots])
    by = {p: np.mean([s for _w, pp, s in ballots if pp == p]) for p in FV.PARTIES if any(pp == p for _w, pp, _s in ballots)}
    if yes == 1: return "unanimous yes"
    if yes == 0: return "unanimous no"
    if all(v in (0, 1) for v in by.values()): return "party line"
    return "mixed split"


def main():
    segs = json.load(open(SEG))
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    rc = FV.assemble()["rc"]
    rows, unmatched = [], collections.Counter()
    for ident, m in segs.items():
        for bill, f in m["bills"].items():
            k = (m["session"], bill)
            b = corpus.get(k)
            if not b:
                unmatched["bill not in corpus (carry-over numbering / misheard number)"] += 1; continue
            same_day = [x for x in rc.get(k, []) if x[0] == m["date"]]
            origin = (bill.startswith("HB") and m["chamber"] == "H") or (bill.startswith("SB") and m["chamber"] == "S")
            rows.append({"k": k, "meet": ident, "origin": origin, "f": f, "bill": b, "vote": same_day[0] if same_day else None,
                         "law": any(LAW.search(t.strip()) for _d, t, _c in b["actions"]), "passed_ch": any(PASS_CH.match(t.strip()) for _d, t, _c in b["actions"])})
    print(f"bill segments matched to bills: {len(rows)}; with a recorded vote that same day: "
          f"{sum(r['vote'] is not None for r in rows)}; unmatched {dict(unmatched)}")
    by = collections.Counter((r["k"][0], r["meet"].split("-")[1]) for r in rows)
    print("by session/chamber:", dict(sorted(by.items())))

    # 1. same meeting
    voted = [r for r in rows if r["vote"] is not None]
    if voted:
        print("\n1. DEBATE vs THE ROOM'S VOTE AT THAT MEETING (median minutes / turns / share with public speakers / with stated opposition)")
        g = collections.defaultdict(list)
        for r in voted:
            g[shape(r["vote"][4], r["bill"]["chief_party"])].append(r["f"])
        for sh in ("unanimous yes", "party line", "mixed split", "unanimous no"):
            L = g.get(sh, [])
            if L:
                print(f"   {sh:14s} n={len(L):4d}  {np.median([x['seconds'] for x in L])/60:5.1f} min  "
                      f"{np.median([x['turns'] for x in L]):4.0f} turns  public {np.mean([x['public'] > 0 for x in L]):5.0%}  "
                      f"opposition stated {np.mean([x['oppose'] > 0 for x in L]):5.0%}")
    # 2. next stages, for bills the meeting reported (bill went on: a later action exists)
    print("\n2. AFTER THE COMMITTEE: bills heard in their OWN chamber with a recorded vote that day (forward-looking;\n"
          "   a bill heard in the other chamber has already passed its own, so it is excluded)")
    # only bills the committee PASSED that day (most ballots yes): a bill killed at the meeting obviously goes no further,
    # and long contested debate goes with kills -- conditioning on "advanced" is what makes this forward-looking
    voted_origin = [r for r in voted if r["origin"] and np.mean([s_ for _w, _p, s_ in r["vote"][4]]) > .5]
    print(f"   bills passed by the committee that day: {len(voted_origin)}")
    for lab, test in (("public opposition stated", lambda f: f["oppose"] > 0), ("long debate (> 10 min)", lambda f: f["seconds"] > 600),
                      ("members of the public spoke", lambda f: f["public"] > 0)):
        a = [r for r in voted_origin if test(r["f"])]; b = [r for r in voted_origin if not test(r["f"])]
        if a and b:
            print(f"   {lab:28s} passed chamber {np.mean([r['passed_ch'] for r in a]):5.0%} (n={len(a)}) vs "
                  f"{np.mean([r['passed_ch'] for r in b]):5.0%} (n={len(b)});  became law "
                  f"{np.mean([r['law'] for r in a]):5.0%} vs {np.mean([r['law'] for r in b]):5.0%}")
    # 3. who spoke
    print("\n3. LEGISLATORS NAMED IN THE DEBATE vs THEIR OWN VOTE THAT DAY (broke from their party's majority)")
    named = [0, 0]; unnamed = [0, 0]
    for r in voted:
        ballots = r["vote"][4]
        maj = {p: np.mean([s for _w, pp, s in ballots if pp == p]) >= .5 for p in FV.PARTIES if any(pp == p for _w, pp, _s in ballots)}
        names = {n.upper() for n in r["f"]["members"]}
        for w, pp, s in ballots:
            if pp not in maj:
                continue
            surname = w.split()[-1].upper().replace("-", "")
            hit = any(surname == n.replace("-", "") for n in names)
            t = named if hit else unnamed
            t[0] += int(s != maj[pp]); t[1] += 1
    if named[1] and unnamed[1]:
        print(f"   named in the debate: broke from party {named[0]}/{named[1]} ({named[0]/named[1]:.1%})   "
              f"not named: {unnamed[0]}/{unnamed[1]} ({unnamed[0]/unnamed[1]:.1%})")


if __name__ == "__main__":
    main()
