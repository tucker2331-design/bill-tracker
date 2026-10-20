#!/usr/bin/env python3
"""The model adopted by the owner on 2026-10-19 ("approved"), FROZEN for the 2027 forward test.

A copy of levers.py's GBMX and linear_fn at commit b8433fa, so research may keep changing levers.py while this file
(hashed in frozen/prereg_2027.json) stays fixed. Prediction = log-odds average of
  80%  bagged trees: 8 x GBMX(depth 6, lr .03, 260 rounds, 50% rows, 50% inputs per tree, seeds 0..7), averaged
  20%  penalised logistic: inputs standardised, 3 hinges per input, 8 strongest-input products, all x voter side, ridge 10
Selected on 2024; 2025 and 2026 seen (docs/testing/first_vote.md "A second model family in the blend").

ARM B (owner 2026-10-20: "if they are going to consistently improve accuracy then yes") = predict_online(): the same
bagged trees, but the linear half is refit before every session WEEK on earlier years + that session's votes from
earlier weeks (weight 3; only once >= 3,000 session votes exist), blended 70/30 (online_relinear.py, chosen on 2024).
"""
from __future__ import annotations
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV, gbm

TREES = {"depth": 6, "lr": .03, "rounds": 260, "subsample": .5, "colsample": .5, "bags": 8}
LINEAR = {"hinges": 3, "lam": 10, "pairs": 8}
W_LINEAR = 0.2
ONLINE = {"session_weight": 3.0, "min_session_votes": 3000, "linear_share": 0.3}


class GBMX(gbm.GBM):
    """gbm.GBM plus row subsampling, column subsampling per tree, and sample weights. Same tree-growing code."""
    def __init__(self, subsample=1.0, colsample=1.0, seed=0, **kw):
        super().__init__(**kw); self.subsample, self.colsample, self.seed = subsample, colsample, seed

    def fit(self, X, y, w=None):
        X = np.asarray(X, float); y = np.asarray(y, float); n, k = X.shape
        w = np.ones(n) if w is None else np.asarray(w, float)
        self.cuts = [np.unique(np.quantile(X[:, j], np.linspace(0, 1, self.nbins + 1)[1:-1])) for j in range(k)]
        B = self._bin(X); rng = np.random.default_rng(self.seed)
        p0 = np.clip(np.average(y, weights=w), 1e-4, 1 - 1e-4); self.base = np.log(p0 / (1 - p0))
        F = np.full(n, self.base); self.trees = []; self.tree_cols = []
        for _ in range(self.rounds):
            p = 1 / (1 + np.exp(-F)); g = (p - y) * w; h = np.maximum(p * (1 - p), 1e-6) * w
            rows_ = rng.random(n) < self.subsample if self.subsample < 1 else np.ones(n, bool)
            cols = np.sort(rng.choice(k, max(1, int(round(k * self.colsample))), replace=False)) if self.colsample < 1 else np.arange(k)
            gm = np.where(rows_, g, 0.0); hm = np.where(rows_, h, 0.0)
            tree = self._grow(B[:, cols], gm, hm)
            F += self.lr * self._apply(tree, B[:, cols])
            self.trees.append(tree); self.tree_cols.append(cols)
        return self

    def predict(self, X):
        B = self._bin(np.asarray(X, float)); F = np.full(len(B), self.base)
        for tree, cols in zip(self.trees, self.tree_cols):
            F += self.lr * self._apply(tree, B[:, cols])
        return 1 / (1 + np.exp(-F))


