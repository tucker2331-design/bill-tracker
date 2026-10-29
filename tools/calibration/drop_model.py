#!/usr/bin/env python3
"""Can we predict that a bill will be struck, tabled or continued at its first vote? (owner, 2026-10-20)

Target (per bill): the first recorded vote is UNANIMOUS NO -- in practice "subcommittee recommends striking from the
docket", "laying on the table", "continued to next session", "passed by indefinitely" (gains.py / withdraw_probe.py).
Everything below is knowable BEFORE that vote (structural records; no bill text):
  base inputs   the member model's inputs averaged per side of the room (shape_first.bill_table)
  long_session  even year: only a long (60-day) session can continue a bill to the next session
  room_drop     that committee's unanimous-no share in EARLIER sessions of the same parity (even / odd)
  pat_drop      the patron's unanimous-no share on their bills in EARLIER sessions (shrunk toward the mean)
  pat_load      bills the patron filed this session (log)
  room_load     bills referred to that committee this session (log)
Year-ahead: score year t from a GBM learned on all years before t (2022, 2024, 2025, 2026).
Mode `fit`: AUC with base inputs only vs base + new inputs, and precision / recall at P >= 0.5.
Mode `stack`: P(unanimous no) as an input to the member vote (accept.stacked_year_ahead, x voter side).
"""
from __future__ import annotations
import sys, os, re, math, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV, shape_first as SF, gbm
from corpus import load, _party_lookup

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
_party, person = _party_lookup()
ROWS = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
YEARS = sorted({r["yr"] for r in ROWS})
MOTION = (("strike", re.compile(r"strik\w* from (the )?docket", re.I)), ("table", re.compile(r"\btabl|on the table", re.I)),
          ("continue", re.compile(r"continu\w* to", re.I)), ("pbi", re.compile(r"passed by indefinitely", re.I)))


def table():
    keys, X, Y, yr = SF.bill_table(ROWS)
    rc = FV.assemble()["rc"]
    pat = {k: person(corpus[k]["chief"]) or corpus[k]["chief"] for k in keys}
    room = {k: FV.first_room(corpus[k]) or "?" for k in keys}
    load_p = collections.Counter((k[0], person(b["chief"]) or b["chief"]) for k, b in corpus.items() if b["chief"])
    load_r = collections.Counter((k[0], FV.first_room(corpus[k]) or "?") for k in corpus)
    y = (Y == 3).astype(float)
    by_pat = collections.defaultdict(list); by_room = collections.defaultdict(list)
    for k, t, u in zip(keys, yr, y):
        by_pat[pat[k]].append((t, u)); by_room[(room[k], t % 2)].append((t, u))
    mean = y.mean(); extra = []
    for k, t in zip(keys, yr):
        pp = [u for tt, u in by_pat[pat[k]] if tt < t]; rr = [u for tt, u in by_room[(room[k], t % 2)] if tt < t]
        extra.append([float(t % 2 == 0), (sum(rr) + 5 * mean) / (len(rr) + 5), (sum(pp) + 5 * mean) / (len(pp) + 5),
                      math.log1p(load_p[(k[0], pat[k])]), math.log1p(load_r[(k[0], room[k])])])
    motion = []
    for k in keys:
        d = rc[k][0][0]; acts = [t for dd, t, _c in corpus[k]["actions"] if dd == d and re.search(r"\d+-Y", t)]
        motion.append(next((m for m, rx in MOTION if acts and rx.search(acts[0])), "other"))
    return keys, X, np.array(extra), y, yr, np.array(motion)


def auc(p, y):
    o = np.argsort(p); r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1 = y.sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def oos(keys, X, E, y, yr, extra=True):
    """P(unanimous no) for every bill of 2021+ from a model learned on earlier years only."""
    F = np.column_stack([X, E]) if extra else X
    p = np.full(len(y), np.nan)
    for t in [u for u in YEARS if u >= 2021]:
        tr = yr < t; te = yr == t
        p[te] = gbm.GBM(depth=4, lr=.05, rounds=200).fit(F[tr], y[tr]).predict(F[te])
    return p


def fit():
    keys, X, E, y, yr, motion = table()
    pa, pb = oos(keys, X, E, y, yr, False), oos(keys, X, E, y, yr, True)
    for t in [u for u in YEARS if u >= 2022]:
        m = yr == t
        print(f"{t}: {m.sum()} bills, unanimous no {y[m].mean():.1%} "
              f"({', '.join(f'{k} {((motion == k) & m & (y == 1)).sum()}' for k, _ in MOTION)}, "
              f"other {((motion == 'other') & m & (y == 1)).sum()})")
        for nm, p in (("base inputs", pa), ("base + new inputs", pb)):
            f = m & (p >= .5)
            print(f"   {nm:18s} AUC {auc(p[m], y[m]):.3f}; flagged P>=.5: {f.sum()} bills, {y[f].mean() if f.any() else float('nan'):.0%} "
                  f"right; caught {(f & (y == 1)).sum()} of {(m & (y == 1)).sum()}")
    pickle.dump(dict(zip(keys, pb)), open(os.path.join(HERE, ".cache", "drop_p.pkl"), "wb"))


def stack():
    import accept as AC
    P = pickle.load(open(os.path.join(HERE, ".cache", "drop_p.pkl"), "rb"))
    def sig(r):
        p = P.get(r["bill"]); s = float(r["same"])
        if p is None or np.isnan(p):
            return {"drop_same": 0.0, "drop_other": 0.0}
        lg = math.log(max(p, 1e-4) / (1 - min(p, 1 - 1e-4))) + 2.5      # centred near the base rate (~8%)
        return {"drop_same": lg * s, "drop_other": lg * (1 - s)}
    AC.stacked_year_ahead(sig, "DROP MODEL: P(first vote unanimous no) x side", ridge=10.0)


if __name__ == "__main__":
    {"fit": fit, "stack": stack}[sys.argv[1]]()
