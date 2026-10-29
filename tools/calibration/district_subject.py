#!/usr/bin/env python3
"""District make-up x the bill's subject (owner 2026-10-24: externals). The member model reads district measures
(d_*: white, Black, Hispanic, income, college, poverty, owner-occupied, age; 2024+ only) as plain inputs; the trees
rarely cross them with a SPECIFIC subject. Here each district measure, centred within its chamber, is crossed with
the bill's coarse subject group (subject_labels.json; the 10 commonest groups) and with side -- e.g. renter-heavy
districts on housing bills. 2024 has the measures but learns from 2022 (none), so 2025 learns from 2024 and 2026 from
2024-25 -- the honest lines are 2025 and 2026.  Run: python3 rerun_no2021.py district_subject:-
"""
from __future__ import annotations
import sys, os, json, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import first_vote as FV

SUBJ = {}
for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
    s, b = k.split("|", 1); SUBJ[(s, b)] = v
TOP = [s for s, _ in collections.Counter(x for v in SUBJ.values() for x in v).most_common(10)]
D = ["d_white", "d_black", "d_college", "d_poverty", "d_owner", "d_income"]
rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["yr"] >= 2024 and r.get("d_has")]
MU = {(yr, ch): {d: sum(r[d] for r in rows if (r["yr"], r["chamber_S"]) == (yr, ch)) /
                 max(1, sum(1 for r in rows if (r["yr"], r["chamber_S"]) == (yr, ch))) for d in D}
      for yr in (2024, 2025, 2026) for ch in (0, 1)}


def sig(r):
    out = {}
    subs = set(SUBJ.get(r["bill"], [])); ok = r.get("d_has") and (r["yr"], r["chamber_S"]) in MU
    s = float(r["same"])
    for i, t in enumerate(TOP):
        for d in D:
            x = (r[d] - MU[(r["yr"], r["chamber_S"])][d]) if (ok and t in subs) else 0.0
            out[f"{i}_{d}_same"] = x * s; out[f"{i}_{d}_other"] = x * (1 - s)
    return out
