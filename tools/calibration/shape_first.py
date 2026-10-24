#!/usr/bin/env python3
"""Predict the vote's SHAPE first, then the members (owner, 2026-10-15: "use the 85% we have ... look at what the party
line votes have in common ... maybe even just predict it will be party line ... categorize that hard 1/3").

SHAPE of a first vote (all ballots): unanimous yes / party line (each party votes as a block, the two blocks opposite) /
mixed split (anything else that is not unanimous) / unanimous no.
  1. Shape model: one row per first vote; inputs = every first_vote.NUM column averaged over each side (the patron's
     party, the other party) + room size; one-vs-rest boosted trees; YEAR-AHEAD for 2021 / 2022 / 2024 / 2025.
  2. Hard-third TAXONOMY: the fixed hardest third of ballots under the member model (year-ahead), broken down by actual
     shape, predicted shape, voter side, venue, patron standing -- with the member model's accuracy in each cell.
  3. "Predict it will be party line": on hard-third ballots of bills the shape model calls party-line, compare the member
     model with the rule "vote with your party; the patron's party yes, the other party no".
  4. Shape probabilities x voter side stacked into the member model (accept.stacked_year_ahead).
"""
from __future__ import annotations
import sys, os, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV, gbm

SHAPES = ["unanimous yes", "party line", "mixed split", "unanimous no"]
YEARS = (2019, 2020, 2021, 2022, 2024, 2025)


def shape_of(rows_of_bill):
    ys = [r["y"] for r in rows_of_bill]
    if all(ys): return 0
    if not any(ys): return 3
    by = collections.defaultdict(list)
    for r in rows_of_bill:
        by[r["same"]].append(r["y"])
    if len(by) == 2 and all(len(set(v)) == 1 for v in by.values()) and set(by[1]) != set(by[0]):
        return 1
    return 2


def bill_table(rows):
    g = collections.defaultdict(list)
    for r in rows:
        g[r["bill"]].append(r)
    keys, X, Y, yr = [], [], [], []
    for k, rs in g.items():
        own = [r for r in rs if r["same"]]; oth = [r for r in rs if not r["same"]]
        f = []
        for side in (own, oth):
            f += [float(np.mean([r[c] for r in side])) if side else 0.0 for c in FV.NUM]
        f += [len(own), len(oth)]
        keys.append(k); X.append(f); Y.append(shape_of(rs)); yr.append(rs[0]["yr"])
    return keys, np.array(X, float), np.array(Y), np.array(yr)


def shape_oos(rows):
    keys, X, Y, yr = bill_table(rows)
    out = {}
    for t in (2021, 2022, 2024, 2025):
        tr, te = yr < t, yr == t
        cols = []
        for k in range(4):
            yk = (Y[tr] == k).astype(float)
            cols.append(gbm.GBM(depth=4, lr=.05, rounds=200).fit(X[tr], yk).predict(X[te]) if yk.any() else np.zeros(te.sum()))
        P = np.clip(np.column_stack(cols), 1e-6, None); P /= P.sum(1, keepdims=True)
        for k_, p_, y_ in zip([k for k, m in zip(keys, te) if m], P, Y[te]):
            out[k_] = (p_, int(y_))
        acc = (P.argmax(1) == Y[te]).mean(); base = max(np.mean(Y[te] == k) for k in range(4))
        print(f"  shape model {t}: {te.sum()} votes; top shape right {acc:.1%} (always guessing the commonest: {base:.1%})", flush=True)
    return out


def main():
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] in YEARS]
    S = shape_oos(rows)
    B = AC.base_preds()
    # 2. taxonomy of the fixed hardest third, pooled 2021-2025
    cells = collections.defaultdict(lambda: [0, 0]); allc = collections.defaultdict(lambda: [0, 0])
    rule = {"model": [0, 0], "party rule": [0, 0]}
    for t, (te, p) in B.items():
        y = np.array([r["y"] for r in te]); right = (p >= .5) == (y == 1)
        hard = set(np.argsort(np.abs(p - .5))[:len(p) // 3].tolist())
        for i, r in enumerate(te):
            if r["bill"] not in S:
                continue
            ps, actual = S[r["bill"]]; pred = int(ps.argmax())
            ven = "sub" if r["ven_sub"] else "com" if r["ven_com"] else "floor"
            for key in (("actual shape", SHAPES[actual]), ("predicted shape", SHAPES[pred]),
                        ("voter", "patron's party" if r["same"] else "other party"), ("venue", ven),
                        ("patron", "majority" if r["maj"] else "minority")):
                c = cells[key] if i in hard else allc[key]
                c[0] += 1; c[1] += int(right[i])
            if i in hard and pred == 1 and ps[1] >= .5:
                party_says = int(r["same"])            # patron's party yes, other party no
                rule["model"][0] += 1; rule["model"][1] += int(right[i])
                rule["party rule"][0] += 1; rule["party rule"][1] += int(party_says == r["y"])
    print("\n2. THE HARDEST THIRD, BROKEN DOWN (2021/2022/2024/2025 pooled; share of the hard third, model accuracy there,"
          " and accuracy on the other two-thirds)")
    tot = sum(v[0] for k, v in cells.items() if k[0] == "actual shape")
    for dim in ("actual shape", "predicted shape", "voter", "venue", "patron"):
        print(f"  by {dim}:")
        for k, v in sorted(cells.items(), key=lambda kv: -kv[1][0]):
            if k[0] == dim:
                e = allc.get(k, [0, 0])
                print(f"     {k[1]:16s} {v[0] / tot:5.1%} of the hard third, right {v[1] / v[0]:5.1%}"
                      + (f"   (rest: right {e[1] / e[0]:5.1%})" if e[0] else ""))
    m, pr = rule["model"], rule["party rule"]
    if m[0]:
        print(f"\n3. HARD-THIRD BALLOTS ON BILLS PREDICTED PARTY-LINE (p >= 0.5): {m[0]} ballots; member model right "
              f"{m[1] / m[0]:.1%}; 'vote with your party' rule right {pr[1] / pr[0]:.1%}")

    def sig(r):
        v = S.get(r["bill"])
        if v is None:
            return {f"{n}_{s}": 0.0 for n in ("pl", "mx", "uy") for s in ("same", "other")}
        p, _a = v; s = float(r["same"])
        return {"pl_same": p[1] * s, "pl_other": p[1] * (1 - s), "mx_same": p[2] * s, "mx_other": p[2] * (1 - s),
                "uy_same": p[0] * s, "uy_other": p[0] * (1 - s)}
    print()
    AC.stacked_year_ahead(sig, "4. SHAPE FORECAST (party line / mixed / unanimous yes) x voter side", ridge=10.0)


if __name__ == "__main__":
    main()
