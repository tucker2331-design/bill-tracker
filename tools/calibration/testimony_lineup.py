#!/usr/bin/env python3
"""Testimony by WHO and WHICH SIDE -- the stakeholder lineup (owner, 2026-10-14: "testimony data has no influence in
every context and use of the data? the type of testimony, from who, about what").

The first test (stakeholder_effect.py) used only comment VOLUME and wording -> no gain. This one uses the organizations
themselves. Data: HODSpeak written testimony, re-collected with each organization's side (va_hodspeak_v2; counts and
organization names only -- no person's name, locality or text is stored). House committees only (the House runs
HODSpeak), 2021 / 2022 / 2024 / 2025.

AN ORGANIZATION'S LEAN IS LEARNED, NEVER ASSIGNED. From earlier years only: on the bills an organization supported
(opposed), how did each party actually vote at the first vote? lean = (Democrats' yes share - Republicans' yes share) on
bills it supported, minus the same on bills it opposed; shrunk toward 0 for organizations seen on few bills.
For a bill, the LINEUP = sum of supporters' leans - sum of opponents' leans (positive = a coalition that, in the past,
lined up with Democrats).

Two tests, both year-ahead (fit on earlier years, score the next; pooled per bill; accept at z >= 3):
  1. MEMBER VOTES   accept.stacked_year_ahead with lineup x voter party, organizations for/against, two-sided fight
  2. FATE           among House bills that drew testimony before their first decision (testimony exists only once a bill
                    is on an agenda, so presence itself would leak), does the lineup change P(gets out of committee)?
"""
from __future__ import annotations
import sys, os, json, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV

SRC = os.path.join(HERE, "..", "historical_cache", "va_hodspeak_v2")
YEARS = tuple(int(y) for y in os.environ.get("LINEUP_YEARS", "2021,2022,2024,2025").split(","))
SHRINK = 3.0


def cards():
    """(session, 'HB 41') -> list of (meeting date, {org: [support, oppose, unclear]}, counts)."""
    out = collections.defaultdict(list)
    for y in YEARS:
        path = os.path.join(SRC, f"{y}.json")
        if not os.path.exists(path):
            raise SystemExit(f"missing {path} -- run hodspeak_comments.py --v2 {y}")
        for m in json.load(open(path))["meetings"].values():
            for bill, c in m["bills"].items():
                out[(str(y), bill[:2] + " " + bill[2:])].append((m["date"], c.get("org_stances", {}), c))
    return out


def party_yes(rc):
    """(session, bill) -> {party: yes share} at the bill's FIRST recorded vote."""
    res = {}
    for k, lst in rc.items():
        if not lst:
            continue
        ballots = lst[0][4]
        res[k] = {p: np.mean([s for _w, pp, s in ballots if pp == p]) for p in FV.PARTIES
                  if any(pp == p for _w, pp, _s in ballots)}
    return res


def leans(C, PY, before_year):
    """organization -> shrunk lean from bills in sessions < before_year."""
    acc = collections.defaultdict(lambda: [0.0, 0])
    D, R = FV.PARTIES
    for k, lst in C.items():
        if int(k[0]) >= before_year or k not in PY or D not in PY[k] or R not in PY[k]:
            continue
        gap = PY[k][D] - PY[k][R]
        for _d, st, _c in lst:
            for org, (s, o, _u) in st.items():
                side = (s > 0) - (o > 0)
                if side:
                    acc[org][0] += side * gap; acc[org][1] += 1
    return {org: v / (n + SHRINK) for org, (v, n) in acc.items()}


def lineup(lst, L, day):
    sup = opp = 0; score = 0.0; known = 0
    for d, st, _c in lst:
        if d > day:
            continue
        for org, (s, o, _u) in st.items():
            side = (s > 0) - (o > 0)
            if side > 0: sup += 1
            if side < 0: opp += 1
            if side and org in L:
                score += side * L[org]; known += 1
    return {"lu_score": score, "lu_known": math.log1p(known), "lu_for": math.log1p(sup), "lu_against": math.log1p(opp),
            "lu_two_sided": float(sup > 0 and opp > 0)}


