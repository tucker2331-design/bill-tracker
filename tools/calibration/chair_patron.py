#!/usr/bin/env python3
"""The patron chairs the committee that hears the bill (owner list, 2026-10-23: non-AI ideas). A chair controls the
docket and can steer their own bills; the member model knows if the patron SITS in the room (pat_in_room), not if they
RUN it. Rosters: historical_cache/va_chairs/<session code>.json (2019-2025; no 2026 file -> 0 there). Matched by
chamber + committee name ("Senate Education and Health" = room "S:Education and Health") + surname.
  pc_same / pc_other   the patron is the chair, x voter side
  vc_same / vc_other   the VOTER is the chair, x side
Run through rerun_no2021.py (learning years 2022+): python3 rerun_no2021.py chair_patron:-
"""
from __future__ import annotations
import sys, os, re, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from corpus import load

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
CODE = {2019: "191", 2020: "201", 2021: "211", 2022: "221", 2023: "231", 2024: "241", 2025: "251"}
norm = lambda s: re.sub(r"[^a-z]", "", re.sub(r"^(house|senate)\s+", "", s.lower()).replace("&", "and"))
sur = lambda n: re.sub(r"[^a-z]", "", (n or "").split(",")[0].split()[-1].lower()) if n else ""
CHAIR = {}
for yr, code in CODE.items():
    p = os.path.join(HERE, "..", "historical_cache", "va_chairs", f"{code}.json")
    for cc, v in json.load(open(p)).items():
        if v.get("chair"):
            CHAIR[(yr, cc[0], norm(v["name"]))] = sur(v["chair"][0])


def sig(r):
    ch, name = r["room"].split(":", 1) if ":" in r["room"] else ("?", r["room"])
    c = CHAIR.get((r["yr"], ch, norm(name)))
    if not c:
        return {"pc_same": 0.0, "pc_other": 0.0, "vc_same": 0.0, "vc_other": 0.0}
    pc = float(sur(corpus[r["bill"]]["chief"]) == c); vc = float(sur(r["who"]) == c); s = float(r["same"])
    return {"pc_same": pc * s, "pc_other": pc * (1 - s), "vc_same": vc * s, "vc_other": vc * (1 - s)}
