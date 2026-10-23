#!/usr/bin/env python3
"""Which part of the Code of Virginia a bill changes, as a vote signal (owner, 2026-10-23: "exhaust all non ai
possibilities"). The worst wrong calls are subject-driven; the Code section is a far finer, fixed identifier than the
43 coarse subject labels (e.g. § 38.2-3418.x = health-insurance coverage requirements, inside "Insurance").

Source: the introduced text (2025/2026 only -- LIS authorization), the enacting clause "A BILL to amend and reenact
§ ... of the Code of Virginia" (fixed legal grammar; INTERNAL ONLY until sourced from an LIS field, Standard #3).
Keys per bill: Code chapter (title + first two digits of the section, "38.2-34") and Code title ("38.2").
For every first vote: this side's support rate on EARLIER first votes (2025, and this session before the vote's
week) of bills touching the same chapter (else title), shrunk -- and this member's own rate there.
Used like the session booster: a small logistic layer on arm C, refit weekly on the session's earlier weeks, applied
only if the same layer fit before last week lowered last week's log loss. Scored on 2025 and 2026.
Run: python3 code_sections.py
"""
from __future__ import annotations
import sys, os, re, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, first_vote as FV, accept as AC, text_features as TF, booster_2027 as BC

SEC = re.compile(r"§+\s*(\d+(?:\.\d+)?(?::\d+)?)-(\d+(?:\.\d+)*)")
lg = lambda q: math.log(max(q, 1e-4) / max(1 - q, 1e-4))


def keys(session, bill):
    p = os.path.join(TF.CORPUS, session, bill.replace(" ", "") + ".html")
    if not os.path.exists(p):
        return None
    t = TF._text(p)
    m = re.search(r"(A BILL|An Act) to (.{0,1500}?)(?:Be it enacted|Patrons?\b|$)", t)
    clause = m.group(2) if m else ""
    ch, ti = set(), set()
    for title, sec in SEC.findall(clause):
        ti.add(title); ch.add(f"{title}-{sec.split('.')[0][:2]}")
    return ch, ti


def main():
    rc = FV.assemble()["rc"]
    D = {}
    for split in ("confirm", "repeat"):
        te, p0, p1 = G.load(split)
        pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        D[split] = (te, p0, pC)
    K = {}
    for split, (te, _a, _b) in D.items():
        for r in te:
            if r["bill"] not in K:
                K[r["bill"]] = keys(*r["bill"])
    cov = np.mean([v is not None and bool(v[0]) for v in K.values()])
    print(f"bills with Code chapters parsed: {cov:.0%} of {len(K)}")
    # one chronological stream of 2025 + 2026 first votes; features from strictly earlier WEEKS
    stream = []
    for split, (te, _a, _b) in D.items():
        for i, r in enumerate(te):
            stream.append((BC._week(rc[r["bill"]][0][0]), split, i))
    stream.sort()
    cnt = collections.Counter(); F = {s: np.zeros((len(D[s][0]), 4)) for s in D}
    weeks = sorted({w for w, _s, _i in stream})
    by_w = collections.defaultdict(list)
    for w, s, i in stream:
        by_w[w].append((s, i))
    for w in weeks:
        for s, i in by_w[w]:                                       # featurise from counts before this week
            r = D[s][0][i]; k = K.get(r["bill"])
            if not k:
                continue
            ch, ti = k; side = r["same"]; base = .85 if side else .55
            n = sum(cnt[("c", c, side, "n")] for c in ch); y_ = sum(cnt[("c", c, side, "s")] for c in ch)
            if n < 5:
                n = sum(cnt[("t", t, side, "n")] for t in ti); y_ = sum(cnt[("t", t, side, "s")] for t in ti)
            rate = (y_ + 10 * base) / (n + 10)
            mn = sum(cnt[("m", r["who"], c, side, "n")] for c in ch); my = sum(cnt[("m", r["who"], c, side, "s")] for c in ch)
            mrate = (my + 5 * rate) / (mn + 5)
            F[s][i] = [(lg(rate) - lg(base)) * side, (lg(rate) - lg(base)) * (1 - side), lg(mrate) - lg(rate), math.log1p(n)]
        for s, i in by_w[w]:                                       # then learn this week
            r = D[s][0][i]; k = K.get(r["bill"])
            if not k:
                continue
            ch, ti = k; side = r["same"]; y = r["y"]
            for c in ch:
                cnt[("c", c, side, "n")] += 1; cnt[("c", c, side, "s")] += y
                cnt[("m", r["who"], c, side, "n")] += 1; cnt[("m", r["who"], c, side, "s")] += y
            for t in ti:
                cnt[("t", t, side, "n")] += 1; cnt[("t", t, side, "s")] += y
    for split in ("confirm", "repeat"):
        te, p0, pC = D[split]; y = np.array([r["y"] for r in te], float)
        lgC = np.log(np.clip(pC, 1e-6, 1 - 1e-6) / (1 - np.clip(pC, 1e-6, 1 - 1e-6)))
        X = np.column_stack([np.ones(len(te)), lgC, F[split]]); prior = np.array([0, 1, 0, 0, 0, 0], float)
        wk = np.array([BC._week(rc[r["bill"]][0][0]) for r in te]); ws = sorted(set(wk)); out = lgC.copy(); used = 0
        def fit(Xa, ya):
            b = prior.copy()
            for _ in range(60):
                p = 1 / (1 + np.exp(-np.clip(Xa @ b, -30, 30)))
                st = np.linalg.solve(Xa.T @ (Xa * (p * (1 - p))[:, None]) + 30 * np.eye(len(b)), Xa.T @ (ya - p) - 30 * (b - prior))
                b += st
                if np.max(np.abs(st)) < 1e-7:
                    return b
            raise RuntimeError("code_sections layer did not converge")
        for jj, w in enumerate(ws):
            if jj < 2:
                continue
            past = wk < w; prev = wk == ws[jj - 1]; early = wk < ws[jj - 1]
            if early.sum() < 3000:
                continue
            q = 1 / (1 + np.exp(-(X[prev] @ fit(X[early], y[early]))))
            if AC._ll(q, y[prev]).mean() >= AC._ll(pC[prev], y[prev]).mean():
                continue
            now = wk == w; out[now] = X[now] @ fit(X[past], y[past]); used += 1
        p2 = 1 / (1 + np.exp(-out)); hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
        r1 = (pC >= .5) == (y == 1); r2 = (p2 >= .5) == (y == 1); c1 = np.abs(pC - .5) >= .3; c2 = np.abs(p2 - .5) >= .3
        print(f"{L.SPLITS[split][1]} (applied {used} of {len(ws)} weeks): member {r1.mean():.4f}->{r2.mean():.4f}  hardest third "
              f"{r1[hard].mean():.4f}->{r2[hard].mean():.4f}  calls {c1.mean():.1%}->{c2.mean():.1%}  wrong calls {(c1 & ~r1).sum()}->{(c2 & ~r2).sum()}", flush=True)


if __name__ == "__main__":
    main()
