#!/usr/bin/env python3
"""Non-AI bar for the member-centric AI test (llm_member.py): the member's OWN first votes on the 6 most similar
earlier bills (same TF-IDF and date rule as the packets), as a signal on top of arm C, on ALL can't-call votes.
Signals: s1 = similarity-weighted own yes share (centred), s2 = the same share minus the own party's share on those
bills (how the member departs from the party on this kind of bill), s3 = weighted share of those bills the whole room
killed (<= 10% yes). Weights fit on 2025 can't-call votes, tested on 2026.  Run: python3 knn_own.py
"""
from __future__ import annotations
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import llm_member as M, levers as L, gains as G, first_vote as FV, summary_memory as SM
from corpus import load

lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def signals():
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    summ = SM.summaries(); rc = FV.assemble()["rc"]
    date = {k: v[0][0] for k, v in rc.items() if v and v[0][0] != "9999"}
    text = {k: M.blind(corpus[k]["title"] + ". " + summ[k]) for k in summ if k in corpus}
    vec = M._tfidf({k: [w for w in M.WORD.findall(t.lower()) if w not in M.STOP] for k, t in text.items()})
    R = [r for r in L.rows() if r["yr"] >= 2019 and r["bill"] in date]
    by_bill = collections.defaultdict(list); by_who = collections.defaultdict(list)
    for r in R:
        by_bill[r["bill"]].append(r); by_who[r["who"]].append(r)
    share = {(k, p): np.mean([x["y"] for x in rs if x["party"] == p]) for k, rs in by_bill.items()
             for p in {x["party"] for x in rs}}
    killed = {k: np.mean([x["y"] for x in rs]) <= .1 for k, rs in by_bill.items()}
    out = {}
    for split in ("confirm", "repeat"):
        te, _a, _b = G.load(split)
        pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        I = [i for i, r in enumerate(te) if abs(pC[i] - .5) < .31 and r["bill"] in date and r["bill"] in vec]
        S = np.zeros((len(I), 3)); miss = 0
        for j, i in enumerate(I):
            r = te[i]; v0 = vec[r["bill"]]; d0 = date[r["bill"]]
            past = [q for q in by_who[r["who"]] if date[q["bill"]] < d0 and q["bill"] in vec and q["bill"] != r["bill"]]
            sims = sorted(((M._cos(v0, vec[q["bill"]]), q) for q in past), key=lambda t: -t[0])[:6]
            w = np.array([s for s, _ in sims]); 
            if not len(w) or w.sum() <= 0:
                miss += 1; continue                                  # no history: signals stay 0 (counted)
            w = w / w.sum(); yv = np.array([q["y"] for _, q in sims], float)
            ps = np.array([share[(q["bill"], r["party"])] for _, q in sims])
            kv = np.array([killed[q["bill"]] for _, q in sims], float)
            S[j] = [(w @ yv - .5) * 2, w @ (yv - ps), w @ kv]
        y = np.array([te[i]["y"] for i in I], float)
        out[split] = (lo(pC[I]), S, y, miss)
    return out


def fit(off, X, y, lam=1.0):
    b = np.zeros(X.shape[1])
    for _ in range(60):
        p = 1 / (1 + np.exp(-(off + X @ b)))
        b += np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]) + lam * np.eye(len(b)), X.T @ (y - p) - lam * b)
    return b


def main():
    D = signals()
    off, X, y, miss = D["confirm"]; b = fit(off, X, y)
    print(f"2025 can't-call votes {len(y)} (no history {miss}); weights own-share {b[0]:+.2f} vs-party {b[1]:+.2f} room-killed {b[2]:+.2f}")
    for split, yr in (("confirm", "2025 (in-sample)"), ("repeat", "2026 (year-ahead)")):
        off, X, y, miss = D[split]
        p0 = 1 / (1 + np.exp(-off)); p1 = 1 / (1 + np.exp(-(off + X @ b)))
        r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1); c1 = np.abs(p1 - .5) >= .31
        print(f"  {yr}: {len(y)} votes | right {r0.mean():.3f} -> {r1.mean():.3f} | now callable {c1.sum()} right {r1[c1].mean() if c1.any() else float('nan'):.3f}")


if __name__ == "__main__":
    main()
