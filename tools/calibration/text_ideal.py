#!/usr/bin/env python3
"""Text-linked ideal points from EVERY contested roll call, used as one feature for the first-vote GBM.

Round-5 follow-up (2026-09-28). ideal_factors.py showed member x content factors learned from FIRST votes alone
never beat the GBM (too few ballots per member). A statistician would instead learn each member's positions from
all their contested votes -- floor, committee, subcommittee, every earlier year -- and place each bill on the same
axes from its CONTENT, the Gerrish & Blei idea ("ideal points from bill text"):

    logit P(member m supports roll call r on bill b) = a_r + < u_m , V z_b >

  a_r      the roll call's own intercept (how popular that motion was) -- absorbs everything common to the room
  u_m      member position, k axes
  V z_b    the bill's location from its summary words, subject, patron and patron's party (bill_features)

Then, for a first vote the model has never seen, the feature is  fit = < u_m , V z_b >  -- how well this member's
learned positions match this bill's content, with no outcome information about the bill itself.

LEAKAGE CONTROL: for target year Y the factors are trained ONLY on roll calls from years < Y (expanding window),
and the target bill's own roll calls are never in training. Settings are fixed on 2024, scored once on 2025.

Run: python3 tools/calibration/text_ideal.py
"""
from __future__ import annotations
import sys, os, pickle, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import first_vote as FV
import gbm
from ideal_factors import bill_features

OUT = os.environ.get("IF_OUT", "/tmp")


def contested(D, min_minority=0.1):
    """[(year, bill_key, rc_id, [(who, sup)])] for roll calls where the losing side had at least 10%."""
    out = []
    for key, lst in D["rc"].items():
        yr = int(key[0][:4])
        for i, (date, _vo, vid, ven, ballots) in enumerate(lst):
            n = len(ballots); s = sum(1 for _w, _p, sup in ballots if sup)
            if n >= 5 and min(s, n - s) / n >= min_minority:
                out.append((yr, key, f"{key}|{i}", [(w, int(sup)) for w, _p, sup in ballots]))
    return out


def train_points(rcs, feats, members, n_bf, k=6, lam=1e-2, lr=0.01, epochs=4, batch=8192, seed=0):
    mid = {m: i for i, m in enumerate(members)}
    rid = {r[2]: i for i, r in enumerate(rcs)}
    M = np.array([mid[w] for r in rcs for w, _s in r[3]]); R = np.array([rid[r[2]] for r in rcs for _ in r[3]])
    B = [feats[r[1]] for r in rcs for _ in r[3]]; Y = np.array([s for r in rcs for _w, s in r[3]], float)
    rng = np.random.default_rng(seed)
    U = rng.normal(0, .05, (len(members), k)); V = rng.normal(0, .05, (n_bf, k)); A = np.zeros(len(rcs))
    state = {n: [np.zeros_like(x), np.zeros_like(x)] for n, x in (("U", U), ("V", V), ("A", A))}
    t = 0
    def adam(name, P, g):
        m_, v_ = state[name]; m_ *= .9; m_ += .1 * g; v_ *= .999; v_ += .001 * g * g
        P -= lr * (m_ / (1 - .9 ** t)) / (np.sqrt(v_ / (1 - .999 ** t)) + 1e-8)
    for _ in range(epochs):
        order = rng.permutation(len(Y))
        for s in range(0, len(Y), batch):
            ix = order[s:s + batch]; t += 1
            bb = [B[i] for i in ix]
            rows = np.concatenate([np.full(len(i), j) for j, (i, _v) in enumerate(bb)])
            idx = np.concatenate([i for i, _v in bb]); val = np.concatenate([v for _i, v in bb])
            vb = np.zeros((len(ix), k)); np.add.at(vb, rows, val[:, None] * V[idx])
            u = U[M[ix]]
            z = A[R[ix]] + (u * vb).sum(1)
            g = (1 / (1 + np.exp(-z)) - Y[ix]) / len(ix)
            gU = np.zeros_like(U); np.add.at(gU, M[ix], g[:, None] * vb); gU += lam * U
            gV = np.zeros_like(V); np.add.at(gV, idx, val[:, None] * (g[:, None] * u)[rows]); gV += lam * V
            gA = np.zeros_like(A); np.add.at(gA, R[ix], g)
            adam("U", U, gU); adam("V", V, gV); adam("A", A, gA)
    return U, V, mid


