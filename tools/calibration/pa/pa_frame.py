#!/usr/bin/env python3
"""The PA corpus as one pandas frame of HB/SB, with every feature knowable AT FILING computed once.

LEAKAGE RULE (same as Virginia's tools/calibration/search.py): a feature may use only what is known when the bill is
referred — its own sponsors, title, committee, and EARLIER sessions' outcomes. Never its own later actions.

Person key across sessions: (body, surname). PA's export carries no member id (knowledge/pa_bill_history_xml.md);
surnames are written with initials where two members share one ("D. MILLER"), so collisions are rare but possible —
features built on it are labelled as person-level estimates, and every test reports its n.
"""
from __future__ import annotations

import collections
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pa_corpus import load, SESSIONS  # noqa: E402

MONEY = {"APPROPRIATIONS", "FINANCE"}


def norm_title(t: str) -> str:
    """Exact-title key: lower case, whitespace collapsed, trailing period dropped. Equality only (no fuzzy match)."""
    return re.sub(r"\s+", " ", (t or "").strip().lower()).rstrip(".")


def frame(D=None) -> pd.DataFrame:
    D = D or load()
    rows = []
    for s in SESSIONS:
        for b in D[s]["bills"]:
            p = b["prime"] or {}
            rows.append({
                "session": s, "year": b["year"], "sid": b["sid"], "body": b["body"], "number": b["number"],
                "subtype": b["subtype"] or "-", "title": b["title"], "tkey": norm_title(b["title"]),
                "title_form": b["title_form"], "cmte": b["first_cmte"] or "(none)",
                "p_name": p.get("surname", ""), "p_party": p.get("party", ""), "p_district": p.get("district", ""),
                "p_key": f"{b['body']}|{p.get('surname', '')}", "majority": b["majority"],
                "in_maj": int(b["prime_in_majority"]), "n_cosp": b["n_cosponsors"],
                "n_maj_cosp": b["n_majority_cosp"], "n_min_cosp": b["n_minority_cosp"],
                "n_other_party_cosp": sum(1 for c in b["cosponsors"] if c["party"] and c["party"] != p.get("party")),
                "n_cross_chamber_cosp": sum(1 for c in b["cosponsors"] if c["body"] and c["body"] != b["body"]),
                "cosp_districts": len({(c["body"], c["district"]) for c in b["cosponsors"]}),
                "cosp_keys": tuple(sorted({f"{c['body']}|{c['surname']}" for c in b["cosponsors"]})),
                "memo": int(b["memo"]), "intro": b["intro_date"],
                "out": int(b["reported1"]), "out_amended": int(b["reported_amended1"]),
                "passed": int(b["passed_origin"]), "passed2": int(b["passed_second"]), "law": int(b["law"]),
                "defeated": int(b["defeated_origin"]), "vetoed": int(b["vetoed"]), "recommitted": int(b["recommitted"]),
                "tally": b["first_tally"], "actions": b["actions"],
            })
    df = pd.DataFrame(rows)
    df["intro"] = pd.to_datetime(df["intro"])          # NaT for a bill with no dated action (counted below)
    df["chamber_maj"] = df["majority"]
    df["second_body"] = df["body"].map({"H": "S", "S": "H"})
    # second chamber's majority that session (split control is the PA 2009-10 and 2023-26 natural experiment)
    maj = {(s, b): D[s]["majority"].get(b) for s in SESSIONS for b in ("H", "S")}
    df["second_maj"] = [maj[(s, b)] for s, b in zip(df["session"], df["second_body"])]
    df["p_party_runs_second"] = (df["p_party"] == df["second_maj"]).astype(int)
    df["money_cmte"] = df["cmte"].isin(MONEY).astype(int)
    df["maj_cosp_share"] = df["n_maj_cosp"] / (df["n_cosp"].where(df["n_cosp"] > 0, 1))
    df["bipartisan"] = (df["n_other_party_cosp"] > 0).astype(int)
    # within-session filing facts (knowable at filing: the patron's own filings to date)
    df = df.sort_values(["session", "intro", "number"]).reset_index(drop=True)
    df["patron_volume"] = df.groupby(["session", "p_key"])["sid"].transform("count")
    df["patron_bill_rank"] = df.groupby(["session", "p_key"]).cumcount() + 1
    df["same_day_batch"] = df.groupby(["session", "p_key", "intro"])["sid"].transform("count")
    df["cmte_load"] = df.groupby(["session", "cmte"])["sid"].transform("count")
    first_day = df.groupby("session")["intro"].transform("min")
    df["days_in"] = (df["intro"] - first_day).dt.days
    df["second_year"] = (df["days_in"].fillna(0) >= 365).astype(int)
    df["names_locality"] = df["title"].str.contains(r"\b(?:County|City of|Borough|Township)\b", regex=True).astype(int)
    # tenure = number of EARLIER sessions this person was prime sponsor of any bill
    seen = collections.defaultdict(set)
    tenure = []
    for s, k in zip(df["session"], df["p_key"]):
        tenure.append(sum(1 for x in seen[k] if x < s))
        seen[k].add(s)
    df["tenure"] = tenure
    return df


def prior_rate(df: pd.DataFrame, key_cols, outcome="out", min_n=1):
    """For each row, the outcome rate of rows with the same key in EARLIER sessions only (NaN when none)."""
    out = pd.Series(float("nan"), index=df.index)
    order = sorted(df["session"].unique())
    acc = collections.defaultdict(lambda: [0, 0])
    for s in order:
        idx = df.index[df["session"] == s]
        keys = list(zip(*[df.loc[idx, c] for c in key_cols])) if len(key_cols) > 1 else list(df.loc[idx, key_cols[0]])
        out.loc[idx] = [acc[k][0] / acc[k][1] if acc[k][1] >= min_n else float("nan") for k in keys]
        for k, y in zip(keys, df.loc[idx, outcome]):
            acc[k][0] += int(y)
            acc[k][1] += 1
    return out


if __name__ == "__main__":
    F = frame()
    print(F.groupby("session").agg(bills=("sid", "count"), out=("out", "mean"), passed=("passed", "mean"),
                                   law=("law", "mean"), in_maj=("in_maj", "mean")).round(3))
