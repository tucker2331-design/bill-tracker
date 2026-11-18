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
import zlib

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


SUFFIX = {"JR", "SR", "II", "III", "IV"}


def resolve(name, session, body, idx, by_sur):
    """Open States voter_name -> roll key, or None. Forms seen in PA files: 'Dan Frankel', 'Regina G. Young',
    'Lynda Schlegel Culver', 'G. Roni Green', 'ARMANINI', and (other states) 'Williams, D.'."""
    m = idx.get((session, body), {})
    sur = by_sur.get((session, body), {})
    n = (name or "").strip()
    if not n:
        return None
    if "," in n:
        last, first = [x.strip() for x in n.split(",", 1)]
        toks = first.split() + last.split()
    else:
        toks = n.split()
    toks = [t for t in toks if norm(t) not in SUFFIX]
    if not toks:
        return None
    first_i = norm(toks[0])[:1] if len(toks) > 1 else ""
    cands_last = [norm(toks[-1])]
    if len(toks) >= 3:
        cands_last.insert(0, norm(toks[-2]) + norm(toks[-1]))     # two-word surnames ("Schlegel Culver")
    for L in cands_last:
        if first_i and (first_i + L) in m:
            return first_i + L
        if L in m:
            return L
        c = sur.get(L, [])
        if len(c) == 1:
            return c[0]
        if first_i:
            c2 = [x for x in c if x.startswith(first_i)]
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
    all_orgs = {}
    for fn in files:
        for o in rows(zipfile.ZipFile(os.path.join(SESS_DIR, fn)), "_organizations.csv"):
            all_orgs.setdefault(o["id"], o)
    for fn in files:
        z = zipfile.ZipFile(os.path.join(SESS_DIR, fn))
        m = re.search(r"(\d{4}-\d{4})", fn)
        if not m or m.group(1) not in OS_TO_OURS:
            unresolved[f"<session file not mapped: {fn}>"] += 1
            continue
        s = OS_TO_OURS[m.group(1)]
        orgs = all_orgs
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
            mt = e.get("motion_text", "") or ""
            cm = re.match(r"Committee vote \(([^)]+)\):\s*(.*)", mt)     # PA: committee roll calls carry the room in the motion
            meta[e["id"]] = {"eid": e["id"], "session": s, "bill": bills.get(e.get("bill_id") or ""), "date": e.get("start_date", "")[:10],
                             "motion": mt, "cls": e.get("motion_classification", ""), "result": e.get("result", ""),
                             "chamber": chamber(oid), "committee": bool(cm) or o.get("classification") == "committee",
                             "org": cm.group(1) if cm else o.get("name", ""), "action": cm.group(2) if cm else mt}
        events.extend(meta.values())
        vp = rows(z, "_vote_people.csv")
        by_id = {}
        for r in vp:                       # pass 1: learn voter_id -> roll key from names that resolve cleanly
            e = meta.get(r.get("vote_event_id"))
            if e and e["chamber"] and r.get("voter_id"):
                k = resolve(r.get("voter_name"), s, e["chamber"], idx, by_sur)
                if k:
                    by_id.setdefault((e["chamber"], r["voter_id"]), k)
        for r in vp:
            e = meta.get(r.get("vote_event_id"))
            if e is None:
                unresolved["<ballot without roll call>"] += 1
                continue
            opt = (r.get("option") or "").lower()
            key = resolve(r.get("voter_name"), s, e["chamber"], idx, by_sur) if e["chamber"] else None
            if key is None and e["chamber"] and r.get("voter_id"):
                key = by_id.get((e["chamber"], r["voter_id"]))
            if key is None and e["chamber"]:
                L = norm(r.get("voter_name"))
                ends = [k for k in idx.get((s, e["chamber"]), {}) if L and k.endswith(L)] if L == norm((r.get("voter_name") or "").upper()) and (r.get("voter_name") or "").isupper() else []
                if len(ends) == 1:
                    key = ends[0]
            if key is None:
                unresolved[(r.get("voter_name") or "<blank>")[:40]] += 1
            party = idx[(s, e["chamber"])][key][1] if key else None
            ballots.append((e["eid"], f"{e['chamber']}|{key}" if key else None, party, opt))
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
    yn["half"] = yn.eid.map(lambda e: zlib.crc32(e.encode()) % 2)    # deterministic split
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