def fit_feature(rows, U, V, mid, feats, k):
    out = np.zeros(len(rows))
    for j, r in enumerate(rows):
        m = mid.get(r["who"])
        if m is None or r["bill"] not in feats:
            continue
        i, v = feats[r["bill"]]
        out[j] = float(U[m] @ (v @ V[i]))
    return out


def main():
    from corpus import load
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    D = FV.assemble()
    rcs_all = contested(D)
    print(f"contested roll calls: {len(rcs_all)}, ballots {sum(len(r[3]) for r in rcs_all)}", flush=True)
    rows = pickle.load(open(FV.ROWS, "rb"))
    rows = [r for r in rows if r["y"] >= 0 and r["yr"] in (2019, 2020, 2021, 2022, 2024, 2025)]
    keys = sorted({r[1] for r in rcs_all} | {r["bill"] for r in rows})
    feats, n_bf = bill_features(keys, corpus)
    members = sorted({w for r in rcs_all for w, _s in r[3]} | {r["who"] for r in rows})
    k = int(os.environ.get("TI_K", 6)); lam = float(os.environ.get("TI_LAM", 1e-2))
    cache = os.path.join(OUT, f"ti_feat_k{k}_lam{lam}.pkl")
    if os.path.exists(cache):
        feat = pickle.load(open(cache, "rb"))
    else:
        feat = {}
        for Y in (2019, 2020, 2021, 2022, 2024, 2025):
            train = [r for r in rcs_all if r[0] < Y]
            U, V, mid = train_points(train, feats, members, n_bf, k=k, lam=lam)
            ys = [r for r in rows if r["yr"] == Y]
            f = fit_feature(ys, U, V, mid, feats, k)
            feat[Y] = f
            print(f"  points for {Y} from {len(train)} roll calls: feature sd {f.std():.3f}", flush=True)
        pickle.dump(feat, open(cache, "wb"))
    by_year = collections.defaultdict(list)
    for r in rows: by_year[r["yr"]].append(r)
    for Y in by_year:
        for r, x in zip(by_year[Y], feat[Y]):
            r["ti_fit"] = x
            r["ti_fit_x_other"] = x * (1 - r["same"])      # the axis likely matters most across the aisle
    cols = FV.NUM + ["ti_fit", "ti_fit_x_other"]
    X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
    def score(train_years, test_year, label):
        tr = [r for Y in train_years for r in by_year[Y]]; te = by_year[test_year]
        y = np.array([r["y"] for r in te]); same = np.array([r["same"] for r in te])
        for name, cs in (("GBM alone", FV.NUM), ("GBM + text ideal points", cols)):
            p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), np.array([r["y"] for r in tr], float)).predict(X(te, cs))
            right = (p >= .5) == (y == 1)
            if name == "GBM alone":
                o = np.argsort(np.abs(p - .5)); hf = o[:len(o) // 3]
            o2 = np.argsort(np.abs(p - .5)); h2 = o2[:len(o2) // 3]
            print(f"  [{label}] {name:26s} all {right.mean():.4f}  other-party {right[same == 0].mean():.4f}  "
                  f"hardest third (re-ranked) {right[h2].mean():.4f}  (fixed set) {right[hf].mean():.4f}", flush=True)
    score((2019, 2020, 2021, 2022), 2024, "choose on 2024")
    score(FV.TRAIN_YEARS, 2025, "score on 2025")


if __name__ == "__main__":
    main()
