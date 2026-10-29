#!/usr/bin/env python3
"""Know when we will be wrong (owner, 2026-10-21: "limiting the scenarios we guess wrong is supremely important ... try
to then predict that we cant predict it instead of allowing our model to knowingly fail").

Every member vote gets either a CALL (yes / no) or "can't call". Two ways to decide which votes to call:
  confidence   call the votes whose predicted chance is furthest from 50/50 (arm C's own p)
  error model  a second model predicts P(arm C is wrong) from: arm C's confidence, whether its two halves (bagged
               trees vs the linear refit) disagree, how far the session booster moved it, the bill's risk of being
               dropped at its first vote (drop_model.py, year-ahead), and the member model's inputs
Year-ahead: the error model for 2025 learns from 2024; for 2026 from 2024 + 2025. The CUTOFF is also fixed on the
earlier years: the loosest cutoff whose called votes were right >= TARGET of the time there, then applied unchanged.
Run: python3 abstain.py [target]   (default 0.95)
"""
from __future__ import annotations
import sys, os, pickle
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, first_vote as FV, gbm

BAG = {"depth": 6, "subsample": 0.5, "colsample": 0.5, "bags": 8}
lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def year(split, drop):
    te, p0, p1 = G.load(split)
    pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
    pB = np.load(os.path.join(L.PRED, f"online_relinear_{split}_W3.0_s0.3_m3000.npy"))
    pb = np.load(os.path.join(L.PRED, f"gbm_{split}_{L._key(BAG)}.npy"))
    pl = (lo(pB) - .7 * lo(pb)) / .3                                   # the linear half, recovered in log-odds
    y = np.array([r["y"] for r in te]); wrong = ((pC >= .5) != (y == 1)).astype(float)
    dp = np.array([drop.get(r["bill"], np.nan) for r in te]); dp = np.where(np.isnan(dp), .1, dp)
    extra = np.column_stack([np.abs(lo(pC)), lo(pC), np.abs(lo(pb) - pl), np.abs(lo(pC) - lo(pB)), lo(dp),
                             lo(dp) * np.array([r["same"] for r in te])])
    X = np.column_stack([extra, np.array([[r[c] for c in FV.NUM] for r in te], float)])
    return te, pC, y, wrong, X, p0


def cutoff(score, wrong, target):
    """Loosest threshold on `score` (lower = safer) whose called votes are right >= target."""
    o = np.argsort(score); acc = np.cumsum(1 - wrong[o]) / np.arange(1, len(o) + 1)
    ok = np.where(acc >= target)[0]
    return score[o][ok.max()] if len(ok) else -np.inf


def main(target):
    drop = pickle.load(open(os.path.join(HERE, ".cache", "drop_p.pkl"), "rb"))
    D = {sp: year(sp, drop) for sp in ("choose", "confirm", "repeat")}
    for test, train in (("confirm", ["choose"]), ("repeat", ["choose", "confirm"])):
        te, pC, y, wrong, X, p0 = D[test]
        Xtr = np.vstack([D[s][4] for s in train]); wtr = np.concatenate([D[s][3] for s in train])
        m = gbm.GBM(depth=4, lr=.05, rounds=200).fit(Xtr, wtr)
        e_te = m.predict(X)
        # the cutoff must be set on scores the error model did not learn from: 2 folds split by BILL
        bills = np.array([hash(str(r["bill"])) % 2 for s in train for r in D[s][0]]); e_tr = np.zeros(len(wtr))
        for f in (0, 1):
            e_tr[bills == f] = gbm.GBM(depth=4, lr=.05, rounds=200).fit(Xtr[bills != f], wtr[bills != f]).predict(Xtr[bills == f])
        c_te = -np.abs(pC - .5); c_tr = np.concatenate([-np.abs(D[s][1] - .5) for s in train])
        ty = L.SPLITS[test][1]
        print(f"\n=== {ty} (error model and cutoffs learned on {', '.join(str(L.SPLITS[s][1]) for s in train)}), target {target:.0%}")
        for name, s_tr, s_te in (("confidence", c_tr, c_te), ("error model", e_tr, e_te)):
            t = cutoff(s_tr, wtr, target); call = s_te <= t
            print(f"  {name:12s}: called {call.mean():.1%} of votes, right {1 - wrong[call].mean():.2%}; "
                  f"can't call {(~call).mean():.1%} (would have been right {1 - wrong[~call].mean():.1%})")
            o = np.argsort(s_te)
            print("     accuracy calling the safest k%: " + "  ".join(
                f"{k}% {1 - wrong[o[:len(o) * k // 100]].mean():.3f}" for k in (50, 60, 70, 80, 90)))


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.95)
