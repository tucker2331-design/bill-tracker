#!/usr/bin/env python3
"""Does the AI checklist (llm_rubric.py) improve member votes on top of arm C? (2026-10-26)
Inputs per vote, from the bill's checklist crossed with the voter's position:
  own / other   the voter's party's support rating and the other party's ((x - 50) / 50)
  c, k          consensus and set-aside risk ((x - 50) / 50)
  flags         cost prog bus loc ins study crim tech local
  x voter party (Democrat +1 / Republican -1), x same party as patron (+1 / -1), x voter's party is majority
  topic         one-hot x voter party
Ridge logistic on top of arm C's log-odds. Learned on one year, scored on the other, both directions.
Reported: ALL votes (accuracy, log loss), the hard third (arm C can't-call), calls at |p - .5| >= .31 (count, wrong),
and calls at equal wrong calls.  Bills without a checklist keep arm C unchanged (counted).
Run: python3 rubric_eval.py [lam]
"""
from __future__ import annotations
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, llm_rubric as RB

FLAGS = ["cost", "prog", "bus", "loc", "ins", "study", "crim", "tech", "local"]
TOPICS = ["elections", "guns", "abortion_health_rights", "criminal_justice", "immigration", "labor", "energy_environment",
          "taxes", "education", "health_insurance", "health_other", "housing", "business_regulation", "local_government",
          "transportation", "gambling", "cannabis_alcohol", "civil_rights", "government_operations", "agriculture", "other"]


def feats(r, a):
    dem = 1.0 if r["party"] == "Democratic" else -1.0 if r["party"] == "Republican" else 0.0
    same = 1.0 if r["same"] else -1.0; maj = 1.0 if r["maj"] else -1.0
    own = ((a["d"] if dem > 0 else a["g"]) - 50) / 50 if dem else 0.0
    oth = ((a["g"] if dem > 0 else a["d"]) - 50) / 50 if dem else 0.0
    c = (a["c"] - 50) / 50; k = (a["k"] - 50) / 50
    fl = [float(a.get(f, 0)) for f in FLAGS]
    base = [own, oth, c, k, own * maj, own * same, k * same, c * same]
    x = base + fl + [f * dem for f in fl] + [f * same for f in fl] + [f * maj for f in fl]
    t = a.get("topic", "other"); x += [dem * (t == tp) for tp in TOPICS]
    return x


def data(split, R):
    te, _a, _b = G.load(split); pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
    has = np.array([tuple(r["bill"]) in R and not R[tuple(r["bill"])].get("r") for r in te])
    X = np.array([feats(r, R[tuple(r["bill"])]) if h else [0.0] * len(feats(r, {"d": 50, "g": 50, "c": 50, "k": 50}))
                  for r, h in zip(te, has)])
    p = np.clip(pC, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)), X, np.array([r["y"] for r in te], float), has


def fit(off, X, y, lam):
    b = np.zeros(X.shape[1])
    for _ in range(40):
        p = 1 / (1 + np.exp(-(off + X @ b)))
        b += np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]) + lam * np.eye(len(b)), X.T @ (y - p) - lam * b)
    return b


def report(name, p0, p1, y, has):
    ll = lambda p: float(-(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1))).mean())
    r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1); hard = np.abs(p0 - .5) < .31
    c0 = ~hard; c1 = np.abs(p1 - .5) >= .31; w0 = int((c0 & ~r0).sum())
    o = np.argsort(-np.abs(p1 - .5)); n_eq = int(np.searchsorted(np.cumsum(~r1[o]), w0 + 1))
    print(f"{name}: {len(y)} votes ({has.mean():.0%} with a checklist)")
    print(f"   all votes   right {r0.mean():.4f} -> {r1.mean():.4f}   log loss {ll(p0):.4f} -> {ll(p1):.4f}")
    print(f"   hard third  right {r0[hard].mean():.4f} -> {r1[hard].mean():.4f}  ({hard.sum()} votes)")
    print(f"   calls       {c0.sum()} wrong {w0} -> {c1.sum()} wrong {int((c1 & ~r1).sum())};  at <= {w0} wrong: {c0.sum()} -> {n_eq} calls")


def main(lam):
    R = RB.load(); print(f"checklists loaded: {len(R)} bills (recognized: {sum(1 for a in R.values() if a.get('r'))})")
    D = {s: data(s, R) for s in ("confirm", "repeat")}
    for a, b in (("confirm", "repeat"), ("repeat", "confirm")):
        off, X, y, has = D[a]; w = fit(off[has], X[has], y[has], lam)
        off, X, y, has = D[b]; p0 = 1 / (1 + np.exp(-off)); p1 = 1 / (1 + np.exp(-(off + X @ w)))
        report(f"learn {a} -> score {b}", p0, p1, y, has)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 30.0)
