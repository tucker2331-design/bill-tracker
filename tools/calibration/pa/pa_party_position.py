#!/usr/bin/env python3
"""Predicting each PARTY's position on a roll call — the wall under every member-vote model (owner 2026-11-18:
"if the wall is predicting the party's position, start thinking about how we could predict it and run tests").

Target, per roll call: did the majority of the party OPPOSITE the sponsor vote yes? (The sponsor's party votes yes on
its own bills almost always — measured below.) Every input is knowable before the roll call (replayed by date):

  standing      sponsor in the voting chamber's majority; committee vs floor; first vs second chamber; motion kind
  cosponsors    how many, how many from the other party (PA lists final co-sponsors, undated — flagged)
  sponsor       the other party's record on this sponsor's earlier contested roll calls
  law           the other party's record on earlier roll calls for bills amending the same law (title's statute)
  room          the other party's record in this committee / on this floor
  title words   a word model on the bill title, fit on earlier sessions only (out-of-fold inside training)
  companion     the other party's side on the same-title bill's earlier roll call in the other chamber
  same bill     the other party's side on THIS bill's earlier roll calls (later votes only)
  reading       a reader's rating of the title (pilot file, if present: reading_pilot.json)

Held out: fit 2017-2021 -> score 2023-24; fit 2017-2023 -> score 2025-26.
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pa_batch3 as B3  # noqa: E402
from pa_drafting import law_key  # noqa: E402
from pa_frame import frame  # noqa: E402

STOP = r"(?u)\b[a-z][a-z]+\b"
BOILER = re.compile(r"an act amending|of the pennsylvania consolidated statutes|act of [a-z]+ \d+, \d{4} \(p\.l\.[^)]*\)|"
                    r"known as the|further providing for|providing for|in general provisions|and making|repealing", re.I)


def rollcalls():
    F = frame()
    E, B, _u = B3.load(F)
    X = B3.per_event(E, B, F)
    bills = F.assign(bill=F.body.map({"H": "HB", "S": "SB"}) + " " + F.number.astype(str),
                     law=F.title.map(law_key).fillna("(none)"))
    keep = ["session", "bill", "body", "p_party", "p_key", "in_maj", "n_cosp", "n_other_party_cosp", "n_maj_cosp", "title", "tkey", "law", "cmte", "cosp_keys"]
    R = X.reset_index().merge(bills[keep], on=["session", "bill"], how="inner")
    R = R[R.p_party.isin(["D", "R"]) & R.date.astype(bool)]
    R["date"] = pd.to_datetime(R.date, errors="coerce")
    R = R[R.date.notna()].copy()
    R["other"] = np.where(R.p_party == "D", "R", "D")
    R["other_side"] = [r[f"{o}_side"] for (_i, r), o in zip(R.iterrows(), R.other)]
    R["own_side"] = [r[f"{p}_side"] for (_i, r), p in zip(R.iterrows(), R.p_party)]
    R = R[R.other_side.notna()].copy()
    R["y"] = R.other_side.astype(float).astype(int)
    vmaj = {(s, b): m for s, b, m in zip(F.session, F.body, F.majority)}
    R["sp_maj_here"] = [int(vmaj.get((s, c)) == p) for s, c, p in zip(R.session, R.chamber, R.p_party)]
    R["committee_vote"] = R.committee.astype(int)
    R["own_body"] = (R.chamber == R.body).astype(int)
    R["kind"] = R.motion.map(B3.motion_kind)
    for k, _ in B3.MOTION + [("other", "")]:
        R["m_" + k] = (R.kind == k).astype(int)
    R["room"] = np.where(R.committee, R.org.str.upper(), "FLOOR-" + R.chamber)
    R["contested"] = ((R.no / (R.yes + R.no)) >= 0.10).astype(int)
    R["other_cosp_share"] = R.n_other_party_cosp / R.n_cosp.where(R.n_cosp > 0, 1)
    R["any_other_cosp"] = (R.n_other_party_cosp > 0).astype(int)
    R = R.sort_values("date").reset_index(drop=True)
    R["_i"] = np.arange(len(R))
    R["first"] = (~R.duplicated(["session", "bill", "chamber"])).astype(int)
    return F, R


def add_priors(R):
    Rc = R[R.contested == 1]
    R = B3.prior(R, R, ["other", "p_key"], "y", "oth_on_sponsor")
    R = B3.prior(Rc, R, ["other", "p_key"], "y", "oth_on_sponsor_contested")
    R = B3.prior(R, R, ["other", "law"], "y", "oth_on_law")
    R = B3.prior(Rc, R, ["other", "law"], "y", "oth_on_law_contested")
    R = B3.prior(R, R, ["other", "room"], "y", "oth_in_room")
    R = B3.prior(R, R, ["other", "sp_maj_here", "room"], "y", "oth_in_room_by_standing")
    R = B3.prior(R, R, ["other", "cmte"], "y", "oth_on_first_committee")
    # same bill, earlier roll calls (any chamber)
    R = B3.prior(R, R, ["session", "bill"], "y", "oth_same_bill", alpha=1.0)
    # companion: same title, other chamber, earlier dates
    R["twin_key"] = R.session + "|" + R.tkey + "|" + np.where(R.body == "H", "S", "H")
    R["self_key"] = R.session + "|" + R.tkey + "|" + R.body
    T = R[["self_key", "date", "y"]].rename(columns={"self_key": "twin_key"})
    g = T.groupby(["twin_key", "date"]).y.agg(["sum", "count"]).reset_index().sort_values("date")
    g[["cs", "cn"]] = g.groupby("twin_key")[["sum", "count"]].cumsum()
    M = pd.merge_asof(R[["twin_key", "date", "_i"]].sort_values("date"), g[["twin_key", "date", "cs", "cn"]], on="date", by="twin_key", allow_exact_matches=False)
    M = M.set_index("_i").reindex(R["_i"])
    has = M.cn.fillna(0).to_numpy() > 0
    R["twin_seen"] = has.astype(int)
    R["twin_oth_yes"] = np.where(has, M.cs.to_numpy() / np.maximum(M.cn.fillna(1).to_numpy(), 1), 0.5)
    return R


def add_moderation(R, F):
    """Sponsor and co-sponsor moderation = their defection rate on contested roll calls in the PREVIOUS session
    (no same-session information). Minority/other-party chair co-signing uses the 2025-26 roster only."""
    E, B, _u = B3.load(F)
    X = B3.per_event(E, B, F)
    _d, yn = B3.t_defection(B, X)
    yn = yn.merge(X[["session", "yes", "no"]].rename(columns={"session": "s2"}), left_on="eid", right_index=True)
    yn = yn[(yn.no / (yn.yes + yn.no)) >= 0.10]
    prev = {s: t for s, t in zip(["2019_0", "2021_0", "2023_0", "2025_0"], ["2017_0", "2019_0", "2021_0", "2023_0"])}
    rate = yn.groupby(["session", "who"]).defect.mean()
    def mod(session, who):
        ps = prev.get(session)
        return rate.get((ps, who), np.nan) if ps else np.nan
    idx, _bs = B3.roll_index(F)
    sp_mod, oc_mod, oc_max, oc_n = [], [], [], []
    for s_, body, pk, ck, pp in zip(R.session, R.body, R.p_key, R.cosp_keys, R.p_party):
        sp_mod.append(mod(s_, f"{body}|{B3.norm(pk.split('|', 1)[1])}"))
        vals = []
        for k in ck:
            b2, sur = k.split("|", 1)
            nk = B3.norm(sur)
            party = idx.get((s_, b2), {}).get(nk, (None, None))[1]
            if party and party != pp:
                vals.append(mod(s_, f"{b2}|{nk}"))
        v = [x for x in vals if x == x]
        oc_mod.append(np.mean(v) if v else np.nan); oc_max.append(np.max(v) if v else np.nan); oc_n.append(len(vals))
    R["sponsor_moderation"] = sp_mod
    R["sponsor_moderation_known"] = R.sponsor_moderation.notna().astype(int)
    R["sponsor_moderation"] = R.sponsor_moderation.fillna(R.sponsor_moderation.median())
    R["oth_cosp_moderation_mean"] = pd.Series(oc_mod).fillna(-1).to_numpy()
    R["oth_cosp_moderation_max"] = pd.Series(oc_max).fillna(-1).to_numpy()
    return R


def title_text(t):
    return BOILER.sub(" ", (t or "").lower())


def title_scores(R, tr_mask, te_mask):
    """Out-of-fold (by session) title-word scores for training rows; a fit on all training rows for test rows."""
    txt = R.title.map(title_text)
    s = pd.Series(np.nan, index=R.index)
    sess = sorted(R.session[tr_mask].unique())
    for hold in sess:
        fit = tr_mask & (R.session != hold)
        app = tr_mask & (R.session == hold)
        vec = TfidfVectorizer(token_pattern=STOP, ngram_range=(1, 2), min_df=3, sublinear_tf=True)
        Xf = vec.fit_transform(txt[fit])
        m = LogisticRegression(max_iter=3000, C=1.0).fit(Xf, R.y[fit])
        s[app] = m.predict_proba(vec.transform(txt[app]))[:, 1]
    vec = TfidfVectorizer(token_pattern=STOP, ngram_range=(1, 2), min_df=3, sublinear_tf=True)
    m = LogisticRegression(max_iter=3000, C=1.0).fit(vec.fit_transform(txt[tr_mask]), R.y[tr_mask])
    s[te_mask] = m.predict_proba(vec.transform(txt[te_mask]))[:, 1]
    # the words that most push the other party to NO / YES (for reading)
    names = np.array(vec.get_feature_names_out())
    co = m.coef_[0]
    return s, {"toward_no": names[np.argsort(co)[:15]].tolist(), "toward_yes": names[np.argsort(-co)[:15]].tolist()}


GROUPS = {
    "standing": ["sp_maj_here", "committee_vote", "own_body"],
    "motion": None,                       # filled with m_* columns
    "cosponsors (undated)": ["n_cosp", "n_other_party_cosp", "other_cosp_share", "any_other_cosp"],
    "sponsor record": ["oth_on_sponsor", "oth_on_sponsor_n", "oth_on_sponsor_contested", "oth_on_sponsor_contested_n"],
    "law record": ["oth_on_law", "oth_on_law_n", "oth_on_law_contested", "oth_on_law_contested_n"],
    "room record": ["oth_in_room", "oth_in_room_n", "oth_in_room_by_standing", "oth_in_room_by_standing_n", "oth_on_first_committee", "oth_on_first_committee_n"],
    "title words": ["title_score"],
    "companion's earlier vote": ["twin_seen", "twin_oth_yes"],
    "moderation (sponsor, other-party co-sponsors)": ["sponsor_moderation", "sponsor_moderation_known", "oth_cosp_moderation_mean", "oth_cosp_moderation_max"],
}


def evaluate(R, label, until, test, reading=None):
    tr, te = (R.session <= until).to_numpy(), (R.session == test).to_numpy()
    R = R.copy()
    R["title_score"], words = title_scores(R, pd.Series(tr, index=R.index), pd.Series(te, index=R.index))
    GROUPS["motion"] = [c for c in R.columns if c.startswith("m_")]
    allc = [c for g in GROUPS.values() for c in g]
    out = {"label": label, "words": words}
    for subset, mask in {"first roll call in each chamber": R["first"].to_numpy() == 1, "every roll call (+ same bill's earlier votes)": np.ones(len(R), bool)}.items():
        cols = allc + (["oth_same_bill", "oth_same_bill_n"] if "every" in subset else [])
        trm, tem = tr & mask, te & mask
        y = R.y.to_numpy()
        yt = y[tem]
        cont = R.contested.to_numpy()[tem] == 1
        res = {"roll_calls": int(tem.sum()), "other_party_yes_rate": round(100 * yt.mean(), 1),
               "sponsor_party_yes_rate": round(100 * R.own_side.astype(float).to_numpy()[tem].mean(), 1),
               "contested_share": round(100 * cont.mean(), 1)}
        mk = lambda: HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_depth=5, l2_regularization=1.0, random_state=0)
        m = mk().fit(R.loc[trm, cols], y[trm])
        p = m.predict_proba(R.loc[tem, cols])[:, 1]
        res["all_inputs"] = {"accuracy": round(100 * ((p >= 0.5) == yt).mean(), 1), "auc": round(roc_auc_score(yt, p), 3),
                             "accuracy_contested": round(100 * ((p >= 0.5) == yt)[cont].mean(), 1),
                             "auc_contested": round(roc_auc_score(yt[cont], p[cont]), 3) if len(set(yt[cont])) == 2 else None}
        base_auc = res["all_inputs"]["auc"]
        res["auc_lost_without"] = {}
        res["auc_alone"] = {}
        for g, gc in GROUPS.items():
            keep = [c for c in cols if c not in gc]
            pm = mk().fit(R.loc[trm, keep], y[trm]).predict_proba(R.loc[tem, keep])[:, 1]
            res["auc_lost_without"][g] = round(base_auc - roc_auc_score(yt, pm), 3)
            pa = mk().fit(R.loc[trm, gc], y[trm]).predict_proba(R.loc[tem, gc])[:, 1]
            res["auc_alone"][g] = round(roc_auc_score(yt, pa), 3)
        out[subset] = res
        if "first" in subset:
            R.loc[tem, "pred_first"] = p
    return out, R


def main():
    F, R = rollcalls()
    R = add_priors(R)
    R = add_moderation(R, F)
    res = {"method": __doc__.split("\n\n")[1].strip(), "roll_calls": int(len(R))}
    keep_pred = {}
    for label, (until, test) in {"2023-24": ("2021_0", "2023_0"), "2025-26": ("2023_0", "2025_0")}.items():
        o, Rp = evaluate(R, label, until, test)
        res[label] = o
        keep_pred[label] = Rp.loc[(Rp.session == test) & (Rp["first"] == 1), ["session", "bill", "chamber", "eid", "y", "pred_first", "title", "p_party", "contested", "committee_vote"]]
    with open(os.path.join(HERE, "results_party_position.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    pd.concat(keep_pred.values()).to_pickle(os.path.join(HERE, ".party_position_preds.pkl"))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
