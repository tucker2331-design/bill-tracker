#!/usr/bin/env python3
"""What the adopted blend changes, counted in votes and bills (owner, 2026-10-19: "quantify the gains. those 1 percent
gains is that a bill unsuccessfully predicted before now being predicted?").

For each test year (2024 choose, 2025 confirm, 2026 repeat), base model vs adopted blend (blend_2027.py settings, read
from the saved research predictions):
  votes   fixed (wrong -> right), broken (right -> wrong), net
  rooms   bills whose result (most members yes) is fixed / broken
  where   remaining misses by the ACTUAL shape of the vote (unanimous yes / party line / mixed split / unanimous no)
          x voter side, and rooms missed by how close the actual vote was
Run: python3 gains.py
"""
from __future__ import annotations
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, shape_first as SF

BLEND = {"parts": [["gbm", {"depth": 6, "subsample": 0.5, "colsample": 0.5, "bags": 8}, 0.8],
                   ["linear", {"hinges": 3, "lam": 10, "pairs": 8}, 0.2]]}


def load(split):
    te, p0 = L.base_p(split)
    f = os.path.join(L.PRED, f"blend_{split}_{L._key(BLEND)}.npy")
    if not os.path.exists(f):
        raise SystemExit(f"missing {f}: run levers.py blend with the adopted settings on {split} first")
    return te, p0, np.load(f)


def main():
    for split in ("choose", "confirm", "repeat"):
        te, p0, p1 = load(split); ty = L.SPLITS[split][1]
        y = np.array([r["y"] for r in te]); r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1)
        hard = np.zeros(len(y), bool); hard[np.argsort(np.abs(p0 - .5))[:len(y) // 3]] = True
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        shape = np.zeros(len(y), int); margin = {}
        for k, I in g.items():
            s = SF.shape_of([te[i] for i in I]); shape[I] = s
            margin[k] = abs(2 * y[I].sum() - len(I))           # yes minus no
        rm0 = {k: (p0[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for k, I in g.items()}
        rm1 = {k: (p1[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for k, I in g.items()}
        fix, brk = int((~r0 & r1).sum()), int((r0 & ~r1).sum())
        rf = sum(1 for k in g if not rm0[k] and rm1[k]); rb = sum(1 for k in g if rm0[k] and not rm1[k])
        print(f"\n=== {ty} ({split}) : {len(y):,} votes on {len(g):,} bills")
        print(f"  votes: fixed {fix}, broken {brk}, net {fix - brk:+d}  ({(fix - brk) / len(y):+.2%});  "
              f"hardest third: fixed {int((~r0 & r1 & hard).sum())}, broken {int((r0 & ~r1 & hard).sum())}")
        print(f"  rooms: fixed {rf}, broken {rb}, net {rf - rb:+d} of {len(g)};  rooms still missed {sum(not v for v in rm1.values())}")
        same = np.array([bool(r["same"]) for r in te])
        print("  misses left, by actual shape x voter side (share of all misses; accuracy base -> blend):")
        miss = ~r1
        for s, name in enumerate(SF.SHAPES):
            for side, sn in ((True, "own party"), (False, "other party")):
                m = (shape == s) & (same == side)
                if m.any():
                    print(f"    {name:14s} {sn:11s} votes {m.sum():6d}  misses {(miss & m).sum():5d} ({(miss & m).sum() / miss.sum():5.1%})"
                          f"  accuracy {r0[m].mean():.3f} -> {r1[m].mean():.3f}")
        print("  rooms missed, by how close the real vote was (yes minus no, absolute):")
        for lo, hi, nm in ((0, 1, "tie or 1"), (2, 3, "2-3"), (4, 7, "4-7"), (8, 99, "8+")):
            ks = [k for k in g if lo <= margin[k] <= hi]
            if ks:
                print(f"    {nm:9s} bills {len(ks):5d}  missed {sum(not rm1[k] for k in ks):4d}  "
                      f"room accuracy {np.mean([rm0[k] for k in ks]):.3f} -> {np.mean([rm1[k] for k in ks]):.3f}")


if __name__ == "__main__":
    main()
