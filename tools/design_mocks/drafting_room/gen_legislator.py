#!/usr/bin/env python3
"""Generate project/Legislator.dc.html from legislator_example.json. Usage: python3 gen_legislator.py <out_dir>"""
import json, os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
ROOT = "/home/user/bill-tracker"
L = json.load(open(os.path.join(ROOT, "tools/calibration/pa/legislator_example.json")))
prof = json.load(open(os.path.join(ROOT, "tools/historical_cache/census/district_profiles.json")))
ch = "lower" if L["body"] == "H" else "upper"
L["names"] = {d: (v["member"] or {}).get("name", "") for d, v in prof["states"]["PA"]["chambers"][ch]["districts"].items()}
tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "legislator_template.html")).read()
out = tpl.replace("/*DATA*/", "const DATA = " + json.dumps(L, separators=(",", ":")) + ";")
os.makedirs(os.path.join(OUT, "project"), exist_ok=True)
open(os.path.join(OUT, "project", "Legislator.dc.html"), "w").write(out)
print("wrote", len(out))
