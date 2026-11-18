#!/usr/bin/env python3
"""Does each element of the drafting-room / portfolio design actually MEAN anything? (owner 2026-11-17: "what's the
correlation of them actually meaning anything or were you just guessing their significance for the format?")

One test for every element: add it to a baseline that already knows the sponsor's party standing (majority/minority)
x chamber x session year, fit on earlier sessions, score on a later one never seen. Report the gain in AUC and in log
loss, and how many bills the element says anything about (coverage). An element earns a place on a screen only if it
adds on held-out data.

  held-out A: fit 2009-2021 -> score 2023-24 (last completed session)
  held-out B: fit 2009-2023 -> score 2025-26 (first committee, essentially settled)
  roster elements (seat, chair co-sign) exist for 2025-26 only -> fit odd bill numbers, score even.

TIMING CAVEAT for every co-sponsor element: PA's export lists the FINAL co-sponsors, undated. A co-sponsor who signed
after the committee acted would leak the outcome (Virginia found the same trap — testing/carrier_effect). Co-sponsor
elements are flagged `timing_unverified`.
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
from pa_frame import frame, prior_rate  # noqa: E402


def tried_before(F):
    """Earlier filing of the same title in the same chamber: 'died', 'cleared' or 'none'; same-room and same-carrier flags."""
    last = {}
    prev, same_room, same_carrier = [], [], []
    for i in F.sort_values(["session", "number"]).index:
        b = F.loc[i]
        e = last.get((b.body, b.tkey)) if b.tkey else None
        if e is not None and e["session"] < b.session:
            prev.append((i, "died" if not e["out"] else "cleared"))
            same_room.append((i, int(e["cmte"] == b.cmte)))
            same_carrier.append((i, int(e["p_key"] == b.p_key)))
        else:
            prev.append((i, "none")); same_room.append((i, 0)); same_carrier.append((i, 0))
        if b.tkey:
            last[(b.body, b.tkey)] = b
    return (pd.Series(dict(prev)), pd.Series(dict(same_room)), pd.Series(dict(same_carrier)))


def design(F):
    X = pd.DataFrame(index=F.index)
    X["base"] = F.groupby(["in_maj", "body", "second_year"])["out"].transform("mean")   # replaced by train-only rates below
    room = prior_rate(F, ["body", "cmte", "in_maj"])
    X["room_record"] = room.fillna(F["out"].mean())
    X["room_known"] = room.notna().astype(int)
    p, sr, sc = tried_before(F)
    X["tried_died_same_room"] = ((p == "died") & (sr == 1)).astype(int)
    X["tried_cleared_same_room"] = ((p == "cleared") & (sr == 1)).astype(int)
    X["tried_died_other_room"] = ((p == "died") & (sr == 0)).astype(int)
    X["tried_cleared_other_room"] = ((p == "cleared") & (sr == 0)).astype(int)
    pr = prior_rate(F, ["p_key"])
    X["carrier_record"] = pr.fillna(F["out"].mean())
    X["carrier_known"] = pr.notna().astype(int)
    X["maj_cosp_share"] = F["maj_cosp_share"].where(F["n_cosp"] > 0, 0)
    X["no_cosp"] = (F["n_cosp"] == 0).astype(int)
    X["bipartisan"] = F["bipartisan"]
    X["log_cosp"] = np.log1p(F["n_cosp"])
    X["title_amend"] = (F["title_form"] == "amend").astype(int)
    X["title_new"] = F["title_form"].isin(["provide", "establish"]).astype(int)
    return X, (p != "none")


ELEMENTS = {
    "tried before (same title earlier, same/other room)": (["tried_died_same_room", "tried_cleared_same_room", "tried_died_other_room", "tried_cleared_other_room"], "tried"),
    "the room's record for this standing": (["room_record", "room_known"], "room"),
    "the carrier's own record": (["carrier_record", "carrier_known"], "carrier"),
    "majority co-sponsor share [timing_unverified]": (["maj_cosp_share", "no_cosp"], None),
    "co-sponsor count [timing_unverified]": (["log_cosp", "no_cosp"], None),
    "a co-sponsor from the other party [timing_unverified]": (["bipartisan"], None),
    "title form (amend vs new act)": (["title_amend", "title_new"], None),
}


def fit_score(Xtr, ytr, Xte, yte, cols):
    m = LogisticRegression(max_iter=2000).fit(Xtr[cols], ytr)
    p = m.predict_proba(Xte[cols])[:, 1]
    return roc_auc_score(yte, p), log_loss(yte, p)


def baseline_cols(F, tr_mask):
    rates = F[tr_mask].groupby(["in_maj", "body", "second_year"])["out"].mean()
    b = F.set_index(["in_maj", "body", "second_year"]).index.map(rates).to_numpy(dtype=float)
    return np.where(np.isnan(b), F[tr_mask]["out"].mean(), b)


def main():
    F = frame().reset_index(drop=True)
    X, has_prev = design(F)
    y = F["out"]
    res = {"method": __doc__.split("\n\n")[1].strip(), "held_out": {}}
    for label, (train_until, test) in {"A: 2023-24": ("2021_0", "2023_0"), "B: 2025-26": ("2023_0", "2025_0")}.items():
        tr = F["session"] <= train_until
        te = F["session"] == test
        X["logit_base"] = np.log(np.clip(baseline_cols(F, tr), 1e-3, 1 - 1e-3) / (1 - np.clip(baseline_cols(F, tr), 1e-3, 1 - 1e-3)))
        b_auc, b_ll = fit_score(X[tr], y[tr], X[te], y[te], ["logit_base"])
        rows = {"baseline (party standing x chamber x session year)": {"auc": round(b_auc, 3), "log_loss": round(b_ll, 4)}}
        for name, (cols, cov) in ELEMENTS.items():
            auc, ll = fit_score(X[tr], y[tr], X[te], y[te], ["logit_base"] + cols)
            coverage = {"tried": has_prev[te].mean(), "room": X.loc[te, "room_known"].mean(),
                        "carrier": X.loc[te, "carrier_known"].mean()}.get(cov, 1.0)
            rows[name] = {"auc_gain": round(auc - b_auc, 3), "log_loss_gain": round(b_ll - ll, 4),
                          "bills_it_speaks_to": f"{round(100 * coverage)}%"}
        allc = ["logit_base"] + sorted({c for cols, _ in ELEMENTS.values() for c in cols})
        auc, ll = fit_score(X[tr], y[tr], X[te], y[te], allc)
        rows["everything together"] = {"auc_gain": round(auc - b_auc, 3), "log_loss_gain": round(b_ll - ll, 4)}
        res["held_out"][label] = {"bills": int(te.sum()), **rows}
    # roster elements, 2025-26 only (odd -> even)
    from pa_batch2 import rosters, _bills
    from states import pa_roster as PR
    T = F[(F.session == "2025_0") & (F.cmte != "(none)")].copy()
    members, chair, _ = rosters()
    T["ckey"] = [(b, PR.committee_key({"H": "House", "S": "Senate"}[b], c)) for b, c in zip(T.body, T.cmte)]
    T = T[T.ckey.isin(members)].copy()
    T["on_cmte"] = [int(d in members[k]) for d, k in zip(T.p_district, T.ckey)]
    T["is_chair"] = [int(chair.get(k) == d) for d, k in zip(T.p_district, T.ckey)]
    cos = [[c["district"] for c in b["cosponsors"] if c["body"] == body] for b, body in zip(_bills(T.sid), T.body)]
    T["chair_cosigns"] = [int(chair.get(k) in ds and not ic) for k, ds, ic in zip(T.ckey, cos, T.is_chair)]
    odd, even = T[T.number % 2 == 1], T[T.number % 2 == 0]
    rates = odd.groupby(["in_maj", "body"])["out"].mean()
    for D in (odd, even):
        b = D.set_index(["in_maj", "body"]).index.map(rates).to_numpy(dtype=float)
        D["logit_base"] = np.log(b / (1 - b))
    b_auc, b_ll = fit_score(odd, odd.out, even, even.out, ["logit_base"])
    rr = {"baseline": {"auc": round(b_auc, 3), "log_loss": round(b_ll, 4)}}
    for name, cols in {"sponsor sits on the committee": ["on_cmte"], "sponsor is the majority chair": ["is_chair"],
                       "the majority chair co-signs [timing_unverified]": ["chair_cosigns"]}.items():
        auc, ll = fit_score(odd, odd.out, even, even.out, ["logit_base"] + cols)
        rr[name] = {"auc_gain": round(auc - b_auc, 3), "log_loss_gain": round(b_ll - ll, 4),
                    "bills_it_speaks_to": f"{round(100 * even[cols[0]].mean())}%"}
    res["roster_2025_26 (fit odd bill numbers, score even)"] = rr
    with open(os.path.join(HERE, "results_element_value.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
