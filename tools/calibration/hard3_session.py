#!/usr/bin/env python3
"""Hard third: THIS-SESSION kill traces (2026-10-25). Earlier tests used the patron's / room's kill share in EARLIER
sessions (drop_model: no gain). New: the same traces inside the current session, strictly before the vote date:
  pat_kill   share of the patron's bills already first-voted this session that died unanimously (shrunk, + count)
  room_kill  share of this room's first votes so far this session that were unanimous NO (shrunk)
  pat_pass   share of the patron's bills so far this session passed unanimously
Scored on can't-call votes, x side, year-ahead both ways.  Run: python3 hard3_session.py
"""
from __future__ import annotations
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, first_vote as FV, knn_own as K
from corpus import load


def main():
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    rc = FV.assemble()["rc"]; date = {k: v[0][0] for k, v in rc.items() if v and v[0][0] != "9999"}
    R = [r for r in L.rows() if r["yr"] >= 2024 and r["bill"] in date]
    by_bill = collections.defaultdict(list)
    for r in R:
        by_bill[r["bill"]].append(r)
    res = {k: ("dead" if max(x["y"] for x in rs) == 0 else "all" if min(x["y"] for x in rs) == 1 else "split") for k, rs in by_bill.items()}
    room_of = {k: rs[0]["room"] for k, rs in by_bill.items()}
    pat = {k: corpus[k]["chief"] for k in by_bill if k in corpus}
    D = {}
    for split in ("confirm", "repeat"):
        te, _a, _b = G.load(split); pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        I = [i for i, r in enumerate(te) if abs(pC[i] - .5) < .31 and r["bill"] in date]
        rows = []
        for i in I:
            k = te[i]["bill"]; d0 = date[k]
            same = [c for c in by_bill if c[0] == k[0] and date[c] < d0]
            pb = [res[c] for c in same if pat.get(c) == pat.get(k)]; rb = [res[c] for c in same if room_of[c] == room_of[k]]
            pk = (sum(x == "dead" for x in pb) + .1) / (len(pb) + 1); pp = (sum(x == "all" for x in pb) + .4) / (len(pb) + 1)
            rk = (sum(x == "dead" for x in rb) + .1 * 5) / (len(rb) + 5)
            rows.append([pk - .1, pp - .4, rk - .1, np.log1p(len(pb)) / 3])
        F = np.array(rows); side = np.array([1.0 if te[i]["same"] else -1.0 for i in I])
        y = np.array([te[i]["y"] for i in I], float); dead = np.array([res.get(te[i]["bill"]) == "dead" for i in I])
        p = np.clip(pC[I], 1e-6, 1 - 1e-6); D[split] = (np.log(p / (1 - p)), np.column_stack([F, F * side[:, None]]), y, dead, F)
        hi = F[:, 0] > .2
        print(f"{split}: {len(y)} votes; patron already lost a bill unanimously this session (share>.3): {hi.mean():.1%} of votes, "
              f"unanimous NO there {dead[hi].mean():.1%} vs {dead[~hi].mean():.1%}")
    for a, b in (("confirm", "repeat"), ("repeat", "confirm")):
        off, X, y, _d, _F = D[a]; w = K.fit(off, X, y, lam=3.0)
        off, X, y, _d, _F = D[b]; p0 = 1 / (1 + np.exp(-off)); p1 = 1 / (1 + np.exp(-(off + X @ w)))
        r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1); c = np.abs(p1 - .5) >= .31
        print(f"fit {a} -> {b}: right {r0.mean():.3f} -> {r1.mean():.3f} (fixed {(~r0 & r1).sum()}, broken {(r0 & ~r1).sum()}); new calls {c.sum()} right {r1[c].mean() if c.any() else float('nan'):.3f}")


if __name__ == "__main__":
    main()
