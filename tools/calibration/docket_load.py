#!/usr/bin/env python3
"""Docket load and earlier agendas (owner list, 2026-10-23: non-AI ideas). From LIS DOCKET.CSV / SUBDOCKET.CSV
(2025-2026 only, already cached under historical_cache/va/; no new requests):
  dk_size   log number of bills on the same committee (or subcommittee) docket on the vote's date -- a crowded
            meeting may push bills to be continued or tabled
  dk_prior  number of EARLIER dockets this bill sat on before the vote date without a first vote (re-docketed)
each x voter side. 2022/2024 have no docket file (inputs 0), so only 2025 can teach the weights: the honest test is
the 2026 replication line of rerun_no2021.py.  Run: python3 rerun_no2021.py docket_load:-
"""
from __future__ import annotations
import sys, os, csv, gzip, math, collections, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import first_vote as FV

rc = FV.assemble()["rc"]
VA = os.path.join(HERE, "..", "historical_cache", "va")
iso = lambda d: datetime.datetime.strptime(d, "%m/%d/%Y").date().isoformat()
size = collections.Counter(); on = collections.defaultdict(list)
for code, yr in (("20251", "2025"), ("20261", "2026")):
    for fn, sub in (("DOCKET.CSV.gz", False), ("SUBDOCKET.CSV.gz", True)):
        for row in csv.DictReader(gzip.open(os.path.join(VA, code, fn), "rt", encoding="utf-8", errors="replace")):
            d = iso(row["Doc_date"]); room = row["Com_no"] + ("/" + row["Sub_no"] if sub else "")
            b = row["Bill_no"].strip(); key = (yr, b[:2] + " " + b[2:])
            size[(room, d)] += 1; on[key].append((d, room))


def sig(r):
    k = r["bill"]; s = float(r["same"])
    if k not in on:
        return {"dk_size_same": 0.0, "dk_size_other": 0.0, "dk_prior_same": 0.0, "dk_prior_other": 0.0}
    vd = rc[k][0][0]
    today = [size[(room, d)] for d, room in on[k] if d == vd]
    sz = math.log1p(max(today)) - 2.5 if today else 0.0
    prior = math.log1p(len({d for d, _r in on[k] if d < vd}))
    return {"dk_size_same": sz * s, "dk_size_other": sz * (1 - s), "dk_prior_same": prior * s, "dk_prior_other": prior * (1 - s)}