def main():
    C = cards()
    D_ = FV.assemble(); rc = D_["rc"]
    PY = party_yes(rc)
    Lby = {y: leans(C, PY, y) for y in YEARS}
    print({y: len(L) for y, L in Lby.items()}, "organizations with a learned lean (earlier years only)")
    D = FV.PARTIES[0]

    def sig(r):
        k = r["bill"]; yr = int(k[0])
        if yr not in Lby:
            return {c: 0.0 for c in ("lu_score_dem", "lu_score_rep", "lu_for", "lu_against", "lu_two_sided")}
        f = lineup(C.get(k, []), Lby[yr], rc[k][0][0])
        dem = float(r["party"] == D)
        return {"lu_score_dem": f["lu_score"] * dem, "lu_score_rep": f["lu_score"] * (1 - dem),
                "lu_for": f["lu_for"], "lu_against": f["lu_against"], "lu_two_sided": f["lu_two_sided"]}
    AC.stacked_year_ahead(sig, "TESTIMONY LINEUP (learned organization leans) -- all ballots", ridge=10.0)
    AC.stacked_year_ahead(sig, "TESTIMONY LINEUP -- ballots on bills with testimony", only_covered=True, ridge=10.0)

    # descriptive: does the lineup line up with how the parties split, on bills it covers (year-ahead leans)?
    rows = []
    for k, lst in C.items():
        yr = int(k[0])
        if k in PY and D in PY[k] and FV.PARTIES[1] in PY[k] and rc.get(k):
            f = lineup(lst, Lby[yr], rc[k][0][0])
            if f["lu_known"] > 0:
                rows.append((f["lu_score"], PY[k][D] - PY[k][FV.PARTIES[1]], f["lu_two_sided"]))
    if rows:
        a = np.array(rows)
        print(f"\nbills with a known-lean lineup and a first vote: {len(a)}; correlation of lineup with the actual "
              f"party gap (D yes - R yes): r = {np.corrcoef(a[:, 0], a[:, 1])[0, 1]:.3f}")
        for lab, m in (("two-sided fight", a[:, 2] == 1), ("one-sided", a[:, 2] == 0)):
            print(f"  {lab:16s} n={m.sum():5d}  mean party gap {a[m, 1].mean():+.3f}  |gap| {np.abs(a[m, 1]).mean():.3f}")


def fate_test():
    """Among House bills with testimony dated on/before their first committee decision: does the lineup change the
    chance of getting out of committee, beyond fate.py's own year-ahead prediction? Stacked logistic, fitted on earlier
    years' covered bills, scored on the next; per-bill log loss, pooled z."""
    import fate as FT, stats as ST
    C = cards(); D_ = FV.assemble(); PY = party_yes(D_["rc"])
    Lby = {y: leans(C, PY, y) for y in YEARS}
    R, _ = FT.bills(tuple(range(2020, max(YEARS) + 1))); R = [r for r in R if r["standing"] in ("majority", "minority")]
    F = FT.featurise(R); cols = sorted(F[0]); X = np.array([[f[c] for c in cols] for f in F], float)
    Y = np.array([FT.MCLASSES.index(FT._m(r)) for r in R]); yr = np.array([r["year"] for r in R])
    def decided(r):
        for d, t, _c in r["actions"]:
            if any(p_.search(t.strip()) for _k, p_ in FT.RULES) or FT.LEFT.match(t.strip()):
                return d
        return "9999"
    data = {}
    for t in YEARS:
        tr, te = yr < t, yr == t
        if not tr.any():
            continue
        Bp = FT.baseline([r for r, m in zip(R, tr) if m], [r for r, m in zip(R, te) if m])
        P = FT.BLEND * FT.fit_predict(X[tr], Y[tr], X[te]) + (1 - FT.BLEND) * Bp
        rows = []
        for r, pv, yy in zip([r for r, m in zip(R, te) if m], P[:, 0], Y[te]):
            k = (r["session"], r["bill"])
            if r["bill"].startswith("HB") and k in C:
                dd = decided(r)
                if any(d <= dd for d, _s, _c in C[k]):
                    f = lineup(C[k], Lby[t], dd)
                    sign = 1.0 if r["chief_party"] == FV.PARTIES[0] else -1.0     # lineup toward the PATRON's party
                    rows.append((np.log(np.clip(pv, 1e-6, 1 - 1e-6) / (1 - np.clip(pv, 1e-6, 1 - 1e-6))),
                                 [f["lu_score"] * sign, f["lu_for"], f["lu_against"], f["lu_two_sided"]], float(yy == 0)))
        data[t] = rows
        print(f"fate {t}: House bills with testimony before their first decision: {len(rows)}", flush=True)
    names = ["lu_toward_patron", "lu_for", "lu_against", "lu_two_sided"]
    ys = sorted(data); diffs = []
    for i, t in enumerate(ys[1:], 1):
        tr_rows = [x for y in ys[:i] for x in data[y]]; te_rows = data[t]
        def fit(cols_n):
            Xt = np.array([[x[0]] + x[1][:cols_n] for x in tr_rows]); yt = np.array([x[2] for x in tr_rows])
            f = ST.logit(Xt, yt, ["lg"] + names[:cols_n], ridge=10.0, tol=1e-7, max_iter=200)
            b = np.array([f[n][0] for n in ["const", "lg"] + names[:cols_n]])
            Xe = np.array([[1.0, x[0]] + x[1][:cols_n] for x in te_rows])
            with np.errstate(all="ignore"):
                return 1 / (1 + np.exp(-(Xe @ b)))
        p0, p1 = fit(0), fit(len(names)); y = np.array([x[2] for x in te_rows])
        ll = lambda p: -(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
        d = ll(p0) - ll(p1); diffs.append(d)
        print(f"  fate {t}: n {len(y)}, advanced {y.mean():.1%}, log-loss gain {d.mean():+.4f}", flush=True)
    d = np.concatenate(diffs)
    print(f"POOLED fate (testimony lineup): gain {d.mean():+.4f}, z = {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):.1f}")


if __name__ == "__main__":
    main()
    fate_test()
