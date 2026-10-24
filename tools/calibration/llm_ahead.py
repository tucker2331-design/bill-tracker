#!/usr/bin/env python3
"""AI bill-reading, year-ahead and coverage (owner 2026-10-24: "expand coverage ... take more out of the undesirable
1/3rd and into the highly marketable and useful 2/3"). Opus ratings (helper agents, blinded): 100 bills 2024
(.cache/llm_ratings_opus.jsonl) to LEARN the weights; 150 + 150 'can't call'-heavy bills from 2025 / 2026
(.cache/llm_ratings_opus_2025.jsonl / _2026.jsonl) to TEST, weights unchanged.
Model on top of arm C:  logit p = logit(p_C) + b_D * (dem - 50)/50 [Democratic voters] + b_R * (rep - 50)/50 [Republicans]
Reported per test year, on the rated bills' first votes: accuracy; calls (|p - .5| >= .31) and wrong calls; and
COVERAGE AT EQUAL WRONG CALLS -- the most votes the new model can call (most confident first) while making no more
wrong calls than arm C makes at its own cutoff.  Run: python3 llm_ahead.py
"""
from __future__ import annotations
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G

lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def ratings(path, ids):
    out = {}
    for line in open(path):
        line = line.strip()
        if line.startswith("{"):
            d = json.loads(line); out[tuple(ids[d["id"]])] = d
    return out


def rows(split, R):
    te, p0, p1 = G.load(split); pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
    I = [i for i, r in enumerate(te) if r["bill"] in R and r["party"] in ("Democratic", "Republican")]
    xd = np.array([(R[te[i]["bill"]]["dem"] - 50) / 50 if te[i]["party"] == "Democratic" else 0.0 for i in I])
    xr = np.array([(R[te[i]["bill"]]["rep"] - 50) / 50 if te[i]["party"] == "Republican" else 0.0 for i in I])
    return lo(pC[I]), xd, xr, np.array([te[i]["y"] for i in I], float)


def fit(off, X, y, lam=1.0):
    b = np.zeros(X.shape[1])
    for _ in range(60):
        p = 1 / (1 + np.exp(-(off + X @ b)))
        b += np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]) + lam * np.eye(len(b)), X.T @ (y - p) - lam * b)
    return b


def main():
    i24 = json.load(open(os.path.join(HERE, ".cache", "llm_pilot_ids.json")))
    off, xd, xr, y = rows("choose", ratings(os.path.join(HERE, ".cache", "llm_ratings_opus.jsonl"), i24))
    b = fit(off, np.column_stack([xd, xr]), y)
    print(f"weights learned on 2024 (100 bills, {len(y)} votes): Democrats {b[0]:+.2f}, Republicans {b[1]:+.2f}")
    for split, yr in (("confirm", "2025"), ("repeat", "2026")):
        path = os.path.join(HERE, ".cache", f"llm_ratings_opus_{yr}.jsonl")
        if not os.path.exists(path):
            print(yr, "ratings not saved yet"); continue
        ids = json.load(open(os.path.join(HERE, ".cache", f"llm_pilot_ids_{yr}.json")))
        off, xd, xr, y = rows(split, ratings(path, ids))
        p0 = 1 / (1 + np.exp(-off)); p1 = 1 / (1 + np.exp(-(off + b[0] * xd + b[1] * xr)))
        r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1); c0 = np.abs(p0 - .5) >= .31; c1 = np.abs(p1 - .5) >= .31
        w0 = int((c0 & ~r0).sum()); o = np.argsort(-np.abs(p1 - .5)); cumw = np.cumsum(~r1[o]); n_eq = int(np.searchsorted(cumw, w0 + 1))
        print(f"{yr}: {len(y)} votes on rated bills | right {r0.mean():.3f} -> {r1.mean():.3f} | calls {c0.sum()} ({c0.mean():.0%}) wrong {w0} -> "
              f"calls {c1.sum()} ({c1.mean():.0%}) wrong {int((c1 & ~r1).sum())} | at no more than {w0} wrong calls: {c0.sum()} -> {n_eq} votes called "
              f"({c0.mean():.0%} -> {n_eq / len(y):.0%})")


if __name__ == "__main__":
    main()
