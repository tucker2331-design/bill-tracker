#!/usr/bin/env python3
"""Round 3b: filing-day committee seats (pa_fate_v3.seats: roll calls strictly before filing, or the previous
session) plus the bill's co-sponsors who sit on its first committee BY THE SAME FILING-DAY RULE — a SEPARATE,
labelled arm, because PA's co-sponsor list itself is final and undated (timing unverified, as in round 2).
Same held-out protocol. Writes results_fate_v3b.json."""
import collections
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pa_frame import frame  # noqa: E402
from pa_fate_v2 import features  # noqa: E402
import pa_batch3  # noqa: E402
from pa_fate_v3 import committee_ballots, fit_eval, room_key, seats, _match  # noqa: E402

F = frame().reset_index(drop=True)
X, C = features(F)
j, B = committee_ballots(F)
S = seats(F, j)
first_vote = collections.defaultdict(dict)
for (s, b, r, k), t in j.groupby(["session", "chamber", "room", "key"]).date.min().items():
    first_vote[(s, b, r)][k] = t
sessions = sorted(F.session.unique())
prev = {s: sessions[i - 1] for i, s in enumerate(sessions) if i > 0}
party_of = dict(zip(B.dropna(subset=["who"]).who, B.dropna(subset=["who"]).party))
cos_on, maj_cos_on = [], []
for s, b, c, ck, d, maj in zip(F.session, F.body, F.cmte, F.cosp_keys, F.intro, F.majority):
    r = room_key(c)
    now, before = first_vote.get((s, b, r), {}), first_vote.get((prev.get(s), b, r), {}) if prev.get(s) else {}
    hits = []
    for x in ck:
        body, sur = x.split("|", 1)
        if body != b:
            continue
        nk = pa_batch3.norm(sur)
        ks = [k for k in _match(now, nk) if pd.notna(d) and now[k] < d] + _match(before, nk)
        if ks:
            hits.append(ks[0])
    cos_on.append(len(set(hits)))
    maj_cos_on.append(int(any(party_of.get(f"{b}|{k}") == maj for k in hits)))
clean = X.copy()
for k in ("seat_before", "seat_before_known", "seat_prior", "seat_prior_known"):
    clean[k] = S[k]
arm = pd.concat([clean, C], axis=1)
arm["cosp_on_cmte"] = np.log1p(cos_on)
arm["maj_cosp_on_cmte"] = maj_cos_on
y = F.out
res = {"held_out": {}}
for label, (until, test) in {"A: 2023-24": ("2021_0", "2023_0"), "B: 2025-26": ("2023_0", "2025_0")}.items():
    tr, te = (F.session <= until).to_numpy(), (F.session == test).to_numpy()
    res["held_out"][label] = {"filing_day_seats": fit_eval(clean, y, tr, te),
                              "plus_cosponsor_arm_timing_unverified": fit_eval(arm, y, tr, te)}
json.dump(res, open(os.path.join(HERE, "results_fate_v3b.json"), "w"), indent=1)
for k, v in res["held_out"].items():
    print(k, {n: {m: v[n][m]["auc"] for m in v[n]} for n in v})
