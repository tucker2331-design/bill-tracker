#!/usr/bin/env python3
"""A model for House subcommittee votes only (owner, 2026-10-22: boost subcommittees to match the rest).
Subcommittee first votes are all House, 11-13% unanimous no; full-committee first votes are mostly Senate. One model
serves both. Here, on the test year's SUBCOMMITTEE votes only, arm A (bagged trees + 20% linear, saved) is compared
with the same recipe trained (a) on subcommittee votes only, (b) on all votes with subcommittee votes weighted `w`.
Run: python3 sub_model.py <split> <mode: only | weight> [w]
"""
from __future__ import annotations
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, first_vote as FV

LIN = {"hinges": 3, "lam": 10, "pairs": 8}
lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def main(split, mode, w):
    trn, ty = L.SPLITS[split]; tr = [r for r in L.rows() if r["yr"] in trn]; te, p0, pA = G.load(split)
    S = np.array([bool(r["ven_sub"]) for r in te]); tes = [r for r, k in zip(te, S) if k]
    if mode == "only":
        T = [r for r in tr if r["ven_sub"]]; wt = np.ones(len(T))
    else:
        T = tr; wt = np.array([w if r["ven_sub"] else 1.0 for r in tr])
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    XT, yT, Xe = X(T), np.array([r["y"] for r in T], float), X(tes)
    pt = np.mean([L.GBMX(depth=6, lr=.03, rounds=260, subsample=.5, colsample=.5, seed=b).fit(XT, yT, wt).predict(Xe) for b in range(8)], axis=0)
    pl = L.linear_fn(T, tes, dict(LIN, sample_w=wt))
    p1 = 1 / (1 + np.exp(-(.8 * lo(pt) + .2 * lo(pl))))
    y = np.array([r["y"] for r in tes]); a = pA[S]; b0 = p0[S]
    hard = np.argsort(np.abs(b0 - .5))[:len(y) // 3]
    g = collections.defaultdict(list)
    for i, r in enumerate(tes):
        g[r["bill"]].append(i)
    room = lambda p: np.mean([((p[I] >= .5).sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
    ra, r1 = (a >= .5) == (y == 1), (p1 >= .5) == (y == 1); ca, c1 = np.abs(a - .5) >= .3, np.abs(p1 - .5) >= .3
    np.save(os.path.join(L.PRED, f"submodel_{split}_{mode}_{w}.npy"), p1)
    print(f"{ty} SUBCOMMITTEE votes ({len(y)}), {mode} w={w}: member {ra.mean():.4f}->{r1.mean():.4f}  hardest third "
          f"{ra[hard].mean():.4f}->{r1[hard].mean():.4f}  room {room(a):.4f}->{room(p1):.4f}  called {ca.mean():.1%}->{c1.mean():.1%} "
          f"right {ra[ca].mean():.4f}->{r1[c1].mean():.4f} wrong calls {(ca & ~ra).sum()}->{(c1 & ~r1).sum()}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 1.0)
