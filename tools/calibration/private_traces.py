#!/usr/bin/env python3
"""Public traces of private decisions (owner, 2026-10-16: "the point is we need to learn how to derive the private
decisions from public data").

A private decision often leaves a public trace BEFORE the vote. Four traces, each tested on member votes with
accept.stacked_year_ahead (fit on earlier years, score 2022/2024/2025, pooled per bill, z >= 3, hardest third shown):
  leaders    caucus leaders sign the bill: co-patrons who sit on the Rules committee (in Virginia, the leadership
             committee; rosters in va_chairs 2019-2025), and the Rules chair as a co-patron -- x voter side
  draft      the draft request number printed when the bill is offered ("... 25103270D"): its rank inside the session
             and chamber (early request = planned months ahead) -- x voter side
  deferral   actions in the bill's history BEFORE its first vote that show bargaining: passed by for the day,
             substitute offered/printed, hearings before the vote -- x voter side
  governor   the governor's party (by session) vs the voter's party and the patron's party
  election   the voter's last general-election margin (va_elections/margins.json, Wikipedia election boxes): a caucus
             often lets members in close seats break from the party on hard bills -- margin and close seat (< 10
             points) x voter side
  patron_seat  the PATRON's last margin: leaders hand easy bills to members in close seats, and the other party
             may deny those members a win -- patron close seat / margin x voter side
Run: python3 private_traces.py leaders | draft | deferral | governor | election
"""
from __future__ import annotations
import sys, os, re, json, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV
from corpus import load, _party_lookup

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
_party, person = _party_lookup()
norm = lambda n: person(n) or n
rc = FV.assemble()["rc"]
GOV = {2019: "Democratic", 2020: "Democratic", 2021: "Democratic", 2022: "Republican", 2023: "Republican",
       2024: "Republican", 2025: "Republican", 2026: "Democratic"}
CODE = {2019: "191", 2020: "201", 2021: "211", 2022: "221", 2023: "231", 2024: "241", 2025: "251"}


def leaders():
    """Rules committee members per (year, chamber), matched by surname to that year's sponsors."""
    names = collections.defaultdict(set)
    for (s, b), x in corpus.items():
        if s.isdigit() and x["chief"]:
            names[(int(s), b[0])].add(norm(x["chief"]))
            for c in x["cops"]:
                names[(int(s), b[0])].add(norm(c))
    rules, rules_chair, miss = {}, {}, collections.Counter()
    for yr, code in CODE.items():
        d = json.load(open(os.path.join(HERE, "..", "historical_cache", "va_chairs", f"{code}.json")))
        for cc, v in d.items():
            if not re.search(r"\brules\b", v["name"], re.I):
                continue
            ch = cc[0]; got = set()
            for sur, _code in v.get("members", []):
                s_ = sur.split(",")[0].strip().lower()
                pool = [w for w in names[(yr, ch)] if w.split()[-1].lower() == s_]
                if len(pool) == 1: got.add(pool[0])
                else: miss[len(pool)] += 1
            rules[(yr, ch)] = got
            ch_name = (v.get("chair") or [None])[0]
            pool = [w for w in names[(yr, ch)] if ch_name and w.split()[-1].lower() == ch_name.split(",")[0].strip().lower()]
            rules_chair[(yr, ch)] = pool[0] if len(pool) == 1 else None
    print("Rules members matched per (year, chamber):", {k: len(v) for k, v in sorted(rules.items())}, "unmatched", dict(miss))
    def sig(r):
        b = corpus[r["bill"]]; yr = r["yr"]; ch = r["bill"][1][0]
        R = rules.get((yr, ch), set()); cops = {norm(c) for c in b["cops"]}
        n = len(cops & R); chief_on = float(norm(b["chief"]) in R); rc_ = float(rules_chair.get((yr, ch)) in cops)
        s = float(r["same"])
        return {"ld_n_same": np.log1p(n) * s, "ld_n_other": np.log1p(n) * (1 - s), "ld_chief_same": chief_on * s,
                "ld_chief_other": chief_on * (1 - s), "ld_rchair_same": rc_ * s, "ld_rchair_other": rc_ * (1 - s)}
    AC.stacked_year_ahead(sig, "A  CAUCUS LEADERS SIGN THE BILL (Rules members / Rules chair as co-patrons) x side", ridge=10.0)


