#!/usr/bin/env python3
"""Generate the drafting room v3 mock (project/Main.dc.html) from the PA worked-example data.
Run from a folder holding main_v4_template.html; writes project/Main.dc.html there."""
import json
import os
import sys

HERE = os.getcwd() if len(sys.argv) < 2 else sys.argv[1]
ROOT = "/home/user/bill-tracker"
E = json.load(open(os.path.join(ROOT, "tools/calibration/pa/example_drafting.json")))
P = json.load(open(os.path.join(ROOT, "tools/historical_cache/census/district_profiles.json")))["states"]["PA"]["chambers"]["lower"]["districts"]

dist = []
for r in E["districts"]:
    pl = P[r["d"]]["places"]
    dist.append([r["d"], r["name"] or "(vacant)", r["party"] or "", r["seats"], r["new_member"], r["bills_filed_2025_26"],
                 r["municipalities"], r["school_districts"], r["counties"], r["senate_overlap"], r["people"],
                 pl["nursing_homes"], pl["nursing_home_beds"], pl["hospitals"], pl["schools"]])
DATA = {"dist": dist, "mv": E["measure_values"], "ml": E["measures"], "shapes": E["shapes"], "senators": E["senators"],
        "steer": E["steering"], "rec": E["room_record_2019_2024"], "ap": E["appropriations"], "ft": E["filing_time"],
        "eb": E["earlier_bills"], "parts": E["parts"],
        "mu": {k: v["of"] for k, v in json.load(open(os.path.join(ROOT, "tools/historical_cache/census/district_profiles.json")))["measures"].items()}}
tpl = open(os.path.join(HERE, "main_v4_template.html")).read()
out = tpl.replace("/*DATA*/", "const DATA = " + json.dumps(DATA, separators=(",", ":")) + ";")
os.makedirs(os.path.join(HERE, "project"), exist_ok=True)
open(os.path.join(HERE, "project", "Main.dc.html"), "w").write(out)
print("wrote", len(out))
