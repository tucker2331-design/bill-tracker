#!/usr/bin/env python3
"""Online refit of the LINEAR half of the adopted blend (owner, 2026-10-19: "continue to try to improve").

online_layer.py showed the session's own temper is learnable from its earlier votes (2026 above all). This goes one
step further: before every session WEEK, the linear model (levers.linear_fn, adopted settings) is refit on all earlier
years PLUS this session's votes cast before that week, the session's votes weighted `W`. The bagged trees stay as
learned from earlier years (refitting them weekly would cost ~4 h per year). Blend 80/20 in log-odds as adopted.
Nothing from the scored week or later is used. Week = Monday-to-Sunday of the first-vote date.
Run: python3 online_relinear.py <W> [linear share]
"""
from __future__ import annotations
import sys, os, math, datetime, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, first_vote as FV, gains as G, accept as AC

LIN = {"hinges": 3, "lam": 10, "pairs": 8}
BAG = {"depth": 6, "subsample": 0.5, "colsample": 0.5, "bags": 8}


def week(d):
    x = datetime.date.fromisoformat(d[:10]); return (x - datetime.timedelta(days=x.weekday())).isoformat()


MIN = int(os.environ.get("ONLINE_MIN", "0"))


def main(W, share):
    rc = FV.assemble()["rc"]; pooled = []
    lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    for split in ("choose", "confirm", "repeat"):
        trn, ty = L.SPLITS[split]
        tr = [r for r in L.rows() if r["yr"] in trn]; te, p0, p1 = G.load(split)
        pb = np.load(os.path.join(L.PRED, f"gbm_{split}_{L._key(BAG)}.npy"))
        y = np.array([r["y"] for r in te], float); wk = np.array([week(rc[r["bill"]][0][0]) for r in te])
        pl = np.zeros(len(te))
        for w in sorted(set(wk)):
            past = np.where(wk < w)[0]; now = np.where(wk == w)[0]
            # 2024's second week was refit on week one alone (11 easy bills) and broke 21 room calls: below MIN
            # session votes the session is not yet representative -- use earlier years only
            if len(past) < MIN:
                past = past[:0]
            rows_ = tr + [te[i] for i in past]
            sw = np.concatenate([np.ones(len(tr)), np.full(len(past), W)])
            pl[now] = L.linear_fn(rows_, [te[i] for i in now], dict(LIN, sample_w=sw))
        p2 = 1 / (1 + np.exp(-((1 - share) * lo(pb) + share * lo(pl))))
        hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        room = lambda p: np.mean([(p[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
        r1 = (p1 >= .5) == (y == 1); r2 = (p2 >= .5) == (y == 1)
        d = collections.defaultdict(float)
        for r, a, c in zip(te, AC._ll(p1, y), AC._ll(p2, y)):
            d[str(r["bill"])] += a - c
        d = np.array(list(d.values())); pooled.append(d)
        np.save(os.path.join(L.PRED, f"online_relinear_{split}_W{W}_s{share}_m{MIN}.npy"), p2)
        print(f"{ty} W={W} share={share} min={MIN}: member {r1.mean():.4f}->{r2.mean():.4f}  hardest third {r1[hard].mean():.4f}->"
              f"{r2[hard].mean():.4f}  room {room(p1):.4f}->{room(p2):.4f}  z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}",
              flush=True)
    d = np.concatenate(pooled)
    print(f"POOLED W={W} share={share} min={MIN}: z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}")


if __name__ == "__main__":
    main(float(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 0.2)
