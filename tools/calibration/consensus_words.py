#!/usr/bin/env python3
"""The consensus-word signal (hard_third_more.py `words`, accepted 2026-10-15 at z = 4.2, hardest third up in 2022/24/25)
-- replicated on 2026, and one variant.

Words come from the official summary AS INTRODUCED (summary_memory.summaries: note == introduced) plus the title -- both
exist before any vote. Each word's log-odds of going with a unanimous-yes / unanimous-no first vote is learned from
EARLIER years only.
  replicate   word scores learned on <= 2025; stacking fitted on 2021/2022/2024/2025 year-ahead predictions; scored once
              on 2026 (base: the locked model trained 2019-2025). 2026 is the already-scored test year: a replication.
  other       variant: words that go with the OTHER party voting yes (vs no) on contested first votes, earlier years only,
              x voter side; rolling 2022/2024/2025 like every other test.
INTERNAL research: word scores are text-derived (Standard #3) -- any product use needs the owner's call.
"""
from __future__ import annotations
import sys, os, re, math, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV, stats as ST, summary_memory as SM
from corpus import load

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
summ = SM.summaries()
STOP = set("the a an of to and or in for on by with as be is are that this from at which any such its it shall may "
           "bill provides requires certain".split())
toks = lambda k: set(re.findall(r"[a-z]{4,}", (summ.get(k, "") + " " + corpus.get(k, {}).get("title", "")).lower())) - STOP


def table(rows, label_fn):
    """word -> per-class counts for bills with a label; label_fn(bill rows) -> class index or None."""
    g = collections.defaultdict(list)
    for r in rows:
        g[r["bill"]].append(r)
    lab = {k: label_fn(rs) for k, rs in g.items()}
    return lab


def scorer(lab, before_year, n_cls):
    cnt = collections.defaultdict(lambda: [0] * n_cls); tot = [0] * n_cls
    for k, c in lab.items():
        if c is not None and int(k[0]) < before_year:
            tot[c] += 1
            for w in toks(k):
                cnt[w][c] += 1
    n = sum(tot)
    def score(k):
        ws = [w for w in toks(k) if sum(cnt[w]) >= 5]
        if not ws:
            return [0.0] * n_cls
        return [float(np.mean([math.log((cnt[w][c] + 1) / (tot[c] + 2)) - math.log((sum(cnt[w]) + 1) / (n + 2)) for w in ws]))
                for c in range(n_cls)]
    return score


def unan(rs):
    ys = [r["y"] for r in rs]
    return 0 if all(ys) else 1 if not any(ys) else 2


