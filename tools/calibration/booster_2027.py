#!/usr/bin/env python3
"""Arm C, FROZEN 2026-10-21: arm B (blend_2027.predict_online) + the self-checked session booster.

Copy of session_booster.py (BOOST_GATED=1, 30 trees, depth 2, lr .05, min leaf 50) at the settings chosen on 2024.
Before each session week w (once >= 3,000 session votes exist before the previous week): shallow trees are boosted on
the session's votes before LAST week, starting from arm B's log-odds, and scored on last week. Only if that lowered
last week's log loss are they refit on all earlier weeks and applied to week w. Otherwise week w keeps arm B.
2024/2025/2026 (vs arm B): member +0.01 / +0.40 / +0.13, hardest third +0.02 / +1.13 / +0.39 -- never worse.
blend_2027.py is not edited (its hash is in prereg_2027.json); this file is hashed in prereg_2027_addendum.json.
"""
from __future__ import annotations
import os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV, gbm, blend_2027 as B

BOOST = {"rounds": 30, "depth": 2, "lr": 0.05, "min_h": 50.0, "min_session_votes": 3000}


class Offset(gbm.GBM):
    def fit_from(self, X, y, F0):
        X = np.asarray(X, float); y = np.asarray(y, float); k = X.shape[1]
        self.cuts = [np.unique(np.quantile(X[:, j], np.linspace(0, 1, self.nbins + 1)[1:-1])) for j in range(k)]
        Bn = self._bin(X); F = F0.copy(); self.trees = []
        for _ in range(self.rounds):
            p = 1 / (1 + np.exp(-F)); tree = self._grow(Bn, p - y, np.maximum(p * (1 - p), 1e-6))
            F += self.lr * self._apply(tree, Bn); self.trees.append(tree)
        return self

    def delta(self, X):
        Bn = self._bin(np.asarray(X, float)); d = np.zeros(len(Bn))
        for tree in self.trees:
            d += self.lr * self._apply(tree, Bn)
        return d


def _week(d):
    x = datetime.date.fromisoformat(d[:10]); return (x - datetime.timedelta(days=x.weekday())).isoformat()


def boost(te, pB, y_known, vote_date):
    """pB: arm B predictions for te; y_known: actual votes (used only for weeks BEFORE the one being predicted)."""
    lg = np.log(np.clip(pB, 1e-6, 1 - 1e-6) / (1 - np.clip(pB, 1e-6, 1 - 1e-6)))
    X = np.array([[r[c] for c in FV.NUM] for r in te], float); y = np.asarray(y_known, float)
    wk = np.array([_week(vote_date(r)) for r in te]); weeks = sorted(set(wk)); F = lg.copy()
    mk = lambda: Offset(depth=BOOST["depth"], lr=BOOST["lr"], rounds=BOOST["rounds"], min_h=BOOST["min_h"])
    ll = lambda p, t: float(-(t * np.log(np.clip(p, 1e-6, 1)) + (1 - t) * np.log(np.clip(1 - p, 1e-6, 1))).mean())
    for j, w in enumerate(weeks):
        past = wk < w; now = wk == w
        if j == 0 or past.sum() < BOOST["min_session_votes"]:
            continue
        prev = wk == weeks[j - 1]; early = wk < weeks[j - 1]
        if early.sum() < BOOST["min_session_votes"]:
            continue
        chk = mk().fit_from(X[early], y[early], lg[early])
        if ll(1 / (1 + np.exp(-(lg[prev] + chk.delta(X[prev])))), y[prev]) >= ll(pB[prev], y[prev]):
            continue
        F[now] = lg[now] + mk().fit_from(X[past], y[past], lg[past]).delta(X[now])
    return 1 / (1 + np.exp(-F))


def predict_boosted(tr, te, vote_date):
    pB = B.predict_online(tr, te, vote_date)
    return boost(te, pB, [r["y"] for r in te], vote_date)
