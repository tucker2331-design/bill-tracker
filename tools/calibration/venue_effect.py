#!/usr/bin/env python3
"""What a ROOM does to a bill, with the bill's content held constant by its identical twin.

THE QUESTION NOBODY IN THE LITERATURE CAN ASK
----------------------------------------------
Every published model of committee outcomes predicts survival from OUTSIDE the room. Yano, Smith &
Wilkerson (NAACL 2012), the standard reference, describes the stage in as many words: consideration
*"behind closed doors, by a Congressional committee"* — so they model it with the sponsor's identity, the
referral, and the bill text. Eidelman, Kornilova & Argyle (COLING 2018) predict floor action across 1.3M
bills in 50 states and find committee information their MOST predictive feature — but their committee
feature is the ASSIGNMENT, not the votes, because state committee roll calls are not in the datasets
everyone uses (Open States carries 0 committee roll calls for Virginia, of 69,422).

LIS publishes them. [[testing/kill_points]] reads 19,192 of them. This module asks what they make possible.

THE DESIGN: THE COMPANION IS THE CONTROL
-----------------------------------------
Virginia runs companion bills — the same text filed in both chambers at once. When one dies and the twin
lives, **content, session, political climate and calendar are all held constant, and what differs is the
room.** That is an experiment the legislature runs on itself ~1,400 times per corpus, for free.

Measured: of 1,443 companion pairs with recorded votes on both sides, **272 (19%) diverged** — identical
text, opposite outcome. **The chamber split on those is 50/50**, so "the House kills more" explains
exactly nothing. What varies is WHICH ROOM.

  base kill rate, content controlled:   committee 7%   subcommittee 12%
  House Privileges and Elections sub:   31%  (+19pp over its kind)

TWO WAYS THIS COULD BE FAKE, AND WHAT WAS DONE ABOUT EACH
-----------------------------------------------------------
1. **Multiple comparisons.** 49 venues were scored, so the most extreme one is extreme partly by luck.
   A permutation test shuffles the kill outcome WITHIN venue kind and asks how often any venue reaches
   the observed excess: **p = 0.037** (75 of 2,000 shuffles). Reported, not assumed.
2. **Circularity, which the first version had.** Scoring by the bill's LAST pre-floor venue makes the
   finding near-tautological: dying in subcommittee IS having your last vote there, and it produced an
   absurd 82% subcommittee base rate. A bill is now counted as SEEN BY every venue that voted on it, and
   the outcome is whether it ever reached a floor vote — a later, separate event.

WHAT IT IS NOT
--------------
Not a causal estimate of a chair's malice. A room's docket is not random: leadership routes bills, and a
room that receives the harder half of a subject will kill more of it even if it treats every bill exactly
as its counterpart would. The companion design removes the bill's CONTENT as an explanation; it does not
remove ROUTING. Read it as "identical text fares measurably worse here than in the other chamber", which
is the actionable form, not as "this chair is hostile".
"""
from __future__ import annotations

import collections
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MIN_N = 15               # a venue below this cannot carry a rate
PERM_ROUNDS = 2000


def _venue_names(E):
    import committee_votes as CV
    lab = collections.defaultdict(collections.Counter)
    for (_yr, vid), e in E.items():
        m = CV._LABEL.search(e["desc"])
        if m:
            lab[CV._ckey(vid)][m.group(1).strip().rstrip(".")[:30]] += 1
    return lambda ck: (lab[ck].most_common(1)[0][0] if lab[ck] else "?")


