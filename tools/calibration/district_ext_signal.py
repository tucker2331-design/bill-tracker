#!/usr/bin/env python3
"""District make-up, extended, as a vote signal (historical_cache/districts_ext.py; owner 2026-10-24: externals).
ACS 2021 (previous maps, sessions 2020-23) and ACS 2023 (2022 maps, sessions 2024+); members placed in districts by the
election that seated them (geo_signal.place). 17 measures, each standardised within map vintage x chamber:
race (white, Black, Hispanic), log income, college degree, poverty, median age; industry (farming/forestry/fishing/
mining, manufacturing, public administration); armed forces, civilian veterans, foreign born, unemployed, transit
commuters, renters; log population density. Each x voter side.
Run: python3 rerun_no2021.py district_ext_signal:-
"""
from __future__ import annotations
import sys, os, json, gzip, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import geo_signal as GS

VA = os.path.join(HERE, "..", "historical_cache", "va_districts")
f = lambda v: float(v) if v not in (None, "", "null") and float(v) > -1e8 else float("nan")


def measures(d):
    tot = f(d["B03002_001E"]); ed = f(d["B15003_001E"]); pv = f(d["B17001_001E"])
    return {"white": f(d["B03002_003E"]) / tot, "black": f(d["B03002_004E"]) / tot, "hisp": f(d["B03002_012E"]) / tot,
            "income": math.log(f(d["B19013_001E"])), "college": sum(f(d[k]) for k in ("B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E")) / ed,
            "poverty": f(d["B17001_002E"]) / pv, "age": f(d["B01002_001E"]), "farm": f(d["DP03_0033PE"]), "mfg": f(d["DP03_0035PE"]),
            "pubadm": f(d["DP03_0045PE"]), "armed": f(d["DP03_0006PE"]), "vet": f(d["DP02_0070PE"]), "foreign": f(d["DP02_0094PE"]),
            "unemp": f(d["DP03_0005PE"]), "transit": f(d["DP03_0021PE"]), "renter": f(d["DP04_0047PE"]),
            "density": math.log(f(d["B01003_001E"]) / f(d["ALAND_SQMI"]))}


Z = {}
for vint in ("2021", "2023"):
    for ch, nm in (("H", "lower"), ("S", "upper")):
        raw = json.load(gzip.open(os.path.join(VA, f"ext_{vint}_{nm}.json.gz"), "rt"))
        M = {int(k.lstrip("0")): measures(v) for k, v in raw.items() if k.lstrip("0").isdigit()}
        keys = sorted(next(iter(M.values())))
        A = np.array([[M[d][k] for k in keys] for d in sorted(M)]); mu = np.nanmean(A, 0); sd = np.nanstd(A, 0)
        for i, d in enumerate(sorted(M)):
            Z[(vint, ch, d)] = {k: (0.0 if np.isnan(A[i, j]) else float((A[i, j] - mu[j]) / (sd[j] or 1))) for j, k in enumerate(keys)}
KEYS = sorted(next(iter(Z.values())))


def district(yr, ch, who):
    e = GS.ELECTION.get((ch, yr)); vint = "2021" if yr <= 2023 else "2023"
    d = GS.SEAT.get((e, ch, GS.person(who) or who)) if e else None
    return Z.get((vint, ch, d)) if d else None


def sig(r):
    z = district(r["yr"], "S" if r["chamber_S"] else "H", r["who"]); s = float(r["same"])
    return {f"dx_{k}_{side}": ((z[k] if z else 0.0) * (s if side == "same" else 1 - s)) for k in KEYS for side in ("same", "other")}
