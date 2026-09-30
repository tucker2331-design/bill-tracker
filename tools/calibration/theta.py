#!/usr/bin/env python3
"""Party positions first, members derived -- the panel's Theta ([[testing/panel_2026-09-29]]).

84.6% of member errors on 2025 sit in a MISSED PARTY POSITION (mathematician). So instead of predicting 20 ballots
and averaging them into a party position, predict the party position directly -- one row per (first vote, side),
side = the patron's party or the other party -- and derive each member from it:

    P(member backs the bill) = q (1 - d) + (1 - q) d
    q = P(the member's side backs it)        d = the member's own rate of breaking from their party

Group inputs are the MEAN of every first_vote.NUM column over that side's ballots (bill columns are constant within
the side; member columns become the side's average), plus the side's size.

Acceptance (panel rule, applied to every change from now on): rolling origin -- each of 2021, 2022, 2024, 2025
scored by a model trained only on earlier years -- paired per-bill log-loss difference against the one-stage GBM,
pooled over all four years, accepted only at z >= 3. 2026 is not touched (already scored once, prereg_2026.py).
"""
from __future__ import annotations
import sys, os, math, pickle, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV, gbm

ORIGINS = ((2021, (2019, 2020)), (2022, (2019, 2020, 2021)), (2024, (2019, 2020, 2021, 2022)),
           (2025, (2019, 2020, 2021, 2022, 2024)))


def _ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def pooled_z(diffs_by_year):
    """diffs: per-BILL summed log-loss (baseline - candidate); positive = candidate better. Bills are the
    independent unit (ballots on one bill move together: design effect ~4.5)."""
    d = np.concatenate(diffs_by_year)
    return d.mean(), d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))


def per_bill(loss, bills):
    g = collections.defaultdict(float)
    for l, b in zip(loss, bills):
        g[b] += l
    return g


def groups(rows):
    g = collections.defaultdict(list)
    for i, r in enumerate(rows):
        g[(r["bill"], r["same"])].append(i)
    keys = list(g)
    X = np.array([[np.mean([rows[i][c] for i in g[k]]) for c in FV.NUM] + [len(g[k])] for k in keys], float)
    y = np.array([np.mean([rows[i]["y"] for i in g[k]]) >= .5 for k in keys], float)
    return keys, g, X, y


def theta_predict(tr, te, depth=4, rounds=200, lr=.05):
    ktr, _gtr, Xtr, ytr = groups(tr)
    kte, gte, Xte, yte = groups(te)
    q = gbm.GBM(depth=depth, lr=lr, rounds=rounds).fit(Xtr, ytr).predict(Xte)
    p = np.zeros(len(te))
    for k, qq in zip(kte, q):
        for i in gte[k]:
            d = te[i]["defect"]
            p[i] = qq * (1 - d) + (1 - qq) * d
    return p, q, yte, kte


def one_stage(tr, te):
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    return gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(te))


def party_acc_from_members(p, te, keys):
    g = collections.defaultdict(list)
    for i, r in enumerate(te):
        g[(r["bill"], r["same"])].append(i)
    return np.array([p[g[k]].mean() >= .5 for k in keys], float)


def main(choose_only=False):
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
    diffs = {"theta-derived": [], "average of both": []}
    origins = [o for o in ORIGINS if o[0] == 2024] if choose_only else ORIGINS
    for t, trn in origins:
        tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == t]
        y = np.array([r["y"] for r in te], float); bills = [r["bill"] for r in te]
        p1 = one_stage(tr, te)
        p2, q, yq, keys = theta_predict(tr, te)
        p3 = (p1 + p2) / 2
        pa1 = party_acc_from_members(p1, te, keys)
        print(f"{t}: party position right  one-stage {np.mean(pa1 == yq):.4f}   theta {np.mean((q >= .5) == yq):.4f}"
              f"   (n sides {len(keys)})")
        b1 = per_bill(_ll(p1, y), bills)
        for name, p in (("theta-derived", p2), ("average of both", p3)):
            bb = per_bill(_ll(p, y), bills)
            diffs[name].append(np.array([b1[k] - bb[k] for k in b1]))
            r = (p >= .5) == (y == 1); o = np.argsort(np.abs(p - .5))
            print(f"   {name:16s} acc {r.mean():.4f} (one-stage {((p1 >= .5) == (y == 1)).mean():.4f})  "
                  f"log loss {_ll(p, y).mean():.4f} (one-stage {_ll(p1, y).mean():.4f})  hardest third {r[o[:len(o)//3]].mean():.4f}",
                  flush=True)
    for name, d in diffs.items():
        m, z = pooled_z(d)
        print(f"POOLED {name}: per-bill log-loss gain {m:+.4f}, z = {z:.1f} -> {'ACCEPT' if z >= 3 else 'reject'}")


if __name__ == "__main__":
    main(choose_only="--choose" in sys.argv)