def observations():
    """One row per (companion-side, venue that voted on it), restricted to sides whose TWIN survived."""
    import committee_votes as CV
    from corpus import load as cload

    d = CV.load()
    E = d["events"]
    name = _venue_names(E)
    B = cload()["bills"]
    idx = {(r["session"], r["bill"].replace(" ", "")): r for r in B}
    byb = collections.defaultdict(list)
    for (_yr, vid), e in E.items():
        byb[(e["session"], e["bill"])].append((vid, e))

    seen, rows, pairs = set(), [], 0
    for r in B:
        if not r["companion"]:
            continue
        k = (r["session"], r["bill"].replace(" ", ""))
        ck = (r["session"], r["companion"].replace(" ", ""))
        if k >= ck or (k, ck) in seen:
            continue
        seen.add((k, ck))
        a, b = byb.get(k), byb.get(ck)
        if not a or not b:
            continue
        ra, rb = idx.get(k), idx.get(ck)
        # A CROSS-CHAMBER pair is the whole point: a same-chamber "companion" shares a room and controls
        # for nothing.
        if not ra or not rb or ra["chamber"] == rb["chamber"]:
            continue
        pairs += 1
        for me, other in ((a, b), (b, a)):
            if not any(e["venue"] == "floor" for _v, e in other):
                continue                      # the control must have survived, or there is no contrast
            killed = not any(e["venue"] == "floor" for _v, e in me)
            for vid, ev in me:
                if ev["venue"] not in ("committee", "subcommittee"):
                    continue
                rows.append({"venue": f"{CV._ckey(vid)} {name(CV._ckey(vid))}",
                             "kind": ev["venue"], "killed": killed, "session": ev["session"]})
    return rows, pairs


def rank(rows, min_n=MIN_N):
    base = collections.defaultdict(lambda: [0, 0])
    for x in rows:
        a = base[x["kind"]]
        a[1] += 1
        a[0] += x["killed"]
    br = {k: h / n for k, (h, n) in base.items()}
    agg = collections.defaultdict(lambda: [0, 0])
    for x in rows:
        a = agg[(x["venue"], x["kind"])]
        a[1] += 1
        a[0] += x["killed"]
    out = [{"venue": v, "kind": k, "killed": h, "seen": n, "rate": h / n,
            "excess": h / n - br[k]} for (v, k), (h, n) in agg.items() if n >= min_n]
    out.sort(key=lambda r: -r["excess"])
    return out, br


def permutation_p(rows, ranked, br, rounds=PERM_ROUNDS, seed=7):
    """How often does ANY venue reach the observed excess when the outcome is shuffled within kind?

    Shuffling within KIND, not globally, so the test cannot be passed merely by rediscovering that
    subcommittees kill more than committees — which is a different (and already known) finding."""
    if not ranked:
        return 1.0
    obs = max(r["excess"] for r in ranked)
    bykind = collections.defaultdict(list)
    for x in rows:
        bykind[x["kind"]].append(x["killed"])
    keys = {(r["venue"], r["kind"]) for r in ranked}
    rnd = random.Random(seed)
    beat = 0
    for _ in range(rounds):
        sh = {k: rnd.sample(v, len(v)) for k, v in bykind.items()}
        ptr = collections.Counter()
        agg = collections.defaultdict(lambda: [0, 0])
        for x in rows:
            i = ptr[x["kind"]]
            ptr[x["kind"]] += 1
            a = agg[(x["venue"], x["kind"])]
            a[1] += 1
            a[0] += sh[x["kind"]][i]
        beat += max(agg[k][0] / agg[k][1] - br[k[1]] for k in keys) >= obs
    return beat / rounds


def main() -> int:
    rows, pairs = observations()
    ranked, br = rank(rows)
    print(f"cross-chamber companion pairs with votes on both sides: {pairs:,}")
    print(f"content-controlled venue observations (twin survived) : {len(rows):,}")
    for k, v in sorted(br.items()):
        n = sum(1 for x in rows if x["kind"] == k)
        print(f"  base kill rate, {k:<14}{v:>6.0%}  (n={n:,})")
    print("\nCONTENT-CONTROLLED KILL RATE — identical text survived in the other chamber")
    print(f"  {'venue':<38}{'kind':>13}{'killed':>8}{'seen':>6}{'rate':>7}{'vs kind':>9}")
    for r in ranked[:10]:
        print(f"  {r['venue'][:36]:<38}{r['kind']:>13}{r['killed']:>8}{r['seen']:>6}"
              f"{r['rate']:>7.0%}{r['excess']:>+9.0%}")
    p = permutation_p(rows, ranked, br)
    print(f"\n  {len(ranked)} venues at n>={MIN_N}; permutation p = {p:.3f} "
          f"({PERM_ROUNDS:,} shuffles within kind)")
    print(f"  -> {'REAL: venue identity matters beyond chance' if p < 0.05 else 'NOT distinguishable from noise'}")
    print("\n  NOT a causal claim about any chair: a room's docket is routed, not random. Read as "
          "'identical text fares worse here than in the other chamber'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
