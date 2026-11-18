#!/usr/bin/env python3
"""Batch 3 — Virginia's member-vote tests on Pennsylvania, from the Open States session CSVs (CC0; 5 downloads, zero
load on PA's site). Reads tools/historical_cache/pa/openstates/sessions/PA_*.zip.

Tests (VA page in brackets):
  coverage            share of HB/SB with any roll call, committee vs floor            [testing/coverage]
  roll_rate           how often each party's majority loses a roll call                  [ledger: majority roll rate]
  contested           unanimous / lopsided / contested first roll calls; majority edge   [testing/contested_vs_routine]
  defection           member defection rate, split-half and session-to-session r        [testing/persuadability]
  pivotality          member on the winning side of a one-vote-decides margin            [votes.py]
  first_vote          predict each member's vote on a bill's first roll call             [testing/first_vote]
  member_law          does defecting on a law predict defecting on that law later?       [testing/member_subject]
  second_chamber      exact cross-party yes votes vs fate in the other chamber           [testing/second_chamber]
  member_stats        absence, loyalty, floor win rate, agrees with committee; stability [ledger vote stats]
  rooms               committee roll calls, if present: kill points, partisan rooms      [testing/rooms]

Identity: a voter is resolved to the PA export's sponsor roll for that session and chamber (surname, disambiguated by
PA's own initial form "D. WILLIAMS"); party comes from that roll. A voter who cannot be resolved is COUNTED and kept
out of every party-based statistic (fail closed), never guessed.
"""
from __future__ import annotations

import collections
import csv
import io
import json
import os
import re
import sys
import zipfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
from pa_frame import frame  # noqa: E402
from pa_drafting import law_key  # noqa: E402

SESS_DIR = os.path.join(ROOT, "tools", "historical_cache", "pa", "openstates", "sessions")
OS_TO_OURS = {"2017-2018": "2017_0", "2019-2020": "2019_0", "2021-2022": "2021_0", "2023-2024": "2023_0", "2025-2026": "2025_0"}


def rows(z, suffix):
    n = [x for x in z.namelist() if x.endswith(suffix)]
    return list(csv.DictReader(io.TextIOWrapper(z.open(n[0]), encoding="utf-8", errors="replace"))) if n else []


def norm(s):
    return re.sub(r"[^A-Z]", "", (s or "").upper())


def roll_index(F):
    """(session, body) -> {normalized key -> (surname_as_exported, party)} from every sponsor row of that session."""
    import pickle
    d = pickle.load(open(os.path.join(HERE, ".cache_corpus.pkl"), "rb"))["data"]
    idx = collections.defaultdict(dict)
    for s, D in d.items():
        for b in D["bills"]:
            for p in [b["prime"]] + b["cosponsors"]:
                if p and p.get("surname") and p.get("body") and p.get("party"):
                    idx[(s, p["body"])][norm(p["surname"])] = (p["surname"], p["party"], p.get("district"))
    by_surname = {}
    for k, m in idx.items():
        sur = collections.defaultdict(list)
        for nk, v in m.items():
            sur[norm(v[0].split(".")[-1].split()[-1]) if "." in v[0] else nk].append(nk)
        by_surname[k] = sur
    return idx, by_surname


