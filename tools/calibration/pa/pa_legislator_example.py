#!/usr/bin/env python3
"""Data for the legislator page mock: one member, every number from public records (PA exports, roster feed, Open
States votes, census district profiles). Writes legislator_example.json. Usage: python3 pa_legislator_example.py H 168

Map: the state with the district highlighted (default) + an inset zoomed to the district with every district that
touches it (shapes from the Census 2024 cartographic boundaries, finer simplification for the inset).
"""
from __future__ import annotations

import collections
import json
import math
import os
import re
import sys
import zipfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "districts"))
from pa_frame import frame, prior_rate  # noqa: E402
from pa_drafting import law_key  # noqa: E402
import build_profiles as BP  # noqa: E402

BODY, DIST = (sys.argv[1], sys.argv[2].zfill(3)) if len(sys.argv) > 2 else ("H", "168")
LAYER = {"H": "sldl", "S": "sldu"}[BODY]


def inset(shapes, d):
    """District + every district touching it, projected to a 400-wide box around the district (with margin)."""
    geo = {BP.district_of(r): g for r, g in shapes}
    me = geo[d]
    nb = [k for k, g in geo.items() if k != d and g.touches(me) or (k != d and g.intersects(me.buffer(1e-4)))]
    minx, miny, maxx, maxy = me.bounds
    padx, pady = (maxx - minx) * 0.35, (maxy - miny) * 0.35
    minx, maxx, miny, maxy = minx - padx, maxx + padx, miny - pady, maxy + pady
    k = math.cos(math.radians((miny + maxy) / 2))
    W = 400.0
    s = W / max((maxx - minx) * k, (maxy - miny))
    H = (maxy - miny) * s

    def ring(coords):
        return "M" + "L".join(f"{(x - minx) * k * s:.1f},{(maxy - y) * s:.1f}" for x, y in coords) + "Z"

    def path(g):
        g2 = g.simplify(0.0008, preserve_topology=True)
        polys = [g2] if g2.geom_type == "Polygon" else list(g2.geoms)
        return "".join(ring(p.exterior.coords) for p in polys)
    out = {"w": round((maxx - minx) * k * s, 1), "h": round(H, 1), "me": path(me), "neighbors": []}
    for n in sorted(nb):
        c = geo[n].intersection(__import__("shapely").geometry.box(minx, miny, maxx, maxy))
        if c.is_empty:
            continue
        pt = geo[n].representative_point()
        out["neighbors"].append({"d": n, "path": path(c), "lx": round((pt.x - minx) * k * s, 1), "ly": round((maxy - pt.y) * s, 1)})
    pt = me.representative_point()
    out["label"] = {"x": round((pt.x - minx) * k * s, 1), "y": round((maxy - pt.y) * s, 1)}
    return out


