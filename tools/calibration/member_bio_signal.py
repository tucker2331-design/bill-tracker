#!/usr/bin/env python3
"""Who the member is outside the chamber (historical_cache/member_bio.py, Wikipedia; owner 2026-10-24: externals).
Covers members elected 2019-2025 (sessions 2020+). Inputs x voter side:
  law_court   the member is a lawyer AND the room is a Courts of Justice / Judiciary committee
  law         the member is a lawyer (any room)        mil   military service        woman
  age         (session year - birth year - 55) / 10, 0 when unknown
  edu_room / health_room / farm_room   educator / health worker / farmer AND the room is Education / Health / Agriculture
Run: python3 rerun_no2021.py member_bio_signal:-
"""
from __future__ import annotations
import sys, os, json, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from corpus import _party_lookup

_party, person = _party_lookup()
B = json.load(open(os.path.join(HERE, "..", "historical_cache", "va_members", "bios.json")))
BY = {}
for title, b in B.items():
    if b.get("missing_page"):
        continue
    for seat in b.get("seats", []):
        BY[person(seat["name"]) or seat["name"]] = b
        BY[person(title) or title] = b


def sig(r):
    b = BY.get(r["who"]); s = float(r["same"]); room = r["room"].lower()
    z = {k: 0.0 for k in ("law_court", "law", "mil", "woman", "age", "edu_room", "health_room", "farm_room")}
    if b:
        court = bool(re.search(r"courts of justice|judiciary", room))
        z.update(law_court=float(b["lawyer"] and court), law=float(b["lawyer"]), mil=float(b["military"]),
                 woman=float(b["woman"]), age=((r["yr"] - b["birth_year"] - 55) / 10) if b.get("birth_year") else 0.0,
                 edu_room=float(b["educator"] and "education" in room), health_room=float(b["health"] and "health" in room),
                 farm_room=float(b["farmer"] and "agricultur" in room))
    return {f"{k}_{side}": v * (s if side == "same" else 1 - s) for k, v in z.items() for side in ("same", "other")}
