#!/usr/bin/env python3
"""Two more district tests on the extended data (owner 2026-10-24: externals).
  pair:    the voter's district resembles the PATRON's district (17 standardised measures; similarity = minus the
           Euclidean distance / sqrt(17)), x side -- members from look-alike places back each other's bills across
           party lines?
  subject: 6 key measures (white, college, poverty, farm, renter, density) x the 10 commonest subject groups x side,
           all years 2020+ (district_subject.py had 2024+ only).
Run: python3 rerun_no2021.py district_pair:pair_mode   /   district_pair:subject_mode
"""
from __future__ import annotations
import sys, os, json, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import accept as AC, district_ext_signal as D
from corpus import load

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
SUBJ = {}
for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
    s, b = k.split("|", 1); SUBJ[(s, b)] = v
TOP = [s for s, _ in collections.Counter(x for v in SUBJ.values() for x in v).most_common(10)]
KEY6 = ["white", "college", "poverty", "farm", "renter", "density"]


def pair_mode():
    def sig(r):
        ch = "S" if r["chamber_S"] else "H"; v = D.district(r["yr"], ch, r["who"])
        b = corpus[r["bill"]]; p = D.district(r["yr"], r["bill"][1][0], b["chief"]) if b["chief"] else None
        s = float(r["same"])
        if not (v and p) or D.GS.person(b["chief"]) == D.GS.person(r["who"]):
            return {"sim_same": 0.0, "sim_other": 0.0, "sim_has": 0.0}
        sim = -math.sqrt(sum((v[k] - p[k]) ** 2 for k in D.KEYS) / len(D.KEYS)) + 1.0
        return {"sim_same": sim * s, "sim_other": sim * (1 - s), "sim_has": 1.0}
    AC.stacked_year_ahead(sig, "VOTER'S DISTRICT RESEMBLES THE PATRON'S x side", ridge=10.0)


def subject_mode():
    def sig(r):
        z = D.district(r["yr"], "S" if r["chamber_S"] else "H", r["who"]); subs = set(SUBJ.get(r["bill"], [])); s = float(r["same"])
        out = {}
        for i, t in enumerate(TOP):
            for k in KEY6:
                x = z[k] if (z and t in subs) else 0.0
                out[f"{i}_{k}_same"] = x * s; out[f"{i}_{k}_other"] = x * (1 - s)
        return out
    AC.stacked_year_ahead(sig, "DISTRICT x SUBJECT, all years (6 measures x 10 subjects x side)", ridge=10.0)
