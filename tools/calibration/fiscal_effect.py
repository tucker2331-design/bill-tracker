#!/usr/bin/env python3
"""Do bills that COST money fail more? (owner, 2026-10-14: "go deeper in fiscal stuff also are you saying that bills that
spend money arent as likely to fail as bills that dont?")

Source: the first Department of Planning and Budget fiscal impact statement per bill, 2025 and 2026
(tools/historical_cache/fiscal_statements.py -> va_fiscal/{year}.json). Each statement's PUBLISHED date comes from
HISTORY.CSV (the 'Fiscal Impact Statement from Department of Planning and Budget' action; refid <bill>F122).

COST BANDS (from the statement itself): no state impact / indeterminate / under $1 million a year / $1-10 million /
over $10 million (largest yearly general-fund or nongeneral-fund expenditure in its tables, or the amount its summary
states). Budget amendment necessary: yes / no.

Outcomes: (1) gets out of the FIRST committee (fate.py), (2) passes its chamber (any later stage counts: money bills
are re-referred to Appropriations / Finance and many die THERE, after the first committee).
Comparisons: by patron standing; and SAME PATRON, SAME SESSION (a patron's costly bills vs their no-cost bills).
Timing rule (audit #145): a statement counts as known only if published before the committee's first decision.
"""
from __future__ import annotations
import sys, os, re, json, gzip, csv, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import fate as FT
from math import comb

FIS = os.path.join(HERE, "..", "historical_cache", "va_fiscal")
PASS_CH = re.compile(r"^(read third time and )?passed (house|senate)\b|^vote: passage", re.I)


def statement_dates(year):
    """bill -> date of the first DPB statement (HISTORY.CSV)."""
    out = {}
    with gzip.open(os.path.join(HERE, "..", "historical_cache", "va", f"{year}1", "HISTORY.CSV.gz"), "rt",
                   errors="replace") as fh:
        for r in csv.DictReader(fh):
            ref = (r["History_refid"] or "").strip(); desc = r["History_description"] or ""
            # agency 122 = DPB; 2025 writes "Impact statement from DPB", 2026 "... Department of Planning and Budget"
            if re.search(r"F122(?:\.PDF)?$", ref) and ("DPB" in desc or "Planning and Budget" in desc):
                m, d, y = r["History_date"].split("/")
                iso = f"{y}-{int(m):02d}-{int(d):02d}"
                b = r["Bill_id"].strip(); b = f"{b[:2]} {b[2:]}"
                if b not in out or iso < out[b]:
                    out[b] = iso
    return out


def band(f):
    if not f or "parse_error" in f:
        return None
    amt = max(f.get("gf_cost_max", 0), f.get("ngf_cost_max", 0), f.get("summary_amount_max", 0))
    if f.get("no_impact") and amt == 0:
        return "no state cost"
    if f.get("indeterminate") and amt == 0:
        return "indeterminate"
    if amt == 0:
        return "no amount stated"
    return "under $1M" if amt < 1e6 else "$1M-$10M" if amt < 1e7 else "over $10M"


def first_decision(r):
    for d, t, _c in r["actions"]:
        if any(p.search(t.strip()) for _k, p in FT.RULES) or FT.LEFT.match(t.strip()):
            return d
    return "9999"


def main():
    R, _ = FT.bills(range(2025, 2027))
    R = [r for r in R if r["standing"] in ("majority", "minority")]
    rows = []
    for y in (2025, 2026):
        st = json.load(open(os.path.join(FIS, f"{y}.json"))); sd = statement_dates(y)
        for r in [r for r in R if r["year"] == y]:
            key = r["bill"].replace(" ", "")
            f = st.get(key)
            known = f is not None and sd.get(r["bill"], "9999") < first_decision(r)
            rows.append({"r": r, "f": f, "band": band(f), "known": known,
                         "amend": (f or {}).get("budget_amendment"),
                         "adv": FT._m(r) == "ADVANCED",
                         "passed_chamber": any(PASS_CH.match(t.strip()) for _d, t, _c in r["actions"])})
    print(f"bills {len(rows)}; with a DPB statement {sum(x['f'] is not None for x in rows)}; "
          f"statement out before the first committee decision {sum(x['known'] for x in rows)}")
    order = ["no state cost", "indeterminate", "no amount stated", "under $1M", "$1M-$10M", "over $10M"]
    for outcome, lab in (("adv", "got out of the first committee"), ("passed_chamber", "passed its chamber")):
        print(f"\n{lab.upper()} -- by cost (statements published before the first decision)")
        for st_ in ("majority", "minority"):
            parts = []
            for b in order:
                s = [x[outcome] for x in rows if x["known"] and x["band"] == b and x["r"]["standing"] == st_]
                if s:
                    parts.append(f"{b} {sum(s)}/{len(s)} ({np.mean(s):.0%})")
            print(f"  {st_:8s} " + " | ".join(parts))
        for st_ in ("majority", "minority"):
            a = [x[outcome] for x in rows if x["known"] and x["amend"] == 1 and x["r"]["standing"] == st_]
            b = [x[outcome] for x in rows if x["known"] and x["amend"] == 0 and x["r"]["standing"] == st_]
            if a and b:
                print(f"  {st_:8s} budget amendment needed {sum(a)}/{len(a)} ({np.mean(a):.0%}) vs not {sum(b)}/{len(b)} ({np.mean(b):.0%})")
        # same patron, same session: costly (>= $1M) vs no state cost
        g = collections.defaultdict(lambda: {True: [], False: []})
        for x in rows:
            if x["known"] and x["band"] in ("no state cost", "$1M-$10M", "over $10M"):
                g[(x["r"]["chief"], x["r"]["year"])][x["band"] != "no state cost"].append(x[outcome])
        both = {k: d for k, d in g.items() if d[True] and d[False]}
        if both:
            at = sum(sum(d[True]) for d in both.values()); nt = sum(len(d[True]) for d in both.values())
            af = sum(sum(d[False]) for d in both.values()); nf = sum(len(d[False]) for d in both.values())
            more = sum(np.mean(d[True]) > np.mean(d[False]) for d in both.values())
            less = sum(np.mean(d[True]) < np.mean(d[False]) for d in both.values())
            n = int(more + less); k = int(max(more, less))
            p = 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1
            print(f"  same patron & session: costing $1M+ {at}/{nt} ({at/nt:.0%}) vs no state cost {af}/{nf} ({af/nf:.0%}); "
                  f"patrons better with cost {more}, worse {less}, p = {p:.2g}")


if __name__ == "__main__":
    main()
