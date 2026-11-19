#!/usr/bin/env python3
"""Virginia's (and Pennsylvania's) tests, re-run on California — same protocol: inputs known on the filing day, fit on
earlier sessions, score on a later one. Writes results_ca.json next to this file.

    python3 tools/calibration/ca/ca_frame.py     # once: builds .ca_frame.pkl from the pulled tables
    python3 tools/calibration/ca/ca_stats.py

Held out: A fit 2017-2021 -> score 2023-24; B fit 2017-2023 -> score 2025-26 (the session's floor work ended 31 Aug
2026; first committees long settled). Priors (room, author, tried-before) use ONLY strictly earlier sessions
(2015-16 seeds them).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ca_frame import build  # noqa: E402

R: dict = {}


def prior_rate(F, keys, target="out_first", min_n=3):
    """For each row, the target's rate among rows with the same keys in STRICTLY EARLIER sessions (NaN if < min_n)."""
    out = pd.Series(np.nan, index=F.index)
    for s in sorted(F.session.unique()):
        past = F[F.session < s]
        if past.empty:
            continue
        g = past.groupby(keys)[target].agg(["mean", "count"])
        g = g[g["count"] >= min_n]["mean"]
        cur = F[F.session == s]
        idx = pd.MultiIndex.from_frame(cur[keys]) if len(keys) > 1 else cur[keys[0]]
        out.loc[cur.index] = g.reindex(idx).values
    return out


def features(F, target="out_first"):
    X = pd.DataFrame(index=F.index)
    X["maj"] = (F.author_party == "D").astype(int)            # Democrats held both houses in every session here
    X["committee_bill"] = F.committee_bill
    X["senate"] = F.senate
    start = F.groupby("session").intro_date.transform("min")
    days = (pd.to_datetime(F.intro_date) - pd.to_datetime(start)).dt.days.fillna(0)
    X["year2"] = (days > 300).astype(int)
    X["months_in"] = (days / 30.4).clip(0, 24)
    for c in ("fiscal", "appropriation", "urgency", "vote_2_3", "local_program", "taxlevy"):
        X[c] = F[c]
    X["log_co"] = np.log1p(F.n_coauthors)
    X["bipartisan"] = (F.n_co_other_party > 0).astype(int)
    X["co_other_house"] = (F.n_co_other_house > 0).astype(int)
    F = F.assign(maj=X.maj)
    # priors are rates OF THE TARGET being scored, from strictly earlier sessions
    room = prior_rate(F, ["first_committee", "maj"], target=target)
    X["room_record"] = room.fillna(F[target].mean())
    X["room_known"] = room.notna().astype(int)
    auth = prior_rate(F, ["author_name"], target=target)
    X["author_record"] = auth.fillna(F[target].mean())
    X["author_known"] = auth.notna().astype(int)
    subj = F.subject.str.lower().str.strip()
    topic = F.subject.str.split(":").str[0].str.lower().str.strip()
    F = F.assign(subj=subj, topic=topic)
    tried = prior_rate(F, ["subj"], target=target, min_n=1)
    X["tried_before"] = tried.notna().astype(int)
    X["tried_record"] = tried.fillna(0.0)
    tp = prior_rate(F, ["topic", "maj"], target=target, min_n=10)
    X["topic_record"] = tp.fillna(F[target].mean())
    X["topic_known"] = tp.notna().astype(int)
    # the author's filing volume TO DATE this session (known at filing), and tenure (sessions seen before)
    F = F.assign(_d=pd.to_datetime(F.intro_date))
    X["filed_to_date"] = np.log1p(F.sort_values("_d").groupby(["session", "author_name"]).cumcount()).reindex(F.index)
    first_seen = F.groupby("author_name").session.transform("min")
    X["tenure"] = ((F.session - first_seen) / 2).clip(0, 6)
    return X


GROUPS = {"standing": ["maj", "committee_bill"], "timing": ["year2", "months_in"],
          "fiscal flags": ["fiscal", "appropriation", "urgency", "vote_2_3", "local_program", "taxlevy"],
          "co-authors": ["log_co", "bipartisan", "co_other_house"], "room record": ["room_record", "room_known"],
          "author record": ["author_record", "author_known"], "tried before": ["tried_before", "tried_record"],
          "topic record": ["topic_record", "topic_known"], "author volume + tenure": ["filed_to_date", "tenure"]}


def fit_score(X, y, tr, te, cols):
    m = LogisticRegression(max_iter=2000, C=1.0)
    m.fit(X.loc[tr, cols], y[tr])
    p = m.predict_proba(X.loc[te, cols])[:, 1]
    return p, m


