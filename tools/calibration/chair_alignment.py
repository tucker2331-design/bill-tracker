#!/usr/bin/env python3
"""Chair ALIGNMENT with the bill, and money ties between patron and chair -> does the bill get out of committee?

Owner, 2026-10-14: "chair alignment is how much the chair aligns with the bill, not how relevant the chair's sponsorship
is." So, measured from the chair's own record, before the session (earlier sessions only):
  al_pat_rate    the chair's yes rate on THIS PATRON's earlier bills (recorded votes)           + its count
  al_sim_rate    the chair's yes rate on earlier bills with near-identical summaries to THIS bill + its count
  al_ip_dist     distance on the left-right map between the chair and the bill's sponsors (ideal points fitted on
                 earlier years: first_vote.ideal_points)
  al_same_party  chair in the patron's party
MONEY (ELECT filings held: 2023-10, 2024-01 -- the 2023 election; ELECT now refuses automated requests, so no more
months were fetched): for 2024 and 2025 bills only
  mo_chair_gave  the chair's campaign committee gave to the patron's campaign committee
  mo_shared      overlap of the two campaigns' donor lists (Jaccard, named donors)
  mo_receipts    the patron's total contributions in those filings (log)
Tests: (1) same patron, same session, bills sent to DIFFERENT committees -- does a better-aligned chair go with more
bills getting out? (2) year-ahead: fate.py model + alignment, rolling 2022-2025, pooled per-bill z >= 3.
"""
from __future__ import annotations
import sys, os, re, gzip, csv, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "historical_cache"))
import numpy as np
import fate as FT, first_vote as FV, influence_fate as IF
from math import comb


def chair_records():
    """(chair, patron) -> [yes, n] on the patron's bills by year; (chair, (session,bill)) ballots; per-year IP."""
    D = FV.assemble(); rc = D["rc"]
    from corpus import load, _party_lookup
    _p, person = _party_lookup(); norm = lambda n: person(n) or n
    chief = {(b["session"], b["bill"]): norm(b["chief"]) for b in load()["bills"] if b["chief"]}
    on_patron = collections.defaultdict(lambda: [0, 0])        # (voter, patron, year) -> yes, n
    ballots_of = collections.defaultdict(dict)                 # (session,bill) -> {voter: sup} (first vote)
    for k, lst in rc.items():
        if not k[0].isdigit() or not lst:
            continue
        for date, _o, _v, ven, ballots in lst[:1]:
            for w, _pp, s in ballots:
                ballots_of[k][w] = s
                if k in chief:
                    v = on_patron[(w, chief[k], int(k[0]))]; v[0] += s; v[1] += 1
    return D["nb"], ballots_of, on_patron, FV.ideal_points()


def alignment(R, built, recs):
    norm, pty, edges_y, eff, chair = built
    nb, ballots_of, on_patron, IP = recs
    out = []
    for r in R:
        y = r["year"]; P = norm(r["chief"]); C = chair.get((y, f"{r['bill'][0]}:{IF.nrm(r['comm'])}"))
        f = {"al_known": float(C is not None)}
        if C is None:
            out.append({**f, "al_pat_rate": 0.5, "al_pat_n": 0.0, "al_sim_rate": 0.5, "al_sim_n": 0.0,
                        "al_ip_dist": 0.0, "al_ip_has": 0.0, "al_same_party": 0.0}); continue
        k_ = n_ = 0
        for yy in range(2017, y):
            v = on_patron.get((C, P, yy))
            if v: k_ += v[0]; n_ += v[1]
        f["al_pat_rate"] = (k_ + 2) / (n_ + 4); f["al_pat_n"] = math.log1p(n_)
        ks = ns = 0
        for c, j in nb.get((r["session"], r["bill"]), []):
            if c[0].isdigit() and int(c[0]) < y and j >= 0.3 and C in ballots_of.get(c, {}):
                ks += ballots_of[c][C]; ns += 1
        f["al_sim_rate"] = (ks + 1) / (ns + 2); f["al_sim_n"] = math.log1p(ns)
        pts = IP.get(y, {}); spons = [norm(x) for x in [r["chief"]] + r["cops"]]
        sp = [pts[s][0] for s in spons if s in pts]
        if C in pts and sp:
            f["al_ip_dist"] = abs(pts[C][0] - float(np.mean(sp))); f["al_ip_has"] = 1.0
        else:
            f["al_ip_dist"] = 0.0; f["al_ip_has"] = 0.0
        f["al_same_party"] = float(pty.get(C) == r["chief_party"])
        out.append(f)
    return out


