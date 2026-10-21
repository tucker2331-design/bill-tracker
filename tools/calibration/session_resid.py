#!/usr/bin/env python3
"""Who is surprising the model THIS session? (owner, 2026-10-21: "keep working on the goal")

The weekly refit and the booster learn the session's mood through the shared inputs. They cannot key on a person.
Here, for every vote, three running averages of the model's error so far in the session, from weeks BEFORE the vote's
week only (shrunk toward 0 with `k` pseudo-votes):
  m_res   this member's error (actual - predicted), on this side (own party / other party)
  c_res   this committee's error on this side
  p_res   this patron's error on this side
A small logistic layer on [logit p, m_res, c_res, p_res] is refit weekly on the session's earlier weeks (ridge toward
"no change") and, as in booster_2027, applied to week w only if the same layer fit before LAST week would have lowered
last week's log loss. Base = arm C (booster_2027.boost on arm B). Run: python3 session_resid.py [k]
"""
from __future__ import annotations
import sys, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, first_vote as FV, gains as G, accept as AC, booster_2027 as BC

MIN = 3000
LAM = 30.0


def feats(te, p, y, wk, k):
    """Running residual means from strictly earlier weeks."""
    weeks = sorted(set(wk)); F = np.zeros((len(te), 3))
    acc = [collections.defaultdict(lambda: [0.0, 0]) for _ in range(3)]
    key = lambda r, j: ((r["who"], r["same"]), (r["room"], r["same"]), (r["bill"][0], FV_patron(r), r["same"]))[j]
    for w in weeks:
        idx = np.where(wk == w)[0]
        for i in idx:
            for j in range(3):
                s, n = acc[j][key(te[i], j)]; F[i, j] = s / (n + k)
        for i in idx:                                      # learn this week only after featurising it
            for j in range(3):
                a = acc[j][key(te[i], j)]; a[0] += y[i] - p[i]; a[1] += 1
    return F


_corpus = None


def FV_patron(r):
    global _corpus
    if _corpus is None:
        from corpus import load
        _corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    return _corpus[r["bill"]]["chief"]


def fit(X, y, prior):
    b = prior.copy()
    for _ in range(60):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        g = X.T @ (y - p) - LAM * (b - prior); H = X.T @ (X * (p * (1 - p))[:, None]) + LAM * np.eye(len(b))
        st = np.linalg.solve(H, g); b += st
        if np.max(np.abs(st)) < 1e-7:
            return b
    raise RuntimeError("session_resid layer did not converge")


def main(k):
    rc = FV.assemble()["rc"]; pooled = []
    for split in ("choose", "confirm", "repeat"):
        te, p0, p1 = G.load(split)
        pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        y = np.array([r["y"] for r in te], float)
        wk = np.array([BC._week(rc[r["bill"]][0][0]) for r in te]); weeks = sorted(set(wk))
        lg = np.log(np.clip(pC, 1e-6, 1 - 1e-6) / (1 - np.clip(pC, 1e-6, 1 - 1e-6)))
        R = feats(te, pC, y, wk, k)
        X = np.column_stack([np.ones(len(te)), lg, R]); prior = np.array([0, 1, 0, 0, 0], float)
        out = lg.copy(); used = 0
        for j, w in enumerate(weeks):
            past = wk < w; now = wk == w
            if j < 2 or past.sum() < MIN:
                continue
            prev = wk == weeks[j - 1]; early = wk < weeks[j - 1]
            if early.sum() < MIN:
                continue
            bc = fit(X[early], y[early], prior)
            q = 1 / (1 + np.exp(-(X[prev] @ bc)))
            if AC._ll(q, y[prev]).mean() >= AC._ll(pC[prev], y[prev]).mean():
                continue
            out[now] = X[now] @ fit(X[past], y[past], prior); used += 1
        p2 = 1 / (1 + np.exp(-out))
        hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        room = lambda p: np.mean([((p[I] >= .5).sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
        r1 = (pC >= .5) == (y == 1); r2 = (p2 >= .5) == (y == 1)
        d = collections.defaultdict(float)
        for r, a, c in zip(te, AC._ll(pC, y), AC._ll(p2, y)):
            d[str(r["bill"])] += a - c
        d = np.array(list(d.values())); pooled.append(d)
        np.save(os.path.join(L.PRED, f"session_resid_{split}_k{k}.npy"), p2)
        print(f"{L.SPLITS[split][1]} k={k} (applied {used} of {len(weeks)} weeks): member {r1.mean():.4f}->{r2.mean():.4f}  "
              f"hardest third {r1[hard].mean():.4f}->{r2[hard].mean():.4f}  room(count) {room(pC):.4f}->{room(p2):.4f}  "
              f"z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}", flush=True)
    d = np.concatenate(pooled)
    print(f"POOLED k={k}: z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 10.0)