def bill_fate(F):
    F = F[F.referred == 1].copy()
    out = {}
    for target in ("out_first", "law"):
        X = features(F, target)
        y = F[target].values
        yy = pd.Series(y, index=F.index)
        res = {}
        for name, train, test in (("A_2023", [2017, 2019, 2021], 2023), ("B_2025", [2017, 2019, 2021, 2023], 2025)):
            tr = F.session.isin(train).values
            te = (F.session == test).values
            base_key = X.maj.astype(str) + X.committee_bill.astype(str) + X.senate.astype(str) + X.year2.astype(str)
            base_rate = yy[tr].groupby(base_key[tr]).mean()
            pb = base_key[te].map(base_rate).fillna(yy[tr].mean()).values
            cols = [c for g in GROUPS.values() for c in g]
            p, m = fit_score(X, y, tr, te, cols)
            drops = {}
            for g, gc in GROUPS.items():
                keep = [c for c in cols if c not in gc]
                pd_, _ = fit_score(X, y, tr, te, keep)
                drops[g] = round(roc_auc_score(y[te], p) - roc_auc_score(y[te], pd_), 4)
            from sklearn.ensemble import HistGradientBoostingClassifier
            gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, random_state=0)
            gb.fit(X.loc[tr, cols], y[tr])
            pt = gb.predict_proba(X.loc[te, cols])[:, 1]
            dec = pd.qcut(p, 10, labels=False, duplicates="drop")
            calib = [[round(float(p[dec == d].mean()), 3), round(float(y[te][dec == d].mean()), 3)] for d in sorted(set(dec))]
            res[name] = {"n_test": int(te.sum()), "base_rate": round(float(y[te].mean()), 3),
                         "baseline_auc": round(roc_auc_score(y[te], pb), 3),
                         "model_auc": round(roc_auc_score(y[te], p), 3),
                         "trees_auc": round(roc_auc_score(y[te], pt), 3),
                         "model_log_loss": round(log_loss(y[te], np.clip(p, 1e-6, 1 - 1e-6)), 3),
                         "baseline_log_loss": round(log_loss(y[te], np.clip(pb, 1e-6, 1 - 1e-6)), 3),
                         "auc_lost_without": drops, "calibration_deciles_pred_vs_actual": calib,
                         "coef": {c: round(float(v), 3) for c, v in zip(cols, m.coef_[0])}}
        out[target] = res
    R["bill_fate"] = out


def kill_points(F):
    res = {}
    for s in (2023, 2025):
        d = F[F.session == s]
        n = len(d)
        def share(mask):
            return [int(mask.sum()), round(float(mask.mean()), 3)]
        appro = d.last_committee.str.contains("Appropriations", na=False)
        died = (d.law == 0) & (d.status != "Vetoed")
        origin_side = d.last_committee_house.fillna("") == d.origin
        res[s] = {
            "bills": n,
            "became_law": share(d.law == 1),
            "vetoed": share(d.status == "Vetoed"),
            "never_referred": share(died & (d.referred == 0)),
            "first_policy_committee": share(died & (d.referred == 1) & (d.out_first == 0)),
            "origin_appropriations": share(died & (d.out_first == 1) & appro & origin_side),
            "origin_other_after_first": share(died & (d.out_first == 1) & ~appro & origin_side),
            "second_house_appropriations": share(died & appro & ~origin_side & (d.last_committee != "")),
            "second_house_other": share(died & ~appro & ~origin_side & (d.last_committee != "")),
        }
        res[s]["unplaced"] = n - sum(v[0] for k, v in res[s].items() if isinstance(v, list))
    R["kill_points"] = res


def room_memory(F):
    F = F[F.referred == 1].copy()
    F["subj"] = F.subject.str.lower().str.strip()
    rows = []
    for s in (2017, 2019, 2021, 2023, 2025):
        past = F[F.session < s].groupby("subj").out_first.agg(["min", "max"])
        cur = F[F.session == s]
        died_before = cur.subj.map(past["max"]).eq(0)
        passed_before = cur.subj.map(past["min"]).eq(1)
        rows.append((s, cur.out_first[died_before].mean(), int(died_before.sum()), cur.out_first[passed_before].mean(),
                     int(passed_before.sum()), cur.out_first[~died_before & ~passed_before].mean()))
    t = pd.DataFrame(rows, columns=["session", "out_if_died_before", "n_died_before", "out_if_passed_before",
                                    "n_passed_before", "out_if_new"])
    a = t.n_died_before.sum()
    dies_again = 1 - (t.out_if_died_before * t.n_died_before).sum() / a
    base_die = 1 - F[F.session >= 2017].out_first.mean()
    R["room_memory"] = {"by_session": t.round(3).to_dict("records"),
                        "dies_again_if_died_before": round(float(dies_again), 3), "n": int(a),
                        "die_rate_all": round(float(base_die), 3),
                        "odds_ratio": round(float((dies_again / (1 - dies_again)) / (base_die / (1 - base_die))), 2)}


