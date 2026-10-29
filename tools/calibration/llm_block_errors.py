#!/usr/bin/env python3
"""Where the block-level AI is right / wrong (2026-10-26). One row per (bill, party block) the AI rated: AI chance,
arm C's mean chance over the block's can't-call members, the block's ACTUAL majority (all its members in the room),
and block roles. Prints accuracy of AI vs arm C by role.  Run: python3 llm_block_errors.py
"""
from __future__ import annotations
import sys, os, json, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import gains as G, levers as L
from corpus import load


def table():
    man = json.load(open(os.path.join(HERE, ".cache", "llm_block", "manifest.json"))); A = {}
    for f in glob.glob(os.path.join(HERE, ".cache", "llm_block", "answers_v1_*.jsonl")):
        for line in open(f):
            if line.strip().startswith("{"):
                d = json.loads(line); A[d["id"]] = d
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}; T = []
    for split, yr in (("confirm", "2025"), ("repeat", "2026")):
        te, _a, _b = G.load(split); pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        idx = collections.defaultdict(list)
        for i, r in enumerate(te):
            idx[tuple(r["bill"])].append(i)
        for c, v in man.items():
            if v["yr"] != yr or c not in A or c == "B139" or A[c].get("recognized"):
                continue
            k = tuple(v["bill"]); I = idx[k]; b = corpus[k]; ys = [te[i]["y"] for i in I]
            shape = "all no" if max(ys) == 0 else "all yes" if min(ys) == 1 else "split"
            for p in v["blocks"]:
                if p not in A[c]["p"]:
                    continue
                J = [i for i in I if te[i]["party"] == p]; ask = [i for i in J if abs(pC[i] - .5) < .31]
                T.append(dict(yr=yr, bill=c, party=p, ai=A[c]["p"][p] / 100, armc=float(np.mean(pC[ask])),
                              act=float(np.mean([te[i]["y"] for i in J]) > .5), n_ask=len(ask), shape=shape,
                              patron_party=b["chief_party"] == p, majority=b["majority"] == p,
                              venue="sub" if te[I[0]]["ven_sub"] else "com" if te[I[0]]["ven_com"] else "floor",
                              chamber=b["chamber"], own_cops=sum(1 for q in (b.get("cop_parties") or []) if q == p)))
    return T


def main():
    T = table()
    def show(name, f):
        g = collections.defaultdict(list)
        for t in T:
            g[f(t)].append(t)
        print(f"\n{name}")
        for k in sorted(g, key=str):
            R = g[k]; a = np.mean([(t["ai"] >= .5) == t["act"] for t in R]); c = np.mean([(t["armc"] >= .5) == t["act"] for t in R])
            print(f"  {str(k):28s} blocks {len(R):4d}  actual yes {np.mean([t['act'] for t in R]):.2f}  AI {a:.2f}  arm C {c:.2f}  AI mean chance {np.mean([t['ai'] for t in R]):.2f}")
    print(f"{len(T)} blocks")
    show("block is patron's party / majority party", lambda t: ("patron" if t["patron_party"] else "other") + "/" + ("maj" if t["majority"] else "min"))
    show("room's actual result", lambda t: t["shape"])
    show("venue x chamber", lambda t: t["venue"] + " " + t["chamber"])
    show("year x patron party", lambda t: t["yr"] + " " + ("patron" if t["patron_party"] else "other"))
    show("own-party co-patrons", lambda t: min(t["own_cops"], 3))
    json.dump(T, open(os.path.join(HERE, ".cache", "llm_block", "block_table.json"), "w"))


if __name__ == "__main__":
    main()
