#!/usr/bin/env python3
"""Fine subject labels (subject_labels.json labels_fine, ~1,000 kinds) vs the 43 coarse ones the model reads
(owner, 2026-10-22: fewer wrong calls). The worst wrong calls of 2026 were subject-driven -- e.g. health-insurance
coverage requirements tabled without dissent, inside the broad "Health" / "Insurance" labels.
For each first vote, from EARLIER years' first votes only (year-ahead, no same-year information):
  fs_party   support rate of voters of this party on bills of this fine subject by a patron of this party (shrunk)
  fs_mem     this member's support rate on this fine subject, this side (shrunk toward fs_party)
  fs_n       log evidence count
each x voter side; stacked on the locked model (accept.stacked_year_ahead, z >= 3).
Run: python3 fine_subjects.py
"""
from __future__ import annotations
import sys, os, json, math, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import accept as AC, first_vote as FV
from corpus import load

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
FINE = {}
for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_fine"].items():
    s, b = k.split("|", 1); FINE[(s, b)] = v
ROWS = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] >= 2019]
YEARS = sorted({r["yr"] for r in ROWS})
party_c = {}; mem_c = {}
for Y in YEARS:                                   # counts from years BEFORE Y
    pc = collections.Counter(); mc = collections.Counter()
    for r in ROWS:
        if r["yr"] >= Y:
            continue
        cp = corpus[r["bill"]]["chief_party"]
        for f in FINE.get(r["bill"], []):
            pc[(f, r["party"], cp, "n")] += 1; pc[(f, r["party"], cp, "s")] += r["y"]
            mc[(r["who"], f, r["same"], "n")] += 1; mc[(r["who"], f, r["same"], "s")] += r["y"]
    party_c[Y] = pc; mem_c[Y] = mc


def sig(r):
    fs = FINE.get(r["bill"], []); s = float(r["same"])
    if not fs or r["yr"] not in party_c:
        return {"fp_same": 0.0, "fp_other": 0.0, "fm_same": 0.0, "fm_other": 0.0, "fn": 0.0}
    pc, mc = party_c[r["yr"]], mem_c[r["yr"]]; cp = corpus[r["bill"]]["chief_party"]
    n = sum(pc[(f, r["party"], cp, "n")] for f in fs); k = sum(pc[(f, r["party"], cp, "s")] for f in fs)
    base = .85 if r["same"] else .55
    fp = (k + 20 * base) / (n + 20)
    mn = sum(mc[(r["who"], f, r["same"], "n")] for f in fs); mk = sum(mc[(r["who"], f, r["same"], "s")] for f in fs)
    fm = (mk + 5 * fp) / (mn + 5)
    lg = lambda q: math.log(q / (1 - q))
    return {"fp_same": lg(fp) * s, "fp_other": lg(fp) * (1 - s), "fm_same": (lg(fm) - lg(fp)) * s,
            "fm_other": (lg(fm) - lg(fp)) * (1 - s), "fn": math.log1p(n)}


if __name__ == "__main__":
    AC.stacked_year_ahead(sig, "FINE SUBJECTS: party and member support by fine subject (earlier years) x side", ridge=10.0)
