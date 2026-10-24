#!/usr/bin/env python3
"""A specialist for the votes we cannot call (owner, 2026-10-21: "predict that we cant predict it ... limiting the
scenarios we guess wrong is supremely important").

"Can't call" = arm C's chance between 20% and 80% (the Leans / Toss-up labels) -- about 27-34% of votes, 46% of
other-party votes, mostly whole party blocks. The main model spends most of its capacity on the easy two thirds. The
specialist learns ONLY from earlier years' uncertain votes (out-of-sample predictions of the locked model, accept.
base_preds, 0.2 < p < 0.8), with that prediction's log-odds as an input, and on the test year re-scores only the
votes arm C cannot call (blend `w` in log-odds). Year-ahead: 2024 from 2021-22, 2025 from 2021-24, 2026 from 2021-25.
Measures: share of votes called (outside 20-80%) and accuracy of the calls; member accuracy; hardest third; room.
Run: python3 specialist.py <w> [depth]
"""
from __future__ import annotations
import sys, os, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, first_vote as FV, accept as AC, gbm

lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
TRAIN = {"choose": (2021, 2022), "confirm": (2021, 2022, 2024), "repeat": (2021, 2022, 2024, 2025)}


def main(w, depth):
    B = AC.base_preds()
    B[2026] = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    X = lambda rs, p: np.column_stack([lo(p), np.array([[r[c] for c in FV.NUM] for r in rs], float)])
    for split in ("choose", "confirm", "repeat"):
        Xs, ys = [], []
        for t in TRAIN[split]:
            te_t, p_t = B[t]; m = (p_t > .2) & (p_t < .8)
            Xs.append(X([r for r, k in zip(te_t, m) if k], p_t[m])); ys.append(np.array([r["y"] for r, k in zip(te_t, m) if k], float))
        spec = gbm.GBM(depth=depth, lr=.05, rounds=200).fit(np.vstack(Xs), np.concatenate(ys))
        te, p0, p1 = G.load(split)
        pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        u = (pC > .2) & (pC < .8); p2 = pC.copy()
        ps = spec.predict(X([r for r, k in zip(te, u) if k], p0[u]))      # the locked model's p as its input, as trained
        p2[u] = 1 / (1 + np.exp(-((1 - w) * lo(pC[u]) + w * lo(ps))))
        y = np.array([r["y"] for r in te]); hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        room = lambda p: np.mean([((p[I] >= .5).sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
        def calls(p):
            c = np.abs(p - .5) >= .3; r = (p >= .5) == (y == 1); return c.mean(), r[c].mean(), int((c & ~r).sum())
        r1 = (pC >= .5) == (y == 1); r2 = (p2 >= .5) == (y == 1)
        (c1, a1, e1), (c2, a2, e2) = calls(pC), calls(p2)
        print(f"{L.SPLITS[split][1]} w={w} d={depth}: called {c1:.1%}->{c2:.1%}, calls right {a1:.2%}->{a2:.2%}, wrong calls {e1}->{e2} | "
              f"member {r1.mean():.4f}->{r2.mean():.4f}  hardest third {r1[hard].mean():.4f}->{r2[hard].mean():.4f}  "
              f"room {room(pC):.4f}->{room(p2):.4f}", flush=True)


if __name__ == "__main__":
    main(float(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 4)
