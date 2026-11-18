#!/usr/bin/env python3
"""Batch 3, part b — the member-vote tests that follow Virginia's exact definitions (pa_batch3.py holds the
first-vote model). Same data: Open States PA session CSVs 2017-2026.

  second_chamber   Virginia's table: share of the OTHER party (vs the sponsor) voting yes in chamber 1, among bills
                   passed with at least one no; passes chamber 2? split by whether the sponsor's party runs chamber 2
  persuadability   z-score of defection within party x chamber x session; year-to-year r (VA r 0.68)
  denominator      share of roll calls where a caucus actually split (VA committees: 21%)
  member_subject   residual (member-on-law defection minus their general defection), early vs late era (VA r 0.487)
  rooms            members recorded per committee roll call, unanimous share, decided by <=2 votes (VA: room of 8)
  kill_points      how PA committees kill: by vote or by never voting
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pa_batch3 as B3  # noqa: E402
from pa_frame import frame  # noqa: E402


def second_chamber(A, F):
    fin = A[(A.kind == "final") & (A.chamber == A.body) & (~A.committee)]
    last = fin.sort_values("date").groupby(["session", "bill"]).eid.last()
    fin = fin[fin.eid.isin(set(last))]
    g = fin.groupby(["session", "bill"])
    pb = F.assign(bill=F.body.map({"H": "HB", "S": "SB"}) + " " + F.number.astype(str)).set_index(["session", "bill"])
    vmaj = {(s, b): m for s, b, m in zip(F.session, F.body, F.majority)}
    rows = []
    for (s, b), x in g:
        if (s, b) not in pb.index or s >= "2025_0":
            continue
        meta = pb.loc[(s, b)]
        sp = meta.p_party
        if sp not in ("D", "R") or (x.y == 0).sum() == 0:
            continue                       # VA protocol: bills passed with at least one no
        other = x[x.party != sp]
        if other.empty:
            continue
        sec = {"H": "S", "S": "H"}[meta.body]
        rows.append({"other_yes": other.y.mean(), "runs2": int(vmaj.get((s, sec)) == sp), "passed2": int(meta.passed2)})
    D = pd.DataFrame(rows)
    D["band"] = pd.cut(D.other_yes, [-0.001, 0.10, 0.50, 0.90, 1.0], labels=["0-10%", "10-50%", "50-90%", "90-100%"])
    out = {}
    for r2, gg in D.groupby("runs2"):
        out["sponsor's party runs chamber 2" if r2 else "sponsor's party does not"] = {
            str(bd): f"{int(x.passed2.sum())} of {len(x)} ({round(100 * x.passed2.mean())}%)" for bd, x in gg.groupby("band", observed=True)}
    try:
        import statsmodels.formula.api as smf
        m = smf.logit("passed2 ~ other_yes * runs2", D).fit(disp=0)
        out["logit_other_yes_when_not_running"] = {"coef": round(m.params["other_yes"], 3), "p": float(f"{m.pvalues['other_yes']:.2g}")}
        out["logit_interaction"] = {"coef": round(m.params["other_yes:runs2"], 3), "p": float(f"{m.pvalues['other_yes:runs2']:.2g}")}
    except Exception as e:                 # statsmodels optional; the table stands on its own
        out["logit"] = f"not run: {type(e).__name__}"
    return out


def persuadability(A):
    C = A.dropna(subset=["defect"])
    m = C.groupby(["session", "chamber", "party", "who"]).defect.agg(["mean", "size"]).reset_index()
    m = m[m["size"] >= 40]
    m["z"] = m.groupby(["session", "chamber", "party"])["mean"].transform(lambda v: (v - v.mean()) / (v.std() or 1))
    piv = m.pivot_table(index="who", columns="session", values="z")
    cols = sorted(piv.columns)
    rs = []
    for a, b in zip(cols, cols[1:]):
        both = piv[[a, b]].dropna()
        rs.append({"from": a, "to": b, "members": int(len(both)), "r": round(float(both[a].corr(both[b])), 3)})
    # top third vs bottom third: how much more often they defect next session (raw)
    raw = m.pivot_table(index="who", columns="session", values="mean")
    ratios = []
    for a, b in zip(cols, cols[1:]):
        both = raw[[a, b]].dropna()
        if len(both) > 30:
            q = both[a].quantile([1 / 3, 2 / 3])
            top, bot = both[both[a] >= q.iloc[1]][b].mean(), both[both[a] <= q.iloc[0]][b].mean()
            ratios.append({"from": a, "to": b, "top_third_next": round(100 * top, 2), "bottom_third_next": round(100 * bot, 2)})
    return {"z_year_to_year_r": rs, "top_vs_bottom_third_next_session_pct": ratios}


def denominator(X):
    out = {}
    for c, g in X.groupby("committee"):
        split = ((g.yes_D > 0) & (g.no_D > 0)) | ((g.yes_R > 0) & (g.no_R > 0))
        out["committee" if c else "floor"] = f"{int(split.sum())} of {len(g)} ({round(100 * split.mean())}%) had a caucus split"
    return out


def member_subject(A):
    C = A[(A.contested == 1) & (A.law != "(none)")].dropna(subset=["defect"])
    C = C.assign(era=np.where(C.session <= "2021_0", "early", "late"))
    gen = C.groupby(["era", "who"]).defect.mean()
    cell = C.groupby(["era", "who", "law"]).defect.agg(["mean", "size"]).reset_index()
    cell = cell[cell["size"] >= 10]
    cell["resid"] = cell["mean"] - [gen.get((e, w)) for e, w in zip(cell.era, cell.who)]
    piv = cell.pivot_table(index=["who", "law"], columns="era", values="resid").dropna()
    r = float(piv.early.corr(piv.late)) if len(piv) > 30 else None
    return {"member_law_cells_in_both_eras": int(len(piv)), "residual_r_early_vs_late": round(r, 3) if r is not None else None}


def rooms(A, X):
    C = X[X.committee].copy()
    n = A[A.committee].groupby("eid").size()
    C["members"] = n.reindex(C.index)
    C["margin"] = (C.yes - C.no).abs()
    fav = C[C.yes > C.no]
    return {"committee_roll_calls": int(len(C)), "members_recorded_median": float(C.members.median()),
            "members_quartiles": [float(C.members.quantile(.25)), float(C.members.quantile(.75))],
            "unanimous": f"{int((C.no == 0).sum())} of {len(C)} ({round(100 * (C.no == 0).mean())}%)",
            "decided_by_2_or_fewer": f"{int((C.margin <= 2).sum())} of {len(C)}",
            "favourable": int(len(fav)), "failed_or_tied": int((C.yes <= C.no).sum())}


def kill_points(E, F):
    """Bills that died in their first committee: how many ever got a committee roll call there?"""
    pb = F.assign(bill=F.body.map({"H": "HB", "S": "SB"}) + " " + F.number.astype(str))
    voted = set(zip(E[E.committee].session, E[E.committee].bill))
    out = {}
    for s in ("2023_0",):               # the session with full House committee roll-call coverage, completed
        d = pb[(pb.session == s) & (pb.out == 0) & (pb.cmte != "(none)")]
        k = sum(1 for b in d.bill if (s, b) in voted)
        out[s] = f"{k} of {len(d)} bills that died in their first committee ever got a committee roll call"
    return out


def main():
    F = frame()
    E, B, unresolved = B3.load(F)
    X = B3.per_event(E, B, F)
    _d, yn = B3.t_defection(B, X)
    A = B3.ballots_frame(yn, X, F)
    res = {"method": __doc__.split("\n\n")[1].strip(),
           "second_chamber": second_chamber(A, F), "persuadability": persuadability(A), "denominator": denominator(X),
           "member_subject": member_subject(A), "rooms": rooms(A, X), "kill_points": kill_points(E, F)}
    with open(os.path.join(HERE, "results_batch3b.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
