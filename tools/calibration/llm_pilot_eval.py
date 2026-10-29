#!/usr/bin/env python3
"""Score the AI bill-reading pilot (owner 2026-10-24: "run the 1 dollar test first comparing haiku and opus, or even
sonnet"). Ratings were made by Claude Code helper agents (subscription, not API) on 100 blinded 2024 bills
(.cache/llm_pilot_bills.txt; ids B001-B100 -> .cache/llm_pilot_ids.json, never shown to the models).
For each bill and each party block (Democrats / Republicans voting at the first vote):
  1. SIGNAL     rank correlation of the model's rating (dem / rep) with the block's actual yes share
  2. ADDED      block-majority prediction: arm A's block mean alone vs arm A + the rating, leave-one-BILL-out logistic
  3. MEMBERS    every member's arm A log-odds shifted by b * (rating - 50) / 50, b fit leave-one-bill-out; accuracy and
                wrong calls (|p - .5| >= .31) vs arm A -- all bills and the 50 hardest-third bills
Run: python3 llm_pilot_eval.py <model> [...]     (reads .cache/llm_ratings_<model>.jsonl)
"""
from __future__ import annotations
import sys, os, json, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import gains as G

EXCLUDE = set()          # bill codes (B001...) the model said it remembers: dropped from the evaluation
lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def ranks(x):
    o = np.argsort(x); r = np.empty(len(x)); r[o] = np.arange(len(x)); return r


def spearman(a, b):
    return float(np.corrcoef(ranks(np.asarray(a)), ranks(np.asarray(b)))[0, 1])


def fit1(x, off, y, lam=1.0):
    b = 0.0
    for _ in range(50):
        p = 1 / (1 + np.exp(-(off + b * x))); g = ((y - p) * x).sum() - lam * b; h = (p * (1 - p) * x * x).sum() + lam
        b += g / h
    return b


def main(models):
    ids = {k: tuple(v) for k, v in json.load(open(os.path.join(HERE, ".cache", "llm_pilot_ids.json"))).items()}
    te, p0, pA = G.load("choose"); y = np.array([r["y"] for r in te])
    hard = {te[i]["bill"] for i in np.argsort(np.abs(p0 - .5))[:len(p0) // 3]}
    idx = collections.defaultdict(list)
    for i, r in enumerate(te):
        idx[r["bill"]].append(i)
    for model in models:
        R = {}
        for line in open(os.path.join(HERE, ".cache", f"llm_ratings_{model}.jsonl")):
            line = line.strip()
            if line.startswith("{"):
                d = json.loads(line)
                if d["id"] not in EXCLUDE:
                    R[ids[d["id"]]] = d
        print(f"\n=== {model}: {len(R)} of {len(ids)} bills rated")
        blocks = []                                   # (bill, party, rating, armA block mean, actual share, member idx)
        for b, d in R.items():
            for party, key in (("Democratic", "dem"), ("Republican", "rep")):
                I = [i for i in idx[b] if te[i]["party"] == party]
                if I:
                    blocks.append((b, party, d[key], float(np.mean(pA[I])), float(np.mean(y[I])), I))
        rat = np.array([x[2] for x in blocks]) / 100; am = np.array([x[3] for x in blocks]); act = np.array([x[4] for x in blocks])
        print(f"  SIGNAL  rank corr. with each party's actual yes share: rating {spearman(rat, act):+.3f} | arm A {spearman(am, act):+.3f}")
        maj = (act > .5).astype(float); xr = (rat - .5) * 2; off = lo(am)
        bills = [x[0] for x in blocks]; pa = np.zeros(len(blocks)); pb = np.zeros(len(blocks))
        for j, b in enumerate(bills):
            m = np.array([bb != b for bb in bills]); beta = fit1(xr[m], off[m], maj[m])
            pa[j] = 1 / (1 + np.exp(-off[j])); pb[j] = 1 / (1 + np.exp(-(off[j] + beta * xr[j])))
        ll = lambda p: float(-(maj * np.log(np.clip(p, 1e-6, 1)) + (1 - maj) * np.log(np.clip(1 - p, 1e-6, 1))).mean())
        print(f"  ADDED   block majority, leave-one-bill-out: right {((pa >= .5) == maj).mean():.3f} -> {((pb >= .5) == maj).mean():.3f}; "
              f"log loss {ll(pa):.4f} -> {ll(pb):.4f}")
        # members: shift each member's arm A log-odds by beta * rating, beta fit without the member's bill
        xm, offm, ym, bm = [], [], [], []
        for (b, party, r_, _a, _s, I) in blocks:
            for i in I:
                xm.append((r_ / 100 - .5) * 2); offm.append(lo(np.array([pA[i]]))[0]); ym.append(y[i]); bm.append(b)
        xm, offm, ym = np.array(xm), np.array(offm), np.array(ym, float); bm = np.array([str(b) for b in bm])
        p1 = np.zeros(len(ym))
        for b in set(bm):
            m = bm != b; beta = fit1(xm[m], offm[m], ym[m]); p1[bm == b] = 1 / (1 + np.exp(-(offm[bm == b] + beta * xm[bm == b])))
        p0m = 1 / (1 + np.exp(-offm)); hm = np.array([b in {str(h) for h in hard} for b in bm])
        for name, m in (("all 100 bills", np.ones(len(ym), bool)), ("50 hardest-third bills", hm)):
            r0 = (p0m[m] >= .5) == (ym[m] == 1); r1 = (p1[m] >= .5) == (ym[m] == 1)
            c0 = np.abs(p0m[m] - .5) >= .31; c1 = np.abs(p1[m] - .5) >= .31
            n = int(c0.sum()); top = np.argsort(-np.abs(p1[m] - .5))[:n]          # the same number of calls as arm A
            print(f"  MEMBERS {name}: {m.sum()} votes, right {r0.mean():.3f} -> {r1.mean():.3f}; calls {c0.mean():.1%} -> {c1.mean():.1%}, "
                  f"wrong calls {(c0 & ~r0).sum()} -> {(c1 & ~r1).sum()}; at arm A's {n} calls: wrong {(c0 & ~r0).sum()} -> {(~r1[top]).sum()}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--exclude=")]
    EXCLUDE.update(x for a in sys.argv[1:] if a.startswith("--exclude=") for x in open(a.split("=", 1)[1]).read().split())
    main(args or ["haiku", "sonnet", "opus"])
