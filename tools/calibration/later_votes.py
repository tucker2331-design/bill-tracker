#!/usr/bin/env python3
"""Does training on LATER committee votes improve first-vote predictions? (fv_all.py rows; owner 2026-10-21)
Same locked tree settings (depth 6, lr .03, 260 rounds); trained on first votes + later committee/subcommittee votes of
the training years, weight `w` on the later ones, `first` flag as an extra input; scored on the test year's FIRST votes
against the locked model's cached predictions (same rows, same order).
Run: python3 later_votes.py <split> <w> [noflag]
"""
from __future__ import annotations
import sys, os, pickle
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV, levers as L

ALL = os.path.join(HERE, ".cache", "fv_rows_all.pkl")
BAGS = int(os.environ.get("LATER_BAGS", "0"))


def fn_factory(w, flag):
    rows = [r for r in pickle.load(open(ALL, "rb")) if r["y"] >= 0]
    cols = list(FV.NUM) + (["first"] if flag else [])
    def fn(tr, te, s):
        years = {r["yr"] for r in tr}
        T = [r for r in rows if r["yr"] in years]
        X = lambda rs: np.array([[r.get(c, 1) for c in cols] for r in rs], float)   # test rows are first votes: first=1
        wt = np.array([1.0 if r["first"] else w for r in T]); XT, yT, Xe = X(T), np.array([r["y"] for r in T], float), X(te)
        if BAGS:                                     # the adopted bagged trees (8 x 50% rows / 50% inputs)
            return np.mean([L.GBMX(depth=6, lr=.03, rounds=260, subsample=.5, colsample=.5, seed=b).fit(XT, yT, wt).predict(Xe)
                            for b in range(BAGS)], axis=0)
        return L.GBMX(depth=6, lr=.03, rounds=260, seed=0).fit(XT, yT, wt).predict(Xe)
    return fn


if __name__ == "__main__":
    split, w = sys.argv[1], float(sys.argv[2]); flag = "noflag" not in sys.argv
    L.run("later", fn_factory(w, flag), {"w": w, "flag": flag, **({"bags": BAGS} if BAGS else {})}, (split,))
