#!/usr/bin/env python3
"""PA bill fate, round 2: how close can PA get to Virginia's locked 0.80, and what moves it?
(owner 2026-11-18: "tell me how the model compares to VA and how we should proceed to boost its accuracy").

Outcome: got out of the first committee. Held out: A fit 2009-2021 -> score 2023-24; B fit 2009-2023 -> score
2025-26 (first committee essentially settled). Every feature is knowable on the day of filing:
  * nothing that counts a session's future (patron_volume and cmte_load are replaced by counts TO DATE);
  * a twin counts only if the other chamber's twin was filed on or before this bill;
  * co-sponsor features are a SEPARATE, labelled arm (PA lists final co-sponsors, undated — leakage risk).
Ladder: baseline (standing x chamber x year) -> logistic on clean features -> boosted trees on clean features ->
+ co-sponsor arm (timing unverified).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pa_frame import frame, prior_rate  # noqa: E402
from pa_element_value import tried_before  # noqa: E402
from pa_drafting import law_key  # noqa: E402


def features(F):
    X = pd.DataFrame(index=F.index)
    X["in_maj"] = F.in_maj
    X["senate"] = (F.body == "S").astype(int)
    X["months_in"] = (F.days_in.fillna(0) / 30.4).clip(0, 24)
    X["last6"] = (F.days_in.fillna(0) >= 545).astype(int)
    room = prior_rate(F, ["body", "cmte", "in_maj"])
    X["room_record"] = room.fillna(F.out.mean()); X["room_known"] = room.notna().astype(int)
    p, sr, sc = tried_before(F)
    for k, m in {"died_same": (p == "died") & (sr == 1), "cleared_same": (p == "cleared") & (sr == 1),
                 "died_other": (p == "died") & (sr == 0), "cleared_other": (p == "cleared") & (sr == 0),
                 "same_carrier_refile": (p != "none") & (sc == 1)}.items():
        X["tried_" + k] = m.astype(int)
    car = prior_rate(F, ["p_key"])
    X["carrier_record"] = car.fillna(F.out.mean()); X["carrier_known"] = car.notna().astype(int)
    carroom = prior_rate(F, ["p_key", "cmte"])
    X["carrier_room_record"] = carroom.fillna(F.out.mean()); X["carrier_room_known"] = carroom.notna().astype(int)
    X["tenure"] = F.tenure.clip(0, 8)
    X["bill_rank"] = np.log1p(F.patron_bill_rank)
    X["cmte_load_to_date"] = np.log1p(F.groupby(["session", "cmte"]).cumcount())
    X["locality"] = F.names_locality
    X["amend"] = (F.title_form == "amend").astype(int)
    X["money_cmte"] = F.money_cmte
    X["no_cmte"] = (F.cmte == "(none)").astype(int)
    # twin filed on or before this bill (knowable at filing)
    first = {}
    for s, b, t, d in zip(F.session, F.body, F.tkey, F.intro):
        if t:
            k = (s, b, t)
            if k not in first or (pd.notna(d) and d < first[k]):
                first[k] = d
    X["twin_before"] = [int(bool(t) and (s, {"H": "S", "S": "H"}[b], t) in first and pd.notna(d)
                            and pd.notna(first[(s, {"H": "S", "S": "H"}[b], t)]) and first[(s, {"H": "S", "S": "H"}[b], t)] <= d)
                        for s, b, t, d in zip(F.session, F.body, F.tkey, F.intro)]
    # law's usual room share (from earlier sessions only)
    law = F.title.map(law_key)
    usual = pd.Series(np.nan, index=F.index)
    for s in sorted(F.session.unique()):
        past = F[(F.session < s) & law.notna() & (F.cmte != "(none)")]
        if past.empty:
            continue
        tab = past.assign(law=law[past.index]).groupby(["body", "law"]).cmte.agg(lambda x: x.value_counts().index[0])
        idx = F.index[(F.session == s) & law.notna()]
        usual.loc[idx] = [int(tab.get((b, l)) == c) if (b, l) in tab.index else np.nan for b, l, c in zip(F.loc[idx, "body"], law[idx], F.loc[idx, "cmte"])]
    X["in_usual_room"] = usual.fillna(0.5)
    # co-sponsor arm (timing unverified)
    C = pd.DataFrame(index=F.index)
    C["log_cosp"] = np.log1p(F.n_cosp); C["bipartisan"] = F.bipartisan
    C["maj_cosp_share"] = F.maj_cosp_share.where(F.n_cosp > 0, 0); C["cross_chamber_cosp"] = (F.n_cross_chamber_cosp > 0).astype(int)
    return X, C


def score(y, p):
    return {"auc": round(roc_auc_score(y, p), 3), "log_loss": round(log_loss(y, p), 4), "brier": round(brier_score_loss(y, p), 4)}


def main():
    F = frame().reset_index(drop=True)
    X, C = features(F)
    y = F.out
    res = {"method": __doc__.split("\n\n")[1].strip(), "virginia_locked_2026": {"model_auc": 0.80, "baseline_auc": 0.68}, "held_out": {}}
    for label, (until, test) in {"A: 2023-24": ("2021_0", "2023_0"), "B: 2025-26": ("2023_0", "2025_0")}.items():
        tr, te = F.session <= until, F.session == test
        rates = F[tr].groupby(["in_maj", "body", "second_year"]).out.mean()
        base = F.set_index(["in_maj", "body", "second_year"]).index.map(rates).to_numpy(dtype=float)
        base = np.where(np.isnan(base), F[tr].out.mean(), base)
        out = {"bills": int(te.sum()), "baseline": score(y[te], base[te.to_numpy()])}
        lr = LogisticRegression(max_iter=4000, C=1.0).fit(X[tr], y[tr])
        out["logistic_clean"] = score(y[te], lr.predict_proba(X[te])[:, 1])
        gb = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                            random_state=0).fit(X[tr], y[tr])
        pg = gb.predict_proba(X[te])[:, 1]
        out["trees_clean"] = score(y[te], pg)
        XC = pd.concat([X, C], axis=1)
        gb2 = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                             random_state=0).fit(XC[tr], y[tr])
        out["trees_plus_cosponsors_timing_unverified"] = score(y[te], gb2.predict_proba(XC[te])[:, 1])
        # calibration of the clean trees: predicted vs actual by decile
        d = pd.DataFrame({"p": pg, "y": y[te].to_numpy()})
        d["bin"] = pd.qcut(d.p, 10, labels=False, duplicates="drop")
        out["trees_clean_calibration"] = [{"pred": round(g.p.mean(), 3), "actual": round(g.y.mean(), 3), "n": int(len(g))} for _, g in d.groupby("bin")]
        # which inputs carry the trees (drop-one on the test year)
        drops = {}
        groups = {"tried before": [c for c in X if c.startswith("tried_")], "room record": ["room_record", "room_known"],
                  "carrier records": ["carrier_record", "carrier_known", "carrier_room_record", "carrier_room_known"],
                  "timing": ["months_in", "last6"], "usual room": ["in_usual_room"], "twin filed first": ["twin_before"],
                  "standing": ["in_maj"]}
        for g, cols in groups.items():
            keep = [c for c in X.columns if c not in cols]
            m = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                               random_state=0).fit(X.loc[tr, keep], y[tr])
            drops[g] = round(out["trees_clean"]["auc"] - roc_auc_score(y[te], m.predict_proba(X.loc[te, keep])[:, 1]), 3)
        out["auc_lost_without"] = drops
        res["held_out"][label] = out
    with open(os.path.join(HERE, "results_fate_v2.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
