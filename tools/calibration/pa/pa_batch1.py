#!/usr/bin/env python3
"""BATCH 1 — every Virginia bill-level test, re-run on Pennsylvania from PA's own Bill History exports.

One corpus (pa_corpus / pa_frame), one runner, one results file (results_batch1.json). Each test names the Virginia
page it replicates and uses that page's method, adapted only where PA's record differs (said in the test's `note`).

Sessions: completed 2009_0 .. 2023_0; 2025_0 is the live session (ends 30 Nov 2026) — used only as a held-out check
where the outcome is the first committee (almost all settled), never for end-of-session outcomes (law, second
chamber), where it is still incomplete.

Run:  python3 tools/calibration/pa/pa_batch1.py      (≈1 min; prints each result, writes results_batch1.json)
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pa_frame import frame, prior_rate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DONE = ["2009_0", "2011_0", "2013_0", "2015_0", "2017_0", "2019_0", "2021_0", "2023_0"]   # completed sessions
R = {}


def pct(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(100 * x, 1)


def two_prop(a1, n1, a2, n2):
    """Rates, difference (pts) and Fisher exact p for a1/n1 vs a2/n2."""
    if min(n1, n2) == 0:
        return {"a": None, "b": None, "diff_pts": None, "p": None, "n": [n1, n2]}
    p = stats.fisher_exact([[a1, n1 - a1], [a2, n2 - a2]])[1]
    return {"a": pct(a1 / n1), "b": pct(a2 / n2), "diff_pts": round(100 * (a1 / n1 - a2 / n2), 1),
            "p": float(f"{p:.2g}"), "n": [int(n1), int(n2)]}


def record(name, va_page, result, note=""):
    R[name] = {"replicates": va_page, "note": note, **result}
    print(f"\n=== {name}  (VA: {va_page})")
    print(json.dumps(result, indent=1, default=str)[:2500])


# ── 1. the calibration ledger: every bucket stat, fit one session -> predict the next ─────────────────────────
def bucket(series, edges, labels):
    return pd.cut(series, bins=edges, labels=labels, include_lowest=True).astype(str)


def score_stat(train, test, feat, outcome):
    base = train[outcome].mean()
    rates = train.groupby(feat)[outcome].mean()
    pred = test[feat].map(rates).fillna(base)
    unseen = int(test[feat].map(rates).isna().sum())
    mae_null = (test[outcome] - base).abs().mean()
    mae = (test[outcome] - pred).abs().mean()
    return round(100 * (mae_null - mae) / mae_null, 1), unseen


def verdict(o, p):
    if o is None:
        return "n/a"
    if o >= 5 or p >= 5:
        return "USABLE" if min(o, p) > -1 else "CONDITIONAL"
    if o >= 2 or p >= 2:
        return "WEAK" if min(o, p) > -1 else "CONDITIONAL"
    if min(o, p) < -1:
        return "HARMFUL"
    return "NOISE"


def ledger(F):
    F = F.copy()
    F["cosp_share_b"] = np.where(F["n_cosp"] == 0, "none", bucket(F["maj_cosp_share"], [-.01, .5, .999, 1.0], ["<=half", "most", "all"]))
    F["vol_b"] = bucket(F["patron_volume"], [0, 1, 5, 15, 1e9], ["1", "2-5", "6-15", "16+"])
    F["tenure_b"] = bucket(F["tenure"], [-1, 0, 1, 3, 99], ["new", "1", "2-3", "4+"])
    F["rank_b"] = bucket(F["patron_bill_rank"], [0, 1, 3, 10, 1e9], ["1", "2-3", "4-10", "11+"])
    F["batch_b"] = bucket(F["same_day_batch"], [0, 1, 3, 1e9], ["1", "2-3", "4+"])
    F["count_b"] = bucket(F["n_cosp"] + 1, [0, 1, 5, 15, 30, 1e9], ["1", "2-5", "6-15", "16-30", "31+"])
    F["spread_b"] = bucket(F["cosp_districts"], [-1, 0, 5, 15, 1e9], ["0", "1-5", "6-15", "16+"])
    F["xchamber"] = (F["n_cross_chamber_cosp"] > 0).astype(int)
    F["district_b"] = bucket(pd.to_numeric(F["p_district"], errors="coerce").fillna(0), [-1, 50, 100, 150, 999], ["1-50", "51-100", "101-150", "151+"])
    F["load_b"] = F.groupby("session")["cmte_load"].transform(lambda s: pd.qcut(s.rank(method="first"), 4, labels=["q1", "q2", "q3", "q4"]).astype(str))
    F["recency_b"] = F.groupby("session")["days_in"].transform(lambda s: pd.qcut(s.rank(method="first"), 4, labels=["q1", "q2", "q3", "q4"]).astype(str))
    pr = prior_rate(F, ["p_key"])
    F["prior_rate_b"] = np.where(pr.isna(), "none", bucket(pr.fillna(0), [-.01, .2, .5, 1], ["<20%", "20-50%", ">50%"]))
    prc = prior_rate(F, ["p_key", "cmte"])
    F["prior_cmte_b"] = np.where(prc.isna(), "none", bucket(prc.fillna(0), [-.01, .2, .5, 1], ["<20%", "20-50%", ">50%"]))
    # patron generosity / network breadth from the PREVIOUS session
    gen, net = {}, {}
    for s, g in F.groupby("session"):
        c = collections.Counter(k for ks in g["cosp_keys"] for k in ks)
        gen[s] = c
        net[s] = g.groupby("p_key")["cosp_keys"].apply(lambda col: len({k for ks in col for k in ks})).to_dict()
    order = sorted(F["session"].unique())
    prev = {s: order[i - 1] if i else None for i, s in enumerate(order)}
    F["generosity_b"] = [("none" if prev[s] is None else str(min(gen[prev[s]].get(k, 0) // 25, 4))) for s, k in zip(F["session"], F["p_key"])]
    F["network_b"] = [("none" if prev[s] is None else str(min(net[prev[s]].get(k, 0) // 25, 4))) for s, k in zip(F["session"], F["p_key"])]
    stats_ = {
        "patron_in_majority": "in_maj", "patron_party": "p_party", "committee": "cmte", "chamber": "body",
        "bill_type (subtype: joint resolution J vs act)": "subtype", "majority_copatron_share": "cosp_share_b",
        "patron_volume": "vol_b", "member_tenure_band (member_id_band analog)": "tenure_b", "cmte_load": "load_b",
        "patron_bill_rank": "rank_b", "patron_prior_in_this_cmte": "prior_cmte_b", "patron_district_band": "district_b",
        "patron_generosity": "generosity_b", "same_day_batch": "batch_b", "bipartisan_copatrons": "bipartisan",
        "patron_count": "count_b", "copatron_district_spread": "spread_b", "cross_chamber_copatrons": "xchamber",
        "money_committee": "money_cmte", "names_locality": "names_locality", "filing_recency_band": "recency_b",
        "patron_network_breadth": "network_b", "patron_prior_rate": "prior_rate_b",
        "PA: co-sponsorship memo filed": "memo", "PA: second year of the session": "second_year",
        "PA: title form (enacting-clause analog)": "title_form",
    }
    rows = {}
    for label, col in stats_.items():
        o, uo = score_stat(F[F.session == "2021_0"], F[F.session == "2023_0"], col, "out")
        p, up = score_stat(F[F.session == "2021_0"], F[F.session == "2023_0"], col, "passed")
        o2, _ = score_stat(F[F.session == "2023_0"], F[F.session == "2025_0"], col, "out")
        rows[label] = {"out": o, "pass": p, "verdict": verdict(o, p), "replication_out_2023to2025": o2,
                       "unseen_buckets_2023": uo}
    na = {"patron_matches_cmte_majority": "identical to patron_in_majority in PA (committee majorities mirror the chamber)",
          "subject_primary / subject_count / cmte_prior_on_this_subject / subject_cmte_match / patron_prior_on_this_subject":
              "PA's export carries no subject vocabulary — BLOCKED (Open States subjects to be checked in batch 3)",
          "patron_on_cmte / cmte_member_copatrons / committee_size": "need committee rosters — batch 2 (2025-26 only)",
          "text_versions_at_intro": "every PA bill has exactly one printer's number at introduction — constant, untestable",
          "dls_tag / catchline_segments / emergency / prefiled": "Virginia drafting/filing artefacts with no PA equivalent (PA's analog of prefiling, the co-sponsorship memo, is tested)",
          "has_chief_copatron / bipartisan_chief_pair": "PA has no chief co-patron role",
          "patron_absence / patron_prior_loyalty / patron_prior_floor_win_rate / patron_agrees_with_current_cmte":
              "need per-member votes — batch 3"}
    record("calibration_ledger", "testing/calibration_ledger",
           {"method": "fit 2021-22 -> predict 2023-24; % reduction in mean absolute error vs the 2021-22 base rate (VA: fit 2023 -> predict 2024)",
            "stats": rows, "not_testable_here": na})


# ── 2. the fate model + panel audit (forecast at filing) ──────────────────────────────────────────────────────
def model_frame(F):
    X = pd.DataFrame(index=F.index)
    X["in_maj"] = F["in_maj"]
    X["senate"] = (F["body"] == "S").astype(int)
    X["second_year"] = F["second_year"]
    X["days_in"] = F["days_in"].fillna(F["days_in"].median())
    X["n_maj_cosp"] = F["n_maj_cosp"]
    X["n_min_cosp"] = F["n_min_cosp"]
    X["bipartisan"] = F["bipartisan"]
    X["memo"] = F["memo"]
    X["money"] = F["money_cmte"]
    X["joint_res"] = (F["subtype"] == "J").astype(int)
    for f in ("amend", "provide", "establish", "repeal", "appropriate"):
        X[f"form_{f}"] = (F["title_form"] == f).astype(int)
    X["tenure"] = F["tenure"]
    X["patron_volume"] = F["patron_volume"]
    X["cmte_prior"] = prior_rate(F, ["body", "cmte"])
    X["cmte_x_maj_prior"] = prior_rate(F, ["body", "cmte", "in_maj"])
    X["patron_prior"] = prior_rate(F, ["p_key"])
    return X


def fate_model(F):
    X = model_frame(F)
    y = F["out"]
    cell = ["in_maj", "body", "second_year"]
    out = {}
    for test in ("2021_0", "2023_0", "2025_0"):
        tr = F["session"] < test
        te = F["session"] == test
        base_rates = F[tr].groupby(cell)["out"].mean()
        base = F[te].set_index(cell).index.map(base_rates).to_numpy(dtype=float)
        base = np.where(np.isnan(base), y[tr].mean(), base)
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.1, random_state=0)
        m.fit(X[tr], y[tr])
        pm = m.predict_proba(X[te])[:, 1]
        blend = 0.5 * pm + 0.5 * base           # VA's rule: model averaged 50:50 with the baseline
        ablate = {}
        for name, cols in {"majority only": ["in_maj"], "+ room record": ["in_maj", "cmte_prior", "cmte_x_maj_prior"],
                           "+ carrier record": ["in_maj", "cmte_prior", "cmte_x_maj_prior", "patron_prior", "tenure"]}.items():
            mm = HistGradientBoostingClassifier(max_depth=3, max_iter=100, random_state=0).fit(X.loc[tr, cols], y[tr])
            ablate[name] = round(roc_auc_score(y[te], mm.predict_proba(X.loc[te, cols])[:, 1]), 3)
        out[test] = {"n": int(te.sum()), "base_rate": pct(y[te].mean()),
                     "baseline_logloss": round(log_loss(y[te], base), 3), "model_logloss": round(log_loss(y[te], blend), 3),
                     "baseline_auc": round(roc_auc_score(y[te], base), 3), "model_auc": round(roc_auc_score(y[te], blend), 3),
                     "panel_audit_auc_ladder": ablate}
        if test == "2025_0":
            bins = pd.cut(blend, [0, .2, .4, .6, .8, 1.0], include_lowest=True)
            cal = pd.DataFrame({"bin": bins, "y": y[te].to_numpy()}).groupby("bin", observed=True)["y"].agg(["count", "mean"])
            out[test]["how_chances_hold_up"] = {str(k): {"bills": int(v["count"]), "actually_out_per_100": round(100 * v["mean"])}
                                                for k, v in cal.iterrows()}
            top = pd.Series(blend).rank(pct=True) >= 0.9
            out[test]["top_decile_out_per_100"] = round(100 * y[te].to_numpy()[top.to_numpy()].mean())
    record("bill_fate + panel_audit", "testing/bill_fate · testing/panel_audit",
           {"outcome": "gets out of its first committee (reported) — PA committees record no kill vote in the export, so fate is binary",
            "model": "boosted trees depth 3 × 100, averaged 50:50 with the baseline (patron standing × chamber × session year), trained on earlier sessions only",
            "year_ahead": out})


# ── 3. bill states: does a record ever leave its state? ───────────────────────────────────────────────────────
def bill_states(F):
    D = F[F.session.isin(DONE)]
    defs = {
        "Reported (as committed/amended) -> passes its chamber": (lambda v, c: v.startswith("Reported as"), lambda v, c: c == "passed"),
        "Re-referred to (another committee) -> re-reported": (lambda v, c: v == "Re-referred to", lambda v, c: c == "reported"),
        "Re-committed to -> re-reported": (lambda v, c: v == "Re-committed to", lambda v, c: c == "reported"),
        "Laid on the table -> removed from table": (lambda v, c: v == "Laid on the table,", lambda v, c: v == "Removed from table,"),
        "Laid on the table (Rule 71 / Rule 9) -> removed": (lambda v, c: v.startswith("Laid on the table (Pursuant"), lambda v, c: v == "Removed from table,"),
        "Defeated on final passage -> later passes": (lambda v, c: c == "defeated", lambda v, c: c == "passed"),
        "Passed its chamber -> passes the other": (lambda v, c: c == "passed", None),
    }
    res = {}
    for label, (enter, leave) in defs.items():
        n = left = 0
        for body, acts in zip(D["body"], D["actions"]):
            idx = next((i for i, a in enumerate(acts) if enter(a[2], a[3]) and (label.startswith("Passed") is False or a[1] == body)), None)
            if idx is None:
                continue
            n += 1
            later = acts[idx + 1:]
            if leave is None:
                other = "S" if body == "H" else "H"
                left += any(a[3] == "passed" and a[1] == other for a in later)
            else:
                left += any(leave(a[2], a[3]) for a in later)
        res[label] = {"bills": n, "left_the_state": left, "share": pct(left / n) if n else None}
    record("bill_states", "testing/bill_states", {"sessions": "2009-2024 (completed)", "states": res,
           "note": "PA's 'Laid on the table' is routine procedure (a reported bill is tabled, then removed when scheduled) — unlike Virginia, where tabling kills"})


# ── 4. continuance analog: the re-committal ───────────────────────────────────────────────────────────────────
def recommittal(F):
    D = F[F.session.isin(DONE)]
    n = moved = 0
    gaps = []
    for acts in D["actions"]:
        idx = next((i for i, a in enumerate(acts) if a[2] == "Re-committed to"), None)
        if idx is None:
            continue
        n += 1
        nxt = next((a for a in acts[idx + 1:] if a[3] in ("reported", "passed", "floor") and a[2] != "Laid on the table,"), None)
        if nxt and nxt[0] and acts[idx][0]:
            moved += 1
            gaps.append((nxt[0] - acts[idx][0]).days)
    g = np.array(gaps)
    record("continuance (PA analog: re-committal)", "testing/continuance",
           {"bills_recommitted": n, "ever_moved_again": moved, "share": pct(moved / n),
            "days_to_move_median": float(np.median(g)) if len(g) else None,
            "days_to_move_p90": float(np.percentile(g, 90)) if len(g) else None,
            "moved_within_30_days_share_of_movers": pct((g <= 30).mean()) if len(g) else None},
           note="PA has no continuance (two-year session; bills die at its end). Its parking move is 'Re-committed to' "
                "(usually Appropriations or Rules, after second consideration).")


# ── 5. where bills die (kill points, bill level) ──────────────────────────────────────────────────────────────
def kill_points(F):
    D = F[F.session.isin(DONE)]
    stages = collections.Counter()
    for _, b in D.iterrows():
        other = "S" if b["body"] == "H" else "H"
        acts = b["actions"]
        rep2 = any(a[1] == other and a[3] == "reported" for a in acts)
        if b["law"]:
            stages["became law"] += 1
        elif not b["out"]:
            stages["died in its first committee (never reported)"] += 1
        elif b["defeated"] and not b["passed"]:
            stages["defeated on its first floor"] += 1
        elif not b["passed"]:
            stages["reported, never passed its first floor (tabled / re-committed / not called)"] += 1
        elif not rep2:
            stages["passed one chamber, died in the second chamber's committee"] += 1
        elif not b["passed2"]:
            stages["reported in the second chamber, never passed there"] += 1
        elif b["vetoed"]:
            stages["vetoed"] += 1
        else:
            stages["passed both, not law (concurrence / conference / still with Governor)"] += 1
    tot = sum(stages.values())
    record("kill_points (bill level)", "testing/kill_points",
           {"bills": tot, "stages": {k: {"bills": v, "share": pct(v / tot)} for k, v in stages.most_common()}},
           note="Virginia's kill_points also splits subcommittee vs full committee from committee roll calls; PA's export "
                "has no committee roll calls, so this is the bill-level half only")


# ── 6. the room: spread, partisan gap, rewrite rate, never-acts, persistence ──────────────────────────────────
def rooms(F):
    D = F[F.session.isin(DONE) & (F.cmte != "(none)")]
    def table(sub):
        g = sub.groupby(["body", "cmte"])
        t = pd.DataFrame({"n": g["sid"].count(), "rate": g["out"].mean(),
                          "maj": sub[sub.in_maj == 1].groupby(["body", "cmte"])["out"].mean(),
                          "min": sub[sub.in_maj == 0].groupby(["body", "cmte"])["out"].mean(),
                          "rewrite": sub[sub.out == 1].groupby(["body", "cmte"])["out_amended"].mean()})
        t["gap"] = t["maj"] - t["min"]
        t["never_acts"] = 1 - t["rate"]
        return t
    t = table(D)
    t = t[t.n >= 100]
    a = table(D[D.session.isin(["2009_0", "2011_0", "2013_0", "2015_0"])])
    b = table(D[D.session.isin(["2017_0", "2019_0", "2021_0", "2023_0"])])
    j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
    j = j[(j.n_a >= 50) & (j.n_b >= 50)]
    def r(col):
        x = j[[f"{col}_a", f"{col}_b"]].dropna()
        return round(float(np.corrcoef(x.iloc[:, 0], x.iloc[:, 1])[0, 1]), 2) if len(x) > 3 else None
    record("rooms / venue spread / profiles (room panel) / clock (never-acts)",
           "testing/venue_shopping · testing/profiles · testing/clock · testing/calibration_scope",
           {"rooms_with_100_plus_bills": int(len(t)),
            "report_rate_range": [pct(t.rate.min()), pct(t.rate.max())],
            "partisan_gap_range_pts": [pct(t.gap.min()), pct(t.gap.max())],
            "rewrite_rate_range": [pct(t.rewrite.min()), pct(t.rewrite.max())],
            "never_acts_range": [pct(t.never_acts.min()), pct(t.never_acts.max())],
            "era_persistence_r (2009-16 vs 2017-24, rooms with 50+ bills each)": {"report_rate": r("rate"), "partisan_gap": r("gap"), "rewrite_rate": r("rewrite")},
            "widest_gaps": {f"{k[0]} {k[1]}": f"{pct(v['maj'])}% vs {pct(v['min'])}%" for k, v in t.sort_values("gap", ascending=False).head(5).iterrows()},
            "narrowest_gaps": {f"{k[0]} {k[1]}": f"{pct(v['maj'])}% vs {pct(v['min'])}%" for k, v in t.sort_values("gap").head(5).iterrows()}},
           note="In PA a committee that never reports a bill is the kill — there is no recorded no-vote, so Virginia's "
                "'never acts' and 'kills' collapse into one number here. Dies-on-a-record and unanimity need committee "
                "roll calls (not in the export).")
    # calibration_scope: the committee stat by chamber
    byc = {}
    for body in ("H", "S"):
        tr, te = F[(F.session == "2021_0") & (F.body == body)], F[(F.session == "2023_0") & (F.body == body)]
        byc[body] = score_stat(tr, te, "cmte", "out")[0]
    R["rooms / venue spread / profiles (room panel) / clock (never-acts)"]["committee_stat_by_chamber_out_pct_mae"] = byc
    print("committee stat by chamber:", byc)


# ── 7. venue shopping: same idea, different room ──────────────────────────────────────────────────────────────
def venue_shopping(F):
    D = F[F.session.isin(DONE) & (F.cmte != "(none)") & (F.tkey != "")]
    groups = D.groupby(["body", "tkey"])
    tot = D.groupby(["body", "cmte"])["out"].agg(["sum", "count"])
    hi_wins = lo_wins = pairs = 0
    diffs = []
    for (body, _), g in groups:
        if g["cmte"].nunique() < 2:
            continue
        # leave-group-out room rate: the room's record WITHOUT this idea's bills
        gs = g.groupby("cmte")["out"].agg(["sum", "count"])
        rr = {}
        for c in gs.index:
            s_, n_ = tot.loc[(body, c)]
            s_, n_ = s_ - gs.loc[c, "sum"], n_ - gs.loc[c, "count"]
            if n_ >= 30:
                rr[c] = s_ / n_
        g = g[g["cmte"].isin(rr)]
        if g["cmte"].nunique() < 2:
            continue
        g = g.assign(room=g["cmte"].map(rr))
        hi = g[g.room == g.room.max()]
        lo = g[g.room == g.room.min()]
        pairs += 1
        diffs.append(hi["out"].mean() - lo["out"].mean())
        hi_wins += hi["out"].mean() > lo["out"].mean()
        lo_wins += hi["out"].mean() < lo["out"].mean()
    d = np.array(diffs)
    p = stats.binomtest(hi_wins, hi_wins + lo_wins).pvalue if hi_wins + lo_wins else None
    record("venue_shopping", "testing/venue_shopping",
           {"same_idea_groups (exact title, same chamber, 2+ rooms)": pairs,
            "mean_diff_pts (higher-rate room minus lower-rate room)": pct(d.mean()) if len(d) else None,
            "groups_where_higher_room_did_better": int(hi_wins), "groups_where_lower_room_did_better": int(lo_wins),
            "sign_test_p": float(f"{p:.2g}") if p else None},
           note="Room rates are leave-group-out (computed without the group's own bills). In PA an exact title = same statute "
                "+ section amended, not necessarily the same policy (see room_memory caveat) — read this as 'same part of the law, different room'.")


# ── 8. venue effect: the companion bill as a control group ────────────────────────────────────────────────────
def venue_effect(F):
    D = F[F.session.isin(DONE) & (F.tkey != "")]
    pairs = both = neither = div = h_lived = 0
    for (s, k), g in D.groupby(["session", "tkey"]):
        if set(g["body"]) != {"H", "S"} or len(g) != 2:
            continue
        pairs += 1
        h, sn = g[g.body == "H"].iloc[0], g[g.body == "S"].iloc[0]
        if h.out and sn.out:
            both += 1
        elif not h.out and not sn.out:
            neither += 1
        else:
            div += 1
            h_lived += int(h.out)
    p = stats.binomtest(h_lived, div).pvalue if div else None
    record("venue_effect", "testing/venue_effect",
           {"companion_pairs (exact title, one HB + one SB, same session)": pairs, "both_reported": both,
            "neither": neither, "diverged": div, "house_bill_lived_in_diverged": h_lived,
            "house_share_of_survivors": pct(h_lived / div) if div else None, "binomial_p_vs_50_50": float(f"{p:.2g}") if p else None},
           note="Virginia: 272 of 1,443 pairs diverged with a 50/50 chamber split — variance at the room, not the body. "
                "PA caveat: an exact-title HB/SB pair is the same statute section, not always the same policy.")


# ── 9. room memory: committees remember ideas ─────────────────────────────────────────────────────────────────
def room_memory(F):
    D = F[F.tkey != ""].sort_values("session")
    last = {}
    rows = []
    for _, b in D.iterrows():
        key = (b.body, b.tkey)
        e = last.get(key)
        if e is not None and e["session"] < b.session:
            rows.append({"same_room": e["cmte"] == b.cmte, "prev_died": 1 - e["out"], "died": 1 - b.out,
                         "same_standing": e["in_maj"] == b.in_maj, "new_carrier": e["p_key"] != b.p_key,
                         "session": b.session})
        last[key] = b
    M = pd.DataFrame(rows)
    M = M[M.session.isin(DONE + ["2025_0"]) & M.same_standing]
    def orx(sub):
        a = sub[(sub.prev_died == 1)]
        c = sub[(sub.prev_died == 0)]
        t = [[a.died.sum(), len(a) - a.died.sum()], [c.died.sum(), len(c) - c.died.sum()]]
        o, p = stats.fisher_exact(t)
        return {"died_before_dies_again": pct(a.died.mean()) if len(a) else None,
                "cleared_before_dies": pct(c.died.mean()) if len(c) else None,
                "odds_ratio": round(o, 1) if np.isfinite(o) else None, "p": float(f"{p:.2g}"), "n": [len(a), len(c)]}
    def logor(sub):
        a = sub[sub.prev_died == 1]; c = sub[sub.prev_died == 0]
        t = np.array([[a.died.sum(), len(a) - a.died.sum()], [c.died.sum(), len(c) - c.died.sum()]], float) + 0.5
        return math.log(t[0, 0] * t[1, 1] / (t[0, 1] * t[1, 0])), (1 / t).sum()
    l1, v1 = logor(M[M.same_room]); l2, v2 = logor(M[~M.same_room])
    z = (l1 - l2) / math.sqrt(v1 + v2)
    after_no = M[(M.prev_died == 1)]
    record("room_memory", "testing/room_memory",
           {"refiled_same_idea (exact title, earlier session, same chamber, same patron standing)": int(len(M)),
            "coverage_of_all_bills": pct(len(M) / len(F[F.session.isin(DONE + ['2025_0'])])),
            "same_room": orx(M[M.same_room]), "different_room": orx(M[~M.same_room]),
            "same_room_vs_different_room_z": round(z, 2), "p_two_sided": float(f"{2 * stats.norm.sf(abs(z)):.2g}"),
            "after_a_no_moving_rooms (dies: same room vs different room)": two_prop(
                after_no[after_no.same_room].died.sum(), int(after_no.same_room.sum()),
                after_no[~after_no.same_room].died.sum(), int((~after_no.same_room).sum())),
            "same_room_new_carrier": orx(M[M.same_room & M.new_carrier]),
            "same_room_same_carrier_refile (closest to 'same idea')": orx(M[M.same_room & ~M.new_carrier]),
            "different_room_same_carrier_refile": orx(M[~M.same_room & ~M.new_carrier]),
            "title_reuse": {"distinct_titles": int(F.tkey.nunique()), "bills": int(len(F)),
                            "titles_used_by_5_plus_different_carriers": int((F.groupby(["body", "tkey"]).p_key.nunique() >= 5).sum())}},
           note="CAVEAT: a PA title names the statute and section amended ('…Tax Reform Code…, further providing for "
                "classes of income'), not the policy — 38 carriers filed that one title. So PA's exact-title match means "
                "'same part of the law', coarser than Virginia's catchline. The same-carrier refile rows are the closest "
                "PA gets to 'same idea' without bill text.")


# ── 10. enacting clause analog: the title's form ──────────────────────────────────────────────────────────────
def title_form(F):
    D = F[F.session.isin(DONE)]
    res = {}
    for side, sub in (("majority", D[D.in_maj == 1]), ("minority", D[D.in_maj == 0])):
        am = sub[sub.title_form == "amend"]
        new = sub[sub.title_form.isin(["provide", "establish"])]
        res[side] = {"out": two_prop(am.out.sum(), len(am), new.out.sum(), len(new)),
                     "passed": two_prop(am.passed.sum(), len(am), new.passed.sum(), len(new))}
    mix = D.title_form.value_counts().to_dict()
    record("enacting_clause (PA: the title's form)", "testing/enacting_clause · testing/blind_sweep",
           {"amend_vs_new_act (a = 'An Act amending…', b = 'An Act providing for / establishing…')": res,
            "title_forms": {k: int(v) for k, v in mix.items()}},
           note="PA's official title states what the act does ('An Act amending Title 75…' vs 'An Act providing for…'), "
                "the analog of Virginia's enacting clause. Title is the filed title (PA does not retitle on passage in the export).")


# ── 11. contested vs routine + second chamber ─────────────────────────────────────────────────────────────────
def contested_and_second(F):
    D = F[F.session.isin(DONE) & F.passed.astype(bool) & F.tally.notna()].copy()
    D["opp"] = [n / (y + n) if (y + n) else None for y, n in D["tally"]]
    D["routine"] = (D["opp"] < 0.05).astype(int)
    res = {"bills_passed_origin_with_tally": int(len(D)), "routine_share (<5% no votes on passage)": pct(D.routine.mean())}
    for lab, sub in (("routine", D[D.routine == 1]), ("contested", D[D.routine == 0])):
        own = sub[sub.p_party_runs_second == 1]
        oth = sub[sub.p_party_runs_second == 0]
        res[lab] = {"passes_second_chamber": pct(sub.passed2.mean()), "law": pct(sub.law.mean()),
                    "own_party_runs_second_vs_not (passes second)": two_prop(own.passed2.sum(), len(own), oth.passed2.sum(), len(oth))}
    record("contested_vs_routine + second_chamber", "testing/contested_vs_routine · testing/second_chamber", res,
           note="Opposition share is measured on the ORIGIN-chamber passage roll call (PA's export carries floor tallies, "
                "not committee roll calls), so this conditions on reaching passage. Party-split surplus votes need member votes (batch 3).")


# ── 12. the bill-mix confound: the 2023 House flip ────────────────────────────────────────────────────────────
def bill_mix(F):
    H = F[(F.body == "H") & F.session.isin(["2021_0", "2023_0"])]
    per = H.groupby(["p_key", "session", "p_party"])["out"].agg(["mean", "count"]).reset_index()
    wide = per.pivot_table(index=["p_key", "p_party"], columns="session", values=["mean", "count"])
    wide = wide.dropna()
    wide = wide[(wide[("count", "2021_0")] >= 3) & (wide[("count", "2023_0")] >= 3)]
    out = {}
    for party, lab in (("D", "Democrats (gained the House in 2023)"), ("R", "Republicans (lost it)")):
        w = wide.xs(party, level="p_party")
        d = w[("mean", "2023_0")] - w[("mean", "2021_0")]
        out[lab] = {"members": int(len(w)), "within_member_change_pts": pct(d.mean()),
                    "p (Wilcoxon)": float(f"{stats.wilcoxon(d).pvalue:.2g}") if len(d) > 5 else None}
    # same member, same exact title, refiled across the flip
    t = H.groupby(["p_key", "tkey", "session", "p_party"])["out"].max().unstack("session").dropna()
    for party in ("D", "R"):
        x = t.xs(party, level="p_party") if party in t.index.get_level_values("p_party") else pd.DataFrame()
        out[f"same member + same title refiled, {party}"] = {"bills": int(len(x)),
            "out_2021": pct(x["2021_0"].mean()) if len(x) else None, "out_2023": pct(x["2023_0"].mean()) if len(x) else None}
    S = F[(F.body == "S") & F.session.isin(["2021_0", "2023_0"])]
    out["placebo: Senate (R both sessions)"] = {p: pct(S[S.p_party == p].groupby("session")["out"].mean().diff().iloc[-1]) for p in ("D", "R")}
    record("bill_mix_confound (2023 House flip)", "testing/bill_mix_confound", out,
           note="Same member, before and after their party gained/lost the House: if the majority effect were bill mix "
                "(majority members file easier bills), it would not move with control.")


# ── 13. the carrier: which vehicle is kept, and is carrier skill a trait? ─────────────────────────────────────
def carrier(F):
    D = F[F.session.isin(DONE) & (F.tkey != "")]
    n = maj_kept = exp = 0.0
    for (s, body, k), g in D.groupby(["session", "body", "tkey"]):
        if len(g) < 2 or g.p_key.nunique() < 2 or g.out.sum() != 1 or g.in_maj.nunique() < 2:
            continue
        n += 1
        maj_kept += int(g[g.out == 1].in_maj.iloc[0])
        exp += g.in_maj.mean()
    res = {"contests (same session+chamber+title, mixed-party carriers, exactly one reported)": int(n),
           "majority_carrier_kept": int(maj_kept), "kept_share": pct(maj_kept / n) if n else None,
           "expected_share_from_mix": pct(exp / n) if n else None,
           "binomial_p": float(f"{stats.binomtest(int(maj_kept), int(n), exp / n).pvalue:.2g}") if n else None}
    # carrier lift: member's report rate minus the cell expectation (session x chamber x standing x room)
    E = F[F.session.isin(DONE)].copy()
    cell = E.groupby(["session", "body", "in_maj", "cmte"])["out"].transform("mean")
    E["resid"] = E["out"] - cell
    def rel(a, b):
        x = pd.concat([a, b], axis=1).dropna()
        return (round(float(np.corrcoef(x.iloc[:, 0], x.iloc[:, 1])[0, 1]), 2), int(len(x))) if len(x) > 10 else (None, len(x))
    E["half"] = E.groupby("p_key").cumcount() % 2
    big = E.groupby("p_key")["sid"].count()
    big = big[big >= 20].index
    h = E[E.p_key.isin(big)].groupby(["p_key", "half"])["resid"].mean().unstack()
    lift_sd = E[E.p_key.isin(big)].groupby("p_key")["resid"].mean().std()
    s_order = sorted(E.session.unique())
    pairs = []
    for a, b in zip(s_order, s_order[1:]):
        ma = E[E.session == a].groupby("p_key")["resid"].agg(["mean", "count"])
        mb = E[E.session == b].groupby("p_key")["resid"].agg(["mean", "count"])
        j = ma.join(mb, lsuffix="a", rsuffix="b", how="inner")
        j = j[(j.counta >= 8) & (j.countb >= 8)]
        pairs.append(j[["meana", "meanb"]])
    P = pd.concat(pairs)
    # bipartisan filing and specialisation as traits
    E["bip"] = E["bipartisan"]
    trait = {}
    for name, col in (("bipartisan filing", "bip"),):
        seq = []
        for a, b in zip(s_order, s_order[1:]):
            ma = E[E.session == a].groupby("p_key")[col].agg(["mean", "count"])
            mb = E[E.session == b].groupby("p_key")[col].agg(["mean", "count"])
            j = ma.join(mb, lsuffix="a", rsuffix="b", how="inner")
            seq.append(j[(j.counta >= 8) & (j.countb >= 8)][["meana", "meanb"]])
        trait[name] = rel(*[pd.concat(seq).iloc[:, i] for i in (0, 1)])
    spec = []
    for a, b in zip(s_order, s_order[1:]):
        def topshare(sub):
            return sub.groupby("p_key")["cmte"].agg(lambda c: c.value_counts(normalize=True).iloc[0] if len(c) >= 8 else np.nan)
        spec.append(pd.concat([topshare(E[E.session == a]), topshare(E[E.session == b])], axis=1).dropna())
    trait["specialisation (top-room share)"] = rel(*[pd.concat(spec).iloc[:, i] for i in (0, 1)])
    res.update({"carrier_lift_sd_pts (members with 20+ bills)": pct(lift_sd),
                "carrier_lift_split_half_r": rel(h[0], h[1]),
                "carrier_lift_session_to_session_r": rel(P["meana"], P["meanb"]),
                "other_member_traits_session_to_session_r": trait})
    record("carrier_effect + profiles (member panel)", "testing/carrier_effect · testing/profiles", res,
           note="PA has no incorporation; its analog contest is two carriers filing the same exact title in one chamber "
                "and session where exactly one is reported.")


# ── 14. the blind sweep: let the data nominate ────────────────────────────────────────────────────────────────
def blind_sweep(F):
    F = F.copy()
    F["vol_b"] = pd.cut(F["patron_volume"], [0, 1, 5, 15, 1e9], labels=["1", "2-5", "6-15", "16+"]).astype(str)
    F["cosp_b"] = pd.cut(F["n_cosp"], [-1, 0, 5, 15, 1e9], labels=["0", "1-5", "6-15", "16+"]).astype(str)
    F["tenure_b"] = pd.cut(F["tenure"], [-1, 0, 1, 3, 99], labels=["new", "1", "2-3", "4+"]).astype(str)
    feats = ["title_form", "memo", "bipartisan", "money_cmte", "subtype", "second_year", "vol_b", "cosp_b", "tenure_b",
             "names_locality", "body"]
    tr = F[F.session.isin(["2009_0", "2011_0", "2013_0", "2015_0", "2017_0", "2019_0"])]
    te = F[F.session.isin(["2021_0", "2023_0", "2025_0"])]
    nominated, replicated = [], []
    for f in feats:
        for side in (0, 1):
            a, b = tr[tr.in_maj == side], te[te.in_maj == side]
            base_a, base_b = a.out.mean(), b.out.mean()
            for v, g in a.groupby(f):
                if len(g) < 100:
                    continue
                lift = g.out.mean() - base_a
                p = stats.binomtest(int(g.out.sum()), len(g), base_a).pvalue
                if abs(lift) >= 0.05 and p < 0.01:
                    gb = b[b[f] == v]
                    if len(gb) < 30:
                        continue
                    lift_b = gb.out.mean() - base_b
                    pb = stats.binomtest(int(gb.out.sum()), len(gb), base_b).pvalue
                    item = {"feature": f"{f}={v}", "patron": "majority" if side else "minority",
                            "sweep_lift_pts": pct(lift), "test_lift_pts": pct(lift_b), "test_p": float(f"{pb:.2g}"), "n_test": int(len(gb))}
                    nominated.append(item)
                    if np.sign(lift) == np.sign(lift_b) and pb < 0.05:
                        replicated.append(item)
    record("blind_sweep", "testing/blind_sweep",
           {"swept_on": "2009-2020", "tested_on": "2021-2026", "scored_against": "the patron's own standing (majority / minority), never the overall base — VA's v1 trap",
            "nominated": len(nominated), "replicated": len(replicated),
            "replicated_cells": sorted(replicated, key=lambda d: -abs(d["test_lift_pts"]))})


# ── 15. the clock: of bills still unreported N months after referral, how many are ever reported? ─────────────
def clock(F):
    D = F[F.session.isin(DONE)]
    res = {}
    for months in (0, 1, 2, 3, 6, 12):
        alive = rep = 0
        for acts, body in zip(D["actions"], D["body"]):
            ref = next((a for a in acts if a[2] == "Referred to" and a[1] == body and a[0]), None)
            if ref is None:
                continue
            r = next((a for a in acts if a[1] == body and a[3] == "reported" and a[0]), None)
            cutoff = ref[0] + __import__("datetime").timedelta(days=30 * months)
            if r is not None and r[0] < cutoff:
                continue                      # already reported by the cutoff: not 'still unheard'
            alive += 1
            rep += r is not None
        res[f"unreported at {months} months"] = {"bills": alive, "ever_reported": pct(rep / alive) if alive else None}
    record("clock (time since referral)", "testing/clock", res,
           note="PA sessions run two years with no crossover deadline, so the cliff (if any) is the session's end, not a week.")


# ── 16. second chamber: do surplus cross-party votes in chamber 1 buy anything in chamber 2? ──────────────────
def second_chamber_surplus(F):
    D = F[F.session.isin(DONE) & F.passed.astype(bool) & F.tally.notna()].copy()
    # seats per party per chamber per session, from the session's own sponsor roll (structural: party + district)
    from pa_corpus import load
    seats = {}
    for s, d in load().items():
        for b in d["bills"]:
            for sp in [b["prime"]] + b["cosponsors"]:
                if sp and sp["party"] and sp["district"] and sp["body"]:
                    seats.setdefault((s, sp["body"]), set()).add((sp["party"], sp["district"]))
    own = [sum(1 for p, _ in seats.get((s, b), ()) if p == pp) for s, b, pp in zip(D.session, D.body, D.p_party)]
    D["surplus"] = [max(0, y - o) for (y, n), o in zip(D["tally"], own)]
    D["surplus_b"] = pd.cut(D["surplus"], [-1, 0, 10, 50, 999], labels=["0", "1-10", "11-50", "51+"]).astype(str)
    res = {}
    for runs, lab in ((1, "patron's party runs the second chamber"), (0, "the other party runs it")):
        sub = D[D.p_party_runs_second == runs]
        res[lab] = {b: {"bills": int(len(g)), "passes_second": pct(g.passed2.mean())} for b, g in sub.groupby("surplus_b")}
        ct = pd.crosstab(sub["surplus_b"], sub["passed2"])
        res[lab]["chi2_p"] = float(f"{stats.chi2_contingency(ct)[1]:.2g}") if ct.shape == (4, 2) else None
    record("second_chamber (surplus votes)", "testing/second_chamber", res,
           note="Surplus = yes votes beyond the patron's own party's seats (a floor on cross-party yes votes; exact "
                "party splits need member votes, batch 3). Virginia: surplus buys nothing where your party runs the second chamber.")


def main():
    F = frame()
    print(f"corpus: {len(F):,} HB/SB across {F.session.nunique()} sessions")
    for fn in (ledger, fate_model, bill_states, recommittal, kill_points, rooms, venue_shopping, venue_effect,
               room_memory, title_form, contested_and_second, bill_mix, carrier, blind_sweep, clock, second_chamber_surplus):
        fn(F)
    with open(os.path.join(HERE, "results_batch1.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    print(f"\nwrote results_batch1.json ({len(R)} tests)")


if __name__ == "__main__":
    main()
