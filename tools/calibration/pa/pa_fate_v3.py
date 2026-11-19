#!/usr/bin/env python3
"""PA bill fate, round 3: close the gap to Virginia's locked 0.80 on the 2023-24 holdout (owner 2026-11-19: "even out
pa to va … stats wise too. keep pushing until its even").

Round 2 (pa_fate_v2.py) reached 0.775 (2023-24) and 0.807 (2025-26). The listed next lever was HISTORICAL committee
seats. Batch 3's Open States session files (CC0) record every PA committee roll call with the room in the motion
("Committee vote (Health): …"), so who sat on which committee in which session is known for 2017-2026 — from the
votes themselves, never a roster guess. New inputs, both knowable on the filing day (seats are set at the session's
start):
  * seat — the prime sponsor voted in at least one roll call of the bill's first committee that session;
  * seat_known — the committee has recorded roll calls that session (else seat is unknown, not "no").
Same protocol as round 2: fit on earlier sessions, score on the held-out one; every other input unchanged.
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pa_frame import frame  # noqa: E402
from pa_fate_v2 import features, score  # noqa: E402
import pa_batch3  # noqa: E402


def room_key(name: str) -> str:
    return re.sub(r"[^A-Z]", "", (name or "").upper().replace("&", " AND "))


def seats(F):
    E, B, _unresolved = pa_batch3.load(F)
    com = E[E.committee & E.chamber.notna()][["eid", "session", "chamber", "org"]]
    j = B.dropna(subset=["who"]).merge(com, on="eid")
    j["room"] = j.org.map(room_key)
    j["key"] = j.who.str.split("|").str[1]
    members = j.groupby(["session", "chamber", "room"]).key.apply(set).to_dict()
    rooms = set(members)
    seat, known = [], []
    for s, b, c, p in zip(F.session, F.body, F.cmte, F.p_name):
        k = (s, b, room_key(c))
        if k in rooms:
            known.append(1)
            nk = pa_batch3.norm(p)
            m = members[k]
            seat.append(int(nk in m or any(x.endswith(nk) and len(x) - len(nk) <= 1 for x in m)))
        else:
            known.append(0)
            seat.append(0)
    return np.array(seat), np.array(known), {"committee_rooms_with_roll_calls": len(rooms),
                                             "ballots_in_committee": int(len(j))}


def main():
    F = frame().reset_index(drop=True)
    X, _C = features(F)
    seat, known, cov = seats(F)
    X3 = X.copy()
    X3["seat"] = seat
    X3["seat_known"] = known
    y = F.out
    res = {"method": __doc__.split("\n\n")[1].strip(), "virginia_locked_2026": 0.80, "coverage": cov, "held_out": {}}
    for s in sorted(F.session.unique()):
        m = F.session == s
        res["coverage"][s] = {"bills": int(m.sum()), "seat_known": int(known[m].sum()), "seat": int(seat[m].sum())}
    for label, (until, test) in {"A: 2023-24": ("2021_0", "2023_0"), "B: 2025-26": ("2023_0", "2025_0")}.items():
        tr, te = (F.session <= until).to_numpy(), (F.session == test).to_numpy()
        out = {"bills": int(te.sum())}
        for name, XX in (("round2_inputs", X), ("plus_seats", X3)):
            lr = LogisticRegression(max_iter=4000).fit(XX[tr], y[tr])
            gb = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31,
                                                l2_regularization=1.0, random_state=0).fit(XX[tr], y[tr])
            out[name] = {"logistic": score(y[te], lr.predict_proba(XX[te])[:, 1]),
                         "trees": score(y[te], gb.predict_proba(XX[te])[:, 1])}
        # recency: the last two training sessions only (the 2023 House flip put a new majority in charge)
        rec = (F.session.isin(sorted(s for s in F.session.unique() if s <= until)[-2:])).to_numpy()
        lr = LogisticRegression(max_iter=4000).fit(X3[rec], y[rec])
        out["plus_seats_recent_two_sessions_logistic"] = score(y[te], lr.predict_proba(X3[te])[:, 1])
        sk = te & (known == 1)
        out["seat_effect_test_year"] = {
            "out_rate_seat": round(float(y[sk & (seat == 1)].mean()), 3), "n_seat": int((sk & (seat == 1)).sum()),
            "out_rate_no_seat": round(float(y[sk & (seat == 0)].mean()), 3), "n_no_seat": int((sk & (seat == 0)).sum())}
        res["held_out"][label] = out
    with open(os.path.join(HERE, "results_fate_v3.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