def replicate():
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    lab = table([r for r in rows if r["yr"] != 2026], unan)
    B = AC.base_preds()
    tr_rows, tr_p, tr_F = [], [], []
    for t, (te, p) in B.items():
        sc = scorer(lab, t, 3); cache = {}
        for r, q in zip(te, p):
            if r["bill"] not in cache: cache[r["bill"]] = sc(r["bill"])
            y_, n_, _o = cache[r["bill"]]; s = float(r["same"])
            tr_rows.append(r); tr_p.append(q); tr_F.append([y_ * s, y_ * (1 - s), n_ * s, n_ * (1 - s)])
    te_rows, te_p = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    sc = scorer(lab, 2026, 3); cache = {}; te_F = []
    for r in te_rows:
        if r["bill"] not in cache: cache[r["bill"]] = sc(r["bill"])
        y_, n_, _o = cache[r["bill"]]; s = float(r["same"])
        te_F.append([y_ * s, y_ * (1 - s), n_ * s, n_ * (1 - s)])
    tr_p, te_p = np.array(tr_p), np.array(te_p); tr_F, te_F = np.array(tr_F), np.array(te_F)
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    ytr = np.array([r["y"] for r in tr_rows], float); y = np.array([r["y"] for r in te_rows], float)
    preds = []
    for use in (False, True):
        Xtr = np.column_stack([lg(tr_p)] + ([tr_F] if use else [])); Xte = np.column_stack([lg(te_p)] + ([te_F] if use else []))
        nm = ["lg"] + (["wy_same", "wy_other", "wn_same", "wn_other"] if use else [])
        f = ST.logit(Xtr, ytr, nm, ridge=10.0, tol=1e-7, max_iter=200)
        b = np.array([f[n_][0] for n_ in ["const"] + nm])
        preds.append(1 / (1 + np.exp(-(np.column_stack([np.ones(len(Xte)), Xte]) @ b))))
    p0, p1 = preds
    ll = lambda p: -(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
    d = collections.defaultdict(float)
    for r, a, c in zip(te_rows, ll(p0), ll(p1)):
        d[str(r["bill"])] += a - c
    d = np.array(list(d.values())); z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    hard = np.argsort(np.abs(te_p - .5))[:len(te_p) // 3]
    r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1)
    print(f"REPLICATION ON 2026 (consensus words): accuracy {r0.mean():.4f} -> {r1.mean():.4f}; hardest third "
          f"{r0[hard].mean():.4f} -> {r1[hard].mean():.4f}; per-bill log-loss gain {d.mean():+.5f}, z = {z:.1f}")


def other():
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
    def lab_fn(rs):
        oth = [r["y"] for r in rs if not r["same"]]
        ys = [r["y"] for r in rs]
        if not oth or all(ys) or not any(ys):
            return None                                   # contested votes only
        return 0 if np.mean(oth) >= .5 else 1
    lab = table(rows, lab_fn)
    S = {t: scorer(lab, t, 2) for t in (2021, 2022, 2024, 2025)}
    cache = {}
    def sig(r):
        k = (r["bill"], r["yr"])
        if r["yr"] not in S:
            return {"ow_same": 0.0, "ow_other": 0.0}
        if k not in cache:
            a, b = S[r["yr"]](r["bill"]); cache[k] = a - b
        v = cache[k]; s = float(r["same"])
        return {"ow_same": v * s, "ow_other": v * (1 - s)}
    AC.stacked_year_ahead(sig, "P8b OTHER-PARTY-SUPPORT WORDS (contested votes, earlier years) x side", ridge=10.0)




def mixed():
    """R1 (2026-10-15): words that go with a MIXED split (members break from their party) vs a clean party-line vote,
    contested first votes of earlier years only; enters x the voter's own defection rate and x side."""
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
    def lab_fn(rs):
        ys = [r["y"] for r in rs]
        if all(ys) or not any(ys):
            return None
        by = collections.defaultdict(list)
        for r in rs:
            by[r["same"]].append(r["y"])
        clean = len(by) == 2 and all(len(set(v)) == 1 for v in by.values())
        return 1 if clean else 0                              # 0 = mixed split, 1 = party line
    lab = table(rows, lab_fn)
    S = {t: scorer(lab, t, 2) for t in (2021, 2022, 2024, 2025)}
    cache = {}
    def sig(r):
        k = (r["bill"], r["yr"])
        if r["yr"] not in S:
            return {"mx_def": 0.0, "mx_other": 0.0}
        if k not in cache:
            a, b = S[r["yr"]](r["bill"]); cache[k] = a - b        # + = mixed-prone wording
        v = cache[k]; s = float(r["same"])
        # two inputs: with mx_same added the three were collinear and the fit did not converge (2026-10-15)
        # defect is ~0.03 on average: unscaled, v*defect sat near 0.01 and its coefficient crept without converging
        return {"mx_def": v * r["defect"] / 0.03, "mx_other": v * (1 - s)}
    AC.stacked_year_ahead(sig, "R1 MIXED-SPLIT WORDS x member's defection rate x side", ridge=10.0)


if __name__ == "__main__":
    {"replicate": replicate, "other": other, "mixed": mixed}[sys.argv[1]]()