def linear_fn(tr, te, s):
    """Every input standardised, plus `hinges` piecewise-linear bends per input at training quantiles (an additive
    model, like a GAM), each also crossed with the voter's side (+1 own party, -1 other). Ridge `lam`, penalised Newton.
    Trees cut inputs into steps; this family draws smooth slopes -- its errors differ, which is what a blend needs."""
    def feats(rs, ref=None):
        X = np.array([[r[c] for c in FV.NUM] for r in rs], float)
        if ref is None:
            mu, sd = X.mean(0), X.std(0); sd = np.where(sd < 1e-6, 1.0, sd)
            Z = np.clip((X - mu) / sd, -10, 10)
            knots = [np.unique(np.quantile(Z[:, j], np.linspace(0, 1, s.get("hinges", 0) + 2)[1:-1])) for j in range(Z.shape[1])]
            ref = (mu, sd, knots)
        mu, sd, knots = ref
        Z = np.clip((X - mu) / sd, -10, 10)
        cols = [Z] + [np.maximum(Z[:, j:j + 1] - k, 0) for j in range(Z.shape[1]) for k in knots[j]]
        F = np.column_stack(cols); side = np.array([1.0 if r["same"] else -1.0 for r in rs])[:, None]
        return np.column_stack([np.ones(len(rs)), F, F * side]), ref
    Xtr, ref = feats(tr); Xte, _ = feats(te, ref); y = np.array([r["y"] for r in tr], float)
    sw = np.ones(len(tr)) if s.get("sample_w") is None else np.asarray(s["sample_w"], float)   # arm B weights the session
    def newton(X):
        pen = np.full(X.shape[1], s.get("lam", 10.0)); pen[0] = 1e-6; b = np.zeros(X.shape[1])
        for _it in range(60):
            p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
            step = np.linalg.solve(X.T @ (X * (sw * p * (1 - p))[:, None]) + np.diag(pen), X.T @ (sw * (y - p)) - pen * b)
            b += step
            if np.max(np.abs(step)) < 1e-6:
                return b
        raise RuntimeError("linear model did not converge in 60 Newton steps")
    b = newton(Xtr)
    if s.get("pairs"):
        # L7b: products of the k plain inputs with the largest first-pass weight (own + side terms), each pair x side
        # layout from feats(): [const | Z (k inputs) + hinges (m cols in all) | the same m cols x side]
        k = len(FV.NUM); m = (Xtr.shape[1] - 1) // 2
        w = np.abs(b[1:1 + k]) + np.abs(b[1 + m:1 + m + k])
        top = np.argsort(-w)[:s["pairs"]]
        def pairs(X):
            Z = X[:, 1:1 + k][:, top]
            return np.column_stack([Z[:, i] * Z[:, j] for i in range(len(top)) for j in range(i + 1, len(top))])
        side_tr = np.array([1.0 if r["same"] else -1.0 for r in tr])[:, None]
        side_te = np.array([1.0 if r["same"] else -1.0 for r in te])[:, None]
        Ptr, Pte = pairs(Xtr), pairs(Xte)
        Xtr = np.column_stack([Xtr, Ptr, Ptr * side_tr]); Xte = np.column_stack([Xte, Pte, Pte * side_te])
        b = newton(Xtr)
    if s.get("ids"):
        # L7c: one shift per member x side and per committee (room), learned with the same ridge (unseen -> 0)
        keys = collections.Counter([("m", r["who"], r["same"]) for r in tr] + [("c", r["room"]) for r in tr])
        col = {k_: i for i, k_ in enumerate(k_ for k_, c in keys.items() if c >= s["ids"])}
        def onehot(rs):
            O = np.zeros((len(rs), len(col)))
            for i, r in enumerate(rs):
                for k_ in (("m", r["who"], r["same"]), ("c", r["room"])):
                    if k_ in col:
                        O[i, col[k_]] = 1
            return O
        Xtr = np.column_stack([Xtr, onehot(tr)]); Xte = np.column_stack([Xte, onehot(te)])
        b = newton(Xtr)
    return 1 / (1 + np.exp(-np.clip(Xte @ b, -30, 30)))


def predict(tr, te):
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    Xtr, ytr, Xte = X(tr), np.array([r["y"] for r in tr], float), X(te)
    pt = np.mean([GBMX(depth=TREES["depth"], lr=TREES["lr"], rounds=TREES["rounds"], subsample=TREES["subsample"],
                       colsample=TREES["colsample"], seed=b).fit(Xtr, ytr).predict(Xte) for b in range(TREES["bags"])], axis=0)
    pl = linear_fn(tr, te, LINEAR)
    lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    return 1 / (1 + np.exp(-((1 - W_LINEAR) * lo(pt) + W_LINEAR * lo(pl))))


def _week(d):
    import datetime
    x = datetime.date.fromisoformat(d[:10]); return (x - datetime.timedelta(days=x.weekday())).isoformat()


def predict_online(tr, te, vote_date):
    """Arm B. vote_date(row) -> ISO date of the row's first vote. Each week sees only earlier weeks of the session."""
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    Xtr, ytr, Xte = X(tr), np.array([r["y"] for r in tr], float), X(te)
    pt = np.mean([GBMX(depth=TREES["depth"], lr=TREES["lr"], rounds=TREES["rounds"], subsample=TREES["subsample"],
                       colsample=TREES["colsample"], seed=b).fit(Xtr, ytr).predict(Xte) for b in range(TREES["bags"])], axis=0)
    wk = np.array([_week(vote_date(r)) for r in te]); pl = np.zeros(len(te))
    for w in sorted(set(wk)):
        past = np.where(wk < w)[0]; now = np.where(wk == w)[0]
        if len(past) < ONLINE["min_session_votes"]:
            past = past[:0]
        sw = np.concatenate([np.ones(len(tr)), np.full(len(past), ONLINE["session_weight"])])
        pl[now] = linear_fn(tr + [te[i] for i in past], [te[i] for i in now], dict(LINEAR, sample_w=sw))
    lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    a = ONLINE["linear_share"]
    return 1 / (1 + np.exp(-((1 - a) * lo(pt) + a * lo(pl))))
