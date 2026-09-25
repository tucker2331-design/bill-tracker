#!/usr/bin/env python3
"""Gradient-boosted decision trees for binary outcomes, numpy only (no sklearn/lightgbm here).

Histogram method: each feature is cut into <= 32 quantile bins (fit on TRAIN only). Each round fits one
depth-limited tree to the logistic gradient/hessian; a split's gain is the standard second-order gain
  G_L^2/(H_L+lam) + G_R^2/(H_R+lam) - G^2/(H+lam).
Early stopping on a VALIDATION set, never the test set. Self-test at the bottom recovers an interaction
(XOR-like) that a logistic model cannot represent.
"""
from __future__ import annotations
import numpy as np


class GBM:
    def __init__(self, rounds=400, depth=4, lr=0.08, lam=5.0, min_h=20.0, bins=32, patience=30):
        self.rounds, self.depth, self.lr, self.lam, self.min_h, self.nbins, self.patience = \
            rounds, depth, lr, lam, min_h, bins, patience

    def _bin(self, X):
        return np.stack([np.searchsorted(self.cuts[j], X[:, j], side="right") for j in range(X.shape[1])],
                        axis=1).astype(np.int16)

    def fit(self, X, y, Xv=None, yv=None):
        X = np.asarray(X, float); y = np.asarray(y, float)
        self.cuts = [np.unique(np.quantile(X[:, j], np.linspace(0, 1, self.nbins + 1)[1:-1])) for j in range(X.shape[1])]
        B = self._bin(X)
        p0 = np.clip(y.mean(), 1e-4, 1 - 1e-4)
        self.base = np.log(p0 / (1 - p0))
        F = np.full(len(y), self.base)
        self.trees = []
        if Xv is not None:
            Bv = self._bin(np.asarray(Xv, float)); Fv = np.full(len(yv), self.base); best = (np.inf, 0)
        for r in range(self.rounds):
            p = 1 / (1 + np.exp(-F)); g = p - y; h = np.maximum(p * (1 - p), 1e-6)
            tree = self._grow(B, g, h)
            F += self.lr * self._apply(tree, B)
            self.trees.append(tree)
            if Xv is not None:
                Fv += self.lr * self._apply(tree, Bv)
                pv = np.clip(1 / (1 + np.exp(-Fv)), 1e-6, 1 - 1e-6)
                ll = -np.mean(yv * np.log(pv) + (1 - yv) * np.log(1 - pv))
                if ll < best[0] - 1e-6:
                    best = (ll, r + 1)
                elif r + 1 - best[1] >= self.patience:
                    break
        if Xv is not None:
            self.trees = self.trees[:best[1]]; self.best_val_ll = best[0]
        return self

    def _grow(self, B, g, h):
        nodes = [(np.arange(len(g)), 0, 0)]      # (row idx, depth, node id)
        tree = {}
        nid = 1
        while nodes:
            idx, dep, me = nodes.pop()
            G, H = g[idx].sum(), h[idx].sum()
            if dep >= self.depth or H < 2 * self.min_h:
                tree[me] = ("leaf", -G / (H + self.lam)); continue
            best = (0.0, None)
            base = G * G / (H + self.lam)
            for j in range(B.shape[1]):
                bj = B[idx, j]
                gs = np.bincount(bj, weights=g[idx], minlength=self.nbins + 1)
                hs = np.bincount(bj, weights=h[idx], minlength=self.nbins + 1)
                GL, HL = np.cumsum(gs)[:-1], np.cumsum(hs)[:-1]
                GR, HR = G - GL, H - HL
                ok = (HL >= self.min_h) & (HR >= self.min_h)
                if not ok.any():
                    continue
                gain = np.where(ok, GL * GL / (HL + self.lam) + GR * GR / (HR + self.lam) - base, -1)
                k = int(np.argmax(gain))
                if gain[k] > best[0]:
                    best = (gain[k], (j, k))
            if best[1] is None:
                tree[me] = ("leaf", -G / (H + self.lam)); continue
            j, k = best[1]
            left = B[idx, j] <= k
            l, r = nid, nid + 1; nid += 2
            tree[me] = ("split", j, k, l, r)
            nodes.append((idx[left], dep + 1, l)); nodes.append((idx[~left], dep + 1, r))
        return tree

    def _apply(self, tree, B):
        out = np.zeros(len(B)); stack = [(0, np.arange(len(B)))]
        while stack:
            me, idx = stack.pop()
            node = tree[me]
            if node[0] == "leaf":
                out[idx] = node[1]; continue
            _, j, k, l, r = node
            m = B[idx, j] <= k
            stack.append((l, idx[m])); stack.append((r, idx[~m]))
        return out

    def predict(self, X):
        B = self._bin(np.asarray(X, float))
        F = np.full(len(B), self.base)
        for t in self.trees:
            F += self.lr * self._apply(t, B)
        return 1 / (1 + np.exp(-F))

    def importance(self, n_features):
        """Split counts per feature -- crude but honest."""
        c = np.zeros(n_features)
        for t in self.trees:
            for node in t.values():
                if node[0] == "split":
                    c[node[1]] += 1
        return c


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    X = rng.normal(size=(20000, 3)); y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(float)
    flip = rng.random(20000) < 0.05; y[flip] = 1 - y[flip]
    m = GBM(rounds=200, depth=3).fit(X[:15000], y[:15000], X[15000:], y[15000:])
    acc = ((m.predict(X[15000:]) > .5) == y[15000:]).mean()
    print(f"self-test XOR (95% learnable ceiling): accuracy {acc:.3f} after {len(m.trees)} trees")