def author_effect(F):
    F = F[(F.referred == 1) & (F.committee_bill == 0)].copy()
    res = {}
    for s in (2021, 2023, 2025):
        d = F[F.session == s].sort_values("bill")
        d["half"] = np.arange(len(d)) % 2
        g = d.groupby(["author_name", "half"]).out_first.mean().unstack().dropna()
        n = d.groupby("author_name").size()
        g = g[n.reindex(g.index) >= 10]
        res[f"split_half_r_{s}"] = round(float(g[0].corr(g[1])), 3)
        res[f"authors_{s}"] = int(len(g))
    a = F.groupby(["session", "author_name"]).out_first.agg(["mean", "count"])
    a = a[a["count"] >= 8]["mean"].unstack(0)
    res["session_to_session_r_2021_2023"] = round(float(a[2021].corr(a[2023])), 3)
    res["session_to_session_r_2023_2025"] = round(float(a[2023].corr(a[2025])), 3)
    lift = F.groupby(["session", "author_name"]).out_first.mean() - F.groupby("session").out_first.transform("mean").groupby([F.session, F.author_name]).first()
    res["author_lift_sd_pts"] = round(float(lift.groupby(level=0).std().mean() * 100), 1)
    R["author_effect"] = res


def committee_seat(F, V):
    """Author sits on the first committee (a member who voted there that session) — the room you sit in."""
    mem = V[V["loc"].str.startswith(("CX", "CS"))].groupby(["session", "loc"]).member.apply(set)
    F = F[(F.referred == 1) & (F.committee_bill == 0)].copy()
    F["seat"] = [int(r.author_name in mem.get((r.session, r.first_code), set())) for r in F.itertuples()]
    res = {}
    for maj in (1, 0):
        d = F[(F.author_party == "D") == bool(maj)]
        res["majority" if maj else "minority"] = {
            "out_with_seat": round(float(d[d.seat == 1].out_first.mean()), 3), "n_seat": int(d.seat.sum()),
            "out_without_seat": round(float(d[d.seat == 0].out_first.mean()), 3), "n_without": int((d.seat == 0).sum())}
    w = F.groupby(["session", "author_name"]).filter(lambda g: g.seat.nunique() == 2)
    within = w.groupby(["session", "author_name", "seat"]).out_first.mean().unstack()
    diff = within[1] - within[0]
    res["within_author_pts"] = round(float(diff.mean() * 100), 1)
    res["within_author_better_worse"] = [int((diff > 0).sum()), int((diff < 0).sum())]
    R["committee_seat"] = res


