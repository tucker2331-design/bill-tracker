#!/usr/bin/env python3
"""Combinations: what the model gets wrong in a CELL of district type / region x topic x side (owner 2026-10-24: "if
the district is all rich white people and its in northern virginia do we think they are for or against data centers
... brain storm deeper then your singular tests and run in parallel").

Method -- residual target encoding, year-ahead:
  1. District TYPES: k-means on the 17 standardised district measures (both maps pooled, so a type means the same
     thing on the old and new map); REGIONS: k-means on district interior points. Members placed as in
     district_ext_signal.
  2. For a cell definition (e.g. district type x subject x side), the locked model's out-of-sample miss in that cell,
     mean(actual - predicted), from EARLIER years only (2021 excluded -- the COVID session), shrunk toward 0 with
     M pseudo-votes. A bill with several subjects averages its cells.
  3. That shrunk miss (x side) is the input; tested with rerun_no2021.evaluate (learning years 2022+, scored 2024 +
     2025, 2026 replication).
Modes: dtype6, dtype10, region7, dtype_topic, dtype_room, region_pair, dtype_party.
Run: python3 rerun_no2021.py combo_cells:<mode>
"""
from __future__ import annotations
import sys, os, json, math, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, district_ext_signal as D, geo_signal as GS
from corpus import load

M_SHRINK = float(os.environ.get("COMBO_M", "30"))
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
SUBJ = {}
for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
    s, b = k.split("|", 1); SUBJ[(s, b)] = v


