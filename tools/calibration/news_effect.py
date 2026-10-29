#!/usr/bin/env python3
"""News coverage (Cardinal News mentions BEFORE the first vote) vs first-vote outcomes and the model.
Descriptive on 2024-2025, then year-ahead model test (choose 2024, score 2025). Coverage exists only 2022+, so a
news_known flag marks years where zero means 'not covered' rather than 'no source'."""
import sys, os, json, pickle, collections, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import first_vote as FV, gbm
NEWS = os.path.join(HERE, "..", "historical_cache", "va_news")
ment = collections.defaultdict(list)                       # (session, bill) -> [article dates]
for yr in (2022, 2023, 2024, 2025):
    for a in json.load(open(os.path.join(NEWS, f"cardinal_{yr}.json"))):
        for b in a["bills"]: ment[(str(yr), b)].append(a["date"])
D = FV.assemble()
first_date = {k: lst[0][0] for k, lst in D["rc"].items()}
rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
for r in rows:
    fd = first_date.get(r["bill"], "9999")
    n = sum(1 for d in ment.get(r["bill"], []) if d < fd[:10])     # strictly BEFORE the vote day
    r["news_n"] = float(np.log1p(n)); r["news_any"] = float(n > 0); r["news_known"] = float(r["yr"] >= 2022)
p25 = np.load("/private/tmp/claude-501/-Users-tuckerward-Documents-Projects-bill-tracker/d2c029e9-acd9-410e-81ec-5347fd755620/scratchpad/p2025.npy")
va = [r for r in rows if r["yr"] == 2025]; y = np.array([r["y"] for r in va]); right = (p25 >= .5) == (y == 1)
same = np.array([r["same"] for r in va]); cov = np.array([r["news_any"] for r in va]) > 0
print(f"2025 ballots on bills covered before the vote: {cov.sum()} of {len(va)} ({cov.mean():.1%})")
for lab, m in (("covered", cov), ("not covered", ~cov)):
    print(f"  {lab:12s} yes {y[m].mean():.0%} | other-party yes {y[m & (same == 0)].mean():.0%} | model right {right[m].mean():.1%} (other-party {right[m & (same == 0)].mean():.1%})")
X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
NEW = ["news_n", "news_any", "news_known"]
for label, trn, tst in (("choose on 2024", (2019, 2020, 2021, 2022), 2024), ("score on 2025", FV.TRAIN_YEARS, 2025)):
    tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == tst]
    yy = np.array([r["y"] for r in te]); ss = np.array([r["same"] for r in te]); cv = np.array([r["news_any"] for r in te]) > 0; hf = None
    for name, cs in (("GBM", FV.NUM), ("GBM + news coverage", FV.NUM + NEW)):
        p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), np.array([r["y"] for r in tr], float)).predict(X(te, cs))
        if hf is None: o = np.argsort(np.abs(p - .5)); hf = o[:len(o) // 3]
        rt = (p >= .5) == (yy == 1)
        print(f"  [{label}] {name:20s} all {rt.mean():.4f} other-party {rt[ss == 0].mean():.4f} fixed-hard {rt[hf].mean():.4f} | covered bills {rt[cv].mean():.4f} (n={cv.sum()})", flush=True)