def member_votes(F, V):
    """First committee roll call on each bill: who votes AYE? Baseline: everyone votes yes."""
    Fi = F.set_index("bill")
    V = V[V.bill.isin(Fi.index)].copy()
    V["first_code"] = V.bill.map(Fi.first_code)
    V["author_party"] = V.bill.map(Fi.author_party)
    c = V[V["loc"] == V.first_code]
    first = c.groupby("bill").seq.transform("min")
    c = c[c.seq == first].copy()
    c["aye"] = (c.vote == "AYE").astype(int)
    c["noe"] = (c.vote == "NOE").astype(int)
    c["same_party"] = (c.mparty == c.author_party).astype(int)
    c["m_rep"] = (c.mparty == "R").astype(int)
    c["a_rep"] = (c.author_party == "R").astype(int)
    c["a_committee"] = (c.author_party == "").astype(int)
    for k, col in (("member_aye_record", ["member"]), ("member_party_pair", ["member", "a_rep"]),
                   ("room_aye_record", ["loc", "m_rep", "a_rep"])):
        c[k] = prior_rate(c.assign(out_first=c.aye), col, target="out_first", min_n=5)
        c[k + "_known"] = c[k].notna().astype(int)
        c[k] = c[k].fillna(c.aye.mean())
    for b in ("fiscal", "urgency", "vote_2_3", "appropriation"):
        c[b] = c.bill.map(Fi[b])
    c["topic"] = c.bill.map(Fi.subject.str.split(":").str[0].str.lower().str.strip())
    c["topic_party_aye"] = prior_rate(c.assign(out_first=c.aye), ["topic", "m_rep", "a_rep"], target="out_first", min_n=10)
    c["topic_party_known"] = c.topic_party_aye.notna().astype(int)
    c["topic_party_aye"] = c.topic_party_aye.fillna(c.aye.mean())
    cols = ["topic_party_aye", "topic_party_known", "same_party", "m_rep", "a_rep", "a_committee", "member_aye_record", "member_aye_record_known",
            "member_party_pair", "member_party_pair_known", "room_aye_record", "room_aye_record_known",
            "fiscal", "urgency", "vote_2_3", "appropriation"]
    c["m_rep_x_a_dem"] = c.m_rep * (1 - c.a_rep - c.a_committee)
    cols.append("m_rep_x_a_dem")
    res = {}
    for name, train, test in (("A_2023", [2017, 2019, 2021], 2023), ("B_2025", [2017, 2019, 2021, 2023], 2025)):
        tr = c.session.isin(train).values
        te = (c.session == test).values
        m = LogisticRegression(max_iter=3000).fit(c.loc[tr, cols], c.aye[tr])
        p = m.predict_proba(c.loc[te, cols])[:, 1]
        y = c.aye.values[te]
        cross = te & (c.same_party.values == 0) & (c.a_committee.values == 0)
        pc = m.predict_proba(c.loc[cross, cols])[:, 1]
        yc = c.aye.values[cross]
        conf = (p < 0.2) | (p > 0.8)
        res[name] = {"member_votes": int(te.sum()), "aye_rate": round(float(y.mean()), 3),
                     "always_yes_accuracy": round(float(y.mean()), 3),
                     "model_accuracy": round(float(((p > 0.5) == y).mean()), 3),
                     "model_auc": round(roc_auc_score(y, p), 3),
                     "crossover_votes": int(cross.sum()), "crossover_aye_rate": round(float(yc.mean()), 3),
                     "crossover_auc": round(roc_auc_score(yc, pc), 3),
                     "confident_share": round(float(conf.mean()), 3),
                     "confident_accuracy": round(float(((p[conf] > 0.5) == y[conf]).mean()), 3)}
    R["member_votes_first_committee"] = res


def party_position(F, V):
    """Floor votes: does the Republican caucus (minority) vote mostly NO on a Democrat-authored bill?"""
    Fi = F.set_index("bill")
    fl = V[V["loc"].isin(["AFLOOR", "SFLOOR"]) & V.bill.isin(Fi.index)].copy()
    last = fl.groupby(["bill", "loc"]).seq.transform("max")
    fl = fl[fl.seq == last]
    g = fl.groupby(["session", "bill", "loc", "mparty"]).vote.apply(lambda v: (v == "AYE").mean()).unstack()
    g = g.dropna(subset=["R", "D"]).reset_index()
    g["author_party"] = g.bill.map(Fi.author_party)
    g = g[g.author_party == "D"].copy()
    g["r_no"] = (g["R"] < 0.5).astype(int)
    for b in ("fiscal", "urgency", "vote_2_3", "appropriation", "taxlevy", "local_program", "n_co_other_party"):
        g[b] = g.bill.map(Fi[b])
    g["bipartisan"] = (g.n_co_other_party > 0).astype(int)
    g["senate_floor"] = (g["loc"] == "SFLOOR").astype(int)
    Fi2 = F.assign(subj=F.subject.str.split(":").str[0].str.lower().str.strip())
    g["topic"] = g.bill.map(Fi2.set_index("bill").subj)
    com = V[V["loc"].str.startswith(("CX", "CS")) & (V.mparty == "R")]
    floor_when = fl.groupby(["bill", "loc"]).when.max()
    g["floor_when"] = [floor_when.get((b, l), "") for b, l in zip(g.bill, g["loc"])]
    cw = com.groupby("bill")
    rc = []
    for b, w in zip(g.bill, g.floor_when):
        if b in cw.groups:
            x = cw.get_group(b)
            x = x[x.when < w]
            rc.append((x.vote == "AYE").mean() if len(x) else np.nan)
        else:
            rc.append(np.nan)
    g["r_committee_aye"] = rc
    g["r_committee_known"] = g.r_committee_aye.notna().astype(int)
    g["r_committee_aye"] = g.r_committee_aye.fillna(0.5)
    g["topic_r_no"] = prior_rate(g.rename(columns={"r_no": "out_first"}), ["topic"], min_n=5)
    g["topic_known"] = g.topic_r_no.notna().astype(int)
    g["topic_r_no"] = g.topic_r_no.fillna(g.r_no.mean())
    filing_cols = ["fiscal", "urgency", "vote_2_3", "appropriation", "taxlevy", "local_program", "bipartisan",
                   "senate_floor", "topic_r_no", "topic_known"]
    res = {}
    for name, train, test in (("A_2023", [2017, 2019, 2021], 2023), ("B_2025", [2017, 2019, 2021, 2023], 2025)):
        tr = g.session.isin(train).values
        te = (g.session == test).values
        m = LogisticRegression(max_iter=2000).fit(g.loc[tr, filing_cols], g.r_no[tr])
        p = m.predict_proba(g.loc[te, filing_cols])[:, 1]
        res[name + "_filing_facts_only"] = {"auc": round(roc_auc_score(g.r_no[te], p), 3)}
    cols = filing_cols + ["r_committee_aye", "r_committee_known"]
    for name, train, test in (("A_2023", [2017, 2019, 2021], 2023), ("B_2025", [2017, 2019, 2021, 2023], 2025)):
        tr = g.session.isin(train).values
        te = (g.session == test).values
        m = LogisticRegression(max_iter=2000).fit(g.loc[tr, cols], g.r_no[tr])
        p = m.predict_proba(g.loc[te, cols])[:, 1]
        res[name] = {"floor_votes": int(te.sum()), "r_caucus_no_rate": round(float(g.r_no[te].mean()), 3),
                     "auc": round(roc_auc_score(g.r_no[te], p), 3)}
    R["party_position"] = res


