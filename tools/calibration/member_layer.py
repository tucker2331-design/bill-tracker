#!/usr/bin/env python3
"""Per-member correction layer on the locked member model (owner, 2026-10-16: "use whatever advanced techniques").

The trees treat every member through shared inputs. Some members are more predictable than the trees say (they never
leave the party line) and some less (they cross often, on the bills you would not guess). A hierarchical layer gives
each member their own shift and their own confidence on top of the base prediction, shrunk toward zero (ridge), learned
only from earlier years' out-of-sample predictions:

    logit P(yes) = a + b * logit(base p) + a_m[side] + b_m * logit(base p)

  a_m[side]  the member's own shift, separately on own-party and other-party bills
  b_m        the member's own confidence (b_m > 0: more certain than the trees; < 0: less)
Members never seen in earlier years get zero terms (the base). Penalised Newton with the penalty in the gradient.

Frame: base predictions for 2021/2022/2024/2025 (accept.ORIGINS, each from earlier years) and 2026 (p2026.pkl, learned
through 2025). Score year t from all years before t. Penalty CHOSEN on 2022+2024; 2025 confirms; 2026 replicates.
Run: python3 member_layer.py
"""
from __future__ import annotations
import sys, os, pickle, collections, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC

LAMS = (3.0, 10.0, 30.0, 100.0)


def years():
    B = dict(AC.base_preds())
    B[2026] = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    return B


def design(te, p, members, slope=True):
    lg = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    n, M = len(te), len(members)
    k = 2 + 2 * M + (M if slope else 0)
    X = np.zeros((n, k)); X[:, 0] = 1; X[:, 1] = lg
    for i, r in enumerate(te):
        j = members.get(r["who"])
        if j is None:
            continue
        X[i, 2 + 2 * j + (0 if r["same"] else 1)] = 1
        if slope:
            X[i, 2 + 2 * M + j] = lg[i]
    return X


def fit(X, y, lam):
    pen = np.full(X.shape[1], lam); pen[:2] = 1e-6
    b = np.zeros(X.shape[1]); b[1] = 1.0
    for _ in range(100):
        with np.errstate(all="ignore"):
            p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        g = X.T @ (y - p) - pen * b
        H = X.T @ (X * (p * (1 - p))[:, None]) + np.diag(pen)
        step = np.linalg.solve(H, g); b += step
        if np.max(np.abs(step)) < 1e-6:
            return b
    raise RuntimeError("member layer did not converge")


def score(te, p0, p1):
    y = np.array([r["y"] for r in te], float)
    hard = np.argsort(np.abs(p0 - .5))[:len(p0) // 3]
    g = collections.defaultdict(list)
    for i, r in enumerate(te):
        g[r["bill"]].append(i)
    out = []
    for p in (p0, p1):
        right = (p >= .5) == (y == 1)
        room = np.mean([(p[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
        out.append((right.mean(), right[hard].mean(), room))
    d = collections.defaultdict(float)
    for r, a, b in zip(te, AC._ll(p0, y), AC._ll(p1, y)):
        d[str(r["bill"])] += a - b
    d = np.array(list(d.values()))
    return out, d


def main(slope=True):
    B = years(); ys = sorted(B)
    print(f"MEMBER LAYER ({'shift + confidence' if slope else 'shift only'}) per member x side, ridge toward the base")
    for lam in LAMS:
        diffs = {}
        for t in ys[1:]:
            prior = [u for u in ys if u < t]
            members = {}
            for u in prior:
                for r in B[u][0]:
                    members.setdefault(r["who"], len(members))
            Xtr = np.vstack([design(B[u][0], B[u][1], members, slope) for u in prior])
            ytr = np.concatenate([[r["y"] for r in B[u][0]] for u in prior]).astype(float)
            b = fit(Xtr, ytr, lam)
            te, p0 = B[t]
            with np.errstate(all="ignore"):
                p1 = 1 / (1 + np.exp(-np.clip(design(te, p0, members, slope) @ b, -30, 30)))
            ((a0, h0, r0), (a1, h1, r1)), d = score(te, p0, p1); diffs[t] = d
            print(f"  lam {lam:>5}: {t} member {a0:.4f}->{a1:.4f}  hardest third {h0:.4f}->{h1:.4f}  room {r0:.4f}->{r1:.4f}  "
                  f"per-bill gain {d.mean():+.5f} z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}", flush=True)
        ch = np.concatenate([diffs[2022], diffs[2024]])
        print(f"  lam {lam:>5}: CHOOSE (2022+2024) z {ch.mean() / (ch.std(ddof=1) / math.sqrt(len(ch))):+.1f}", flush=True)


if __name__ == "__main__":
    main(slope="noslope" not in sys.argv)
