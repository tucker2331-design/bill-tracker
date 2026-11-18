#!/usr/bin/env python3
"""Data for the drafting-room mock: one worked idea (care for nursing-home residents), PA House, every number from
the public record. Writes example_drafting.json next to this file; the mock reads nothing else.

The example is chosen because all three layers exist for it: people (residents 65+, census), places (nursing homes
and certified beds, CMS) and a real steering choice (three laws reach the same goal through three different rooms).
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from pa_frame import frame  # noqa: E402
from pa_drafting import law_key  # noqa: E402
from pa_batch2 import rosters  # noqa: E402
from states import pa_roster as PR  # noqa: E402

LAWS = ["Health Care Facilities Act", "Human Services Code", "Older Adults Protective Services Act"]
ROOMS = {"AGING AND OLDER ADULT SERVICES": "Aging & Older Adult Services", "HEALTH": "Health", "HUMAN SERVICES": "Human Services"}
RECENT = ("2019_0", "2021_0", "2023_0")          # room names stable since 2019; 2025-26 still open


def main():
    F = frame()
    F["law_won"] = F["law"]          # the frame's became-law flag, before the column name is reused for the statute
    F["law"] = F.title.map(law_key)
    F["law_flag"] = F["law_won"]
    H = F[F.body == "H"]
    out = {"idea": "Care for nursing-home residents", "chamber": "House"}

    # 1. steering: which room each law went to (House, 2019-2024), and that room's record by standing
    steer = []
    for law in LAWS:
        g = H[(H.law == law) & H.session.isin(RECENT) & (H.cmte != "(none)")]
        vc = g.cmte.value_counts()
        steer.append({"law": law, "bills": int(len(g)),
                      "rooms": [{"room": ROOMS.get(k, k.title()), "k": int(v), "n": int(len(g))} for k, v in vc.head(3).items()]})
    out["steering"] = steer
    rec = {}
    R = H[H.session.isin(RECENT)]
    for code, nice in ROOMS.items():
        g = R[R.cmte == code]
        rec[nice] = {"majority": {"k": int(g[g.in_maj == 1].out.sum()), "n": int((g.in_maj == 1).sum())},
                     "minority": {"k": int(g[g.in_maj == 0].out.sum()), "n": int((g.in_maj == 0).sum())}}
    out["room_record_2019_2024"] = rec

    # 2. district table (all 203 House seats)
    with open(os.path.join(ROOT, "tools", "historical_cache", "census", "district_profiles.json")) as f:
        P = json.load(f)
    D = P["states"]["PA"]["chambers"]["lower"]["districts"]
    members, chair, _ = rosters()
    seat = collections.defaultdict(list)
    for code, nice in ROOMS.items():
        k = ("H", PR.committee_key("House", code))
        for d in members.get(k, ()):
            seat[str(d).zfill(3)].append(nice + (" (chair)" if str(chair.get(k)) == str(d) else ""))
    cur = H[H.session == "2025_0"]
    new = {str(d).zfill(3): int(t == 0) for d, t in zip(cur.p_district, cur.tenure)}
    filed = cur.groupby(cur.p_district.astype(str).str.zfill(3)).size().to_dict()
    past = collections.Counter(str(d).zfill(3) for d, l, s in zip(H.p_district, H.law, H.session) if l in LAWS and s >= "2023_0")
    maj_party = "D"   # PA House 2025-26; checked below against the roster-derived majority
    assert P["states"]["PA"]["chambers"]["lower"]["members_matched"] == 203
    rows = []
    for d, v in D.items():
        m = v["member"] or {}
        rows.append({"d": d, "name": m.get("name"), "party": m.get("party"),
                     "seniors": v["seniors"]["count"], "seniors_share": v["seniors"]["share"], "seniors_moe": v["seniors"]["moe"],
                     "people": v["people"], "nursing_homes": v["places"]["nursing_homes"], "beds": v["places"]["nursing_home_beds"],
                     "hospitals": v["places"]["hospitals"], "seats": seat.get(d, []), "majority": int(m.get("party") == maj_party),
                     "new_member": new.get(d), "bills_filed_2025_26": int(filed.get(d, 0)), "carried_these_laws_since_2023": past.get(d, 0),
                     "municipalities": len(v["local"].get("municipalities", [])),
                     "school_districts": len(v["local"].get("school_districts", [])),
                     "counties": [c for c, _w in v["local"].get("counties", [])],
                     "senate_overlap": v["senate_overlap"][:3]})
    out["districts"] = rows
    tot = {"seniors": sum(r["seniors"] for r in rows), "people": sum(r["people"] for r in rows),
           "nursing_homes": sum(r["nursing_homes"] for r in rows), "beds": sum(r["beds"] for r in rows)}
    out["statewide"] = {**tot, "seniors_share": round(tot["seniors"] / tot["people"], 4)}
    # 3. the money gate and the clock (from results_drafting.json — one source of truth)
    with open(os.path.join(HERE, "results_drafting.json")) as f:
        r = json.load(f)
    out["appropriations"] = r["D4_appropriations"]
    out["filing_time"] = r["D5_filing_time"]
    # 3b. every measure per district (the team picks which one shades the map) + earlier bills per law
    M = P["measures"]
    out["measures"] = {k: v["label"] for k, v in M.items()}
    out["measure_values"] = {d: {k: [v[k]["count"], v[k]["share"]] for k in M} for d, v in D.items()}
    eb = {}
    far = lambda r: "law" if r.law_ else ("passed 2nd chamber" if r.passed2 else ("passed chamber" if r.passed else ("out of committee" if r.out else "died in committee")))
    for law in LAWS:
        g = F[(F.law == law)].sort_values(["session", "number"], ascending=[False, False])
        g = g.assign(law_=g["law_flag"] if "law_flag" in g else 0)
        done = g[g.session < "2025_0"]
        eb[law] = {"bills": int(len(g)), "since": "2009", "out": int(done.out.sum()), "done": int(len(done)), "laws": int(done["law_won"].sum()),
                   "recent": [{"s": r.session[:4] + "–" + str(int(r.session[:4]) + 1)[2:], "bill": ("HB " if r.body == "H" else "SB ") + str(r.number),
                               "who": f"{r.p_name.title()} ({r.p_party})", "far": far(r)} for r in g.head(6).itertuples()]}
    out["earlier_bills"] = eb
    # 4. shapes for the map
    with open(os.path.join(ROOT, "tools", "historical_cache", "census", "district_shapes.json")) as f:
        out["shapes"] = json.load(f)["PA"]["lower"]
    sen = P["states"]["PA"]["chambers"]["upper"]["districts"]
    out["senators"] = {d: (v["member"] or {}) for d, v in sen.items()}
    with open(os.path.join(HERE, "example_drafting.json"), "w") as f:
        json.dump(out, f)
    top = sorted(rows, key=lambda x: -x["beds"])[:5]
    print(json.dumps(out["steering"], indent=1)); print(json.dumps(rec, indent=1)); print(out["statewide"])
    for t in top:
        print(t["d"], t["name"], t["party"], t["seniors"], t["seniors_share"], t["nursing_homes"], t["beds"], t["seats"], t["new_member"], t["bills_filed_2025_26"], t["municipalities"])


if __name__ == "__main__":
    main()
