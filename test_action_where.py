#!/usr/bin/env python3
"""Action_Where — where each history action happened, for What's new's one line per bill (owner 2026-11-01).

VIRGINIA (cached 2026 LIS blobs, the test_state_va_goldens harness): Bill_Tracker stays BYTE-IDENTICAL (that golden
still passes); the side output has one code per history row; a code exists only where the row's OWN committee refid
names a committee, and every such code agrees with LIS's own leading chamber letter (a diagnostic cross-check only —
the code is never read from the text).
PENNSYLVANIA (real 2025_0 sample): codes from each action's @actionChamber (0 unknown); the short line is built from
verb + committee + tally, sentence case, no date (SB509 -> "Referred to Transportation").

GOLDEN (goldens/action_where.json): a SHA-256 of both states' grids. Re-capture ONLY for an intended change:
python3 test_action_where.py --write
"""
import datetime
import hashlib
import json
import os
import sys

import action_where
import test_state_va_goldens as G

FAILS = 0
GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goldens", "action_where.json")


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


# --- Virginia ---
ex = {}
out, digest = G.run(extras=ex)
with open(G.GOLDEN, encoding="utf-8") as f:
    check("VA Bill_Tracker records still byte-identical with the side output on", json.load(f)["sha256"] == digest)
aw, recs = ex["action_where"], {r["bill"]: r for r in out["records"]}
check("VA: one code string per bill, one code per history row",
      set(aw) == set(recs) and all(len(aw[b]) == len(recs[b]["history"]) for b in aw))
st = ex["action_where_stats"]
check("VA: every row placed — 10,011 by refid, 51,237 by LIS's chamber code, 4,166 where LIS lists none, 0 unknown",
      (st.get("action_where_structural"), st.get("action_where_lis_code"), st.get("action_where_no_chamber", 0),
       st.get("action_where_unknown", 0)) == (10011, 51237, 4166, 0), json.dumps(st))
check("VA: refid and LIS code never disagree (0)", st.get("action_where_disagree", 0) == 0)
check("VA: only H / S / 0 codes", set("".join(aw.values())) <= {"H", "S", "0"})
va_grid = action_where.rows_for(aw)

# --- Pennsylvania ---
import pa_bill_tracker as J
import test_pa_intake as T
_r, comp, _ro, _cal, pa_grid = J.build(T.SampleFetcher(), now=datetime.datetime(2026, 11, 1, 20, 0, tzinfo=datetime.timezone.utc))
row = {x[0]: x for x in pa_grid[1:]}
check("PA: header + one row per bill", pa_grid[0] == action_where.ACTION_WHERE_HEADER and len(row) == 5269)
check("PA: every action placed from @actionChamber (0 unknown)", comp["action_where_unknown"] == 0)
sb509 = json.loads(row["SB509"][2])
check("PA: SB509's last line is 'Referred to Transportation', in the House",
      (row["SB509"][1][-1], sb509[-1]) == ("H", "Referred to Transportation"))
hb17 = json.loads(row["HB17"][2])
check("PA: the Governor's actions are G; a verb whose number is in the prose keeps the source line",
      row["HB17"][1][-3:] == "GGG" and hb17[-1].startswith("Act No. 2 of 2026"))
hb1099 = json.loads(row["HB1099"][2])
check("PA: an 'Undefined Action' keeps the source's description (Codex #260)",
      any(ln.startswith("Motion to reconsider final passage") for ln in hb1099))
hist = {r["bill"]: [h["action"] for h in r["history"]] for r in _r}
built = [ln for b in row for ln, full in zip(json.loads(row[b][2] or "[]"), hist[b]) if ln != full]
check("PA: every line BUILT from structure carries no date (kept-whole source lines excepted)",
      len(built) > 15000 and not any(", 202" in ln or ", 201" in ln for ln in built), f"{len(built)} built")

got = {"va": hashlib.sha256(json.dumps(va_grid).encode()).hexdigest(),
       "pa": hashlib.sha256(json.dumps(pa_grid).encode()).hexdigest(),
       "pa_short_from_full_action": comp["action_short_from_full_action"]}
if "--write" in sys.argv:
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump(got, f, indent=1, sort_keys=True)
    print(f"wrote {GOLDEN}")
else:
    with open(GOLDEN, encoding="utf-8") as f:
        check("golden: both Action_Where grids unchanged", json.load(f) == got)
sys.exit(1 if FAILS else 0)
