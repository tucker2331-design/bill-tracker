#!/usr/bin/env python3
"""A small tree model that learns ONLY this session's leftover errors, on top of arm B (owner: "keep working towards
our goal"). Residual errors change shape from year to year (2026: venue and chamber; 2025: summary-wording scores;
2024: subject history) -- the session's own drift. Before each session week: boost a few shallow trees on that
session's earlier votes, STARTING from arm B's log-odds (so the trees only model what B gets wrong this session).
Shrinkage `lr`, `rounds`, `depth` keep it small; below MIN session votes nothing changes.
Run: python3 session_booster.py <rounds> <depth> <lr>
"""
from __future__ import annotations
import sys, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, first_vote as FV, gains as G, accept as AC, gbm
from online_relinear import week

MIN = 3000
GATED = os.environ.get("BOOST_GATED") == "1"
BASE = "online_relinear_{split}_W3.0_s0.3_m3000"


class Offset(gbm.GBM):
    def fit_from(self, X, y, F0):
        X = np.asarray(X, float); y = np.asarray(y, float); n, k = X.shape
        self.cuts = [np.unique(np.quantile(X[:, j], np.linspace(0, 1, self.nbins + 1)[1:-1])) for j in range(k)]
        B = self._bin(X); F = F0.copy(); self.trees = []
        for _ in range(self.rounds):
            p = 1 / (1 + np.exp(-F)); tree = self._grow(B, p - y, np.maximum(p * (1 - p), 1e-6))
            F += self.lr * self._apply(tree, B); self.trees.append(tree)
        return self

    def delta(self, X):
        B = self._bin(np.asarray(X, float)); d = np.zeros(len(B))
        for tree in self.trees:
            d += self.lr * self._apply(tree, B)
        return d


def main(rounds, depth, lr):
    rc = FV.assemble()["rc"]; pooled = []
    for split in ("choose", "confirm", "repeat"):
        te, p0, p1 = G.load(split)
        pB = np.load(os.path.join(L.PRED, BASE.format(split=split) + ".npy"))
        lg = np.log(np.clip(pB, 1e-6, 1 - 1e-6) / (1 - np.clip(pB, 1e-6, 1 - 1e-6)))
        X = np.array([[r[c] for c in FV.NUM] for r in te], float); y = np.array([r["y"] for r in te], float)
        wk = np.array([week(rc[r["bill"]][0][0]) for r in te]); F = lg.copy()
        weeks = sorted(set(wk)); used = 0
        for j, w in enumerate(weeks):
            past = wk < w; now = wk == w
            if past.sum() < MIN:
                continue
            if GATED:
                # self-check (fail-open to B): learn on the weeks before last week, score last week; apply only if
                # that would have helped. Uses nothing from week w.
                prev = wk == weeks[j - 1]; early = wk < weeks[j - 1]
                if early.sum() < MIN:
                    continue
                chk = Offset(depth=depth, lr=lr, rounds=rounds, min_h=50.0).fit_from(X[early], y[early], lg[early])
                q = 1 / (1 + np.exp(-(lg[prev] + chk.delta(X[prev]))))
                if AC._ll(q, y[prev]).mean() >= AC._ll(pB[prev], y[prev]).mean():
                    continue
            m = Offset(depth=depth, lr=lr, rounds=rounds, min_h=50.0).fit_from(X[past], y[past], lg[past])
            F[now] = lg[now] + m.delta(X[now]); used += 1
        print(f"  {L.SPLITS[split][1]}: booster applied in {used} of {len(weeks)} weeks", flush=True)
        p2 = 1 / (1 + np.exp(-F))
        hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        room = lambda p: np.mean([(p[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
        r1 = (pB >= .5) == (y == 1); r2 = (p2 >= .5) == (y == 1)
        d = collections.defaultdict(float)
        for r, a, c in zip(te, AC._ll(pB, y), AC._ll(p2, y)):
            d[str(r["bill"])] += a - c
        d = np.array(list(d.values())); pooled.append(d)
        np.save(os.path.join(L.PRED, f"session_booster_{split}_r{rounds}_d{depth}_lr{lr}{'_gated' if GATED else ''}.npy"), p2)
        print(f"{L.SPLITS[split][1]} r{rounds} d{depth} lr{lr}{' gated' if GATED else ''}: member {r1.mean():.4f}->{r2.mean():.4f}  hardest third "
              f"{r1[hard].mean():.4f}->{r2[hard].mean():.4f}  room {room(pB):.4f}->{room(p2):.4f}  "
              f"z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}", flush=True)
    d = np.concatenate(pooled)
    print(f"POOLED r{rounds} d{depth} lr{lr}{' gated' if GATED else ''}: z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]))
