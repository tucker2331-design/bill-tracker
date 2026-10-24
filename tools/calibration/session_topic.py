#!/usr/bin/env python3
"""H6 -- this session's party lines on this topic (owner, 2026-10-15: bring up the hardest third).

The model knows each party's record on a SUBJECT across all earlier years (subj_party) and each ROOM's rate this session
(ses_rate), but not how each party has voted on THIS SUBJECT THIS SESSION. Party lines move between sessions (2026: a
Democratic governor and legislature). For every first-vote ballot: the yes share of the voter's side (patron's party /
other party) on earlier first votes THIS SESSION in the same coarse subject, dated strictly before the vote, smoothed.
Tested with accept.stacked_year_ahead (2022/2024/2025 pooled, fixed hardest third reported).
"""
from __future__ import annotations
import sys, os, json, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import accept as AC, first_vote as FV

rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
subj = {}
for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
    s, b = k.split("|", 1); subj[(s, b)] = v
rc = FV.assemble()["rc"]
day = {r["bill"]: rc[r["bill"]][0][0] for r in rows}
events = collections.defaultdict(list)       # (session, subject, same) -> sorted [(date, y)]
for r in rows:
    for t in subj.get(r["bill"], []):
        events[(r["bill"][0], t, r["same"])].append((day[r["bill"]], r["y"]))
for k in events:
    events[k].sort()
import bisect
def sig(r):
    d = day[r["bill"]]; k_ = n_ = 0
    for t in subj.get(r["bill"], []):
        ev = events.get((r["bill"][0], t, r["same"]), [])
        i = bisect.bisect_left(ev, (d, -1))
        n_ += i; k_ += sum(y for _d, y in ev[:i])
    prior = .87 if r["same"] else .62
    rate = (k_ + 10 * prior) / (n_ + 10)
    s = float(r["same"])
    return {"st_same": (rate - prior) * s, "st_other": (rate - prior) * (1 - s), "st_n": min(n_, 200) / 200}
AC.stacked_year_ahead(sig, "H6 THIS SESSION'S PARTY LINES ON THIS TOPIC x voter side", ridge=10.0)
