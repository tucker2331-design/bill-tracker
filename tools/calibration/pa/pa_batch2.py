#!/usr/bin/env python3
"""BATCH 2 — the Virginia tests that need COMMITTEE ROSTERS, on Pennsylvania 2025-26.

PA publishes rosters only as a current feed (committee assignments RSS, cached 2026-11-01 under
tools/historical_cache/pa/2025_0/), so these tests run on ONE session: 2025-26. Members join to bill sponsors on
(chamber, district) — both structural fields (the export's sponsor@districtNumber, the roster's parss:District).

Caveats said in every result: the roster is a snapshot (Nov 2026), so a member who changed committees mid-session is
placed by where they sit now; one session means no year-ahead test, so the ledger stats are scored by an odd/even
bill-number split within the session (fit on odd, predict even) instead of fit-one-session-predict-the-next.

Replicates: testing/committee_seat · testing/influence_and_sources (chair co-sponsorship) · calibration ledger
(patron_on_cmte, cmte_member_copatrons, committee_size).
"""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from pa_frame import frame  # noqa: E402
from pa_batch1 import score_stat, two_prop, pct  # noqa: E402
from states import pa_roster as PR  # noqa: E402
import test_pa_intake as S  # noqa: E402  (the cached-feed fetcher: no network)


def rosters():
    roster, st = PR.run_roster(S.SampleFetcher(), S.PA.urls)
    body = {"House": "H", "Senate": "S"}
    members = collections.defaultdict(set)      # (body, committee key) -> {district}
    # PA lists TWO chairs per committee, both role "Chair": the majority chair (who runs the room) and the minority
    # chair. The majority chair is the Chair whose party is the chamber's majority (party counts from the roster).
    seats = collections.Counter((body[r["chamber"]], r["party"]) for r in {(x["chamber"], x["member_id"], x["party"]): x for x in roster}.values())
    maj = {b: max(("D", "R"), key=lambda p: seats[(b, p)]) for b in ("H", "S")}
    chair, min_chair = {}, {}
    for r in roster:
        k = (body[r["chamber"]], r["key"])
        members[k].add(r["district"])
        if r["role"] == "Chair":
            (chair if r["party"] == maj[k[0]] else min_chair)[k] = r["district"]
    st = {**st, "majority_by_roster": maj, "committees_with_majority_chair": len(chair), "committees_with_minority_chair": len(min_chair)}
    return members, chair, st


def main():
    F = frame()
    T = F[(F.session == "2025_0") & (F.cmte != "(none)")].copy()
    members, chair, st = rosters()
    chamber_word = {"H": "House", "S": "Senate"}
    T["ckey"] = [(b, PR.committee_key(chamber_word[b], c)) for b, c in zip(T.body, T.cmte)]
    T = T[T.ckey.isin(members)].copy()
    T["on_cmte"] = [int(d in members[k]) for d, k in zip(T.p_district, T.ckey)]
    T["is_chair"] = [int(chair.get(k) == d) for d, k in zip(T.p_district, T.ckey)]
    rows = F[(F.session == "2025_0")].set_index("sid")
    T["cosp_districts_list"] = [[c["district"] for c in b["cosponsors"] if c["body"] == body]
                                for b, body in zip(_bills(T.sid), T.body)]
    T["chair_cosponsors"] = [int(chair.get(k) in ds and not ic) for k, ds, ic in zip(T.ckey, T.cosp_districts_list, T.is_chair)]
    T["n_cmte_cosp"] = [sum(1 for d in ds if d in members[k]) for ds, k in zip(T.cosp_districts_list, T.ckey)]
    T["cmte_size"] = [len(members[k]) for k in T.ckey]
    R = {"roster": {"snapshot": "committee assignments RSS, 2026-11-01", **st},
         "bills_2025_26_with_a_rostered_first_committee": int(len(T))}
    # committee seat, within standing
    seat = {}
    for side, lab in ((1, "majority patron"), (0, "minority patron")):
        g = T[T.in_maj == side]
        a, b = g[g.on_cmte == 1], g[g.on_cmte == 0]
        seat[lab] = two_prop(a.out.sum(), len(a), b.out.sum(), len(b))
    # within patron: the same member's bills in a committee they sit on vs one they do not
    wp = []
    for k, g in T.groupby("p_key"):
        if g.on_cmte.nunique() == 2:
            wp.append(g[g.on_cmte == 1].out.mean() - g[g.on_cmte == 0].out.mean())
    wp = np.array(wp)
    seat["within_patron"] = {"patrons": int(len(wp)), "mean_diff_pts": pct(wp.mean()) if len(wp) else None,
                             "better": int((wp > 0).sum()), "worse": int((wp < 0).sum()),
                             "sign_test_p": float(f"{stats.binomtest(int((wp > 0).sum()), int((wp != 0).sum())).pvalue:.2g}") if (wp != 0).any() else None}
    ch = T[T.is_chair == 1]
    peers = T[(T.on_cmte == 1) & (T.is_chair == 0) & (T.in_maj == 1)]      # other MAJORITY members of the same room
    seat["majority_chair_is_the_prime_sponsor (b = other majority members on the committee)"] = two_prop(
        ch.out.sum(), len(ch), peers.out.sum(), len(peers))
    R["committee_seat (a = patron sits on the first committee, b = does not)"] = seat
    # chair co-sponsorship (influence_and_sources): this bill vs the same patron's other bills
    cc = T[T.chair_cosponsors == 1]
    diffs = []
    for k, g in T[T.is_chair == 0].groupby("p_key"):
        if g.chair_cosponsors.nunique() == 2:
            diffs.append(g[g.chair_cosponsors == 1].out.mean() - g[g.chair_cosponsors == 0].out.mean())
    diffs = np.array(diffs)
    R["chair_cosponsors_this_bill"] = {
        "bills": int(len(cc)), "reported": pct(cc.out.mean()) if len(cc) else None,
        "same_patrons_other_bills_reported": pct(T[(T.p_key.isin(cc.p_key)) & (T.chair_cosponsors == 0) & (T.is_chair == 0)].out.mean()),
        "within_patron": {"patrons": int(len(diffs)), "mean_diff_pts": pct(diffs.mean()) if len(diffs) else None,
                          "better": int((diffs > 0).sum()), "worse": int((diffs < 0).sum()),
                          "sign_test_p": float(f"{stats.binomtest(int((diffs > 0).sum()), int((diffs != 0).sum())).pvalue:.2g}") if (diffs != 0).any() else None}}
    # the three ledger stats, odd/even split within 2025-26
    T["cmte_cosp_b"] = np.select([T.n_cmte_cosp == 0, T.n_cmte_cosp <= 2], ["0", "1-2"], "3+")
    T["size_b"] = np.select([T.cmte_size <= 12, T.cmte_size <= 20], ["<=12", "13-20"], "21+")
    odd, even = T[T.number % 2 == 1], T[T.number % 2 == 0]
    R["ledger_stats (fit odd bill numbers -> predict even, 2025-26)"] = {
        lab: {"out": score_stat(odd, even, col, "out")[0], "pass": score_stat(odd, even, col, "passed")[0]}
        for lab, col in (("patron_on_cmte", "on_cmte"), ("cmte_member_copatrons", "cmte_cosp_b"), ("committee_size", "size_b"))}
    with open(os.path.join(HERE, "results_batch2.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    print(json.dumps(R, indent=1, default=str))


def _bills(sids):
    from pa_corpus import load
    idx = {b["sid"]: b for b in load()["2025_0"]["bills"]}
    return [idx[s] for s in sids]


if __name__ == "__main__":
    main()
