#!/usr/bin/env python3
"""The owner's strategic-calculation traces (2026-10-23: "most bills are shot down ... bc of a strategic calculation
balancing polarities"). All structural, all knowable before the vote; each stacked on the locked model with
accept.stacked_year_ahead (year-ahead, z >= 3 to accept), x voter side:
  lownum    leadership priorities get the first bill numbers ("hb1 was the 15 dollar minimum wage"): bill number <= 25,
            x patron in the majority
  fight     a big fight holds up related bills: share of THIS session's earlier first votes on the same coarse subject
            that split on party lines (shrunk), and whether the patron is in the minority
  fund      the general fund is already packed: log number of bills with a fiscal impact statement that already passed
            a first vote this session in this chamber, x this bill has a fiscal impact statement; + even (budget) year
  election  election years: House sessions in odd years (members face November), x side, x close seat (< 10 points)
  veto      a governor's veto comes back: the bill is a near-copy (content similarity >= 0.5) of a bill vetoed in an
            earlier session, x side, x the governor's party now vs then
Run: python3 strategy_traces.py <mode>
"""
from __future__ import annotations
import sys, os, re, json, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import accept as AC, first_vote as FV
from corpus import load, _party_lookup

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
_party, person = _party_lookup()
D = FV.assemble(); rc, nb = D["rc"], D["nb"]
GOV = {2017: "Democratic", 2018: "Democratic", 2019: "Democratic", 2020: "Democratic", 2021: "Democratic",
       2022: "Republican", 2023: "Republican", 2024: "Republican", 2025: "Republican", 2026: "Democratic"}
num = lambda b: int(re.sub(r"\D", "", b) or 0)


def lownum():
    def sig(r):
        b = corpus[r["bill"]]; low = float(num(r["bill"][1]) <= 25); maj = float(b["standing"] == "majority"); s = float(r["same"])
        return {"ln_maj_same": low * maj * s, "ln_maj_other": low * maj * (1 - s), "ln_min": low * (1 - maj)}
    AC.stacked_year_ahead(sig, "LOW BILL NUMBER (<= 25) x majority patron x side", ridge=10.0)


def _first_votes():
    """(session, date, key, party_line?, fiscal?, passed?) for every first vote."""
    out = []
    for k, lst in rc.items():
        b = corpus.get(k)
        if not b or not lst or not lst[0][0] or lst[0][0] == "9999" or b["chief_party"] not in FV.PARTIES:
            continue
        d, _o, _v, _ven, bl = lst[0]
        by = collections.defaultdict(list)
        for _w, pp, sup in bl:
            by[pp].append(sup)
        pl = len(by) == 2 and all(len(set(v)) == 1 for v in by.values()) and len({v[0] for v in by.values()}) == 2
        fis = any("impact statement" in t.lower() for dd, t, _c in b["actions"] if dd and dd < d)
        out.append((k[0], d, k, pl, fis, sum(x[2] for x in bl) > len(bl) / 2))
    return sorted(out, key=lambda x: (x[0], x[1]))


def fight():
    SUBJ = {}
    for kk, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        ss, bb = kk.split("|", 1); SUBJ[(ss, bb)] = v
    ev = _first_votes()
    feat = {}
    by_s = collections.defaultdict(list)
    for s, d, k, pl, _f, _p in ev:
        by_s[s].append((d, k, pl))
    for s, lst in by_s.items():
        c = collections.Counter(); i = 0
        for d, k, pl in lst:
            while i < len(lst) and lst[i][0] < d:
                for x in SUBJ.get(lst[i][1], []):
                    c[(x, "n")] += 1; c[(x, "p")] += lst[i][2]
                i += 1
            subs = SUBJ.get(k, [])
            n = sum(c[(x, "n")] for x in subs); p = sum(c[(x, "p")] for x in subs)
            feat[k] = ((p + 2 * .2) / (n + 10), math.log1p(n))
    def sig(r):
        f = feat.get(r["bill"])
        if not f:
            return {"fi_same": 0.0, "fi_other": 0.0, "fi_min": 0.0}
        x = (f[0] - .2) * 5; s = float(r["same"]); mino = float(corpus[r["bill"]]["standing"] != "majority")
        return {"fi_same": x * s, "fi_other": x * (1 - s), "fi_min": x * mino}
    AC.stacked_year_ahead(sig, "BIG FIGHT: party-line share on the same subject so far this session x side / minority", ridge=10.0)


def fund():
    ev = _first_votes(); feat = {}
    by = collections.defaultdict(list)
    for s, d, k, _pl, fis, passed in ev:
        by[(s, k[1][0])].append((d, k, fis, passed))
    for g, lst in by.items():
        i = 0; n = 0
        for d, k, fis, _p in lst:
            while i < len(lst) and lst[i][0] < d:
                n += lst[i][2] and lst[i][3]; i += 1
            feat[k] = (math.log1p(n), float(fis))
    def sig(r):
        f = feat.get(r["bill"])
        if not f:
            return {"fu_fis_same": 0.0, "fu_fis_other": 0.0, "fu_even_fis": 0.0}
        load_, fis = f; s = float(r["same"]); even = float(r["yr"] % 2 == 0)
        return {"fu_fis_same": (load_ - 3) * fis * s, "fu_fis_other": (load_ - 3) * fis * (1 - s), "fu_even_fis": even * fis}
    AC.stacked_year_ahead(sig, "GENERAL FUND LOAD: fiscal bills already passed this session x this bill has a cost x side", ridge=10.0)


def election():
    M = json.load(open(os.path.join(HERE, "..", "historical_cache", "va_elections", "margins.json")))
    last = lambda yr, ch: str(max(int(y) for y in M if ch in M[y] and int(y) < yr))
    idx = {}
    for y, chs in M.items():
        for ch, w in chs.items():
            for name, v in w.items():
                idx[(y, ch, person(name) or name)] = v
    def sig(r):
        ch = "S" if r["chamber_S"] else "H"; s = float(r["same"])
        ey = float(ch == "H" and r["yr"] % 2 == 1)
        v = idx.get((last(r["yr"], ch), ch, person(r["who"]) or r["who"]))
        close = float(bool(v) and not v["uncontested"] and v["margin"] < .10)
        return {"el_same": ey * s, "el_other": ey * (1 - s), "el_close_other": ey * close * (1 - s)}
    AC.stacked_year_ahead(sig, "ELECTION YEAR (House, odd years) x side x close seat", ridge=10.0)


def veto():
    VETO = re.compile(r"vetoed by governor|governor'?s veto|veto sustained", re.I)
    vetoed = {k for k, b in corpus.items() if any(VETO.search(t) for _d, t, _c in b["actions"])}
    def sig(r):
        k = r["bill"]; best = None
        for c, j in nb.get(k, []):
            if c[0] < k[0] and c in vetoed and j >= .5:
                best = c; break
        if not best:
            return {"ve_same": 0.0, "ve_other": 0.0, "ve_govflip": 0.0}
        s = float(r["same"]); flip = float(GOV.get(int(k[0][:4])) != GOV.get(int(best[0][:4])))
        return {"ve_same": s, "ve_other": 1 - s, "ve_govflip": flip * (1 - s)}
    print("bills vetoed in the corpus:", len(vetoed))
    AC.stacked_year_ahead(sig, "VETOED BEFORE, REFILED: near-copy of a vetoed bill x side x governor changed party", ridge=10.0)


if __name__ == "__main__":
    {"lownum": lownum, "fight": fight, "fund": fund, "election": election, "veto": veto}[sys.argv[1]]()