def draft():
    LD = re.compile(r"\b(\d{8})D\b")
    num = {}
    for k, b in corpus.items():
        for _d, t, _c in b["actions"][:3]:
            m = LD.search(t)
            if m:
                num[k] = int(m.group(1)); break
    rank = {}
    by = collections.defaultdict(list)
    for k, v in num.items():
        by[(k[0], k[1][0])].append((v, k))
    for g, lst in by.items():
        lst.sort()
        for i, (_v, k) in enumerate(lst):
            rank[k] = i / max(1, len(lst) - 1)
    print(f"draft numbers found for {len(num)} bills")
    def sig(r):
        q = rank.get(r["bill"]); s = float(r["same"])
        if q is None:
            return {"dr_same": 0.0, "dr_other": 0.0, "dr_has": 0.0}
        return {"dr_same": (q - .5) * s, "dr_other": (q - .5) * (1 - s), "dr_has": 1.0}
    AC.stacked_year_ahead(sig, "B  DRAFT REQUEST ORDER (early = planned) x side", ridge=10.0)


def deferral():
    PBD = re.compile(r"passed by for the day", re.I)
    SUBS = re.compile(r"substitute (printed|offered)|offered.*substitute", re.I)
    HEAR = re.compile(r"subcommittee (recommends|failed)|^reported from|^tabled|continued", re.I)
    def sig(r):
        b = corpus[r["bill"]]; d = rc[r["bill"]][0][0]
        before = [t for dd, t, _c in b["actions"] if dd and dd < d]
        f = [sum(bool(PBD.search(t)) for t in before), sum(bool(SUBS.search(t)) for t in before),
             sum(bool(HEAR.search(t)) for t in before)]
        # two inputs x side (six did not converge: the three counts are mostly zero together)
        s = float(r["same"]); bargain = np.log1p(f[0] + f[1]); hear = np.log1p(f[2])
        return {"bargain_same": bargain * s, "bargain_other": bargain * (1 - s), "hear_other": hear * (1 - s)}
    AC.stacked_year_ahead(sig, "C  DEFERRAL / BARGAINING TRACES BEFORE THE VOTE x side", ridge=10.0)


def governor():
    def sig(r):
        g = GOV.get(r["yr"]); b = corpus[r["bill"]]
        v_gov = float(r["party"] == g); p_gov = float(b["chief_party"] == g)
        return {"gov_voter": v_gov, "gov_patron": p_gov, "gov_both": v_gov * p_gov}
    AC.stacked_year_ahead(sig, "D  THE GOVERNOR'S PARTY vs voter and patron", ridge=10.0)


def election(patron=False):
    M = json.load(open(os.path.join(HERE, "..", "historical_cache", "va_elections", "margins.json")))
    # the last general election before each session: House every odd year, Senate 2019 and 2023
    last = lambda yr, ch: str(max(int(y) for y in M if ch in M[y] and int(y) < yr))
    idx = {}
    for y, chs in M.items():
        for ch, winners in chs.items():
            for name, v in winners.items():
                idx[(y, ch, norm(name))] = v
    sur = collections.defaultdict(list)
    for (y, ch, n), v in list(idx.items()):
        sur[(y, ch, n.split()[-1].lower())].append(v)
    seen, hit = collections.Counter(), collections.Counter()
    def look(r):
        ch = "S" if r["chamber_S"] else "H"
        if patron:  # the patron sits in the bill's own chamber
            ch = r["bill"][1][0]; who = norm(corpus[r["bill"]]["chief"] or "?")
        else:
            who = norm(r["who"])
        y = last(r["yr"], ch)
        v = idx.get((y, ch, who))
        if v is None:
            pool = sur.get((y, ch, who.split()[-1].lower()), [])
            v = pool[0] if len(pool) == 1 else None
        seen[r["yr"]] += 1; hit[r["yr"]] += v is not None
        return v
    def sig(r):
        v = look(r); s = float(r["same"])
        if v is None:
            return {"el_close_same": 0.0, "el_close_other": 0.0, "el_marg_same": 0.0, "el_marg_other": 0.0, "el_has": 0.0}
        m = 1.0 if v["uncontested"] else min(1.0, v["margin"]); close = float(m < 0.10)
        return {"el_close_same": close * s, "el_close_other": close * (1 - s), "el_marg_same": (m - .3) * s,
                "el_marg_other": (m - .3) * (1 - s), "el_has": 1.0}
    AC.stacked_year_ahead(sig, "F  PATRON'S SEAT: patron's last margin / close seat x voter side" if patron else
                          "E  ELECTORAL PRESSURE: last general-election margin / close seat x side", ridge=10.0)
    print("    ballots matched to an election result:", {y: f"{hit[y]}/{seen[y]} ({hit[y] / seen[y]:.1%})" for y in sorted(seen)})


if __name__ == "__main__":
    {"leaders": leaders, "draft": draft, "deferral": deferral, "governor": governor, "election": election,
     "patron_seat": lambda: election(patron=True)}[sys.argv[1]]()
