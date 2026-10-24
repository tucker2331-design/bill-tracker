#!/usr/bin/env python3
"""Rebuild the 2023 first-vote rows (add_2023.py's replay, cached in .cache this time) and the locked model's
out-of-sample predictions for them (trained on 2019-2022 only), so 2023 can serve as a history / learning year for
the combination tests (combo_cells.py, rerun_no2021.py FIT2023=1). 2023 comes from LIS legacy CSV files already
cached under historical_cache/va/231 (the authorized route for pre-2025 sessions). No requests.
Run: python3 build_2023.py
"""
from __future__ import annotations
import sys, os, pickle
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ["IF_OUT"] = os.path.join(HERE, ".cache")
import numpy as np
import add_2023 as A, first_vote as FV, gbm, collections


def main():
    orig_rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    rc23, cops23, stats = A.build_2023()
    party, person = A._party_lookup()
    D = FV.assemble(); D2 = dict(D); D2["rc"] = {**D["rc"], **rc23}
    base = A._load(); bills2 = []
    for b in base["bills"]:
        if b["session"] == "2023" and (b["session"], b["bill"]) in cops23:
            names = cops23[(b["session"], b["bill"])]
            b = {**b, "cops": [person(n) or n for n in names], "cop_parties": [party(n) for n in names]}
        bills2.append(b)
    FV.assemble = lambda: D2; FV.load = lambda: {**base, "bills": bills2}
    rows = FV.add_room_aggregates(FV.add_districts(FV.add_ideal(FV.add_text(FV.features()))))
    r23 = [r for r in rows if r["yr"] == 2023 and r["y"] >= 0]
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    tr = [r for r in orig_rows if r["yr"] in (2019, 2020, 2021, 2022)]
    p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(r23))
    pickle.dump((r23, p), open(os.path.join(HERE, ".cache", "p2023.pkl"), "wb"))
    y = np.array([r["y"] for r in r23])
    print(f"2023: {len(r23)} ballots on {len({r['bill'] for r in r23})} bills; locked-model accuracy {((p >= .5) == (y == 1)).mean():.4f}")
    print("stats:", dict(stats), collections.Counter(r["ven_sub"] for r in r23))


if __name__ == "__main__":
    main()
