#!/usr/bin/env python3
"""Round 3b: the seat signal combined with standing and chamber, and the bill's co-sponsors who sit on its first
committee (a SEPARATE, labelled arm: PA's co-sponsor list is final and undated, so its timing is unverified, as in
round 2). Same held-out protocol. Writes results_fate_v3b.json."""
import json, os, sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pa_frame import frame
from pa_fate_v2 import features, score
import pa_batch3
from pa_fate_v3 import room_key

F = frame().reset_index(drop=True)
X, C = features(F)
E, B, _ = pa_batch3.load(F)
com = E[E.committee & E.chamber.notna()][["eid", "session", "chamber", "org"]]
j = B.dropna(subset=["who"]).merge(com, on="eid"); j["room"] = j.org.map(room_key); j["key"] = j.who.str.split("|").str[1]
members = j.groupby(["session", "chamber", "room"]).key.apply(set).to_dict()
maj_party = {(s, b): m for (s, b), m in zip(zip(F.session, F.body), F.majority)}
party_of = {}
for (eid, who, party, opt) in B.dropna(subset=["who"]).itertuples(index=False):
    party_of[who] = party
seat, known, cos_seat, cos_maj_seat = [], [], [], []
for s, b, c, p, ck in zip(F.session, F.body, F.cmte, F.p_name, F.cosp_keys):
    k = (s, b, room_key(c)); m = members.get(k)
    if m is None:
        seat.append(0); known.append(0); cos_seat.append(0); cos_maj_seat.append(0); continue
    known.append(1); nk = pa_batch3.norm(p)
    seat.append(int(nk in m or any(x.endswith(nk) and len(x) - len(nk) <= 1 for x in m)))
    cs = [pa_batch3.norm(x.split("|", 1)[1]) for x in ck if x.split("|", 1)[0] == b]
    hits = [x for x in cs if x in m]
    cos_seat.append(len(hits))
    cos_maj_seat.append(int(any(party_of.get(f"{b}|{x}") == maj_party.get((s, b)) for x in hits)))
X3 = X.copy(); X3["seat"] = seat; X3["seat_known"] = known
X3["seat_x_maj"] = X3.seat * X.in_maj; X3["seat_x_senate"] = X3.seat * X.senate
XC = pd.concat([X3, C], axis=1); XC["cosp_on_cmte"] = np.log1p(cos_seat); XC["maj_cosp_on_cmte"] = cos_maj_seat
y = F.out; res = {"held_out": {}}
for label, (until, test) in {"A: 2023-24": ("2021_0", "2023_0"), "B: 2025-26": ("2023_0", "2025_0")}.items():
    tr, te = (F.session <= until).to_numpy(), (F.session == test).to_numpy()
    out = {}
    for name, XX in (("clean_seats_interactions", X3), ("plus_cosponsor_arm_timing_unverified", XC)):
        lr = LogisticRegression(max_iter=5000).fit(XX[tr], y[tr])
        gb = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=0).fit(XX[tr], y[tr])
        pl, pg = lr.predict_proba(XX[te])[:, 1], gb.predict_proba(XX[te])[:, 1]
        out[name] = {"logistic": score(y[te], pl), "trees": score(y[te], pg), "blend": score(y[te], (pl + pg) / 2)}
    res["held_out"][label] = out
json.dump(res, open(os.path.join(HERE, "results_fate_v3b.json"), "w"), indent=1)
for k, v in res["held_out"].items():
    print(k, {n: {m: v[n][m]["auc"] for m in v[n]} for n in v})