MOTION = [("final", r"FINAL PASSAGE|UNCONTESTED CALENDAR"), ("concur", r"CONCUR"), ("re-report", r"Re-report|Re-Reported"),
          ("report_amended", r"Report Bill As Amended|Reported as Amended"), ("report", r"Report Bill|Reported"),
          ("amendment", r"Amendment|A\d{4,5}"), ("table", r"[Tt]able"), ("recommit", r"[Rr]e-?commit")]


def motion_kind(m):
    for k, pat in MOTION:
        if re.search(pat, m or ""):
            return k
    return "other"


def ballots_frame(yn, X, F):
    """Every resolved yes/no ballot with its roll call and its bill's filing facts."""
    A = yn.merge(X[["bill", "date", "chamber", "org", "motion", "yes", "no"]], left_on="eid", right_index=True)
    A["date"] = pd.to_datetime(A.date, errors="coerce")
    A = A[A.date.notna()]
    bills = F.assign(bill=F.body.map({"H": "HB", "S": "SB"}) + " " + F.number.astype(str),
                     law=F.title.map(law_key).fillna("(none)"))[["session", "bill", "body", "p_party", "in_maj", "cosp_keys", "p_key", "majority", "law", "n_cosp", "bipartisan"]]
    A = A.merge(bills, on=["session", "bill"], how="inner")
    A["y"] = (A.opt == "yes").astype(int)
    A["room"] = np.where(A.committee, A.org.str.upper(), "FLOOR-" + A.chamber)
    A["kind"] = A.motion.map(motion_kind)
    A["contested"] = ((A.no / (A.yes + A.no)) >= 0.10).astype(int)
    vmaj = {(s, b): m for s, b, m in zip(F.session, F.body, F.majority)}     # majority of the VOTING chamber
    A["vmaj"] = [vmaj.get((s, c)) for s, c in zip(A.session, A.chamber)]
    A["member_maj"] = (A.party == A.vmaj).astype(int)
    A["sponsor_maj_here"] = (A.p_party == A.vmaj).astype(int)
    A["sp_same"] = (A.party == A.p_party).astype(int)
    return A.sort_values("date").reset_index(drop=True)


def prior(A, T, keys, col, name, alpha=5.0, base=None):
    """Rate of `col` for `keys` over ballots strictly BEFORE each target's date (replay; no same-day or later info),
    shrunk toward `base` with weight alpha. Adds name, name_n."""
    g = A.groupby(keys + ["date"])[col].agg(["sum", "count"]).reset_index().sort_values("date")
    g[["cs", "cn"]] = g.groupby(keys)[["sum", "count"]].cumsum()
    T = T.sort_values("date")
    M = pd.merge_asof(T[keys + ["date", "_i"]], g[keys + ["date", "cs", "cn"]], on="date", by=keys, allow_exact_matches=False)
    M = M.set_index("_i").reindex(T["_i"])
    b = A[col].mean() if base is None else base
    T[name] = ((M.cs.fillna(0) + alpha * b) / (M.cn.fillna(0) + alpha)).to_numpy()
    T[name + "_n"] = np.log1p(M.cn.fillna(0).to_numpy())
    return T


