#!/usr/bin/env python3
"""Calls with a statistical guarantee (owner, 2026-10-23: "do more research on statistical determination").

From the selective-prediction literature (risk-coverage, El-Yaniv & Wiener; "Learn then Test" / conformal risk
control, Angelopoulos & Bates): instead of a cutoff that merely WORKED on earlier years, pick the loosest cutoff whose
error rate among calls is <= ALPHA with confidence 1 - DELTA on the calibration years -- an exact binomial
(Clopper-Pearson) upper bound, scanned from strict to loose and stopped at the first failure (fixed-sequence testing,
so the guarantee holds over the whole scan). The guarantee assumes the new year resembles the calibration years;
the test year shows how far it holds.
Mondrian version: a separate guaranteed cutoff per group (venue x side), so EVERY group's calls meet the target, not
just the average (subcommittee other-party votes no longer hide behind easy Senate votes).
Arm C predictions; calibration = earlier years (2025 <- 2024; 2026 <- 2024 + 2025).
Run: python3 guaranteed_calls.py [alpha] [delta]
"""
from __future__ import annotations
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G

ALPHA = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05
DELTA = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05


def binom_cdf(k, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if k < n else 1.0
    lp, lq = math.log(p), math.log1p(-p); tot = -math.inf
    for i in range(k + 1):
        t = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
        tot = t if tot == -math.inf else max(tot, t) + math.log1p(math.exp(-abs(tot - t)))
    return math.exp(tot)


def upper(k, n, delta):
    """Clopper-Pearson one-sided upper bound on the error rate: the p with P(X <= k | n, p) = delta."""
    a, b = k / n, 1.0
    for _ in range(50):
        m = (a + b) / 2
        if binom_cdf(k, n, m) > delta: a = m
        else: b = m
    return b


BONF = os.environ.get("BONF") == "1"


def cutoff(conf, wrong, alpha, delta):
    """Loosest |p - .5| cutoff passing the bound. Default: scan strict -> loose, stop at the first failure (fixed
    sequence). BONF=1: test every cutoff at delta / (number of cutoffs) and take the loosest that passes (Bonferroni;
    valid without the monotone stopping rule, more conservative per test)."""
    grid = np.round(np.arange(.49, .0, -.01), 2); best = None
    d = delta / len(grid) if BONF else delta
    for t in grid:
        m = conf >= t; n = int(m.sum())
        if n < 30:
            continue
        if upper(int(wrong[m].sum()), n, d) <= alpha:
            best = t
        elif not BONF:
            break
    return best


def load(split):
    te, p0, p1 = G.load(split); p = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
    y = np.array([r["y"] for r in te]); grp = np.array([("sub" if r["ven_sub"] else "com" if r["ven_com"] else "floor") + "/" +
                                                        ("own" if r["same"] else "other") for r in te])
    return np.abs(p - .5), (p >= .5) != (y == 1), grp


def main():
    D = {s: load(s) for s in ("choose", "confirm", "repeat")}
    print(f"target: calls wrong <= {ALPHA:.0%}, with {1 - DELTA:.0%} confidence (exact binomial bound)")
    for test, cal in (("confirm", ["choose"]), ("repeat", ["choose", "confirm"])):
        c, w, g = D[test]; cc = np.concatenate([D[s][0] for s in cal]); cw = np.concatenate([D[s][1] for s in cal])
        cg = np.concatenate([D[s][2] for s in cal]); ty = L.SPLITS[test][1]
        t = cutoff(cc, cw, ALPHA, DELTA); call = c >= t
        print(f"\n{ty}  one cutoff (|p-.5| >= {t}): called {call.mean():.1%}, right {1 - w[call].mean():.2%}, wrong calls {int((call & w).sum())}")
        callm = np.zeros(len(c), bool); rows = []
        for k in sorted(set(cg)):
            tk = cutoff(cc[cg == k], cw[cg == k], ALPHA, DELTA); m = g == k
            if tk is not None:
                callm[m] = c[m] >= tk
            sel = m & callm
            rows.append(f"    {k:12s} cutoff {tk if tk is not None else 'none':>5}  called {sel.sum() / max(1, m.sum()):5.1%}  "
                        f"right {1 - w[sel].mean() if sel.any() else float('nan'):.2%}")
        print(f"    per group (venue x side): called {callm.mean():.1%}, right {1 - w[callm].mean():.2%}, wrong calls {int((callm & w).sum())}")
        print("\n".join(rows))


if __name__ == "__main__":
    main()
