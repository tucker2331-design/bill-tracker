#!/usr/bin/env python3
"""Hard third, new public information (owner 2026-10-25: "exhaust all options for new info"). Two untested sources,
both public before the vote, scored ONLY on can't-call votes (arm C |p - .5| < .31), year-ahead both ways:
  A. staff set-phrases in the official introduced summary (LIS staff wording, not opinion): commission
     recommendation, reenactment clause, identical-to, study / work group / report, delayed or specific effective date,
     emergency, pilot, "contingent" funding.  Text-derived -> INTERNAL ONLY (Standard #3).
  B. same room, same session, earlier date: highest TF-IDF similarity to a bill the room killed unanimously, and to
     one it passed unanimously.
Each signal enters x side (voter in patron's party or not) on top of arm C's log-odds; weights fit on one year,
scored on the other.  Run: python3 hard3_newinfo.py
"""
from __future__ import annotations
import sys, os, re, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import llm_member as M, levers as L, gains as G, first_vote as FV, summary_memory as SM
from corpus import load
import knn_own as K

PHRASES = {"commission": r"recommendation of the|recommended by the", "reenact": r"reenact", "identical": r"identical to",
           "study": r"\bstudy\b|work group|workgroup|\breport\b", "effective": r"effective date|shall become effective",
           "emergency": r"emergency exists|\bemergency\b", "pilot": r"\bpilot\b", "contingent": r"contingent|subject to appropriation"}


def build():
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    summ = SM.summaries(); rc = FV.assemble()["rc"]
    date = {k: v[0][0] for k, v in rc.items() if v and v[0][0] != "9999"}
    text = {k: M.blind(corpus[k]["title"] + ". " + summ[k]) for k in summ if k in corpus}
    vec = M._tfidf({k: [w for w in M.WORD.findall(t.lower()) if w not in M.STOP] for k, t in text.items()})
    R = [r for r in L.rows() if r["yr"] >= 2019 and r["bill"] in date]
    by_bill = collections.defaultdict(list); by_room = collections.defaultdict(set)
    for r in R:
        by_bill[r["bill"]].append(r); by_room[r["room"]].add(r["bill"])
    dead = {k for k, rs in by_bill.items() if max(x["y"] for x in rs) == 0}
    alive = {k for k, rs in by_bill.items() if min(x["y"] for x in rs) == 1}
    out = {}
    for split in ("confirm", "repeat"):
        te, _a, _b = G.load(split)
        pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        I = [i for i, r in enumerate(te) if abs(pC[i] - .5) < .31 and r["bill"] in vec and r["bill"] in date]
        cache = {}; F = []
        for i in I:
            r = te[i]; k = r["bill"]
            if k not in cache:
                s = summ[k].lower(); f = [1.0 if re.search(p, s) else 0.0 for p in PHRASES.values()]
                prev = [c for c in by_room[r["room"]] if c[0] == k[0] and date.get(c, "9999") < date[k] and c in vec]
                sk = max([M._cos(vec[k], vec[c]) for c in prev if c in dead] or [0.0])
                sp = max([M._cos(vec[k], vec[c]) for c in prev if c in alive] or [0.0])
                cache[k] = f + [sk, sp]
            F.append(cache[k])
        F = np.array(F); side = np.array([1.0 if te[i]["same"] else -1.0 for i in I])
        X = np.column_stack([F, F * side[:, None]])
        y = np.array([te[i]["y"] for i in I], float)
        killed = np.array([k in dead for k in [te[i]["bill"] for i in I]])
        out[split] = (M_lo(pC[I]), X, y, killed, F)
    return out


def M_lo(p):
    p = np.clip(p, 1e-6, 1 - 1e-6); return np.log(p / (1 - p))


def main():
    D = build(); names = list(PHRASES) + ["room_killed_similar", "room_passed_similar"]
    for split in ("confirm", "repeat"):
        _o, _X, y, killed, F = D[split]
        print(f"{split}: {len(y)} can't-call votes; share on unanimous-NO rooms {killed.mean():.1%}")
        for j, n in enumerate(names):
            m = F[:, j] > (0.5 if j < len(PHRASES) else 0.35)
            if m.sum() >= 30:
                print(f"   {n:20s} on {m.mean():5.1%} of votes; unanimous-NO {killed[m].mean():.1%} vs {killed[~m].mean():.1%} without")
    for a, b in (("confirm", "repeat"), ("repeat", "confirm")):
        off, X, y, _k, _F = D[a]; w = K.fit(off, X, y, lam=3.0)
        off, X, y, _k, _F = D[b]; p0 = 1 / (1 + np.exp(-off)); p1 = 1 / (1 + np.exp(-(off + X @ w)))
        r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1); c = np.abs(p1 - .5) >= .31
        print(f"fit {a} -> score {b}: right {r0.mean():.3f} -> {r1.mean():.3f} (fixed {(~r0 & r1).sum()}, broken {(r0 & ~r1).sum()}); "
              f"new calls {c.sum()} right {r1[c].mean() if c.any() else float('nan'):.3f}")


if __name__ == "__main__":
    main()
