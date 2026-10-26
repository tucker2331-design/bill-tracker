#!/usr/bin/env python3
"""Pooled 2025 + 2026 coverage check for the block-level AI (2026-10-26). For the 2027 session the AI weight and the
call cutoff can be learned on BOTH rated years (1,834 can't-call votes) and then frozen for a 2027 forward test.
This prints, for guarantees of 81 / 85 / 90 right in 100 (one-sided 95% Clopper-Pearson, guaranteed_calls.cutoff):
the pooled weight, the cutoff, and how many hard votes would be called in each year at what accuracy.
Run: python3 llm_pool.py [answers tag]
"""
from __future__ import annotations
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv = sys.argv[:1]
import numpy as np
import llm_cover as C, knn_own as K, guaranteed_calls as GC


def main():
    D, _missing = C.data(); yrs = ("2025", "2026")
    o = np.array([a[2] for yy in yrs for a in D[yy]]); X = np.array([[a[3]] for yy in yrs for a in D[yy]])
    y = np.array([a[1] for yy in yrs for a in D[yy]], float); yr = np.array([yy for yy in yrs for _a in D[yy]])
    b = K.fit(o, X, y); p = 1 / (1 + np.exp(-(o + X @ b))); r = (p >= .5) == (y == 1)
    print(f"pooled: {len(y)} can't-call votes; AI weight {b[0]:+.2f}")
    for a in (0.19, 0.15, 0.10):
        t = GC.cutoff(np.abs(p - .5), ~r, a, 0.05); c = np.abs(p - .5) >= (t if t is not None else 9)
        per = ", ".join(f"{yy}: {(c & (yr == yy)).sum()} calls, {r[c & (yr == yy)].mean() if (c & (yr == yy)).any() else float('nan'):.0%} right"
                        for yy in yrs)
        print(f"  guarantee {100 - round(a * 100)} in 100: cutoff {t}; calls {c.sum()} ({c.mean():.1%}) right "
              f"{r[c].mean() if c.any() else float('nan'):.3f} | {per}")


if __name__ == "__main__":
    main()
