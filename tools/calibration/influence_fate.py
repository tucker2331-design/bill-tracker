#!/usr/bin/env python3
"""Relationships and influence -> does the bill get out of its first committee? (owner, 2026-10-14: "influence scores
and relationship maps definitely could have influence if you find the numbers ... lobbying is very much relationship
based"; "replicate [Gemini's 'committee chair alignment'] with serious findings")

Earlier work tested relationships on MEMBER VOTES only (round 5: co-sponsorship ties, reciprocity -- no gain; round 8:
chairs -- no gain). Never on the bill's FATE, which is where agenda power (the chair decides what is heard) should show.

Inputs per bill, from EARLIER sessions only unless stated (public record: bill sponsors and actions, chair rosters):
  NETWORK   net_in        distinct legislators who co-sponsored the patron's earlier bills        (log1p)
            net_in_cross  ... of them from the other party                                         (log1p)
            net_out       distinct legislators whose bills the patron co-sponsored                (log1p)
            net_rank      the patron's PageRank in the earlier co-sponsorship graph (x 1000)
  CHAIR     ch_is_patron  the patron chairs the committee the bill is referred to (this session)
            ch_same_party the chair is in the patron's party
            ch_backed     times the chair co-sponsored the patron's earlier bills                  (log1p)
            ch_backed_by  times the patron co-sponsored the chair's earlier bills                  (log1p)
            ch_on_bill    the chair is a co-patron of THIS bill (at filing)
  EFFECT.   eff_floor     share of the patron's earlier bills that passed their chamber (smoothed)
            eff_law       share that became law (smoothed)
            -- a Legislative-Effectiveness-style record (Bucchianeri, Volden & Wiseman, APSR 2025: stages a member's
               bills reach). Built from our own records; CEL's published scores are not used (their site terms
               forbid use without written permission).
Test: fate.py's model + one group at a time, rolling origin 2022-2025, per-bill multiclass log loss, pooled z >= 3.
Chairs exist 2019-2025 (legacy_chairs.py), validated against the 2025 API roster in chairs_yearahead.py.
"""
from __future__ import annotations
import sys, os, re, json, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import fate as FT
from corpus import load, _party_lookup

CH = os.path.join(HERE, "..", "historical_cache", "va_chairs")
CODE = {2019: "191", 2020: "201", 2021: "211", 2022: "221", 2023: "231", 2024: "241", 2025: "251"}
nrm = lambda s: re.sub(r"[^a-z ]", "", (s or "").lower().replace("&", "and")).strip()
PASS_CH = re.compile(r"^(read third time and )?passed (house|senate)\b", re.I)


def pagerank(edges, nodes, d=0.85, it=40):
    idx = {n: i for i, n in enumerate(nodes)}; N = len(nodes)
    out = collections.defaultdict(float)
    for (a, b), w in edges.items():
        out[a] += w
    pr = np.full(N, 1.0 / N)
    for _ in range(it):
        new = np.full(N, (1 - d) / N)
        for (a, b), w in edges.items():
            new[idx[b]] += d * pr[idx[a]] * w / out[a]
        pr = new / new.sum()
    return {n: pr[idx[n]] for n in nodes}


def build():
    party, person = _party_lookup()
    norm = lambda n: person(n) or n
    allb = [b for b in load()["bills"] if b["session"].isdigit() and re.match(r"^[HS]B \d+$", b["bill"])]
    no_chief = sum(1 for b in allb if not b["chief"])
    allb = [b for b in allb if b["chief"]]
    print(f"bills without a recorded chief patron, left out of the network: {no_chief}")
    # co-sponsorship edges by year: supporter -> patron
    edges_y = collections.defaultdict(collections.Counter)
    pty = {}
    for b in allb:
        y = int(b["session"]); c = norm(b["chief"]); pty[c] = b["chief_party"]
        for k, kp in zip(b["cops"], b["cop_parties"] + [None] * len(b["cops"])):
            kk = norm(k)
            if kk != c:
                edges_y[y][(kk, c)] += 1
                if kp: pty.setdefault(kk, kp)
    # effectiveness record by (patron, year)
    eff = collections.defaultdict(lambda: [0, 0, 0])          # n, passed chamber, law
    for b in allb:
        c = norm(b["chief"]); e = eff[(c, int(b["session"]))]
        e[0] += 1; e[1] += any(PASS_CH.match(t.strip()) for _d, t, _c in b["actions"]); e[2] += bool(b["passed"])
    # chairs: (year, "H:committee") -> chair name, matched to legislators who sponsored bills that year
    names_y = collections.defaultdict(set)
    for b in allb:
        names_y[(int(b["session"]), b["bill"][0])].add(norm(b["chief"]))
    miss = collections.Counter()
    def match(raw, yr, ch):
        sur, _, ini = raw.partition(",")
        sur = sur.strip().lower(); ini = ini.replace(".", "").replace(" ", "").lower()
        pool = [w for w in names_y[(yr, ch)] if w.split()[-1].lower() == sur]
        if len(pool) > 1 and ini:
            pool = [w for w in pool if w[0].lower() == ini[0]]
        if len(pool) == 1:
            return pool[0]
        miss[len(pool)] += 1
        return None
    chair = {}
    for yr, code in CODE.items():
        for cc, v in json.load(open(os.path.join(CH, f"{code}.json"))).items():
            ch = cc[0]; name = nrm(re.sub(r"^(House|Senate)\s+", "", v["name"]))
            raw = (v.get("chairs") or ([v["chair"]] if v.get("chair") else []))
            got = [match(s, yr, ch) for s, _ in raw]
            chair[(yr, f"{ch}:{name}")] = next((g for g in got if g), None)
    print(f"chairs matched {sum(v is not None for v in chair.values())} of {len(chair)}; unmatched by pool size {dict(miss)}")
    return norm, pty, edges_y, eff, chair