def t_first_vote(yn, X, F):
    """Each member's vote on each bill's FIRST roll call in a chamber (VA protocol: replay day by day; slices)."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    A = ballots_frame(yn, X, F)
    A["_i"] = np.arange(len(A))
    A["defect_c"] = np.where(A.contested == 1, A.defect, np.nan)
    first_eids = set(A.sort_values("date").groupby(["session", "bill", "chamber"]).eid.first())
    T = A[A.eid.isin(first_eids)].copy()
    T["same_party"] = (T.party == T.p_party).astype(int)
    T["cosponsor"] = [int(any(norm(k.split("|")[1]) == w.split("|")[1] for k in ck)) for ck, w in zip(T.cosp_keys, T.who)]
    T["committee_vote"] = T.committee.astype(int)
    T["senate"] = (T.chamber == "S").astype(int)
    T["own_body"] = (T.chamber == T.body).astype(int)
    for i, (k, _) in enumerate(MOTION + [("other", "")]):
        T["m_" + k] = (T.kind == k).astype(int)
    # replayed records (earlier dates only)
    Ac = A[A.contested == 1]
    T = prior(A, T, ["party", "p_key"], "y", "party_on_sponsor")
    T = prior(Ac, T, ["party", "p_key"], "y", "party_on_sponsor_contested")
    T = prior(A, T, ["who", "p_key"], "y", "member_on_sponsor")
    T = prior(Ac, T, ["party", "room"], "y", "party_in_room_contested")
    T = prior(A, T, ["party", "law"], "y", "party_on_law")
    T = prior(Ac, T, ["party", "law"], "y", "party_on_law_contested")
    T = prior(A, T, ["who", "law"], "y", "member_on_law")
    T = prior(Ac, T, ["who"], "y", "member_contested_yes")
    T = prior(A.dropna(subset=["defect_c"]), T, ["who"], "defect_c", "member_defects_contested", base=0.05)
    Ao = A[A.sp_same == 0]
    T = prior(Ao, T, ["party", "room"], "y", "party_in_room_on_other_party_bills")
    # standing-keyed records: survive a change of majority (2023 House flip)
    T = prior(Ac, T, ["member_maj", "sp_same", "room"], "y", "party_in_room_by_standing_contested")
    T = prior(Ac, T, ["member_maj", "sp_same"], "y", "party_by_standing_contested")
    T = prior(Ac, T, ["who", "sp_same"], "y", "member_on_side_contested")
    T = prior(Ac, T, ["who", "sponsor_maj_here"], "y", "member_on_standing_contested")
    T["cosp_from_member_party"] = [sum(1 for k in ck) for ck in T.cosp_keys]   # count; party split needs roll lookup
    basics = ["same_party", "member_maj", "sponsor_maj_here", "in_maj", "committee_vote", "senate", "own_body"]
    full = basics + ["cosponsor", "n_cosp", "bipartisan"] + [c for c in T.columns if c.startswith("m_")] + \
        [c for c in T.columns if c.startswith(("party_on", "member_on", "party_in", "member_contested", "member_defects"))]
    out = {"features": full}
    for label, (until, test) in {"2023-24": ("2021_0", "2023_0"), "2025-26": ("2023_0", "2025_0")}.items():
        tr, te = T.session <= until, T.session == test
        yt = T.y[te].to_numpy()
        res = {"ballots": int(te.sum()), "always_yes": round(100 * (yt == 1).mean(), 1)}
        cont = T.contested[te].to_numpy() == 1
        other = T.same_party[te].to_numpy() == 0
        # ceiling: every member votes with their own party's majority on that roll call (hindsight)
        ceil = (T.defect[te].to_numpy() == 0)
        res["ceiling_party_position_known"] = round(100 * ceil.mean(), 1)
        from sklearn.metrics import roc_auc_score
        sess = sorted(T.session[tr].unique())
        val = T.session == sess[-1]; fit_v = T.session < sess[-1]
        for nm, cols in {"basics": basics, "full": full}.items():
            mk = lambda: HistGradientBoostingClassifier(max_iter=500, learning_rate=0.05, max_depth=6, l2_regularization=1.0, random_state=0)
            # threshold chosen on the LAST TRAINING session with a model that never saw it (VA protocol) — never on the test
            mv = mk().fit(T.loc[fit_v, cols], T.y[fit_v])
            pv = mv.predict_proba(T.loc[val, cols])[:, 1]
            grid = np.linspace(0.3, 0.8, 51)
            thr = float(grid[np.argmax([((pv >= t) == T.y[val].to_numpy()).mean() for t in grid])])
            m = mk().fit(T.loc[tr, cols], T.y[tr])
            p = m.predict_proba(T.loc[te, cols])[:, 1]
            acc = (p >= thr) == yt
            conf = np.abs(p - thr)
            hard = conf <= np.quantile(conf, 1 / 3)
            oc = other & cont
            res[nm] = {"threshold_from_" + sess[-1]: round(thr, 2), "all": round(100 * acc.mean(), 1), "other_party": round(100 * acc[other].mean(), 1),
                       "contested": round(100 * acc[cont].mean(), 1), "hardest_third": round(100 * acc[hard].mean(), 1),
                       "auc_other_party_contested": round(roc_auc_score(yt[oc], p[oc]), 3) if len(set(yt[oc])) == 2 else None,
                       "acc_other_party_contested": round(100 * acc[oc].mean(), 1)}
            if nm == "full":
                order = np.argsort(-conf)
                res["full"]["confident_calls"] = {f"top {q}%": round(100 * acc[order[: int(len(order) * q / 100)]].mean(), 1) for q in (30, 50, 67, 80)}
        res["always_yes_other_party_contested"] = round(100 * (yt[other & cont] == 1).mean(), 1)
        res["slices"] = {"contested_ballots": int(cont.sum()), "always_yes_contested": round(100 * (yt[cont] == 1).mean(), 1),
                         "ceiling_contested": round(100 * ceil[cont].mean(), 1)}
        out[label] = res
    return out, A


def t_pivotal(A):
    """A member is pivotal on a roll call decided by one vote's margin when on the winning side."""
    ev = A.groupby("eid").agg(yes=("yes", "first"), no=("no", "first"))
    close = ev[(ev.yes - ev.no).abs() <= 1].index
    P = A[A.eid.isin(close)]
    won = P.y == (P.yes > P.no).astype(int)
    return {"one_vote_roll_calls": int(len(close)), "of_roll_calls": int(len(ev)),
            "members_ever_pivotal": int(P[won].who.nunique())}


