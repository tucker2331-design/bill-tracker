#!/usr/bin/env python3
"""All the weak signals together (owner, 2026-10-23: "keep exhausting non ai methods and combinations of them").

Every signal was rejected ALONE. Many weak, partly independent signals can still add up, and some may only matter in
combination (e.g. a cost x a crowded docket x the minority). Two ways to combine, both on the locked model's
out-of-sample predictions, learning years 2022+ (the no-2021 rule fixed in rerun_no2021.py), scored 2024 + 2025
(accept at pooled z >= 3), 2026 as replication:
  linear   one ridge logistic layer over ALL signal inputs at once (ridge 30 / 100)
  trees    shallow boosted trees on the residual, starting from the locked model's log-odds, over all signal inputs
           plus the member model's own inputs (lets combinations appear)
Signals: each module's own signal function, captured exactly as it was rejected (rerun_no2021.capture).
Run: python3 mega_stack.py
"""
from __future__ import annotations
import sys, os, math, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV, rerun_no2021 as RR, booster_2027 as BC

MODULES = ["cosponsor_ties:-", "fine_subjects:-", "chair_patron:-", "docket_load:-", "budget_signal:-",
           "strategy_traces:fund", "strategy_traces:fight", "strategy_traces:lownum",
           "private_traces:draft", "private_traces:governor", "private_traces:election",
           "sub_probe:drop", "sub_probe:memsub", "withdraw_probe:test"]
lo = RR.lo


def main():
    sigs = []
    for m in MODULES:
        got = RR.capture(m)
        sigs += [(m + "|" + str(i), s) for i, (s, _l, _r) in enumerate(got)]
        print(f"  captured {m}: {len(got)}", flush=True)
    memo = {}
    def allsig(r):
        key = (r["yr"], r["bill"], r["who"])
        if key in memo:
            return memo[key]
        out = {}
        for tag, s in sigs:
            for k, v in s(r).items():
                out[f"{tag}:{k}"] = v
        memo[key] = out
        return out
    for ridge in ([] if os.environ.get("TREES_ONLY") else [30.0, 100.0]):
        try:
            RR.evaluate(allsig, f"ALL SIGNALS, ONE RIDGE LAYER (ridge {ridge:g})", ridge=ridge)
        except RuntimeError as e:                  # recorded, not hidden: ~60 collinear inputs, Newton does not settle
            print(f"ALL SIGNALS, ONE RIDGE LAYER (ridge {ridge:g}): FIT FAILED -- {e}", flush=True)
    # trees on the residual
    B = {t: v for t, v in AC.base_preds().items() if t >= 2022}
    B[2026] = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    D = {}
    for t, (te, p) in B.items():
        S = [allsig(r) for r in te]; names = sorted(S[0])
        F = np.array([[s[n] for n in names] for s in S], float)
        N = np.array([[r[c] for c in FV.NUM] for r in te], float)
        D[t] = (te, p, lo(p), np.column_stack([F, N]), np.array([r["y"] for r in te], float))
    diffs = {}
    print("ALL SIGNALS + MEMBER INPUTS, RESIDUAL TREES (60 rounds, depth 3, lr .03)")
    for t in (2024, 2025, 2026):
        fy = [u for u in RR.FIT_YEARS if u < t]
        X = np.vstack([D[u][3] for u in fy]); y = np.concatenate([D[u][4] for u in fy]); F0 = np.concatenate([D[u][2] for u in fy])
        m = BC.Offset(depth=3, lr=.03, rounds=60, min_h=50.0).fit_from(X, y, F0)
        te, p, lg, Xt, yt = D[t]
        p1 = 1 / (1 + np.exp(-(lg + m.delta(Xt))))
        g = collections.defaultdict(float)
        for r, a, c in zip(te, AC._ll(p, yt), AC._ll(p1, yt)):
            g[str(r["bill"])] += a - c
        d = np.array(list(g.values())); diffs[t] = d
        hard = np.argsort(np.abs(p - .5))[:len(p) // 3]; r0 = (p >= .5) == (yt == 1); r1 = (p1 >= .5) == (yt == 1)
        c0 = np.abs(p - .5) >= .3; c1 = np.abs(p1 - .5) >= .3
        print(f"    {t}: member {r0.mean():.4f}->{r1.mean():.4f}  hardest third {r0[hard].mean():.4f}->{r1[hard].mean():.4f}  "
              f"wrong calls {(c0 & ~r0).sum()}->{(c1 & ~r1).sum()} (calls {c0.mean():.1%}->{c1.mean():.1%})  "
              f"z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}", flush=True)
    d = np.concatenate([diffs[2024], diffs[2025]])
    print(f"    POOLED 2024+2025: z = {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}; 2026 replication z "
          f"{diffs[2026].mean() / (diffs[2026].std(ddof=1) / math.sqrt(len(diffs[2026]))):+.1f}", flush=True)


if __name__ == "__main__":
    main()