def kmeans(X, k, seed=0, iters=100):
    rng = np.random.default_rng(seed); C = X[rng.choice(len(X), k, replace=False)]
    for _ in range(iters):
        lab = np.argmin(((X[:, None, :] - C[None]) ** 2).sum(-1), 1)
        C2 = np.array([X[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
        if np.allclose(C2, C):
            break
        C = C2
    return lab


DKEYS = sorted(D.Z); XD = np.array([[D.Z[k][m] for m in D.KEYS] for k in DKEYS])
TYPE6 = dict(zip(DKEYS, kmeans(XD, 6))); TYPE10 = dict(zip(DKEYS, kmeans(XD, 10)))
GKEYS = sorted(k for k in GS.G if k[0] in ("2021", "2023"))
XG = np.array([[GS.G[k][0], GS.G[k][1] * math.cos(math.radians(37.5))] for k in GKEYS])
REGION = dict(zip(GKEYS, kmeans(XG, 7)))


def seat(yr, ch, who):
    e = GS.ELECTION.get((ch, yr)); vint = "2021" if yr <= 2023 else "2023"
    d = GS.SEAT.get((e, ch, GS.person(who) or who)) if e else None
    return (vint, ch, d) if d else None


_topics = None


def topics():
    global _topics
    if _topics is None:
        saved = sys.argv; sys.argv = [saved[0]]          # issue_points reads K / ridge from argv at import
        import issue_points as IP
        sys.argv = saved
        keys = [k for k in corpus if k in IP.SUMM]
        train = [k for k in keys if k[0][:4].isdigit() and int(k[0][:4]) <= 2022]
        T = IP.topics(train, keys); _topics = {k: int(np.argmax(np.abs(v))) * 2 + int(v[np.argmax(np.abs(v))] > 0) for k, v in T.items()}
    return _topics


IDENTITY = ("mem_subj", "mem_room", "mem_patron", "patron_room", "room_subj", "patron_subj")


def cells(r, mode):
    same = r["same"]
    if mode in IDENTITY:                  # people and rooms, no district needed
        subs = SUBJ.get(r["bill"], []) or ["(none)"]; P = corpus[r["bill"]]["chief"] or "?"
        if mode == "mem_subj":
            return [("ms", r["who"], s, same) for s in subs]
        if mode == "mem_room":
            return [("mr", r["who"], r["room"], same)]
        if mode == "mem_patron":
            return [("mp", r["who"], P)]
        if mode == "patron_room":
            return [("pr", P, r["room"], same)]
        if mode == "room_subj":
            return [("rs", r["room"], s, same) for s in subs]
        if mode == "patron_subj":
            return [("ps", P, s, same) for s in subs]
    ch = "S" if r["chamber_S"] else "H"; st = seat(r["yr"], ch, r["who"])
    if not st:
        return []
    subs = SUBJ.get(r["bill"], []) or ["(none)"]
    if mode == "dtype6":
        return [("t6", TYPE6.get(st), s, same) for s in subs]
    if mode == "dtype10":
        return [("t10", TYPE10.get(st), s, same) for s in subs]
    if mode == "region7":
        return [("rg", REGION.get(st), s, same) for s in subs]
    if mode == "dtype_topic":
        t = topics().get(r["bill"]); return [("tt", TYPE6.get(st), t, same)] if t is not None else []
    if mode == "dtype_room":
        return [("tr", TYPE6.get(st), r["room"], same)]
    if mode == "region_pair":
        b = corpus[r["bill"]]; ps = seat(r["yr"], r["bill"][1][0], b["chief"]) if b["chief"] else None
        return [("rp", REGION.get(st), REGION.get(ps) if ps else -1, s, same) for s in subs]
    if mode == "dtype_party":
        return [("tp", TYPE6.get(st), r["party"], corpus[r["bill"]]["chief_party"], s) for s in subs]
    raise ValueError(mode)


def build(mode):
    """year -> {cell: (sum of misses, n)} from years strictly before it (2021 excluded)."""
    B = {t: v for t, v in AC.base_preds().items() if t >= 2022}
    B[2026] = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    p23 = os.path.join(HERE, ".cache", "p2023.pkl")
    if os.environ.get("FIT2023") == "1" and os.path.exists(p23):
        B[2023] = pickle.load(open(p23, "rb"))       # build_2023.py: LIS legacy 2023, locked model trained 2019-22
    per_year = {}
    for t, (te, p) in B.items():
        acc = collections.defaultdict(lambda: [0.0, 0])
        for r, q in zip(te, p):
            cs = cells(r, mode)
            for c in cs:
                a = acc[c]; a[0] += (r["y"] - q) / len(cs); a[1] += 1 / len(cs)
        per_year[t] = acc
    table = {}
    for t in sorted(B):
        tot = collections.defaultdict(lambda: [0.0, 0.0])
        for u, acc in per_year.items():
            if u < t:
                for c, (s_, n) in acc.items():
                    tot[c][0] += s_; tot[c][1] += n
        table[t] = tot
    return table


def make(mode):
    T = build(mode)
    def sig(r):
        tab = T.get(r["yr"], {}); cs = cells(r, mode); s = float(r["same"])
        x = float(np.mean([tab[c][0] / (tab[c][1] + M_SHRINK) if c in tab else 0.0 for c in cs])) * 10 if cs else 0.0
        return {"cm_same": x * s, "cm_other": x * (1 - s)}
    AC.stacked_year_ahead(sig, f"COMBINATION CELLS: {mode} (shrink {M_SHRINK:g})", ridge=10.0)


def combo_id():
    """The identity families (all leaned positive in 2025 and 2026), together: one input each, x side."""
    fams = ("mem_subj", "patron_subj", "room_subj", "patron_room", "mem_patron", "mem_room")
    T = {m: build(m) for m in fams}
    def sig(r):
        s = float(r["same"]); out = {}
        for m in fams:
            tab = T[m].get(r["yr"], {}); cs = cells(r, m)
            x = float(np.mean([tab[c][0] / (tab[c][1] + M_SHRINK) if c in tab else 0.0 for c in cs])) * 10 if cs else 0.0
            out[f"{m}_same"] = x * s; out[f"{m}_other"] = x * (1 - s)
        return out
    AC.stacked_year_ahead(sig, f"COMBINATION CELLS: identity families together (shrink {M_SHRINK:g})", ridge=10.0)


def combo_all():
    """Every cell family that leaned positive in 2025 AND 2026 (wave 1), together: one input each, x side."""
    fams = ("mem_subj", "mem_patron", "mem_room", "dtype_party", "region_pair", "region7", "dtype6")
    T = {m: build(m) for m in fams}
    def sig(r):
        s = float(r["same"]); out = {}
        for m in fams:
            tab = T[m].get(r["yr"], {}); cs = cells(r, m)
            x = float(np.mean([tab[c][0] / (tab[c][1] + M_SHRINK) if c in tab else 0.0 for c in cs])) * 10 if cs else 0.0
            out[f"{m}_same"] = x * s; out[f"{m}_other"] = x * (1 - s)
        return out
    AC.stacked_year_ahead(sig, f"COMBINATION CELLS: all positive families together (shrink {M_SHRINK:g})", ridge=10.0)


for _m in ("dtype6", "dtype10", "region7", "dtype_topic", "dtype_room", "region_pair", "dtype_party") + IDENTITY:
    globals()[_m] = (lambda m: (lambda: make(m)))(_m)
