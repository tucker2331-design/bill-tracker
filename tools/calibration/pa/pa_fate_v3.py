#!/usr/bin/env python3
"""PA bill fate, round 3: close the gap to Virginia's locked 0.80 on the 2023-24 holdout (owner 2026-11-19: "even out
pa to va … stats wise too. keep pushing until its even").

Round 2 (pa_fate_v2.py) reached 0.775 (2023-24) and 0.807 (2025-26). The listed next lever was committee seats.
Batch 3's Open States session files (CC0) record every PA committee roll call with the room in the motion
("Committee vote (Health): …") and its date. ONLY what is on the record before the bill is filed is used
(Codex #277: a roll call after filing — let alone the bill's own reporting vote — is a future observation):
  * seat_before / seat_before_known — the sponsor voted in a roll call of the bill's first committee dated strictly
    before the bill's filing date this session; known only if that committee had such a roll call;
  * seat_prior / seat_prior_known — the sponsor voted in that committee in the PREVIOUS session (complete at filing);
    known only if that committee had roll calls then.
Unavailable membership stays unknown (flag 0), never "no seat". The first, leaky version (any roll call in the
session) is kept as a labelled contrast only, so the size of the leak is on the record.
Same protocol as round 2: fit on earlier sessions, score on the held-out one; every other input unchanged.
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pa_frame import frame  # noqa: E402
from pa_fate_v2 import features, score  # noqa: E402
import pa_batch3  # noqa: E402


def room_key(name) -> str:
    if not isinstance(name, str):      # a missing room (NaN/None) is "", never a crash (Gemini #277)
        return ""
    return re.sub(r"[^A-Z]", "", name.upper().replace("&", " AND "))


def _match(keys, nk: str):
    """The roll-call keys that are this sponsor (exact, or the first-initial form used for shared surnames)."""
    return [k for k in keys if k == nk or (k.endswith(nk) and len(k) - len(nk) <= 1)]


def committee_ballots(F):
    E, B, _unresolved = pa_batch3.load(F)
    com = E[E.committee & E.chamber.notna()][["eid", "session", "chamber", "org", "date"]]
    j = B.dropna(subset=["who"]).merge(com, on="eid")
    j["room"] = j.org.map(room_key)
    j["key"] = j.who.str.split("|").str[1]
    j["date"] = pd.to_datetime(j.date, errors="coerce")
    return j.dropna(subset=["date", "key"]), B


def seats(F, j):
    first_vote = collections.defaultdict(dict)        # (session, chamber, room) -> {member key: first roll-call date}
    for (s, b, r, k), t in j.groupby(["session", "chamber", "room", "key"]).date.min().items():
        first_vote[(s, b, r)][k] = t
    room_first = j.groupby(["session", "chamber", "room"]).date.min().to_dict()
    sessions = sorted(F.session.unique())
    prev = {s: sessions[i - 1] for i, s in enumerate(sessions) if i > 0}
    out = {n: [] for n in ("seat_before", "seat_before_known", "seat_prior", "seat_prior_known", "seat_any_LEAKY",
                           "seat_any_known_LEAKY")}
    for s, b, c, p, d in zip(F.session, F.body, F.cmte, F.p_name, F.intro):
        r, nk = room_key(c), pa_batch3.norm(p)
        fv = first_vote.get((s, b, r), {})
        rf = room_first.get((s, b, r))
        known_before = int(rf is not None and pd.notna(d) and rf < d)
        out["seat_before_known"].append(known_before)
        out["seat_before"].append(int(known_before and any(fv[k] < d for k in _match(fv, nk))))
        pv = first_vote.get((prev.get(s), b, r), {}) if prev.get(s) else {}
        out["seat_prior_known"].append(int(bool(pv)))
        out["seat_prior"].append(int(bool(pv) and bool(_match(pv, nk))))
        out["seat_any_known_LEAKY"].append(int(bool(fv)))
        out["seat_any_LEAKY"].append(int(bool(_match(fv, nk))))
    return {k: np.array(v) for k, v in out.items()}


def fit_eval(XX, y, tr, te):
    lr = LogisticRegression(max_iter=4000).fit(XX[tr], y[tr])
    gb = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                        random_state=0).fit(XX[tr], y[tr])
    pl, pg = lr.predict_proba(XX[te])[:, 1], gb.predict_proba(XX[te])[:, 1]
    return {"logistic": score(y[te], pl), "trees": score(y[te], pg), "blend": score(y[te], (pl + pg) / 2)}


def main():
    F = frame().reset_index(drop=True)
    X, _C = features(F)
    j, _B = committee_ballots(F)
    S = seats(F, j)
    clean = X.copy()
    for k in ("seat_before", "seat_before_known", "seat_prior", "seat_prior_known"):
        clean[k] = S[k]
    leaky = X.copy()
    leaky["seat"], leaky["seat_known"] = S["seat_any_LEAKY"], S["seat_any_known_LEAKY"]
    y = F.out
    res = {"method": __doc__.split("\n\n")[1].strip(), "virginia_locked_by_year": {"2022": 0.676, "2023": 0.725,
           "2024": 0.756, "2025": 0.809}, "coverage": {}, "held_out": {}}
    for s in sorted(F.session.unique()):
        m = (F.session == s).to_numpy()
        res["coverage"][s] = {"bills": int(m.sum()), **{k: int(S[k][m].sum()) for k in S}}
    for label, (until, test) in {"A: 2023-24": ("2021_0", "2023_0"), "B: 2025-26": ("2023_0", "2025_0")}.items():
        tr, te = (F.session <= until).to_numpy(), (F.session == test).to_numpy()
        yes, known = S["seat_prior"] == 1, S["seat_prior_known"] == 1
        res["held_out"][label] = {
            "bills": int(te.sum()),
            "round2_inputs": fit_eval(X, y, tr, te),
            "plus_filing_day_seats": fit_eval(clean, y, tr, te),
            "LEAKY_any_roll_call_in_session_contrast_only": fit_eval(leaky, y, tr, te),
            "seat_prior_effect_test_year": {
                "out_rate_seat_prior": round(float(y[te & yes].mean()), 3), "n": int((te & yes).sum()),
                "out_rate_known_no_seat_prior": round(float(y[te & known & ~yes].mean()), 3),
                "n_no": int((te & known & ~yes).sum())}}
    with open(os.path.join(HERE, "results_fate_v3.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