def t_member_law(A):
    """Does a member's defection on a law (earlier session) predict their defection on the same law later?"""
    D = A[A.contested == 1].dropna(subset=["defect"])
    sess = sorted(D.session.unique())
    rows = []
    for a, b in zip(sess, sess[1:]):
        x = D[D.session == a].groupby(["who", "law"]).defect.agg(["mean", "size"])
        y = D[D.session == b].groupby(["who", "law"]).defect.agg(["mean", "size"])
        gen_a = D[D.session == a].groupby("who").defect.mean()
        j = x.join(y, lsuffix="_a", rsuffix="_b", how="inner")
        j = j[(j.size_a >= 5) & (j.size_b >= 5) & (j.index.get_level_values(1) != "(none)")]
        if len(j) < 30:
            continue
        j["general_a"] = [gen_a.get(w) for w, _l in j.index]
        r_law = j.mean_a.corr(j.mean_b); r_gen = j.general_a.corr(j.mean_b)
        rows.append({"from": a, "to": b, "member_law_pairs": int(len(j)), "r_same_law": round(float(r_law), 3), "r_general_record": round(float(r_gen), 3)})
    return rows


def t_second_chamber(A, F):
    """Origin-chamber final passage: yes votes from the party that runs the second chamber, beyond what passage
    needed, vs the bill passing the second chamber (exact party split, re-test of the batch-1 proxy)."""
    fin = A[(A.kind == "final") & (A.chamber == A.body) & (A.committee_vote == 0) if "committee_vote" in A else (A.kind == "final") & (A.chamber == A.body) & (~A.committee)]
    ev = fin.groupby(["session", "bill", "eid"]).agg(yes=("y", "sum"), n=("y", "size"), body=("body", "first")).reset_index()
    ev = ev.sort_values("eid").groupby(["session", "bill"]).last().reset_index()
    sm = {(s, b): m for s, b, m in zip(F.session, F.second_body, F.second_maj)}
    pb = F.assign(bill=F.body.map({"H": "HB", "S": "SB"}) + " " + F.number.astype(str))
    p2 = {(s, b): (int(x), pp) for s, b, x, pp in zip(pb.session, pb.bill, pb.passed2, pb.p_party)}
    rows = []
    for _, r in ev.iterrows():
        sec_body = {"H": "S", "S": "H"}[r.body]
        m2 = sm.get((r.session, r.bill and sec_body), None)
        info = p2.get((r.session, r.bill))
        if not info:
            continue
        party_yes = fin[(fin.session == r.session) & (fin.bill == r.bill) & (fin.eid == r.eid)]
        m2 = F[(F.session == r.session)].second_maj.iloc[0] if m2 is None else m2
        sec_maj = {(s, b): mm for s, b, mm in zip(F.session, F.body, F.majority)}.get((r.session, sec_body))
        yes_sec = int(((party_yes.party == sec_maj) & (party_yes.y == 1)).sum())
        tot_sec = int((party_yes.party == sec_maj).sum())
        rows.append({"session": r.session, "passed2": info[0], "sponsor_runs_second": int(info[1] == sec_maj),
                     "share_second_party_yes": yes_sec / tot_sec if tot_sec else np.nan})
    D = pd.DataFrame(rows).dropna()
    D = D[D.session < "2025_0"]
    out = {}
    for spon, g in D.groupby("sponsor_runs_second"):
        g = g.copy()
        g["q"] = pd.cut(g.share_second_party_yes, [-0.01, 0.5, 0.9, 0.999, 1.0], labels=["<50%", "50-90%", "90-99%", "all"])
        out["sponsor's party runs chamber 2" if spon else "other party runs chamber 2"] = {
            str(q): {"k": int(x.passed2.sum()), "n": int(len(x))} for q, x in g.groupby("q", observed=True)}
    return out


