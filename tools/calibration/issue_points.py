#!/usr/bin/env python3
"""Issue-adjusted ideal points (classic statistics, no AI; owner 2026-10-23: "exhaust all non ai possibilities").

text_party.py reads summary words per PARTY cell. It cannot say that one Democrat parts from her caucus on policing
bills while another parts on energy. Here each member gets their own slope on each of K topic directions of the bill
summaries (TF-IDF -> truncated SVD, fit on training years only), learned on the RESIDUAL of the locked model:
    logit P(yes) = logit(base p) + a_m[side] + beta_m . topic(bill)          (ridge `lam`, per member)
For year t, every member's (a, beta) comes only from earlier years' out-of-sample predictions (accept.base_preds);
members with no earlier votes get 0. The resulting shift is tested as a stacked input x side
(accept.stacked_year_ahead, z >= 3). Text-derived: INTERNAL ONLY (Standard #3).
Run: python3 issue_points.py [K] [lam]
"""
from __future__ import annotations
import sys, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, summary_memory as SM, text_party as TP
from corpus import load

K = int(sys.argv[1]) if len(sys.argv) > 1 else 20
LAM = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
SUMM = SM.summaries()
lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def topics(train_keys, all_keys):
    docs = {k: TP.tokens(SUMM[k], corpus[k]["title"]) for k in all_keys if k in SUMM}
    df = collections.Counter(w for k in train_keys if k in docs for w in set(docs[k]))
    # the 5,000 most common terms seen in >= 5 training summaries (keeps the SVD small enough for numpy)
    vocab = {w: i for i, (w, c) in enumerate(sorted(((w, c) for w, c in df.items() if c >= 5), key=lambda x: -x[1])[:5000])}
    n_tr = sum(1 for k in train_keys if k in docs)
    idf = np.zeros(len(vocab))
    for w, i in vocab.items():
        idf[i] = math.log((1 + n_tr) / (1 + df[w])) + 1
    def vec(k):
        v = np.zeros(len(vocab))
        for w in docs.get(k, []):
            if w in vocab:
                v[vocab[w]] += 1
        v = v * idf; n = np.linalg.norm(v); return v / n if n else v
    tr = [k for k in train_keys if k in docs]
    M = np.array([vec(k) for k in tr], np.float32)
    _U, _S, Vt = np.linalg.svd(M - M.mean(0), full_matrices=False)
    P = Vt[:K].T; mu = M.mean(0)
    return {k: (vec(k) - mu) @ P for k in all_keys if k in docs}


def main():
    B = AC.base_preds(); years = sorted(B)
    shift = {}                                        # (year, bill, who) -> beta . topic shift
    for t in years[1:]:
        prior = [u for u in years if u < t]
        tk = {r["bill"] for u in prior for r in B[u][0]}; ak = tk | {r["bill"] for r in B[t][0]}
        T = topics(tk, ak)
        by = collections.defaultdict(list)
        for u in prior:
            te, p = B[u]
            for r, q in zip(te, p):
                if r["bill"] in T:
                    by[r["who"]].append((r["same"], T[r["bill"]], lo(np.array([q]))[0], r["y"]))
        coef = {}
        for who, L in by.items():
            if len(L) < 30:
                continue
            X = np.array([[s, 1 - s] + list(tp) for s, tp, _o, _y in L]); off = np.array([o for *_x, o, _y in L])
            y = np.array([yy for *_x, yy in L], float); b = np.zeros(X.shape[1])
            for _ in range(30):
                p = 1 / (1 + np.exp(-(off + X @ b)))
                st = np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]) + LAM * np.eye(len(b)), X.T @ (y - p) - LAM * b)
                b += st
                if np.max(np.abs(st)) < 1e-6:
                    break
            coef[who] = b
        te, _p = B[t]
        for r in te:
            c = coef.get(r["who"]); tp = T.get(r["bill"])
            if c is not None and tp is not None:
                shift[(t, r["bill"], r["who"])] = float(c[0] * r["same"] + c[1] * (1 - r["same"]) + c[2:] @ tp)
        print(f"  {t}: members fitted {len(coef)}, votes with a shift {sum(1 for k in shift if k[0] == t)}", flush=True)
    def sig(r):
        x = shift.get((r["yr"], r["bill"], r["who"]), 0.0); s = float(r["same"])
        return {"ip_same": x * s, "ip_other": x * (1 - s)}
    AC.stacked_year_ahead(sig, f"ISSUE-ADJUSTED IDEAL POINTS (K={K}, ridge {LAM}) x side", ridge=10.0)


if __name__ == "__main__":
    main()
