#!/usr/bin/env python3
"""Members' budget amendments that name a bill (historical_cache/budget_amendments.py; 2025 + 2026; owner 2026-10-23).
A bill counts as named only for votes ON OR AFTER the day that chamber's member requests became public (LIS
"Budget amendments available"). Inputs x voter side:
  ba_any   a member's budget amendment names this bill        ba_own   ... and it is the bill's own patron's amendment
  ba_amt   log dollars requested for it
Mode describe: how named bills vote at their first vote vs the rest, and how well arm C calls them.
Mode test: through rerun_no2021.evaluate (only 2025 can teach the weights, so 2026 is the real test).
"""
from __future__ import annotations
import sys, os, math, re, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "historical_cache"))
import numpy as np
import first_vote as FV, budget_amendments as BA
from corpus import load

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
rc = FV.assemble()["rc"]
NAMED = collections.defaultdict(list)                 # (session, "HB 551") -> [(public date, member, dollars)]
for a in BA.parse():
    for ref in a["refs"]:
        NAMED[(a["session"], ref)].append((a["public"], a["member"].lower(), a["dollars"]))
sur = lambda n: re.sub(r"[^a-z]", "", (n or "").split()[-1].lower()) if n else ""


def info(key):
    d = rc[key][0][0]; L = [x for x in NAMED.get(key, []) if x[0] <= d]
    if not L:
        return 0.0, 0.0, 0.0
    own = float(any(m == sur(corpus[key]["chief"]) for _d, m, _a in L))
    return 1.0, own, math.log1p(sum(a for *_x, a in L)) / 15


def sig(r):
    a, o, m = info(r["bill"]); s = float(r["same"])
    return {"ba_any_same": a * s, "ba_any_other": a * (1 - s), "ba_own_same": o * s, "ba_amt_same": m * s}


def describe():
    import levers as L, gains as G, shape_first as SF
    for split in ("confirm", "repeat"):
        te, p0, p1 = G.load(split)
        pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy")); y = np.array([r["y"] for r in te])
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        for name, test in (("named in a member budget amendment", lambda k: info(k)[0] == 1),
                           ("  ... by its own patron", lambda k: info(k)[1] == 1), ("not named", lambda k: info(k)[0] == 0)):
            ks = [k for k in g if test(k)]
            if not ks:
                continue
            I = np.concatenate([g[k] for k in ks]); own = np.array([te[i]["same"] == 1 for i in I])
            sh = collections.Counter(SF.shape_of([te[i] for i in g[k]]) for k in ks)
            r_ = (pC[I] >= .5) == (y[I] == 1)
            print(f"{L.SPLITS[split][1]} {name:36s} bills {len(ks):4d} | passed first vote {np.mean([y[g[k]].mean() > .5 for k in ks]):.0%} "
                  f"| unanimous no {sh[3] / len(ks):.0%} | own-party yes {y[I][own].mean():.2f} (predicted {pC[I][own].mean():.2f}) "
                  f"| arm C right {r_.mean():.3f}")


if __name__ == "__main__":
    {"describe": describe}[sys.argv[1]]()