def featurise(R, built):
    norm, pty, edges_y, eff, chair = built
    years = sorted({r["year"] for r in R})
    pr_cache, agg_cache = {}, {}
    for y in years:
        agg = collections.Counter()
        for yy, e in edges_y.items():
            if yy < y:
                agg.update(e)
        agg_cache[y] = agg
        nodes = sorted({a for a, _ in agg} | {b for _, b in agg})
        pr_cache[y] = pagerank(agg, nodes) if nodes else {}
    insup = {y: collections.defaultdict(set) for y in years}; outsup = {y: collections.defaultdict(set) for y in years}
    for y in years:
        for (a, b), w in agg_cache[y].items():
            insup[y][b].add(a); outsup[y][a].add(b)
    out, unmatched = [], collections.Counter()
    for r in R:
        y = r["year"]; P = norm(r["chief"]); pp = r["chief_party"]
        ins = insup[y].get(P, set())
        f = {"net_in": math.log1p(len(ins)), "net_in_cross": math.log1p(sum(pty.get(a) not in (None, pp) for a in ins)),
             "net_out": math.log1p(len(outsup[y].get(P, set()))), "net_rank": 1000 * pr_cache[y].get(P, 0.0)}
        n = s1 = s2 = 0
        for yy in range(2017, y):
            e = eff.get((P, yy))
            if e:
                n += e[0]; s1 += e[1]; s2 += e[2]
        f["eff_floor"] = (s1 + 2) / (n + 5); f["eff_law"] = (s2 + 1.5) / (n + 5)
        key = (y, f"{r['bill'][0]}:{nrm(r['comm'])}")
        C = chair.get(key)
        if key not in chair:
            unmatched["committee not in roster"] += 1
        elif C is None:
            unmatched["chair name unmatched"] += 1
        agg = agg_cache[y]
        f.update({"ch_known": float(C is not None), "ch_is_patron": float(C == P and C is not None),
                  "ch_same_party": float(C is not None and pty.get(C) == pp),
                  "ch_backed": math.log1p(agg.get((C, P), 0)) if C else 0.0,
                  "ch_backed_by": math.log1p(agg.get((P, C), 0)) if C else 0.0,
                  "ch_on_bill": float(C is not None and C in {norm(k) for k in r["cops"]})})
        out.append(f)
    print("chair lookup misses:", dict(unmatched), "of", len(R))
    return out


GROUPS = {"network": ["net_in", "net_in_cross", "net_out", "net_rank"],
          "chair ties": ["ch_known", "ch_is_patron", "ch_same_party", "ch_backed", "ch_backed_by", "ch_on_bill"],
          "effectiveness record": ["eff_floor", "eff_law"]}


def main():
    R, _ = FT.bills(); R = [r for r in R if r["standing"] in ("majority", "minority")]
    F = FT.featurise(R); base_cols = sorted(F[0])
    G = featurise(R, build())
    Y = np.array([FT.MCLASSES.index(FT._m(r)) for r in R]); yr = np.array([r["year"] for r in R])
    adv = (Y == 0)
    # descriptive: advance rate by chair tie, minority patrons only (where agenda power should bite)
    mino = np.array([r["standing"] == "minority" for r in R])
    for c in ("ch_same_party", "ch_backed", "ch_on_bill", "ch_is_patron"):
        v = np.array([g[c] > 0 for g in G])
        for lab, m in (("all", np.ones(len(R), bool)), ("minority patrons", mino)):
            a, b = adv[m & v], adv[m & ~v]
            if len(a) and len(b):
                print(f"  {c:14s} {lab:17s} yes: {a.mean():.1%} (n={len(a)})  no: {b.mean():.1%} (n={len(b)})")
    for gname, cols in GROUPS.items():
        diffs = []
        for t in (2022, 2023, 2024, 2025):
            tr, te = yr < t, yr == t
            X0 = np.array([[f[c] for c in base_cols] for f in F], float)
            X1 = np.column_stack([X0, np.array([[g[c] for c in cols] for g in G], float)])
            Bp = FT.baseline([r for r, m in zip(R, tr) if m], [r for r, m in zip(R, te) if m])
            p0 = FT.BLEND * FT.fit_predict(X0[tr], Y[tr], X0[te]) + (1 - FT.BLEND) * Bp
            p1 = FT.BLEND * FT.fit_predict(X1[tr], Y[tr], X1[te]) + (1 - FT.BLEND) * Bp
            d = FT._mll(p0, Y[te]) - FT._mll(p1, Y[te]); diffs.append(d)
            print(f"  {gname:22s} {t}: log-loss gain {d.mean():+.4f}", flush=True)
        d = np.concatenate(diffs); z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
        print(f"POOLED {gname}: gain {d.mean():+.4f}, z = {z:.1f} -> {'ACCEPT' if z >= 3 else 'reject'}", flush=True)


if __name__ == "__main__":
    main()