def money(R, built):
    """Money ties for 2024/2025 bills from the 2023 election filings held locally."""
    import finance as F
    norm = built[0]; chair = built[4]
    months = ["2023_10", "2024_01"]
    coms = F.committees(months)
    rep_com, com_name = {}, {}
    for m in months:
        with gzip.open(os.path.join(F.CACHE, f"{m}_Report.csv.gz"), "rt", errors="replace") as fh:
            for r in csv.DictReader(fh):
                rep_com[r["ReportId"]] = r["CommitteeCode"]; com_name[r["CommitteeCode"]] = r.get("CommitteeName", "")
    # legislator -> committee codes, via the candidate name on their committees
    leg_com = collections.defaultdict(set)
    for code, c in coms.items():
        leg_com[norm(c["candidate"])].add(code)
    nm = lambda s: re.sub(r"[^a-z ]", "", (s or "").lower()).strip()
    name_to_leg = {nm(com_name.get(code, "")): leg for leg, codes in leg_com.items() for code in codes if com_name.get(code)}
    donors = collections.defaultdict(set); receipts = collections.Counter(); gave = set(); bad_amount = 0
    for m in months:
        with gzip.open(os.path.join(F.CACHE, f"{m}_ScheduleA.csv.gz"), "rt", errors="replace") as fh:
            for r in csv.DictReader(fh):
                to = rep_com.get(r["ReportId"])
                if not to:
                    continue
                dn = nm(f"{r['FirstName']} {r['LastOrCompanyName']}" if r["IsIndividual"] == "True" else r["LastOrCompanyName"])
                donors[to].add(dn)
                try:
                    receipts[to] += float(r["Amount"] or 0)
                except ValueError:
                    bad_amount += 1                               # counted and reported below, never silent
                giver = name_to_leg.get(nm(r["LastOrCompanyName"]))
                if giver:
                    for c in leg_com:
                        if to in leg_com[c]:
                            gave.add((giver, c))
    print(f"money: {len(leg_com)} legislators with committees; {len(gave)} legislator-to-legislator gifts found; "
          f"{bad_amount} contribution rows with an unreadable amount")
    out = []
    for r in R:
        y = r["year"]; P = norm(r["chief"]); C = chair.get((y, f"{r['bill'][0]}:{IF.nrm(r['comm'])}"))
        if y not in (2024, 2025) or C is None or P not in leg_com or C not in leg_com:
            out.append({"mo_has": 0.0, "mo_chair_gave": 0.0, "mo_shared": 0.0, "mo_receipts": 0.0}); continue
        dp = set().union(*(donors[c] for c in leg_com[P])); dc = set().union(*(donors[c] for c in leg_com[C]))
        out.append({"mo_has": 1.0, "mo_chair_gave": float((C, P) in gave),
                    "mo_shared": len(dp & dc) / len(dp | dc) if dp | dc else 0.0,
                    "mo_receipts": math.log1p(sum(receipts[c] for c in leg_com[P]))})
    return out


def within_patron(R, A, col, cut, adv, label):
    g = collections.defaultdict(lambda: {True: [], False: []})
    for r, a, ok in zip(R, A, adv):
        if a.get("al_known", 1) and a.get("mo_has", 1):
            g[(r["chief"], r["year"])][a[col] >= cut].append(ok)
    both = {k: d for k, d in g.items() if d[True] and d[False]}
    if not both:
        print(f"  {label}: no patron-session with both kinds"); return
    at = sum(sum(d[True]) for d in both.values()); nt = sum(len(d[True]) for d in both.values())
    af = sum(sum(d[False]) for d in both.values()); nf = sum(len(d[False]) for d in both.values())
    more = sum(np.mean(d[True]) > np.mean(d[False]) for d in both.values())
    less = sum(np.mean(d[True]) < np.mean(d[False]) for d in both.values())
    n = int(more + less); k = int(max(more, less)); p = 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1
    print(f"  {label}: same patron, same session -- {at}/{nt} ({at/max(nt,1):.1%}) vs {af}/{nf} ({af/max(nf,1):.1%}); "
          f"patrons better {more}, worse {less}, p = {p:.2g}")


def main():
    R, _ = FT.bills(); R = [r for r in R if r["standing"] in ("majority", "minority")]
    built = IF.build(); recs = chair_records()
    A = alignment(R, built, recs); M = money(R, built)
    adv = [FT._m(r) == "ADVANCED" for r in R]
    print("\nCHAIR ALIGNMENT, same patron and session, bills before differently-aligned chairs:")
    within_patron(R, A, "al_pat_rate", 0.75, adv, "chair backed >=75% of this patron's earlier bills")
    within_patron(R, A, "al_sim_rate", 0.75, adv, "chair backed >=75% of near-identical earlier bills")
    within_patron(R, A, "al_same_party", 1.0, adv, "chair in the patron's party")
    print("\nMONEY TIES (2024-2025 bills):")
    within_patron(R, M, "mo_chair_gave", 1.0, adv, "the chair's campaign gave to the patron's")
    within_patron(R, M, "mo_shared", 0.05, adv, "the two campaigns share >=5% of donors")
    F = FT.featurise(R); cols = sorted(F[0])
    Y = np.array([FT.MCLASSES.index(FT._m(r)) for r in R]); yr = np.array([r["year"] for r in R])
    X0 = np.array([[f[c] for c in cols] for f in F], float)
    acol = ["al_known", "al_pat_rate", "al_pat_n", "al_sim_rate", "al_sim_n", "al_ip_dist", "al_ip_has", "al_same_party"]
    X1 = np.column_stack([X0, np.array([[a[c] for c in acol] for a in A], float)])
    diffs = []
    for t in (2022, 2023, 2024, 2025):
        tr, te = yr < t, yr == t
        Bp = FT.baseline([r for r, m in zip(R, tr) if m], [r for r, m in zip(R, te) if m])
        p0 = FT.BLEND * FT.fit_predict(X0[tr], Y[tr], X0[te]) + (1 - FT.BLEND) * Bp
        p1 = FT.BLEND * FT.fit_predict(X1[tr], Y[tr], X1[te]) + (1 - FT.BLEND) * Bp
        d = FT._mll(p0, Y[te]) - FT._mll(p1, Y[te]); diffs.append(d)
        print(f"  chair alignment {t}: log-loss gain {d.mean():+.4f}", flush=True)
    d = np.concatenate(diffs)
    print(f"POOLED chair alignment: gain {d.mean():+.4f}, z = {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):.1f}")


if __name__ == "__main__":
    main()
