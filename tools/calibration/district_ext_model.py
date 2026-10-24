#!/usr/bin/env python3
"""The 17 extended district measures INSIDE the model's linear half (owner 2026-10-24: externals). Same recipe as
arm A (bagged trees 80% + linear 20%, saved tree predictions), the linear half refit with the measures as extra
inputs (it crosses every input with side itself). Choose 2024, confirm 2025, repeat 2026; vs arm A.
Run: python3 district_ext_model.py
"""
from __future__ import annotations
import sys, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, accept as AC, district_ext_signal as D

BAG = {"depth": 6, "subsample": 0.5, "colsample": 0.5, "bags": 8}
LIN = {"hinges": 3, "lam": 10, "pairs": 8, "extra": [f"dz_{k}" for k in D.KEYS] + ["dz_has"]}
lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def attach(rows):
    for r in rows:
        z = D.district(r["yr"], "S" if r["chamber_S"] else "H", r["who"])
        for k in D.KEYS:
            r[f"dz_{k}"] = z[k] if z else 0.0
        r["dz_has"] = float(z is not None)


def main():
    attach(L.rows())
    for split in ("choose", "confirm", "repeat"):
        trn, ty = L.SPLITS[split]; tr = [r for r in L.rows() if r["yr"] in trn]; te, p0, pA = G.load(split); attach(te)
        pl = L.linear_fn(tr, te, LIN); pb = np.load(os.path.join(L.PRED, f"gbm_{split}_{L._key(BAG)}.npy"))
        p1 = 1 / (1 + np.exp(-(.8 * lo(pb) + .2 * lo(pl))))
        y = np.array([r["y"] for r in te]); hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
        ra, r1 = (pA >= .5) == (y == 1), (p1 >= .5) == (y == 1); ca, c1 = np.abs(pA - .5) >= .31, np.abs(p1 - .5) >= .31
        d = collections.defaultdict(float)
        for r, a, c in zip(te, AC._ll(pA, y), AC._ll(p1, y)):
            d[str(r["bill"])] += a - c
        d = np.array(list(d.values()))
        print(f"{ty} vs arm A: member {ra.mean():.4f}->{r1.mean():.4f}  hardest third {ra[hard].mean():.4f}->{r1[hard].mean():.4f}  "
              f"calls {ca.mean():.1%}->{c1.mean():.1%} wrong {(ca & ~ra).sum()}->{(c1 & ~r1).sum()}  z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}", flush=True)


if __name__ == "__main__":
    main()
