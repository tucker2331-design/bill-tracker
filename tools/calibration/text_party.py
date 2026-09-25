#!/usr/bin/env python3
"""Which WORDS predict each party's position at a bill's first vote -- a text classifier on the official
summaries (title stripped), used as one ingredient of first_vote.py.

Four L2-regularised logistic models, one per (voting party, patron's party) cell -- because "firearm" means
opposite things to the two parties and depends on who is carrying the bill. Features: unigram + bigram
TF-IDF, vocabulary fit on training years only, terms in >= 5 training summaries.

LEAKAGE RULE. Every year's score comes ONLY from a model trained on strictly earlier years (expanding
window). Cross-fitting was tried first and failed: see the comment in scores().
"""
from __future__ import annotations
import sys, os, re, math, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load, norm
import summary_memory as SM
import first_vote as FV

PARTIES = ("Democratic", "Republican")
STOP = SM.STOP | {"bill", "provides", "act", "code", "section", "virginia", "commonwealth", "requires",
                  "current", "law", "also", "certain", "relating"}


def tokens(text, title):
    t = norm(text)
    tl = norm(title)
    if tl and t.startswith(tl[:40]):
        t = t[len(tl):]
    w = [x for x in re.findall(r"[a-z][a-z]+", t) if x not in STOP]
    return w + [a + "_" + b for a, b in zip(w, w[1:])]


def labels():
    """(s,b) -> {party: supports01} at the bill's FIRST roll call, parties with >= 3 ballots."""
    D = FV.assemble()
    out = {}
    for k, lst in D["rc"].items():
        ball = lst[0][4]
        lab = {}
        for p in PARTIES:
            xs = [x[2] for x in ball if x[1] == p]
            if len(xs) >= 3:
                lab[p] = int(sum(xs) / len(xs) >= .5)
        if lab:
            out[k] = lab
    return out


def _fit(X, y, lam=1.0, iters=300, lr=0.5):
    with np.errstate(all="ignore"):            # Accelerate false flag (stats.py); finiteness asserted below
        w, b = _fit_(X, y, lam, iters, lr)
    if not np.all(np.isfinite(w)):
        raise FloatingPointError("text_party weights non-finite")
    return w, b


def _fit_(X, y, lam, iters, lr):
    """Plain full-batch gradient descent with L2 -- X is a dense float32 TF-IDF matrix (small vocab)."""
    w = np.zeros(X.shape[1], np.float32); b = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w + b)))
        g = p - y
        w -= lr * (X.T @ g / len(y) + lam * w / len(y))
        b -= lr * g.mean()
    return w, b


def scores():
    """(s,b,party) -> P(that party backs the bill at its first vote), leakage-safe as described above."""
    corpus = {(r["session"], r["bill"]): r for r in load()["bills"]}
    summ = SM.summaries()
    lab = labels()
    docs = {k: tokens(summ[k], corpus[k]["title"]) for k in lab if k in summ and k in corpus
            and corpus[k]["chief_party"] in PARTIES}
    years = sorted({int(k[0][:4]) for k in docs})
    out = {}
    for target in years:
        # EXPANDING WINDOW, the same rule for every year. The first version cross-fitted training years
        # (models that had seen LATER years) while 2025 got past-only models -- so training-row scores were
        # sharper than anything available live, and the GBM over-trusted them (tune accuracy FELL 85.6 ->
        # 82.7). A score is only ever made from strictly earlier years; 2020 gets none.
        pool = [k for k in docs if int(k[0][:4]) < target]
        tgt = [k for k in docs if int(k[0][:4]) == target]
        dfc = collections.Counter(t for k in pool for t in set(docs[k]))
        vocab = {t: i for i, t in enumerate(sorted(t for t, c in dfc.items() if c >= 5))}
        idf = np.array([math.log(len(pool) / dfc[t]) for t in sorted(vocab, key=vocab.get)], np.float32)
        def vec(keys):
            M = np.zeros((len(keys), len(vocab)), np.float32)
            for r, k in enumerate(keys):
                for t, c in collections.Counter(docs[k]).items():
                    j = vocab.get(t)
                    if j is not None:
                        M[r, j] = c
            M *= idf
            n = np.linalg.norm(M, axis=1, keepdims=True); n[n == 0] = 1
            return M / n
        for vp in PARTIES:
            for pp in PARTIES:
                tr = [k for k in pool if corpus[k]["chief_party"] == pp and vp in lab[k]]
                te = [k for k in tgt if corpus[k]["chief_party"] == pp]
                if len(tr) < 50 or not te:
                    continue
                y = np.array([lab[k][vp] for k in tr], np.float32)
                w, b = _fit(vec(tr), y)
                with np.errstate(all="ignore"):
                    p = 1 / (1 + np.exp(-(vec(te) @ w + b)))
                for k, pr in zip(te, p):
                    out[(k[0], k[1], vp)] = float(pr)
    return out, lab, docs


if __name__ == "__main__":
    import time
    t = time.time(); out, lab, docs = scores()
    print(f"{len(out)} party-position scores in {time.time()-t:.0f}s")
    for yr in ("2025",):
        ks = [(k, p) for k in lab if k[0] == yr for p in lab[k] if (k[0], k[1], p) in out]
        y = np.array([lab[k][p] for k, p in ks]); s = np.array([out[(k[0], k[1], p)] for k, p in ks])
        print(f"{yr}: party positions scored {len(ks)}, text-only accuracy {((s>=.5)==y).mean():.1%} "
              f"(always-support {y.mean():.1%}), rank {FV._auc(s, y):.3f}")
