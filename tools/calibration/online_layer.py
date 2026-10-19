#!/usr/bin/env python3
"""Learn the session's own mood as it happens (owner, 2026-10-19: "continue to try to improve").

The adopted model learns its weights from earlier YEARS only. But a session has its own temper: 2026 (new trifecta)
was more partisan, and `gains.py` shows the blend lost ground on party-line votes there (other party 72.6 -> 69.1)
while it gained on consensus votes. Every vote cast earlier in the SAME session is public before the next one.

Layer (refit before every voting day, on that session's earlier votes only; nothing from the test day or later):
    logit P = a[side] + b[side] * logit(p_blend) + c[side, venue]
  side = own party / other party; venue = subcommittee / committee / floor. Ridge `lam` pulls (a, b, c) toward
  (0, 1, 0) -- i.e. toward the blend unchanged -- so early in the session, with few votes, nothing moves.
Base = the adopted blend's saved predictions (levers blend) for 2024 / 2025 / 2026. `lam` chosen on 2024.
Run: python3 online_layer.py
"""
from __future__ import annotations
import sys, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, first_vote as FV, gains as G, accept as AC

LAMS = (30.0, 100.0, 300.0, 1000.0)


def design(te, lg):
    if MODE == "both":
        Xp = _design_mode(te, lg, "party"); Xv = _design_mode(te, lg, "venue")
        return np.column_stack([Xp, Xv[:, 4:]])
    return _design_mode(te, lg, MODE)


def _design_mode(te, lg, MODE):
    if MODE == "party":
        # group = voter's party x side (D own / D other / R own / R other): intercept and slope per group
        X = np.zeros((len(te), 8))
        for i, r in enumerate(te):
            gi = (0 if r["party"] == "Democratic" else 2) + (0 if r["same"] else 1)
            X[i, gi] = 1; X[i, 4 + gi] = lg[i]
        return X
    n = len(te); X = np.zeros((n, 8))
    for i, r in enumerate(te):
        s = 0 if r["same"] else 1
        X[i, s] = 1; X[i, 2 + s] = lg[i]
        v = 0 if r["ven_sub"] else 1 if r["ven_com"] else 2
        if v:                                             # subcommittee is the reference venue
            X[i, 4 + 2 * s + (v - 1)] = 1
    return X


MODE = "both" if "both" in sys.argv else "party" if "party" in sys.argv else "venue"
PRIOR = {"party": np.array([0, 0, 0, 0, 1, 1, 1, 1], float), "venue": np.array([0, 0, 1, 1, 0, 0, 0, 0], float),
         "both": np.array([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0], float)}[MODE]


def fit(X, y, lam):
    b = PRIOR.copy()
    for _ in range(50):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        g = X.T @ (y - p) - lam * (b - PRIOR); H = X.T @ (X * (p * (1 - p))[:, None]) + lam * np.eye(len(b))
        step = np.linalg.solve(H, g); b += step
        if np.max(np.abs(step)) < 1e-7:
            return b
    raise RuntimeError("online layer did not converge")


def main():
    rc = FV.assemble()["rc"]; pooled = collections.defaultdict(list)
    for split in ("choose", "confirm", "repeat"):
        te, p0, p1 = G.load(split)
        y = np.array([r["y"] for r in te], float)
        lg = np.log(np.clip(p1, 1e-6, 1 - 1e-6) / (1 - np.clip(p1, 1e-6, 1 - 1e-6)))
        X = design(te, lg); day = np.array([rc[r["bill"]][0][0] for r in te])
        hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        for lam in LAMS:
            p2 = p1.copy()
            for d in sorted(set(day)):
                past = day < d; now = day == d
                if past.sum() < 200:
                    continue                                  # too few votes yet: keep the blend
                b = fit(X[past], y[past], lam)
                p2[now] = 1 / (1 + np.exp(-np.clip(X[now] @ b, -30, 30)))
            r1 = (p1 >= .5) == (y == 1); r2 = (p2 >= .5) == (y == 1)
            room = lambda p: np.mean([(p[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
            d_ = collections.defaultdict(float)
            for r, a, c in zip(te, AC._ll(p1, y), AC._ll(p2, y)):
                d_[str(r["bill"])] += a - c
            d_ = np.array(list(d_.values())); pooled[lam].append(d_)
            print(f"{L.SPLITS[split][1]} lam {lam:>6}: member {r1.mean():.4f}->{r2.mean():.4f}  hardest third {r1[hard].mean():.4f}->"
                  f"{r2[hard].mean():.4f}  room {room(p1):.4f}->{room(p2):.4f}  z {d_.mean() / (d_.std(ddof=1) / math.sqrt(len(d_))):+.1f}",
                  flush=True)
    for lam, ds in pooled.items():
        d = np.concatenate(ds)
        print(f"POOLED 2024-2026 lam {lam}: z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}")


if __name__ == "__main__":
    main()
