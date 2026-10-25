#!/usr/bin/env python3
"""Coverage test for the block-level AI (2026-10-25; owner: "take more out of the undesirable 1/3rd and into the
highly marketable and useful 2/3"). FROZEN before the last 89 2025 answers arrived (docs/testing/first_vote.md):
  1. weight b: member log-odds = logit(arm C) + b * logit(AI block chance), fit on ALL 2025 answered can't-call votes
     (B139 excluded: its result leaked inside its batch)
  2. cutoff t: guaranteed_calls.cutoff on 2025 -- loosest |p - .5| whose one-sided 95% Clopper-Pearson bound on the
     wrong rate is <= 19% (the same rule as the 81/19 calls)
  3. apply b and t unchanged to 2026; PASS if calls > 0 and right >= 81%.
Run: python3 llm_cover.py
"""
from __future__ import annotations
import sys, os, json, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv = sys.argv[:1]
import numpy as np
import llm_member as M, knn_own as K, guaranteed_calls as GC

LEAKED = {"B139"}


def data():
    man = json.load(open(os.path.join(HERE, ".cache", "llm_block", "manifest.json"))); A = {}
    for f in glob.glob(os.path.join(HERE, ".cache", "llm_block", "answers_v1_*.jsonl")):
        for line in open(f):
            if line.strip().startswith("{"):
                d = json.loads(line); A[d["id"]] = d
    D = collections.defaultdict(list); missing = collections.Counter()
    for c, v in man.items():
        if c in LEAKED or c not in A or A[c].get("recognized"):
            missing[v["yr"]] += 1; continue
        for p, y, pc in v["members"]:
            if p not in A[c]["p"]:
                missing["block " + p] += 1; continue
            D[v["yr"]].append((c, y, M.lo(pc), M.lo(A[c]["p"][p] / 100)))
    return D, missing


def main():
    D, missing = data()
    arr = lambda yr: (np.array([a[2] for a in D[yr]]), np.array([[a[3]] for a in D[yr]]), np.array([a[1] for a in D[yr]], float))
    print(f"votes: 2025 {len(D['2025'])} on {len({a[0] for a in D['2025']})} bills, 2026 {len(D['2026'])}; not scored {dict(missing)}")
    o, X, y = arr("2025"); b = K.fit(o, X, y); p = 1 / (1 + np.exp(-(o + X @ b))); r = (p >= .5) == (y == 1)
    t = GC.cutoff(np.abs(p - .5), ~r, 0.19, 0.05)
    c = np.abs(p - .5) >= (t if t is not None else 9)
    print(f"2025 (learn): weight {b[0]:+.2f}; cutoff {t}; in-sample calls {c.sum()} right {r[c].mean() if c.any() else float('nan'):.3f}")
    o, X, y = arr("2026"); p = 1 / (1 + np.exp(-(o + X @ b))); r = (p >= .5) == (y == 1)
    c = np.abs(p - .5) >= (t if t is not None else 9)
    ok = c.any() and r[c].mean() >= .81
    print(f"2026 (test): calls {c.sum()} of {len(y)} hard votes ({c.mean():.1%}), right {r[c].mean() if c.any() else float('nan'):.3f}, "
          f"wrong {(c & ~r).sum()} -> {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