def stage_two(F, V):
    """The model UPDATED at the second gate: once a bill is out of its first committee, does the first committee's
    roll call (known by then) predict whether it becomes law? Same held-out protocol."""
    Fi = F.set_index("bill")
    c = V[V.bill.isin(Fi.index)].copy()
    c = c[c["loc"] == c.bill.map(Fi.first_code)]
    c = c[c.seq == c.groupby("bill").seq.transform("min")]
    agg = c.assign(aye=(c.vote == "AYE"), noe=(c.vote == "NOE"), r=(c.mparty == "R"), d=(c.mparty == "D"))
    roll = pd.DataFrame({
        "noes": agg.groupby("bill").noe.sum(),
        "r_aye": agg[agg.r].groupby("bill").aye.mean(),
        "d_noe": agg[agg.d].groupby("bill").noe.sum(),
        "abs_share": agg.groupby("bill").vote.apply(lambda v: (v == "ABS").mean())})
    G = F[(F.referred == 1) & (F.out_first == 1)].copy()
    X = features(G, "law")
    r = roll.reindex(G.bill)
    r.index = G.index
    X["noes"] = np.log1p(r.noes.fillna(0))
    X["r_aye"] = r.r_aye.fillna(0.5)
    X["d_noe"] = (r.d_noe.fillna(0) > 0).astype(int)
    X["abs_share"] = r.abs_share.fillna(0)
    X["roll_known"] = r.noes.notna().astype(int)
    base = [c for g in GROUPS.values() for c in g]
    roll_cols = ["noes", "r_aye", "d_noe", "abs_share", "roll_known"]
    y = G.law.values
    res = {}
    for name, train, test in (("A_2023", [2017, 2019, 2021], 2023), ("B_2025", [2017, 2019, 2021, 2023], 2025)):
        tr = G.session.isin(train).values
        te = (G.session == test).values
        p0, _ = fit_score(X, y, tr, te, base)
        p1, _ = fit_score(X, y, tr, te, base + roll_cols)
        res[name] = {"n_test": int(te.sum()), "law_rate": round(float(y[te].mean()), 3),
                     "filing_facts_auc": round(roc_auc_score(y[te], p0), 3),
                     "plus_first_committee_roll_call_auc": round(roc_auc_score(y[te], p1), 3)}
    R["stage_two_law_after_first_committee"] = res


def clock(F):
    d = F[(F.status == "Died")]
    m = pd.to_datetime(d.last_date).dt.strftime("%m-%d")
    top = m.value_counts().head(6)
    R["clock"] = {"died": int(len(d)), "top_death_dates_mm_dd": {k: int(v) for k, v in top.items()},
                  "share_on_top_3_dates": round(float(top.head(3).sum() / len(d)), 3)}


if __name__ == "__main__":
    F, V = build()
    F = F[F.session >= 2015]
    bill_fate(F)
    kill_points(F)
    room_memory(F)
    author_effect(F)
    committee_seat(F, V)
    member_votes(F, V)
    party_position(F, V)
    stage_two(F, V)
    clock(F)
    json.dump(R, open(os.path.join(HERE, "results_ca.json"), "w"), indent=1, default=str)
    print(json.dumps(R, indent=1, default=str)[:6000])