def t_member_stats(A, B, X):
    """Absence, loyalty, floor win rate, agrees with committee — per member-session, and whether each repeats."""
    allb = B[B.who.notna()].merge(X[["session", "committee"]], left_on="eid", right_index=True)
    absent = allb.assign(a=(allb.opt == "other").astype(int)).groupby(["session", "who"]).a.mean()
    fl = A[A.committee_vote == 0] if "committee_vote" in A else A[~A.committee]
    win = fl.assign(w=(fl.y == (fl.yes > fl.no).astype(int)).astype(int)).groupby(["session", "who"]).w.mean()
    loyal = (1 - A.groupby(["session", "who"]).defect.mean())
    out = {}
    for nm, ser in {"absence": absent, "loyalty": loyal, "floor_win_rate": win}.items():
        piv = ser.unstack(0)
        cols = sorted(piv.columns)
        rs = [round(float(piv[[a, b]].dropna()[a].corr(piv[[a, b]].dropna()[b])), 3) for a, b in zip(cols, cols[1:]) if len(piv[[a, b]].dropna()) > 30]
        out[nm] = {"median": round(float(ser.median()), 4), "session_to_session_r": rs}
    return out


def t_rooms(A, X):
    """Committee roll calls: how many fail, how many split, and which rooms split by party."""
    C = X[X.committee]
    C = C.assign(share_no=C.no / (C.yes + C.no).replace(0, np.nan))
    out = {"committee_roll_calls": int(len(C)), "failed": int((C.no >= C.yes).sum()),
           "contested_10pct_no": int((C.share_no >= 0.10).sum())}
    pl = C[(C.share_no >= 0.10)]
    pl = pl.assign(party_line=((pl.D_side == True) != (pl.R_side == True)))  # noqa: E712
    out["contested_that_split_by_party"] = f"{int(pl.party_line.sum())} of {len(pl)}"
    by = C.assign(cont=(C.share_no >= 0.10).astype(int)).groupby(C.org.str.upper()).cont.agg(["mean", "size"])
    by = by[by["size"] >= 50].sort_values("mean", ascending=False)
    out["most_contested_rooms"] = [{"room": r, "contested_pct": round(100 * v["mean"], 1), "roll_calls": int(v["size"])} for r, v in by.head(8).iterrows()]
    out["least_contested_rooms"] = [{"room": r, "contested_pct": round(100 * v["mean"], 1), "roll_calls": int(v["size"])} for r, v in by.tail(5).iterrows()]
    # era stability of a room's contested rate (2017-20 vs 2021-26)
    e = C.assign(cont=(C.share_no >= 0.10).astype(int), era=np.where(C.session <= "2019_0", "a", "b")).groupby([C.org.str.upper(), "era"]).cont.agg(["mean", "size"]).unstack()
    e = e[(e[("size", "a")] >= 30) & (e[("size", "b")] >= 30)]
    out["room_contested_rate_era_r"] = round(float(e[("mean", "a")].corr(e[("mean", "b")])), 3) if len(e) > 5 else None
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
    res["first_vote"], A = t_first_vote(yn, X, F)
    A["committee_vote"] = A.committee.astype(int)
    res["pivotality"] = t_pivotal(A)
    res["member_law"] = t_member_law(A)
    res["second_chamber_exact"] = t_second_chamber(A, F)
    res["member_stats"] = t_member_stats(A, B, X)
    res["rooms"] = t_rooms(A, X)
    with open(os.path.join(HERE, "results_batch3.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
