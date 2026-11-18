#!/usr/bin/env python3
"""Generate project/Main.dc.html (the drafting room) from the PA worked-example data."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/home/user/bill-tracker/tools/calibration/pa/example_drafting.json"
E = json.load(open(SRC))

dist = []
for r in E["districts"]:
    dist.append([r["d"], r["name"] or "(vacant)", r["party"] or "", r["seniors"], r["seniors_share"], r["seniors_moe"],
                 r["people"], r["nursing_homes"], r["beds"], r["hospitals"], r["seats"], r["new_member"],
                 r["bills_filed_2025_26"], r["carried_these_laws_since_2023"], r["municipalities"], r["school_districts"],
                 r["counties"], r["senate_overlap"]])
DATA = {
    "dist": dist,
    "shapes": E["shapes"],
    "senators": E["senators"],
    "steer": E["steering"],
    "rec": E["room_record_2019_2024"],
    "ap": E["appropriations"],
    "ft": E["filing_time"],
    "sw": E["statewide"],
}

TEMPLATE = open(os.path.join(HERE, "main_template.html")).read()
out = TEMPLATE.replace("/*DATA*/", "const DATA = " + json.dumps(DATA, separators=(",", ":")) + ";")
open(os.path.join(HERE, "project", "Main.dc.html"), "w").write(out)
print("wrote", len(out), "bytes")
