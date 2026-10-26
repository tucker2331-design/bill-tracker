#!/usr/bin/env python3
"""Same-meeting twins (2026-10-26). The docket (bills to be heard) is public before a meeting. When two near-identical
bills are heard in the same room on the same day, usually one advances and the other is incorporated or struck.
For each can't-call vote: highest TF-IDF similarity to ANOTHER bill first-voted in the SAME room on the SAME date.
Reports the unanimous-NO rate by twin band, and which twin survives (senior / majority patron, lower bill number).
Year-ahead signal test on top of arm C as in hard3_newinfo.  Run: python3 sameday_twin.py
"""
from __future__ import annotations
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import llm_member as M, levers as L, gains as G, first_vote as FV, summary_memory as SM, knn_own as K
from corpus import load


def main():
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    summ = SM.summaries(); rc = FV.assemble()["rc"]
    date = {k: v[0][0] for k, v in rc.items() if v and v[0][0] != "9999"}
    text = {k: M.blind(corpus[k]["title"] + ". " + summ[k]) for k in summ if k in corpus}
    vec = M._tfidf({k: [w for w in M.WORD.findall(t.lower()) if w not in M.STOP] for k, t in text.items()})
    R = [r for r in L.rows() if r["yr"] >= 2024 and r["bill"] in date]
    by_bill = collections.defaultdict(list)
    for r in R:
        by_bill[r["bill"]].append(r)
    meet = collections.defaultdict(list)
    for k, rs in by_bill.items():
        meet[(rs[0]["room"], date[k])].append(k)
    dead = {k for k, rs in by_bill.items() if max(x["y"] for x in rs) == 0}
    D = {}
    for split in ("confirm", "repeat"):
        te, _a, _b = G.load(split); pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        I = [i for i, r in enumerate(te) if abs(pC[i] - .5) < .31 and r["bill"] in vec and r["bill"] in date]
        sim = {}; num_lower = {}
        for i in I:
            k = te[i]["bill"]
            if k not in sim:
                mates = [c for c in meet[(te[i]["room"], date[k])] if c != k and c in vec]
                best = max(((M._cos(vec[k], vec[c]), c) for c in mates), default=(0.0, None))
                sim[k] = best[0]
                num_lower[k] = best[1] is not None and int(k[1].split()[1]) > int(best[1][1].split()[1]) and k[1][:2] == best[1][1][:2]
        s = np.array([sim[te[i]["bill"]] for i in I]); dd = np.array([te[i]["bill"] in dead for i in I])
        later = np.array([num_lower[te[i]["bill"]] for i in I])
        print(f"{split}: {len(I)} can't-call votes")
        for lo_, hi in ((0, .2), (.2, .4), (.4, .6), (.6, 1.01)):
            m = (s >= lo_) & (s < hi)
            if m.any():
                print(f"   same-meeting twin similarity {lo_:.1f}-{hi:.1f}: {m.mean():5.1%} of votes, room unanimous NO {dd[m].mean():.1%}"
                      + (f"  (this bill numbered after its twin: {dd[m & later].mean():.0%} of {(m & later).sum()}, before: {dd[m & ~later].mean():.0%} of {(m & ~later).sum()})" if lo_ >= .4 else ""))
        side = np.array([1.0 if te[i]["same"] else -1.0 for i in I])
        F = np.column_stack([(s >= .4), (s >= .4) & later]).astype(float)
        p = np.clip(pC[I], 1e-6, 1 - 1e-6)
        D[split] = (np.log(p / (1 - p)), np.column_stack([F, F * side[:, None]]), np.array([te[i]["y"] for i in I], float))
    for a, b in (("confirm", "repeat"), ("repeat", "confirm")):
        off, X, y = D[a]; w = K.fit(off, X, y, lam=3.0)
        off, X, y = D[b]; p0 = 1 / (1 + np.exp(-off)); p1 = 1 / (1 + np.exp(-(off + X @ w)))
        r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1)
        print(f"fit {a} -> {b}: right {r0.mean():.3f} -> {r1.mean():.3f} (fixed {(~r0 & r1).sum()}, broken {(r0 & ~r1).sum()})")


if __name__ == "__main__":
    main()
