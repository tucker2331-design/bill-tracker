#!/usr/bin/env python3
"""Consensus words INSIDE the member model (how it would actually be used) -- rolling origin, 2021/2022/2024/2025.

consensus_words.py showed the word signal helps when stacked on top (z = 4.2 rolling, z = 4.0 replicated on 2026). Here
the per-bill scores become ordinary inputs to the gradient-boosted member model, each year's scores learned only from
EARLIER years' first votes (summary as introduced + title). Compared with the same model without them; per-bill paired
log loss pooled, z >= 3; fixed hardest third reported.
  --bigrams  also use two-word phrases (the P8c variant)
"""
from __future__ import annotations
import sys, os, re, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV, gbm, consensus_words as CW

BIGRAMS = "--bigrams" in sys.argv
if BIGRAMS:
    def toks(k):
        w = [x for x in re.findall(r"[a-z]{3,}", (CW.summ.get(k, "") + " " + CW.corpus.get(k, {}).get("title", "")).lower())
             if x not in CW.STOP]
        return set(x for x in w if len(x) >= 4) | {f"{a}_{b}" for a, b in zip(w, w[1:])}
    CW.toks = toks


def main():
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
    lab = CW.table(rows, CW.unan)
    years = sorted({r["yr"] for r in rows})
    sc = {y: CW.scorer(lab, y, 3) for y in years if y >= 2019}
    cache = {}
    for r in rows:
        k = (r["bill"], r["yr"])
        if k not in cache:
            cache[k] = sc[r["yr"]](r["bill"]) if r["yr"] in sc else [0.0, 0.0, 0.0]
        r["wy"], r["wn"], _ = cache[k]
    cols0 = list(FV.NUM); cols1 = cols0 + ["wy", "wn"]
    X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
    B = AC.base_preds(); diffs = []
    tag = "consensus words + two-word phrases" if BIGRAMS else "consensus words"
    for t, trn in AC.ORIGINS:
        if t == 2021:
            continue                                  # 2021's word scores would come from 2019-2020 only; scored like the others: 2022+
        tr = [r for r in rows if r["yr"] in trn and r["yr"] >= 2019]; te_rows, p0 = B[t]
        te = [r for r in rows if r["yr"] == t]
        assert [r["who"] for r in te] == [r["who"] for r in te_rows], "row order must match the cached baseline"
        p1 = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cols1), np.array([r["y"] for r in tr], float)).predict(X(te, cols1))
        y = np.array([r["y"] for r in te], float)
        d = collections.defaultdict(float)
        for r, a, c in zip(te, AC._ll(p0, y), AC._ll(p1, y)):
            d[str(r["bill"])] += a - c
        d = np.array(list(d.values())); diffs.append(d)
        hard = np.argsort(np.abs(p0 - .5))[:len(p0) // 3]
        r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1)
        print(f"  {tag} in the model, {t}: accuracy {r0.mean():.4f} -> {r1.mean():.4f}; hardest third "
              f"{r0[hard].mean():.4f} -> {r1[hard].mean():.4f}; per-bill log-loss gain {d.mean():+.5f}", flush=True)
    g, z = AC.pooled(diffs)
    print(f"POOLED ({tag} inside the model, 2022/2024/2025): gain {g:+.5f}, z = {z:.1f} -> {'ACCEPT' if z >= 3 else 'reject'}")


if __name__ == "__main__":
    main()
