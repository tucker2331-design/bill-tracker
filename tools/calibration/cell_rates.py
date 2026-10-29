#!/usr/bin/env python3
"""A third model family for the blend: a pure 'who with whom on what' model (owner 2026-10-24: "go straight for what
works"). Our gains came from adding a DIFFERENT family to the trees (the linear half, +0.4-0.8 member). This family
sees only people / rooms / subjects: for every first vote, shrunk yes-rates in identity cells from all EARLIER first
votes (strictly earlier days; same-day votes never see each other), e.g. this member on this subject on this side,
this member on this patron's bills, this patron in this room, this room on this subject, this subject for this voter
party and patron party. A ridge logistic on those rates (x side) is blended into arm A in log-odds; the weight is
chosen on 2024 (choose), then checked on 2025 (confirm) and 2026 (repeat). Wrong calls counted at the guaranteed
cutoff (|p - .5| >= .31).
Run: python3 cell_rates.py
"""
from __future__ import annotations
import sys, os, json, math, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, accept as AC, first_vote as FV
from corpus import load

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
SUBJ = {}
for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
    s, b = k.split("|", 1); SUBJ[(s, b)] = v
CACHE = os.path.join(HERE, ".cache", "cell_rates.pkl")
lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def cells(r):
    P = corpus[r["bill"]]["chief"] or "?"; cp = corpus[r["bill"]]["chief_party"]; subs = SUBJ.get(r["bill"], []) or ["-"]
    w, sm, rm = r["who"], r["same"], r["room"]
    return {"m_side": [(w, sm)], "m_subj": [(w, s, sm) for s in subs], "m_pat": [(w, P)], "m_room": [(w, rm, sm)],
            "p_room": [(P, rm, sm)], "r_subj": [(rm, s, sm) for s in subs], "s_party": [(s, r["party"], cp) for s in subs],
            "p_side": [(P, sm)], "r_side": [(rm, sm)]}


def features(rows):
    """{(yr, bill, who): {family: shrunk logit rate, family_n: log count}} replayed day by day."""
    rc = FV.assemble()["rc"]; day = lambda r: rc[r["bill"]][0][0]
    rows = sorted(rows, key=day); cnt = collections.defaultdict(lambda: [0.0, 0.0]); out = {}
    base = {1: .9, 0: .6}; i = 0
    while i < len(rows):
        d = day(rows[i]); j = i
        while j < len(rows) and day(rows[j]) == d:
            j += 1
        for r in rows[i:j]:
            f = {}
            for fam, cs in cells(r).items():
                ys = [cnt[(fam,) + c] for c in cs]
                k = sum(a for a, _ in ys) / len(ys); n = sum(b for _, b in ys) / len(ys); b0 = base[r["same"]]
                f[fam] = math.log(((k + 5 * b0) / (n + 5)) / (1 - (k + 5 * b0) / (n + 5))) - math.log(b0 / (1 - b0))
                f[fam + "_n"] = math.log1p(n)
            out[(r["yr"], r["bill"], r["who"])] = f
        for r in rows[i:j]:
            for fam, cs in cells(r).items():
                for c in cs:
                    a = cnt[(fam,) + c]; a[0] += r["y"] / len(cs); a[1] += 1 / len(cs)
        i = j
    return out


def main():
    if os.path.exists(CACHE):
        F = pickle.load(open(CACHE, "rb"))
    else:
        F = features(L.rows()); pickle.dump(F, open(CACHE, "wb"))
    names = sorted(next(iter(F.values())))
    def attach(rs):
        for r in rs:
            f = F.get((r["yr"], r["bill"], r["who"]), {})
            for n in names:
                r["cr_" + n] = f.get(n, 0.0)
    attach(L.rows())
    S = {"hinges": 0, "lam": 10, "drop": list(FV.NUM), "extra": ["cr_" + n for n in names]}
    S["extra"] += ["same"]
    res = {}
    for split in ("choose", "confirm", "repeat"):
        trn, ty = L.SPLITS[split]; tr = [r for r in L.rows() if r["yr"] in trn]; te, p0, pA = G.load(split); attach(te)
        pcr = L.linear_fn(tr, te, S); y = np.array([r["y"] for r in te])
        np.save(os.path.join(L.PRED, f"cellrates_{split}.npy"), pcr)
        res[split] = (te, p0, pA, pcr, y)
        r_ = (pcr >= .5) == (y == 1)
        print(f"{ty}: cell-rate model alone {r_.mean():.4f} (arm A {((pA >= .5) == (y == 1)).mean():.4f})", flush=True)
    for w in (0.05, 0.1, 0.15, 0.2, 0.3):
        line = []
        for split in ("choose", "confirm", "repeat"):
            te, p0, pA, pcr, y = res[split]
            p1 = 1 / (1 + np.exp(-((1 - w) * lo(pA) + w * lo(pcr))))
            hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
            ra, r1 = (pA >= .5) == (y == 1), (p1 >= .5) == (y == 1); ca, c1 = np.abs(pA - .5) >= .31, np.abs(p1 - .5) >= .31
            d = collections.defaultdict(float)
            for r, a, c in zip(te, AC._ll(pA, y), AC._ll(p1, y)):
                d[str(r["bill"])] += a - c
            d = np.array(list(d.values()))
            line.append(f"{L.SPLITS[split][1]} member {ra.mean():.4f}->{r1.mean():.4f} hard {ra[hard].mean():.4f}->{r1[hard].mean():.4f} "
                        f"wrong {(ca & ~ra).sum()}->{(c1 & ~r1).sum()} z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}")
        print(f"w={w}: " + " | ".join(line), flush=True)


if __name__ == "__main__":
    main()
