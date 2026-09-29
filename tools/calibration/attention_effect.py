#!/usr/bin/env python3
"""Issue attention before the first vote (GDELT, Virginia legislature coverage per topic) as model inputs.
Year-ahead: choose on 2024, score once on 2025.

Per ballot (all measured BEFORE the vote day):
  att30     Virginia legislature news on the bill's topics in the 30 days before the vote, relative to that session's
            median topic-day volume (GDELT coverage grows over the years; raw counts are not comparable across years)
  surge     last 7 days vs the prior 23 days for those topics (is the issue heating up right now?)
  att_has   the bill carries at least one of the 20 measured topics
"""
from __future__ import annotations
import sys, os, json, datetime as dt, pickle
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import first_vote as FV
import gbm

ATT = os.path.join(HERE, "..", "historical_cache", "va_attention")


def main():
    subj = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1); subj[(s, b)] = v
    att = {}
    for yr in (2019, 2020, 2021, 2022, 2024, 2025):
        p = os.path.join(ATT, f"gdelt_{yr}.json")
        if os.path.exists(p):
            att[yr] = json.load(open(p))
    print("attention years:", sorted(att), {y: len(v) for y, v in att.items()}, flush=True)
    med = {y: (np.median([c for t in v.values() for c in t.values()]) or 1.0) for y, v in att.items()}
    D = FV.assemble()
    first_date = {k: lst[0][0] for k, lst in D["rc"].items()}
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] in att]

    def window(yr, topics, end, days):
        e = dt.date.fromisoformat(end)
        keys = [(e - dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(1, days + 1)]
        return sum(att[yr].get(t, {}).get(k, 0) for t in topics for k in keys)

    for r in rows:
        yr = r["yr"]; topics = [t for t in subj.get(r["bill"], []) if t in att[yr]]
        fd = first_date.get(r["bill"], "")[:10]
        if not topics or not fd:
            r["att30"] = r["surge"] = 0.0; r["att_has"] = 0.0; continue
        a30 = window(yr, topics, fd, 30) / (len(topics) * 30 * med[yr])
        a7 = window(yr, topics, fd, 7) / 7; a23 = (window(yr, topics, fd, 30) - window(yr, topics, fd, 7)) / 23
        r["att30"] = float(np.log1p(a30)); r["surge"] = float(np.log((a7 + 1) / (a23 + 1))); r["att_has"] = 1.0
    NEW = ["att30", "surge", "att_has"]
    X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
    for label, trn, tst in (("choose on 2024", (2019, 2020, 2021, 2022), 2024), ("score on 2025", FV.TRAIN_YEARS, 2025)):
        tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == tst]
        y = np.array([r["y"] for r in te]); same = np.array([r["same"] for r in te]); hf = None
        for name, cs in (("GBM", FV.NUM), ("GBM + issue attention", FV.NUM + NEW)):
            p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), np.array([r["y"] for r in tr], float)).predict(X(te, cs))
            if hf is None:
                o = np.argsort(np.abs(p - .5)); hf = o[:len(o) // 3]
            right = (p >= .5) == (y == 1)
            print(f"  [{label}] {name:22s} all {right.mean():.4f}  other-party {right[same == 0].mean():.4f}  fixed-hard {right[hf].mean():.4f}", flush=True)


if __name__ == "__main__":
    main()
