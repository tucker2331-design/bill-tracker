#!/usr/bin/env python3
"""The acceptance rule, as code -- five-perspective panel, 2026-09-29 ([[testing/panel_2026-09-29]]).

A change is accepted only if it lowers log loss across SEVERAL years together, judged per BILL (ballots on one bill
move together), pooled z >= 3. One lucky year no longer counts.

    base_preds()          the one-stage model's out-of-sample prediction for every first-vote ballot of 2021, 2022,
                          2024, 2025 -- each year from a model trained only on earlier years. Cached.
    stacked_year_ahead()  for an OUTSIDE signal too sparse to go inside the trees (an association's position, public
                          testimony): a logistic layer on [logit(model p)] vs [logit(model p) + signal], fitted on
                          earlier years' out-of-sample predictions and applied to the next year. Scored years 2022,
                          2024, 2025 (2021 has no earlier year to fit on). 2026 is never loaded.
"""
from __future__ import annotations
import sys, os, math, pickle, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np

ORIGINS = ((2021, (2019, 2020)), (2022, (2019, 2020, 2021)), (2024, (2019, 2020, 2021, 2022)),
           (2025, (2019, 2020, 2021, 2022, 2024)))
Z_ACCEPT = 3.0


def _ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def base_preds():
    import first_vote as FV, gbm
    CACHE = os.path.join(os.path.dirname(FV.ROWS), "accept_base_preds.pkl")   # beside the rows, outside git
    if os.path.exists(CACHE):
        c = pickle.load(open(CACHE, "rb"))
        if c.get("rows_mtime") == os.path.getmtime(FV.ROWS) and c.get("num") == list(FV.NUM):
            return c["by_year"]
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    out = {}
    for t, trn in ORIGINS:
        tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == t]
        p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(te))
        out[t] = (te, p)
        print(f"  base predictions {t}: {len(te)} ballots", flush=True)
    pickle.dump({"rows_mtime": os.path.getmtime(FV.ROWS), "num": list(FV.NUM), "by_year": out}, open(CACHE, "wb"))
    return out


def pooled(diffs):
    d = np.concatenate(diffs)
    return float(d.mean()), float(d.mean() / (d.std(ddof=1) / math.sqrt(len(d))))


def stacked_year_ahead(signal, label, only_covered=False, ridge=1.0):
    """signal(row) -> dict of numeric inputs (all 0 when the source says nothing). Returns (gain, z)."""
    import stats as ST
    B = base_preds()
    data = {}
    for t, (te, p) in B.items():
        lg = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
        S = [signal(r) for r in te]
        names = sorted(S[0])
        F = np.array([[s[n] for n in names] for s in S], float)
        cov = np.array([any(v != 0 for v in s.values()) for s in S])
        data[t] = (te, p, lg, F, names, cov)
    diffs, lines = [], []
    years = sorted(data)
    for i, t in enumerate(years[1:], 1):
        fit_years = years[:i]
        Xa = np.concatenate([data[y][2][:, None] for y in fit_years]); Xb = np.concatenate(
            [np.column_stack([data[y][2], data[y][3]]) for y in fit_years])
        ya = np.concatenate([np.array([r["y"] for r in data[y][0]], float) for y in fit_years])
        te, p, lg, F, names, cov = data[t]
        y = np.array([r["y"] for r in te], float)
        preds = []
        for Xtr, Xte, nm in ((Xa, lg[:, None], ["lg"]), (Xb, np.column_stack([lg, F]), ["lg"] + names)):
            # tol 1e-7 / 200 steps: stats.logit's default 1e-9 is below float precision on ~50k ballots and a rare
            # 0/1 input (similar_sponsor.py) made Newton oscillate there -- "did not converge" with no real problem
            f = ST.logit(Xtr, ya, nm, ridge=ridge, tol=1e-7, max_iter=200)
            b = np.array([f[n][0] for n in ["const"] + nm])
            with np.errstate(all="ignore"):
                preds.append(1 / (1 + np.exp(-(np.column_stack([np.ones(len(Xte)), Xte]) @ b))))
        p0, p1 = preds
        m = cov if only_covered else np.ones(len(y), bool)
        g = collections.defaultdict(float)
        for b_, a, c in zip(np.array([str(r["bill"]) for r in te])[m], _ll(p0, y)[m], _ll(p1, y)[m]):
            g[b_] += a - c
        d = np.array(list(g.values())); diffs.append(d)
        r0 = ((p0 >= .5) == (y == 1)); r1 = ((p1 >= .5) == (y == 1))
        lines.append(f"    {t}: covered ballots {cov.sum()} ({cov.mean():.1%}) on {len({str(r['bill']) for r, c in zip(te, cov) if c})} "
                     f"bills; accuracy covered {r0[cov].mean() if cov.any() else float('nan'):.4f} -> "
                     f"{r1[cov].mean() if cov.any() else float('nan'):.4f}; per-bill log-loss gain {d.mean():+.5f}")
    g, z = pooled(diffs)
    print(f"{label}")
    print("\n".join(lines))
    print(f"    POOLED 2022/2024/2025: per-bill log-loss gain {g:+.5f}, z = {z:.1f} -> "
          f"{'ACCEPT' if z >= Z_ACCEPT else 'reject'}", flush=True)
    return g, z


if __name__ == "__main__":
    base_preds()