def main():
    prof = json.load(open(os.path.join(ROOT, "tools/historical_cache/census/district_profiles.json")))
    PA = prof["states"]["PA"]["chambers"]["lower" if BODY == "H" else "upper"]["districts"]
    v = PA[DIST]
    member = v["member"]
    surname = member["name"].split()[-1].upper()
    # --- district facts: every measure vs the state
    tot = collections.defaultdict(lambda: [0, 0])
    for dv in PA.values():
        for k in prof["measures"]:
            c, sh = dv[k]["count"], dv[k]["share"]
            tot[k][0] += c
            tot[k][1] += (c / sh) if sh else 0
    facts = []
    for k, meta in prof["measures"].items():
        st = tot[k][0] / tot[k][1] if tot[k][1] else None
        facts.append({"k": k, "label": meta["label"], "of": meta["of"], "count": v[k]["count"], "share": v[k]["share"],
                      "moe": v[k]["moe"], "state": round(st, 4) if st else None,
                      "ratio": round(v[k]["share"] / st, 2) if st and v[k]["share"] else None})
    facts.sort(key=lambda x: -abs(math.log(x["ratio"])) if x["ratio"] else 0)
    # --- map: state outline paths (all districts) + inset
    shapes = BP.read_shapes("42", LAYER)
    state_paths, dims = BP.svg_paths(shapes, 0.004 if LAYER == "sldl" else 0.006)
    ins = inset(shapes, DIST)
    # --- what they carry
    F = frame()
    F["law_won"] = F["law"]
    F["lawk"] = F.title.map(law_key)
    me = F[(F.body == BODY) & (F.p_district.astype(str).str.zfill(3) == DIST) & (F.p_name.str.upper().str.contains(surname))]
    room_rate = prior_rate(F, ["body", "cmte", "in_maj"]).fillna(F.out.mean())
    F["expected"] = room_rate
    carry = []
    for s, g in me.groupby("session"):
        gg = F.loc[g.index]
        carry.append({"session": s[:4] + "–" + str(int(s[:4]) + 1)[2:], "bills": int(len(g)), "out": int(g.out.sum()),
                      "expected": round(float(gg.expected.sum()), 1), "passed": int(g.passed.sum()), "law": int(g.law_won.sum()),
                      "open": s == "2025_0", "standing": "majority" if g.in_maj.iloc[0] else "minority"})
    focus = collections.Counter(l for l in me.lawk if isinstance(l, str)).most_common(5)
    first_session = me.session.min() if len(me) else None
    # --- who they work with (co-sponsors), from the export
    import pickle
    D = pickle.load(open(os.path.join(HERE, ".cache_corpus.pkl"), "rb"))["data"]
    signs_mine, i_sign = collections.Counter(), collections.Counter()
    party_of = {}
    for s in ("2023_0", "2025_0"):
        for b in D[s]["bills"]:
            p = b["prime"] or {}
            for c in b["cosponsors"]:
                party_of[(c["body"], c["surname"])] = c["party"]
            party_of[(p.get("body"), p.get("surname"))] = p.get("party")
            if p.get("body") == BODY and str(p.get("district")).zfill(3) == DIST:
                for c in b["cosponsors"]:
                    signs_mine[(c["body"], c["surname"])] += 1
            elif any(c["body"] == BODY and str(c["district"]).zfill(3) == DIST for c in b["cosponsors"]):
                i_sign[(p.get("body"), p.get("surname"))] += 1
    mp = member["party"]
    tot_sign = sum(signs_mine.values()); cross_sign = sum(n for k, n in signs_mine.items() if party_of.get(k) not in (mp, None))
    tot_i = sum(i_sign.values()); cross_i = sum(n for k, n in i_sign.items() if party_of.get(k) not in (mp, None))
    work = {"cosign_her_bills": [{"name": k[1].title(), "party": party_of.get(k), "chamber": k[0], "n": n} for k, n in signs_mine.most_common(6)],
            "she_cosigns": [{"name": k[1].title(), "party": party_of.get(k), "chamber": k[0], "n": n} for k, n in i_sign.most_common(6)],
            "cross_party_on_hers": f"{cross_sign} of {tot_sign}", "cross_party_she_signs": f"{cross_i} of {tot_i}"}
    # --- memos she circulated (2025-26 export carries memo titles)
    zf = zipfile.ZipFile([os.path.join(ROOT, "tools/historical_cache/pa/2025_0", f) for f in os.listdir(os.path.join(ROOT, "tools/historical_cache/pa/2025_0")) if f.endswith(".zip")][0])
    xt = zf.read([x for x in zf.namelist() if x.lower().endswith(".xml")][0]).decode("utf-8", "replace")
    memos = []
    for b in re.finditer(r'<bill id="2025\d([HS])B(\d+)".*?</bill>', xt, re.S):
        if b.group(1) != BODY:
            continue
        sp = re.search(r'<sponsor sequenceNumber="01"[^>]*districtNumber="(\d+)"[^>]*>([^<]+)</sponsor>', b.group(0))
        mm = re.search(r"<cosponsorshipMemo[^>]*>(.*?)</cosponsorshipMemo>", b.group(0), re.S)
        if sp and sp.group(1).zfill(3) == DIST and mm:
            import html as _h
            memos.append({"bill": f"{'HB' if BODY == 'H' else 'SB'} {int(b.group(2))}", "title": _h.unescape(mm.group(1)).strip()})
    # --- how they vote (Open States, batch 3 definitions)
    import pa_batch3 as B3
    E, B, _u = B3.load(F)
    X = B3.per_event(E, B, F)
    _d, yn = B3.t_defection(B, X)
    yn = yn.merge(X[["yes", "no", "committee"]].rename(columns={"committee": "cmt"}), left_on="eid", right_index=True)
    yn["contested"] = (yn.no / (yn.yes + yn.no)) >= 0.10
    who = f"{BODY}|{B3.norm(surname)}"
    votes = []
    for s, g in yn[yn.contested].groupby("session"):
        cohort = g[(g.party == mp)].groupby("who").defect.mean()
        mine = g[g.who == who]
        if mine.empty:
            continue
        rank = int((cohort < mine.defect.mean()).sum()) + 1
        votes.append({"session": s[:4] + "–" + str(int(s[:4]) + 1)[2:], "contested_votes": int(len(mine)),
                      "with_party": int((mine.defect == 0).sum()), "crossed": int(mine.defect.sum()),
                      "rank_in_party": f"{rank} of {len(cohort)} (1 = most loyal)"})
    # --- seats now
    from pa_batch2 import rosters
    members, chair, _ = rosters()
    seats = sorted(k[1] for k, ds in members.items() if k[0] == BODY and int(DIST) in {int(x) for x in ds})
    out = {"member": member, "body": BODY, "district": DIST, "first_session_in_data": first_session, "seats": seats,
           "chairs": [k[1] for k, dd in chair.items() if k[0] == BODY and str(dd).zfill(3) == DIST],
           "facts": facts, "places": v["places"], "local": v["local"], "senate_overlap": v["senate_overlap"],
           "senators": {d: x["member"] for d, x in prof["states"]["PA"]["chambers"]["upper"]["districts"].items()},
           "people": v["people"], "median_income": v["median_income"],
           "map": {"state": state_paths, "dims": dims, "inset": ins}, "carry": carry, "focus": focus, "work": work,
           "memos": memos, "votes": votes}
    with open(os.path.join(HERE, "legislator_example.json"), "w") as f:
        json.dump(out, f, default=str)
    print(json.dumps({k: out[k] for k in ("member", "seats", "chairs", "carry", "focus", "votes", "first_session_in_data")}, indent=1, default=str))
    print(json.dumps(work, indent=1)[:900]); print(memos[:5]); print([n["d"] for n in ins["neighbors"]])
    print([(f["label"], f["count"], f["share"], f["state"], f["ratio"]) for f in facts[:6]])


if __name__ == "__main__":
    main()
