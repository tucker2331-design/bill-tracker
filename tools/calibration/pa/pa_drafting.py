#!/usr/bin/env python3
"""Pre-introduction tests: what a lobbyist can still CHANGE before a bill is filed, and does it matter?
(owner 2026-11-18: "consider what tools and info a lobbyist would want to get their bill introduced in the first
place ... run the numbers for it").

Every test answers one drafting-room idea with PA's public record (Bill History exports 2009-2026 + 2024 district
census profiles from tools/districts/build_profiles.py). Outcome = got out of its first committee (`out`) unless
stated. Party standing (majority / minority) is always held fixed, because in PA it explains most of everything.

  D1  district match     do members carry bills that match who lives in their district?
  D2  match -> success   among those bills, do the most-affected districts' sponsors get them out more?
  D3  new members        do first-session members carry bills, and do theirs get out?
  D4  Appropriations     after the first committee, how many bills die in the second (money) gate?
  D5  filing time        does filing early in the session help, within the same member?
  D6  bandwidth          is a member's 30th bill of the session less likely than their 3rd?
  D7  steering           how reliably does the part of the law you amend decide the committee?
  D8  twins              does filing a House and a Senate version together help?
  D9  memo               does a co-sponsorship memo go with better odds?
  D10 pair               does a twin whose two sponsors share constituents do better?

Title text is used ONLY to sort bills into subjects for this internal test (CLAUDE.md standard #3 allows text for
internal diagnostics); nothing here is a lobbyist-facing classifier.
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
from pa_frame import frame  # noqa: E402

RNG = np.random.default_rng(20261118)
CURRENT_MAPS = ("2023_0", "2025_0")        # PA's 2022 maps; members elected 2022 and 2024 sit in these districts

SUBJECTS = {   # subject -> (title pattern, district measure it should track)
    "farming": (r"\bagricultur|\bfarm|title 3 \(agriculture\)", "farm_jobs"),
    "veterans": (r"veteran|title 51 \(military", "veterans"),
    "seniors": (r"older adult|senior citizen|\baging\b|long-term care|nursing (home|facilit)|\bpace\b", "seniors"),
    "schools / children": (r"public school code|child care|early (learning|childhood)|school district", "children"),
    "renters": (r"landlord|tenant|rental", "renters"),
    "poverty / assistance": (r"human services code|public welfare|public assistance|medical assistance|\bsnap\b", "poverty"),
    "transit": (r"public transportation|mass transit|\btransit\b", "no_vehicle"),
    "immigrants / language": (r"immigra|interpret|english learner|language access", "foreign_born"),
    "broadband": (r"broadband|internet", "no_internet"),
}


def rate(s):
    return {"k": int(s.sum()), "n": int(len(s)), "pct": round(100 * s.mean(), 1) if len(s) else None}


def perm_p(observed, null):
    return round((1 + np.sum(np.asarray(null) >= observed)) / (1 + len(null)), 4)


def mh_diff(df, flag, outcome="out", strata=("in_maj",)):
    """Difference in outcome (flag=1 minus flag=0) averaged over strata, weighted by stratum size."""
    num = den = 0.0
    parts = {}
    for key, g in df.groupby(list(strata)):
        a, b = g[g[flag] == 1][outcome], g[g[flag] == 0][outcome]
        if len(a) and len(b):
            w = len(g)
            num += w * (a.mean() - b.mean()); den += w
            parts[str(key)] = {"with": rate(a), "without": rate(b)}
    return {"pts": round(100 * num / den, 1) if den else None, "by_standing": parts}


def profiles():
    with open(os.path.join(ROOT, "tools", "historical_cache", "census", "district_profiles.json")) as f:
        P = json.load(f)["states"]["PA"]["chambers"]
    return {("H" if ch == "lower" else "S", d): v for ch, c in P.items() for d, v in c["districts"].items()}


def d1_d2(F, P):
    out = {}
    T = F[F.session.isin(CURRENT_MAPS)].copy()
    T["dkey"] = list(zip(T.body, T.p_district.astype(str).str.zfill(3)))
    T = T[T.dkey.isin(P)]
    tl = T.title.str.lower()
    for subj, (pat, meas) in SUBJECTS.items():
        T["cat"] = tl.str.contains(pat, regex=True).astype(int)
        T["dshare"] = [P[k][meas]["share"] for k in T.dkey]
        res = {"measure": meas, "bills": int(T.cat.sum())}
        for body in ("H", "S"):
            B = T[T.body == body]
            members = B.groupby("dkey").agg(n=("sid", "size"), c=("cat", "sum"), share=("dshare", "first"))
            if B.cat.sum() < 10:
                res[body] = {"bills": int(B.cat.sum()), "verdict": "too few bills to test (shown as k of n)"}
                continue
            q75 = members.share.quantile(0.75)
            top = members[members.share >= q75]
            # observed: share of this subject's bills filed by members from the top quarter of districts
            obs = top.c.sum() / members.c.sum()
            # expected under no relationship: that quarter's share of ALL bills (they may simply file more)
            exp = top.n.sum() / members.n.sum()
            null = []
            sh = members.share.to_numpy()
            for _ in range(2000):
                perm = RNG.permutation(sh)
                t = perm >= q75
                null.append(members.c.to_numpy()[t].sum() / members.c.sum())
            res[body] = {"subject_bills": int(members.c.sum()), "members": int(len(members)),
                         "from_top_quarter_districts": f"{int(top.c.sum())} of {int(members.c.sum())} ({round(100 * obs)}%)",
                         "expected_from_their_share_of_all_bills": f"{round(100 * exp)}%",
                         "lift": round(obs / exp, 2) if exp else None, "p": perm_p(obs, null),
                         "rank_corr_member_rate_vs_district_share": round(members.assign(r=members.c / members.n)[["r", "share"]].corr("spearman").iloc[0, 1], 3)}
            # D2: among this subject's bills, do top-quarter sponsors get them out more (standing held fixed)?
            C = B[B.cat == 1].copy()
            C["top"] = (C.dshare >= q75).astype(int)
            res[body]["D2_top_quarter_sponsor_out_of_committee"] = mh_diff(C, "top") if C.top.nunique() == 2 else None
        out[subj] = res
    return out


def d3(F):
    T = F[(F.session >= "2011_0")].copy()          # 2009 is the first export: tenure is left-censored there
    T["new"] = (T.tenure == 0).astype(int)
    first = T.groupby(["session", "p_key", "body"]).agg(new=("new", "first"), n=("sid", "size"), in_maj=("in_maj", "first"))
    per_member = first.groupby(["new", "in_maj"]).n.median().to_dict()
    res = {"bills_per_member_median": {f"{'new' if k[0] else 'returning'} / {'majority' if k[1] else 'minority'}": v for k, v in per_member.items()},
           "out_of_committee": mh_diff(T[T.session < "2025_0"], "new", strata=("in_maj", "body"))}
    # within member: first session vs their second, same standing both times
    w = []
    for (pk), g in T.groupby("p_key"):
        ss = sorted(g.session.unique())
        if len(ss) >= 2 and g[g.session == ss[0]].tenure.iloc[0] == 0 and g[g.session == ss[0]].in_maj.iloc[0] == g[g.session == ss[1]].in_maj.iloc[0] and ss[1] < "2025_0":
            w.append(g[g.session == ss[1]].out.mean() - g[g.session == ss[0]].out.mean())
    res["within_member_second_minus_first_session"] = {"members": len(w), "mean_pts": round(100 * float(np.mean(w)), 1) if w else None,
                                                        "better_in_second": int(sum(x > 0 for x in w)), "worse": int(sum(x < 0 for x in w))}
    return res


def d4(F):
    res = {}
    T = F[F.session < "2025_0"]
    for body in ("H", "S"):
        sent = back = passed_if_back = 0
        reported_no_approps = passed_no_approps = 0
        for acts, b, p in zip(T.actions, T.body, T.passed):
            if b != body:
                continue
            origin = [a for a in acts if a[1] == body]
            rep1 = any(a[3] == "reported" for a in origin)
            if not rep1:
                continue
            to_ap = [i for i, a in enumerate(origin) if a[3] == "referral" and "APPROP" in str(a[4]).upper() and a[2].startswith(("Re-referred", "Referred", "Re-committed"))]
            if to_ap:
                sent += 1
                came_back = any(a[3] == "reported" and "APPROP" in str(a[4]).upper() for a in origin[to_ap[0]:])
                back += came_back
                passed_if_back += int(came_back and p)
            else:
                reported_no_approps += 1
                passed_no_approps += p
        res["House" if body == "H" else "Senate"] = {
            "reported_bills_sent_to_appropriations": f"{sent} of {sent + reported_no_approps}",
            "came_back_out": f"{back} of {sent} ({round(100 * back / sent) if sent else 0}%)",
            "passed_chamber_if_it_came_back": f"{passed_if_back} of {back}",
            "passed_chamber_never_sent": f"{passed_no_approps} of {reported_no_approps}"}
    return res


def d5(F):
    T = F[(F.session < "2025_0") & F.days_in.notna()].copy()
    T["when"] = pd.cut(T.days_in, [-1, 90, 180, 365, 545, 800], labels=["0-3 mo", "3-6 mo", "6-12 mo", "12-18 mo", "18+ mo"])
    table = {}
    for (m, w), g in T.groupby(["in_maj", "when"], observed=True):
        table.setdefault("majority" if m else "minority", {})[str(w)] = rate(g.out)
    # within member: early (first 3 months) vs later bills of the same member-session
    T["early"] = (T.days_in <= 90).astype(int)
    d = []
    for _, g in T.groupby(["session", "p_key"]):
        if g.early.nunique() == 2 and len(g) >= 6:
            d.append(g[g.early == 1].out.mean() - g[g.early == 0].out.mean())
    return {"by_filing_time": table, "within_member_first_3_months_minus_later": {
        "member_sessions": len(d), "mean_pts": round(100 * float(np.mean(d)), 1), "better_early": int(sum(x > 0 for x in d)),
        "worse_early": int(sum(x < 0 for x in d))}}


def d6(F):
    T = F[F.session < "2025_0"].copy()
    T["rank_bin"] = pd.cut(T.patron_bill_rank, [0, 5, 15, 30, 1000], labels=["1-5", "6-15", "16-30", "31+"])
    by = {}
    for (m, r), g in T.groupby(["in_maj", "rank_bin"], observed=True):
        by.setdefault("majority" if m else "minority", {})[str(r)] = rate(g.out)
    d = []
    for _, g in T.groupby(["session", "p_key"]):
        if len(g) >= 30:
            d.append(g[g.patron_bill_rank > 20].out.mean() - g[g.patron_bill_rank <= 10].out.mean())
    return {"by_order_of_filing": by, "within_member_bills_after_20th_minus_first_10": {
        "member_sessions": len(d), "mean_pts": round(100 * float(np.mean(d)), 1) if d else None}}


LAW = re.compile(r"amending title (\d+) \(([^)]+)\)|known as (?:the )?([^,;]+?)(?:,|;| in | further| providing|$)", re.I)


def law_key(title):
    m = LAW.search(title or "")
    if not m:
        return None
    return f"Title {m.group(1)} ({m.group(2)})" if m.group(1) else m.group(3).strip().rstrip(".")


def d7(F):
    T = F[F.cmte != "(none)"].copy()
    T["law"] = T.title.map(law_key)
    cov = T.law.notna().mean()
    T = T[T.law.notna()]
    rows = []
    for (body, law), g in T.groupby(["body", "law"]):
        if len(g) >= 20:
            vc = g.cmte.value_counts()
            rows.append({"body": body, "law": law, "bills": len(g), "top_room": vc.index[0], "top_share": round(vc.iloc[0] / len(g), 3),
                         "rooms": int((vc / len(g) >= 0.05).sum())})
    R = pd.DataFrame(rows)
    w = (R.top_share * R.bills).sum() / R.bills.sum()
    big = R.sort_values("bills", ascending=False).head(12)
    return {"bills_whose_title_names_one_law": f"{round(100 * cov)}%", "laws_with_20plus_bills": len(R),
            "bill_weighted_share_to_the_usual_room": round(100 * w, 1),
            "laws_that_go_to_one_room_90pct_plus": f"{int((R.top_share >= 0.9).sum())} of {len(R)}",
            "examples": big[["body", "law", "bills", "top_room", "top_share", "rooms"]].to_dict("records")}


def d8(F):
    T = F[(F.session < "2025_0") & (F.tkey != "")].copy()
    key = collections.defaultdict(set)
    for s, b, t in zip(T.session, T.body, T.tkey):
        key[(s, t)].add(b)
    T["twin"] = [int(len(key[(s, t)]) == 2) for s, t in zip(T.session, T.tkey)]
    return {"law_if_twin_filed": mh_diff(T, "twin", outcome="law"), "out_if_twin_filed": mh_diff(T, "twin"),
            "share_of_bills_with_a_twin": round(100 * T.twin.mean(), 1)}


def d9(F):
    by = F.groupby("session").memo.mean().round(3).to_dict()
    T = F[F.session.isin([s for s, v in by.items() if v > 0.05]) & (F.session < "2025_0")]
    T25 = F[F.session == "2025_0"]
    return {"share_with_memo_by_session": by,
            "out_with_memo_completed_sessions": mh_diff(T, "memo", strata=("in_maj", "body")) if len(T) else "no completed session carries memo links",
            "out_with_memo_2025_first_committee": mh_diff(T25, "memo", strata=("in_maj", "body"))}


def d10(F, P_over):
    """Twins (same title, both chambers, same session) on the current maps: do sponsors who share constituents do better?"""
    T = F[F.session.isin(CURRENT_MAPS) & (F.tkey != "")]
    pairs = []
    g = T.groupby(["session", "tkey"])
    for (s, t), x in g:
        if set(x.body) == {"H", "S"}:
            h = x[x.body == "H"].iloc[0]; sen = x[x.body == "S"].iloc[0]
            ov = dict(P_over.get(str(h.p_district).zfill(3), []))
            pairs.append({"shared": int(str(sen.p_district).zfill(3) in ov), "law": int(h.law or sen.law),
                          "either_out": int(h.out or sen.out), "same_party": int(h.p_party == sen.p_party)})
    D = pd.DataFrame(pairs)
    if D.empty:
        return "no twins"
    return {"twin_pairs": len(D), "pairs_whose_sponsors_share_constituents": int(D.shared.sum()),
            "either_out_if_shared": rate(D[D.shared == 1].either_out), "either_out_if_not": rate(D[D.shared == 0].either_out),
            "same_party_only": {"shared": rate(D[(D.shared == 1) & (D.same_party == 1)].either_out),
                                "not": rate(D[(D.shared == 0) & (D.same_party == 1)].either_out)}}


def main():
    F = frame()
    P = profiles()
    with open(os.path.join(ROOT, "tools", "historical_cache", "census", "district_profiles.json")) as f:
        over = {d: v["senate_overlap"] for d, v in json.load(f)["states"]["PA"]["chambers"]["lower"]["districts"].items()}
    res = {"method": __doc__.split("\n\n")[1].strip(),
           "D1_D2_district_match": d1_d2(F, P), "D3_new_members": d3(F), "D4_appropriations": d4(F),
           "D5_filing_time": d5(F), "D6_bandwidth": d6(F), "D7_steering": d7(F), "D8_twins": d8(F),
           "D9_memo": d9(F), "D10_shared_constituents": d10(F, over)}
    with open(os.path.join(HERE, "results_drafting.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
