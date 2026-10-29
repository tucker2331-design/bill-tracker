#!/usr/bin/env python3
"""Refit the bagged trees ONCE mid-session on that session's first-half votes (owner: "continue to try to improve";
online_layer.py showed the session's temper is learnable). Votes on or after the session's median first-vote date are
scored by (a) the trees learned from earlier years only and (b) trees learned from earlier years + this session's
votes before that date (weight W). Both blended 80/20 with the static linear model's saved predictions, as adopted.
Run: python3 midsession_trees.py <split> <W>
"""
from __future__ import annotations
import sys, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, first_vote as FV, gains as G, accept as AC

BAG = {"depth": 6, "subsample": 0.5, "colsample": 0.5, "bags": 8}
LIN = {"hinges": 3, "lam": 10, "pairs": 8}


def main(split, W):
    rc = FV.assemble()["rc"]; trn, ty = L.SPLITS[split]
    tr = [r for r in L.rows() if r["yr"] in trn]; te, p0, p1 = G.load(split)
    day = np.array([rc[r["bill"]][0][0] for r in te]); cut = np.median(np.array(sorted(day)).astype("datetime64[D]").astype(int))
    dn = day.astype("datetime64[D]").astype(int); first = dn < cut; second = ~first
    pb = np.load(os.path.join(L.PRED, f"gbm_{split}_{L._key(BAG)}.npy"))
    pl = np.load(os.path.join(L.PRED, f"linear_{split}_{L._key(LIN)}.npy"))
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    tr2 = tr + [te[i] for i in np.where(first)[0]]
    w = np.concatenate([np.ones(len(tr)), np.full(first.sum(), W)])
    Xtr, ytr, Xte = X(tr2), np.array([r["y"] for r in tr2], float), X([te[i] for i in np.where(second)[0]])
    pb2 = np.mean([L.GBMX(depth=6, lr=.03, rounds=260, subsample=.5, colsample=.5, seed=b).fit(Xtr, ytr, w).predict(Xte)
                   for b in range(8)], axis=0)
    lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    S = np.where(second)[0]; y = np.array([r["y"] for r in te], float)[S]
    pa = 1 / (1 + np.exp(-(.8 * lo(pb[S]) + .2 * lo(pl[S]))))
    pc = 1 / (1 + np.exp(-(.8 * lo(pb2) + .2 * lo(pl[S]))))
    np.save(os.path.join(L.PRED, f"midsession_{split}_W{W}.npy"), pc)
    hard = np.argsort(np.abs(p0[S] - .5))[:len(S) // 3]
    g = collections.defaultdict(list)
    for j, i in enumerate(S):
        g[te[i]["bill"]].append(j)
    room = lambda p: np.mean([(p[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
    ra, rc_ = (pa >= .5) == (y == 1), (pc >= .5) == (y == 1)
    d = collections.defaultdict(float)
    for j, i in enumerate(S):
        d[str(te[i]["bill"])] += AC._ll(pa[j:j + 1], y[j:j + 1])[0] - AC._ll(pc[j:j + 1], y[j:j + 1])[0]
    d = np.array(list(d.values()))
    print(f"{ty} second half ({len(S)} votes) W={W}: member {ra.mean():.4f}->{rc_.mean():.4f}  hardest third "
          f"{ra[hard].mean():.4f}->{rc_[hard].mean():.4f}  room {room(pa):.4f}->{room(pc):.4f}  "
          f"z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))
