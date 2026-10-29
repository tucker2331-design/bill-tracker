#!/usr/bin/env python3
"""A vetoed bill comes back (2026-10-23). In 2026, 70 bills with a first vote carried exactly the title of a bill vetoed
in 2024 or 2025 (69 Democratic, after the governor changed party); other-party members voted yes 32% vs 48%
predicted, and were called right only 63%. Earlier years have few such refiles, so a year-ahead model cannot learn the
weight -- but the WEEKLY refit of the linear half (arm B) can learn it from the session's own earlier weeks.
Input: ve_ref = this bill has the exact title of a bill vetoed in either of the two previous sessions; crossed with
side by the linear model. Arm B is rerun with that one extra input; trees unchanged (saved bagged predictions).
Run: python3 veto_refile.py
"""
from __future__ import annotations
import sys, os, re, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, first_vote as FV, accept as AC
from corpus import load
from online_relinear import week

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
VETO = re.compile(r"vetoed by governor|governor'?s veto|veto sustained", re.I)
norm = lambda t: re.sub(r"\W+", " ", (t or "").lower()).strip()
vet = collections.defaultdict(set)
for k, b in corpus.items():
    if any(VETO.search(t) for _d, t, _c in b["actions"]):
        vet[int(k[0][:4])].add(norm(b["title"]))
def ve_ref(r):
    y = r["yr"]; t = norm(corpus[r["bill"]]["title"])
    return float(t in vet.get(y - 1, set()) or t in vet.get(y - 2, set()))


def main():
    rc = FV.assemble()["rc"]; BAG = {"depth": 6, "subsample": 0.5, "colsample": 0.5, "bags": 8}
    LIN = {"hinges": 3, "lam": 10, "pairs": 8, "extra": ["ve_ref"]}
    lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    for r in L.rows():
        r["ve_ref"] = ve_ref(r)
    for split in ("choose", "confirm", "repeat"):
        trn, ty = L.SPLITS[split]; tr = [r for r in L.rows() if r["yr"] in trn]; te, p0, p1 = G.load(split)
        for r in te:
            r["ve_ref"] = ve_ref(r)
        pB = np.load(os.path.join(L.PRED, f"online_relinear_{split}_W3.0_s0.3_m3000.npy"))
        pb = np.load(os.path.join(L.PRED, f"gbm_{split}_{L._key(BAG)}.npy"))
        wk = np.array([week(rc[r["bill"]][0][0]) for r in te]); pl = np.zeros(len(te))
        for w in sorted(set(wk)):
            past = np.where(wk < w)[0]; now = np.where(wk == w)[0]
            if len(past) < 3000:
                past = past[:0]
            sw = np.concatenate([np.ones(len(tr)), np.full(len(past), 3.0)])
            pl[now] = L.linear_fn(tr + [te[i] for i in past], [te[i] for i in now], dict(LIN, sample_w=sw))
        p2 = 1 / (1 + np.exp(-(.7 * lo(pb) + .3 * lo(pl))))
        y = np.array([r["y"] for r in te]); hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        room = lambda p: np.mean([((p[I] >= .5).sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
        r1 = (pB >= .5) == (y == 1); r2 = (p2 >= .5) == (y == 1); c1 = np.abs(pB - .5) >= .3; c2 = np.abs(p2 - .5) >= .3
        v = np.array([r["ve_ref"] == 1 for r in te])
        d = collections.defaultdict(float)
        for r, a, c in zip(te, AC._ll(pB, y), AC._ll(p2, y)):
            d[str(r["bill"])] += a - c
        d = np.array(list(d.values()))
        np.save(os.path.join(L.PRED, f"veto_refile_{split}.npy"), p2)
        print(f"{ty} (refile votes {v.sum()}): member {r1.mean():.4f}->{r2.mean():.4f}  hardest third {r1[hard].mean():.4f}->{r2[hard].mean():.4f}  "
              f"room {room(pB):.4f}->{room(p2):.4f}  calls {c1.mean():.1%}->{c2.mean():.1%} wrong {(c1 & ~r1).sum()}->{(c2 & ~r2).sum()}  "
              f"on refiles {r1[v].mean() if v.any() else float('nan'):.3f}->{r2[v].mean() if v.any() else float('nan'):.3f}  "
              f"z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}", flush=True)


if __name__ == "__main__":
    main()
