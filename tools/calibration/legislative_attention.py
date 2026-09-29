#!/usr/bin/env python3
"""Legislative attention on an issue as a salience signal: how many bills on the bill's topic were filed THIS session,
by which party, and how many near-identical bills other patrons filed. All known at filing time (before any vote).
Year-ahead: choose on 2024, score once on 2025."""
import sys, os, json, pickle, collections, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import first_vote as FV, gbm
from corpus import load
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
subj = {}
for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
    s, b = k.split("|", 1); subj[(s, b)] = v
filed = collections.Counter(); by_party = collections.Counter()
for key, b in corpus.items():
    for t in subj.get(key, []):
        filed[(key[0], t)] += 1
        if b["chief_party"] in FV.PARTIES: by_party[(key[0], t, b["chief_party"])] += 1
D = FV.assemble(); nb = D["nb"]
rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
for r in rows:
    s = r["bill"][0]; b = corpus.get(r["bill"]); topics = subj.get(r["bill"], [])
    if not b or not topics:
        r["la_n"] = r["la_other"] = r["la_bipart"] = 0.0; r["la_twins"] = 0.0; r["la_has"] = 0.0; continue
    n = sum(filed[(s, t)] for t in topics)
    other = [p for p in FV.PARTIES if p != b["chief_party"]]
    o = sum(by_party[(s, t, other[0])] for t in topics) if other else 0
    tot = sum(by_party[(s, t, p)] for t in topics for p in FV.PARTIES) or 1
    r["la_n"] = float(np.log1p(n)); r["la_other"] = o / tot
    r["la_bipart"] = 1.0 - abs(2 * (o / tot) - 1)                      # 1 = both parties filing equally on this topic
    r["la_twins"] = float(sum(1 for c, j in nb.get(r["bill"], []) if c[0] == s and j >= .5
                            and corpus.get(c, {}).get("chief") != b["chief"]))
    r["la_has"] = 1.0
NEW = ["la_n", "la_other", "la_bipart", "la_twins", "la_has"]
X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
for label, trn, tst in (("choose on 2024", (2019, 2020, 2021, 2022), 2024), ("score on 2025", FV.TRAIN_YEARS, 2025)):
    tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == tst]
    y = np.array([r["y"] for r in te]); same = np.array([r["same"] for r in te]); hf = None
    for name, cs in (("GBM", FV.NUM), ("GBM + legislative attention", FV.NUM + NEW)):
        p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), np.array([r["y"] for r in tr], float)).predict(X(te, cs))
        if hf is None: o = np.argsort(np.abs(p - .5)); hf = o[:len(o) // 3]
        rt = (p >= .5) == (y == 1)
        print(f"  [{label}] {name:28s} all {rt.mean():.4f}  other-party {rt[same == 0].mean():.4f}  fixed-hard {rt[hf].mean():.4f}", flush=True)