def resolve(name, session, body, idx, by_sur):
    """Open States voter_name -> roll key, or None. Forms seen in Open States: 'Williams', 'Williams, D.', 'Dan Williams'."""
    m = idx.get((session, body), {})
    sur = by_sur.get((session, body), {})
    n = (name or "").strip()
    if not n:
        return None
    if "," in n:
        last, first = [x.strip() for x in n.split(",", 1)]
    else:
        parts = n.split()
        last, first = (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (n, "")
    L, I = norm(last), norm(first)[:1]
    if I and (I + L) in m:
        return I + L
    if L in m:
        return L
    cands = sur.get(L, [])
    if len(cands) == 1:
        return cands[0]
    if I:
        c2 = [c for c in cands if c.startswith(I)]
        if len(c2) == 1:
            return c2[0]
    return None


def load(F):
    idx, by_sur = roll_index(F)
    events, ballots = [], []
    unresolved = collections.Counter()
    files = sorted(f for f in os.listdir(SESS_DIR) if f.endswith(".zip")) if os.path.isdir(SESS_DIR) else []
    if not files:
        raise SystemExit(f"API_FAILURE: no Open States PA session files in {SESS_DIR} — batch 3 needs the owner's links")
    for fn in files:
        z = zipfile.ZipFile(os.path.join(SESS_DIR, fn))
        m = re.search(r"(\d{4}-\d{4})", fn)
        if not m or m.group(1) not in OS_TO_OURS:
            unresolved[f"<session file not mapped: {fn}>"] += 1
            continue
        s = OS_TO_OURS[m.group(1)]
        orgs = {o["id"]: o for o in rows(z, "_organizations.csv")}
        bills = {b["id"]: b["identifier"] for b in rows(z, "_bills.csv")}

        def chamber(oid):
            seen = set()
            while oid and oid in orgs and oid not in seen:
                seen.add(oid)
                c = orgs[oid].get("classification")
                if c in ("lower", "upper"):
                    return {"lower": "H", "upper": "S"}[c]
                oid = orgs[oid].get("parent_id")
            return None
        meta = {}
        for e in rows(z, "_votes.csv"):
            oid = e.get("organization_id") or ""
            o = orgs.get(oid, {})
            meta[e["id"]] = {"eid": e["id"], "session": s, "bill": bills.get(e.get("bill_id") or ""), "date": e.get("start_date", "")[:10],
                             "motion": e.get("motion_text", ""), "cls": e.get("motion_classification", ""), "result": e.get("result", ""),
                             "chamber": chamber(oid), "committee": o.get("classification") == "committee", "org": o.get("name", "")}
        events.extend(meta.values())
        for r in rows(z, "_vote_people.csv"):
            e = meta.get(r.get("vote_event_id"))
            if e is None:
                unresolved["<ballot without roll call>"] += 1
                continue
            opt = (r.get("option") or "").lower()
            key = resolve(r.get("voter_name"), s, e["chamber"], idx, by_sur) if e["chamber"] else None
            if key is None:
                unresolved[(r.get("voter_name") or "<blank>")[:40]] += 1
            party = idx[(s, e["chamber"])][key][1] if key else None
            ballots.append((e["eid"], key, party, opt))
    E = pd.DataFrame(events)
    B = pd.DataFrame(ballots, columns=["eid", "who", "party", "opt"])
    return E, B, unresolved


def per_event(E, B, F):
    yn = B[B.opt.isin(["yes", "no"]) & B.party.isin(["D", "R"])]
    g = yn.groupby(["eid", "party", "opt"]).size().unstack(fill_value=0)
    t = g.reset_index().pivot_table(index="eid", columns="party", values=["yes", "no"], fill_value=0)
    t.columns = [f"{a}_{b}" for a, b in t.columns]
    X = E.set_index("eid").join(t, how="inner")
    for c in ("yes_D", "no_D", "yes_R", "no_R"):
        if c not in X:
            X[c] = 0
    X["yes"] = X.yes_D + X.yes_R; X["no"] = X.no_D + X.no_R
    maj = {(s, b): m for s, b, m in zip(F.session, F.body, F.majority)}
    X["maj"] = [maj.get((s, c)) for s, c in zip(X.session, X.chamber)]
    X["passed"] = X.yes > X.no
    for p in ("D", "R"):
        X[f"{p}_side"] = np.where(X[f"yes_{p}"] > X[f"no_{p}"], True, np.where(X[f"no_{p}"] > X[f"yes_{p}"], False, np.nan))
    return X


def t_coverage(E, F):
    out = {}
    for s, g in E.groupby("session"):
        bills = F[F.session == s]
        with_rc = set(g.bill.dropna())
        ids = set(bills.body.map({"H": "HB", "S": "SB"}) + " " + bills.number.astype(str))
        out[s] = {"bills_with_a_roll_call": f"{len(ids & with_rc)} of {len(ids)}", "roll_calls": int(len(g)),
                  "committee_roll_calls": int(g.committee.sum())}
    return out


def t_roll_rate(X):
    out = {}
    fl = X[~X.committee & X.maj.isin(["D", "R"])]
    for (s, c), g in fl.groupby(["session", "chamber"]):
        m = g.maj.iloc[0]; o = "R" if m == "D" else "D"
        msides = g[f"{m}_side"].dropna(); osides = g[f"{o}_side"].dropna()
        out[f"{s} {c}"] = {"majority_rolled": f"{int(((msides == True) != g.loc[msides.index, 'passed']).sum())} of {len(msides)}",  # noqa: E712
                           "minority_rolled": f"{int(((osides == True) != g.loc[osides.index, 'passed']).sum())} of {len(osides)}"}  # noqa: E712
    return out


def t_contested(X):
    X = X[~X.committee].copy()
    X["share_no"] = X.no / (X.yes + X.no).replace(0, np.nan)
    X["kind"] = pd.cut(X.share_no, [-0.01, 0.0, 0.1, 1.0], labels=["unanimous", "lopsided (<10% no)", "contested"])
    return {k: int(v) for k, v in X.kind.value_counts().items()}


def t_defection(B, X):
    yn = B[B.opt.isin(["yes", "no"]) & B.party.isin(["D", "R"]) & B.who.notna()].merge(X[["session", "D_side", "R_side", "committee"]], left_on="eid", right_index=True)
    yn["side"] = np.where(yn.party == "D", yn.D_side, yn.R_side)
    yn = yn[yn.side.notna()]
    yn["defect"] = ((yn.opt == "yes") != yn.side.astype(bool)).astype(int)
    out = {}
    m = yn.groupby(["session", "party", "who"]).defect.agg(["mean", "size"]).reset_index()
    m = m[m["size"] >= 40]
    out["median_defection_pct"] = {f"{s} {p}": round(100 * g["mean"].median(), 2) for (s, p), g in m.groupby(["session", "party"])}
    # split-half (odd vs even roll calls) within session
    yn["half"] = yn.eid.map(lambda e: hash(e) % 2)
    h = yn.groupby(["session", "who", "half"]).defect.mean().unstack()
    h = h.dropna()
    out["split_half_r"] = round(float(h[0].corr(h[1])), 3) if len(h) > 10 else None
    # session to session
    piv = m.pivot_table(index="who", columns="session", values="mean")
    rs = []
    cols = sorted(piv.columns)
    for a, b in zip(cols, cols[1:]):
        both = piv[[a, b]].dropna()
        if len(both) > 20:
            rs.append({"from": a, "to": b, "members": int(len(both)), "r": round(float(both[a].corr(both[b])), 3)})
    out["session_to_session_r"] = rs
    return out, yn


def t_first_vote(yn, X, F):
    """Each member's vote on each bill's FIRST roll call in a chamber. Features known before the vote."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    yn = yn.merge(X[["bill", "date", "chamber"]], left_on="eid", right_index=True)
    first = yn.sort_values("date").groupby(["session", "bill", "chamber"]).eid.first()
    fv = yn[yn.eid.isin(set(first))].copy()
    bills = F.assign(bill=F.body.map({"H": "HB", "S": "SB"}) + " " + F.number.astype(str))[["session", "bill", "p_party", "in_maj", "cosp_keys", "p_key", "majority", "tkey"]]
    fv = fv.merge(bills, on=["session", "bill"], how="inner")
    fv["y"] = (fv.opt == "yes").astype(int)
    fv["same_party"] = (fv.party == fv.p_party).astype(int)
    fv["member_maj"] = (fv.party == fv.majority).astype(int)
    fv["cosponsor"] = [int(any(norm(k.split("|")[1]) == w for k in ck)) for ck, w in zip(fv.cosp_keys, fv.who)]
    fv["committee"] = fv.committee.astype(int)
    fv["senate"] = (fv.chamber == "S").astype(int)
    # member's prior-session defection and prior agreement with this sponsor (earlier sessions only)
    prior_def = yn.groupby(["session", "who"]).defect.mean()
    sess = sorted(yn.session.unique())
    prev = {s: sess[i - 1] if i else None for i, s in enumerate(sess)}
    fv["prior_defect"] = [prior_def.get((prev[s], w), np.nan) for s, w in zip(fv.session, fv.who)]
    fv["prior_known"] = fv.prior_defect.notna().astype(int)
    fv["prior_defect"] = fv.prior_defect.fillna(fv.prior_defect.median())
    cols = ["same_party", "member_maj", "in_maj", "cosponsor", "committee", "senate", "prior_defect", "prior_known"]
    out = {}
    for label, (until, test) in {"2023-24": ("2021_0", "2023_0"), "2025-26": ("2023_0", "2025_0")}.items():
        tr, te = fv.session <= until, fv.session == test
        if tr.sum() < 1000 or te.sum() < 1000:
            out[label] = "too few ballots"
            continue
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=0).fit(fv.loc[tr, cols], fv.y[tr])
        p = m.predict_proba(fv.loc[te, cols])[:, 1]
        yt = fv.y[te].to_numpy()
        acc = ((p >= 0.5) == yt)
        other = (fv.same_party[te] == 0).to_numpy()
        conf = np.abs(p - 0.5)
        hard = conf <= np.quantile(conf, 1 / 3)
        base = (fv.same_party[te].to_numpy() == yt) | (yt == 1)   # "everyone votes yes" is the PA floor default
        out[label] = {"ballots": int(te.sum()), "accuracy": round(100 * acc.mean(), 1),
                      "everyone_votes_yes": round(100 * (yt == 1).mean(), 1),
                      "other_party_ballots": round(100 * acc[other].mean(), 1), "hardest_third": round(100 * acc[hard].mean(), 1),
                      "contested_only": None}
        # contested first roll calls only (where VA's 86% lives): at least 10% no
        ev = X.loc[fv.eid[te]]
        cont = ((ev.no / (ev.yes + ev.no)) >= 0.10).to_numpy()
        if cont.sum():
            out[label]["contested_only"] = {"ballots": int(cont.sum()), "accuracy": round(100 * acc[cont].mean(), 1),
                                            "everyone_votes_with_party_majority": None}
        _ = base
    return out


def main():
    F = frame()
    E, B, unresolved = load(F)
    X = per_event(E, B, F)
    res = {"method": __doc__.split("\n\n")[1].strip(), "events": int(len(E)), "ballots": int(len(B)),
           "unresolved_voters": {"ballots": int(sum(unresolved.values())), "top": unresolved.most_common(12)}}
    res["coverage"] = t_coverage(E, F)
    res["roll_rate"] = t_roll_rate(X)
    res["contested"] = t_contested(X)
    res["defection"], yn = t_defection(B, X)
    res["first_vote"] = t_first_vote(yn, X, F)
    with open(os.path.join(HERE, "results_batch3.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
