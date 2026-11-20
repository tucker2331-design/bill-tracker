#!/usr/bin/env python3
"""Extra facts for the v5 mockups (owner feedback 2026-11-20). Every number is computed from the PA bill exports
(tools/historical_cache/pa via pa_frame). Writes mock_v5.json.

1. Law picker: how many laws PA bill titles name (the drafting room searches all of them, not 3).
2. Repeat co-signers (legislator page): for each member who co-signs the example member's bills, how often they sign
   compared with their usual rate on other bills from the member's party. "Times their usual rate" separates a real tie
   from someone who signs nearly every party bill.
3. Whose bills the example member signs: the same measure in the other direction.
4. Topic pattern on a law (drafting room): current House members who co-sign bills on that law far more often than
   their usual rate (5+ bills, 1.5x or more), in the sessions they served.
5. Tenure floor: the first session (2009 on) a member sponsored a bill — a lower bound, since the data starts in 2009.
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

MEMBER = "H|BOROWSKI"
RECENT = ["2023_0", "2025_0"]
MIN_SHARED, MIN_TIMES = 10, 1.5            # a "pattern": 10+ shared bills AND at least 1.5x the usual rate


def pairs(mine, pool, key_of):
    """For each signer of `mine`: shared bills, share of mine, usual rate on `pool`, times usual, top committee."""
    signed_mine = collections.Counter(k for ck in mine.cosp_keys for k in ck if k.startswith("H|"))
    signed_pool = collections.Counter(k for ck in pool.cosp_keys for k in ck if k.startswith("H|"))
    out = []
    for k, n in signed_mine.items():
        sh = mine[mine.cosp_keys.map(lambda c, k=k: k in c)]
        usual = signed_pool[k] / len(pool) if len(pool) else 0.0
        share = n / len(mine)
        top = sh.cmte.value_counts()
        out.append({"key": k, "name": key_of.get(k, k.split("|")[1].title()), "n": n, "of": len(mine),
                    "share": round(share, 3), "usual": round(usual, 3),
                    "times": round(share / usual, 1) if usual else None, "sessions": int(sh.session.nunique()),
                    "top_cmte": str(top.index[0]).title(), "top_cmte_n": int(top.iloc[0])})
    return out


def main():
    F = frame().reset_index(drop=True)
    F["lawname"] = F.title.map(law_key)
    vc = F.lawname.value_counts()
    res = {"laws": {"bills": int(len(F)), "bills_naming_a_law": int(F.lawname.notna().sum()), "distinct": int(vc.size),
                    "with_5_plus_bills": int((vc >= 5).sum()), "with_20_plus_bills": int((vc >= 20).sum()),
                    "sessions": f"{F.session.min()[:4]}-{int(F.session.max()[:4]) + 1}"},
           "law_list": [[k, int(v)] for k, v in vc.items()]}

    H = F[F.body == "H"]
    R = H[H.session.isin(RECENT)]
    party = dict(zip(R.p_key, R.p_party))
    name = {k: n.title() for k, n in zip(R.p_key, R.p_name)}
    me = R[R.p_key == MEMBER]
    if me.empty:
        raise SystemExit(f"{MEMBER}: no bills in {RECENT}")
    my_party = me.p_party.iloc[0]

    # 2. who signs my bills, against their usual rate on other same-party bills
    pool = R[(R.p_party == my_party) & (R.p_key != MEMBER)]
    signers = pairs(me, pool, name)
    for s in signers:
        s["party"] = party.get(s["key"], "?")
    # 3. whose bills I sign: per sponsor, the share of their bills I signed against my usual rate on that party's bills
    i_sign = []
    for sp, g in R[R.p_key != MEMBER].groupby("p_key"):
        n = int(g.cosp_keys.map(lambda c: MEMBER in c).sum())
        if not n:
            continue
        p = party.get(sp, "?")
        same = R[(R.p_party == p) & (R.p_key != sp) & (R.p_key != MEMBER)]
        usual = same.cosp_keys.map(lambda c: MEMBER in c).mean() if len(same) else 0.0
        share = n / len(g)
        top = g[g.cosp_keys.map(lambda c: MEMBER in c)].cmte.value_counts()
        i_sign.append({"key": sp, "name": name.get(sp, sp), "party": p, "n": n, "of": int(len(g)), "share": round(share, 3),
                       "usual": round(float(usual), 3), "times": round(share / usual, 1) if usual else None,
                       "sessions": int(g[g.cosp_keys.map(lambda c: MEMBER in c)].session.nunique()),
                       "top_cmte": str(top.index[0]).title(), "top_cmte_n": int(top.iloc[0])})
    pat = lambda xs: sorted([x for x in xs if x["n"] >= MIN_SHARED and (x["times"] or 0) >= MIN_TIMES],
                            key=lambda x: -(x["times"] or 0))
    habitual = sorted([x for x in signers if x["share"] >= 0.6 and (x["times"] or 9) < MIN_TIMES], key=lambda x: -x["n"])
    res["legislator"] = {
        "member": MEMBER, "sessions": RECENT, "her_bills": int(len(me)),
        "rule": {"min_shared": MIN_SHARED, "min_times": MIN_TIMES},
        "signers_pattern": pat(signers)[:10], "signers_pattern_count": len(pat(signers)),
        "signers_total": len(signers), "signers_habitual": [x["name"] for x in habitual],
        "i_sign_pattern": pat(i_sign)[:10], "i_sign_pattern_count": len(pat(i_sign)), "i_sign_sponsors": len(i_sign),
        "i_sign_bills": int(R.cosp_keys.map(lambda c: MEMBER in c).sum()),
    }

    # 4. members with a TOPIC pattern on each example law (current House members only): how often they co-sign bills
    #    on this law against their usual rate on all House bills, in the sessions they served. A raw count would put
    #    the members who sign nearly everything on top (the same trap as the legislator page's co-signers).
    current = set(H[H.session == "2025_0"].p_key)
    h25 = H[H.session == "2025_0"]
    dist_of = {k: str(d).zfill(3) for k, d in zip(h25.p_key, h25.p_district)}
    first = H.groupby("p_key").session.min().to_dict()
    served = H.groupby("p_key").session.apply(set).to_dict()
    per_session = H.groupby("session").size().to_dict()
    signs = collections.Counter((k, s) for ck, s in zip(H.cosp_keys, H.session) for k in ck if k in current)
    record = {}
    for law in json.load(open(os.path.join(HERE, "example_drafting.json"), encoding="utf-8"))["parts"]:
        g = H[H.lawname == law]
        rows = []
        for k in current:
            ss = served.get(k, set())
            gl = g[g.session.isin(ss)]
            if gl.empty:
                continue
            on_law = int(gl.cosp_keys.map(lambda c, k=k: k in c).sum())
            spons = int((gl.p_key == k).sum())
            if on_law + spons == 0:
                continue
            all_bills = sum(per_session[x] for x in ss)
            usual = sum(signs[(k, x)] for x in ss) / all_bills if all_bills else 0.0
            rate = on_law / len(gl)
            rows.append({"key": k, "district": dist_of.get(k), "cosigned": on_law, "of": int(len(gl)), "sponsored": spons,
                         "rate": round(rate, 3), "usual": round(usual, 3), "times": round(rate / usual, 1) if usual else None})
        pattern = sorted([r for r in rows if r["cosigned"] >= 5 and (r["times"] or 0) >= MIN_TIMES],
                         key=lambda r: (-(r["times"] or 0), r["key"]))
        record[law] = {"bills": int(len(g)), "members_with_record": len(rows), "pattern_count": len(pattern),
                       "rows": pattern[:12]}
    res["law_record"] = record
    res["first_session"] = {dist_of[k]: first[k][:4] for k in current if k in dist_of}
    with open(os.path.join(HERE, "mock_v5.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "first_session"}, indent=1)[:4000])


if __name__ == "__main__":
    main()
