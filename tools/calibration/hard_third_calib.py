#!/usr/bin/env python3
"""Two more hard-third attacks (2026-10-15), aimed at the votes that ended UNANIMOUS (51% of the hard third).

  P9  calibration    is the member model systematically too cautious in some cells? First the measured bias inside the
                     hard third (actual yes minus predicted, by voter side x venue), then a stacked recalibration: the
                     model's own log-odds interacted with side and venue, fitted on earlier years.
  P10 unanimity      how often THIS ROOM (subcommittee, else committee) ended unanimous at first votes -- in earlier years,
                     and earlier THIS session (strictly before the vote) -- x voter side.
Run: python3 hard_third_calib.py p9 | p10
"""
from __future__ import annotations
import sys, os, pickle, bisect, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV
from corpus import load

lg = lambda p: float(np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))))


def p9():
    B = AC.base_preds()
    bias = collections.defaultdict(lambda: [0, 0.0, 0.0])
    P = {}
    for t, (te, p) in B.items():
        hard = set(np.argsort(np.abs(p - .5))[:len(p) // 3].tolist())
        for i, r in enumerate(te):
            P[(r["bill"], r["who"])] = p[i]
            if i in hard:
                cell = ("patron's party" if r["same"] else "other party", "sub" if r["ven_sub"] else "com" if r["ven_com"] else "floor")
                b = bias[cell]; b[0] += 1; b[1] += r["y"]; b[2] += p[i]
    print("P9 BIAS INSIDE THE HARD THIRD (actual yes rate vs average predicted):")
    for cell, (n, y, pp) in sorted(bias.items(), key=lambda kv: -kv[1][0]):
        print(f"   {cell[0]:15s} {cell[1]:6s} n={n:6d}  actual yes {y / n:5.1%}  predicted {pp / n:5.1%}  gap {y / n - pp / n:+.1%}")
    def sig(r):
        l = lg(P[(r["bill"], r["who"])]); s = float(r["same"]); sub = float(r["ven_sub"]); com = float(r["ven_com"])
        return {"lg_other": l * (1 - s), "lg_sub": l * sub, "lg_com": l * com, "other_sub": (1 - s) * sub, "other_com": (1 - s) * com}
    AC.stacked_year_ahead(sig, "P9 RECALIBRATION (model log-odds x side x venue)", ridge=10.0)


def p10():
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    rc = FV.assemble()["rc"]
    import re
    SUB = re.compile(r"^assigned .+? sub:\s*(.+)$", re.I)
    def room(k, d):
        b = corpus[k]; sr = None
        for d_, t, _c in b["actions"]:
            if d_ and d_ <= d:
                m = SUB.match(t.strip())
                if m: sr = m.group(1).strip()
        return f"{FV.first_room(b) or '?'}/{sr or ''}"
    g = collections.defaultdict(list)
    for r in rows:
        g[r["bill"]].append(r["y"])
    ev = collections.defaultdict(list)          # room -> [(date, session, unanimous)]
    rk = {}
    for k, ys in g.items():
        d = rc[k][0][0]; rm = room(k, d); rk[k] = rm
        ev[rm].append((d, k[0], int(all(ys) or not any(ys))))
    for v in ev.values():
        v.sort()
    def sig(r):
        k = r["bill"]; d = rc[k][0][0]; e = ev[rk[k]]
        i = bisect.bisect_left(e, (d, "", -1))
        past = [u for dd, s, u in e[:i] if s != k[0]]; now = [u for dd, s, u in e[:i] if s == k[0]]
        a = (sum(past) + 5 * .45) / (len(past) + 5) - .45; b_ = (sum(now) + 5 * .45) / (len(now) + 5) - .45
        s = float(r["same"])
        return {"un_past_same": a * s, "un_past_other": a * (1 - s), "un_now_same": b_ * s, "un_now_other": b_ * (1 - s)}
    AC.stacked_year_ahead(sig, "P10 THIS ROOM'S HABIT OF UNANIMITY (earlier years, earlier this session) x side", ridge=10.0)


if __name__ == "__main__":
    {"p9": p9, "p10": p10}[sys.argv[1]]()
