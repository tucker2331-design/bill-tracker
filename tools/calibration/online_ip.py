#!/usr/bin/env python3
"""Position scores (ideal points) that update DURING the session (owner, 2026-10-21: "keep working on the goal").

first_vote.ideal_points() places members from contested roll calls of EARLIER years only, so a new member has no
position all session: 25% of 2024's votes (post-redistricting freshmen) and 9% of 2026's. Here, before each session
week, the SVD is recomputed per chamber on earlier years PLUS this session's contested roll calls dated before that
week, and the ten ip_* inputs of that week's votes are rebuilt from it (same formulas as first_vote.add_ideal).
Models are trained exactly as arm B (static inputs for the training years); only the scored week's inputs change.
Compared with arm B's saved predictions. Run: python3 online_ip.py <split>
"""
from __future__ import annotations
import sys, os, math, json, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV, levers as L, gains as G, accept as AC, content_votes as CVT
from corpus import load, _party_lookup, PEOPLE
from online_relinear import week

LIN = {"hinges": 3, "lam": 10, "pairs": 8}


def contested():
    people = json.load(open(PEOPLE))
    chamber_of = {k: ("H" if v.get("chamber") == "lower" else "S") for k, v in people.items() if isinstance(v, dict)}
    out = []
    for s, b, vid, date, ven, ballots in CVT.build()["rolls"]:
        sup = sum(x[2] for x in ballots) / len(ballots)
        if .10 <= sup <= .90:
            chs = collections.Counter(chamber_of.get(w) for w, _p, _s in ballots if chamber_of.get(w))
            out.append((int(s[:4]), chs.most_common(1)[0][0] if chs else b[0], date or "9999", ballots))
    return out


def points(rolls_by_ch):
    pts_all = {}
    for ch, rolls in rolls_by_ch.items():
        if not rolls:
            continue
        mem = sorted({w for bl in rolls for w, _p, _s in bl}); mi = {w: i for i, w in enumerate(mem)}
        M = np.zeros((len(mem), len(rolls)), np.float32); pm = {}
        for j, bl in enumerate(rolls):
            for w, p_, s_ in bl:
                M[mi[w], j] = 1.0 if s_ else -1.0; pm[w] = p_
        cnt = (M != 0).sum(0); cnt[cnt == 0] = 1
        M = np.where(M != 0, M - (M.sum(0) / cnt), 0)
        U, S, _ = np.linalg.svd(M, full_matrices=False); X = U[:, :2] * S[:2]; nv = (M != 0).sum(1)
        if np.mean([X[mi[w], 0] for w in mem if pm.get(w) == FV.PARTIES[0]] or [0]) > 0:
            X[:, 0] = -X[:, 0]
        X = X / (X.std(0) + 1e-9)
        for w, i in mi.items():
            pts_all[w] = (float(X[i, 0]), float(X[i, 1]), int(nv[i]))
    return pts_all


def apply(rows, pts, corpus, person):
    out = []
    for r in rows:
        r = dict(r); bill = corpus[r["bill"]]; m = pts.get(r["who"])
        coal = [pts[k] for k in {person(bill["chief"]) or bill["chief"]} | {person(c) or c for c in bill["cops"]} if k in pts]
        b1 = float(np.mean([c[0] for c in coal])) if coal else 0.0; b2 = float(np.mean([c[1] for c in coal])) if coal else 0.0
        if m:
            r.update(ip_has=1, ip_m1=m[0], ip_m2=m[1], ip_n=math.log1p(m[2]),
                     ip_dist=float(math.hypot(m[0] - b1, m[1] - b2)) if coal else 0.0, ip_toward=float(-abs(m[0] - b1)) if coal else 0.0)
        else:
            r.update(ip_has=0, ip_m1=0.0, ip_m2=0.0, ip_dist=0.0, ip_toward=0.0, ip_n=0.0)
        r.update(ip_b1=b1, ip_b2=b2, ip_spread=float(np.ptp([c[0] for c in coal])) if len(coal) > 1 else 0.0, ip_bhas=int(bool(coal)))
        out.append(r)
    return out


def main(split):
    trn, ty = L.SPLITS[split]; rc = FV.assemble()["rc"]
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}; _party, person = _party_lookup()
    tr = [r for r in L.rows() if r["yr"] in trn]; te, p0, p1 = G.load(split)
    pB = np.load(os.path.join(L.PRED, f"online_relinear_{split}_W3.0_s0.3_m3000.npy"))
    C = contested(); prior = collections.defaultdict(list)
    for y, ch, d, bl in C:
        if y < ty:
            prior[ch].append(bl)
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    Xtr, ytr = X(tr), np.array([r["y"] for r in tr], float)
    trees = [L.GBMX(depth=6, lr=.03, rounds=260, subsample=.5, colsample=.5, seed=b).fit(Xtr, ytr) for b in range(8)]
    wk = np.array([week(rc[r["bill"]][0][0]) for r in te]); y = np.array([r["y"] for r in te], float)
    p2 = np.zeros(len(te)); lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    for w in sorted(set(wk)):
        now = np.where(wk == w)[0]; past = np.where(wk < w)[0]
        ses = {ch: prior[ch] + [bl for yy, c, d, bl in C if yy == ty and c == ch and d < w] for ch in ("H", "S")}
        rows_now = apply([te[i] for i in now], points(ses), corpus, person)
        pt = np.mean([m.predict(X(rows_now)) for m in trees], axis=0)
        if len(past) < 3000:
            past = past[:0]
        sw = np.concatenate([np.ones(len(tr)), np.full(len(past), 3.0)])
        pl = L.linear_fn(tr + [te[i] for i in past], rows_now, dict(LIN, sample_w=sw))
        p2[now] = 1 / (1 + np.exp(-(.7 * lo(pt) + .3 * lo(pl))))
    np.save(os.path.join(L.PRED, f"online_ip_{split}.npy"), p2)
    hard = np.argsort(np.abs(p0 - .5))[:len(y) // 3]
    g = collections.defaultdict(list)
    for i, r in enumerate(te):
        g[r["bill"]].append(i)
    room = lambda p: np.mean([((p[I] >= .5).sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
    r1 = (pB >= .5) == (y == 1); r2 = (p2 >= .5) == (y == 1)
    d = collections.defaultdict(float)
    for r, a, c in zip(te, AC._ll(pB, y), AC._ll(p2, y)):
        d[str(r["bill"])] += a - c
    d = np.array(list(d.values()))
    nh = np.array([r["ip_has"] == 0 for r in te])
    print(f"{ty} online positions vs arm B: member {r1.mean():.4f}->{r2.mean():.4f}  hardest third {r1[hard].mean():.4f}->"
          f"{r2[hard].mean():.4f}  room(count) {room(pB):.4f}->{room(p2):.4f}  z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}; "
          f"members with no prior position: {r1[nh].mean():.4f}->{r2[nh].mean():.4f}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
