#!/usr/bin/env python3
"""California analysis frame — one row per regular-session AB/SB, every input known on the day of filing, plus the
outcomes the tests score. Built from the pubinfo tables pulled by fetch_session_tables.py (sessions 2015-2025).

STRUCTURAL ONLY (the same rule as the intake): routing reads BILL_HISTORY_TBL location fields and END_STATUS, never the
action prose; filing-day facts come from the INTRODUCED version (BILL_VERSION_TBL VERSION_NUM 99 / action
"Introduced") — its subject, vote required, appropriation, fiscal committee, urgency, local program, tax levy and its
own author list (authors are recorded per version, so the filing-day co-authors are known, unlike PA's final list).

Outcomes:
  * referred  — the bill reached a policy committee (a history row in its origin house with a committee code)
  * out_first — it got out of that first committee: a (PASS) vote there, or a later origin-house row at a different
                committee or on the floor (the Virginia / Pennsylvania test's outcome)
  * law       — it carries a chapter number
Member votes: every roll call in BILL_DETAIL_VOTE_TBL (AYE / NOE / ABS), with the member's party from LEGISLATOR_TBL.
"""
from __future__ import annotations

import collections
import os
import pickle
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
from states import ca_pubinfo  # noqa: E402

SESSIONS = (2015, 2017, 2019, 2021, 2023, 2025)
CACHE = os.path.join(HERE, ".ca_frame.pkl")
SCHEMA = ca_pubinfo.load_schema(open(os.path.join(ROOT, "tools", "historical_cache", "ca", "pubinfo_load.zip"), "rb").read())
PARTY = {"DEM": "D", "REP": "R"}


def rows(year, table):
    path = os.path.join(ROOT, "tools", "historical_cache", "ca", str(year), "tables", f"{table}.dat")
    cols = SCHEMA[table]
    bad = 0
    with open(path, encoding="utf-8", errors="replace", newline="\n") as f:
        for raw in f:
            parts = raw.rstrip("\n").split("\t")
            if len(parts) != len(cols):
                bad += 1
                continue
            yield {c: ca_pubinfo._field(v) for c, v in zip(cols, parts)}
    if bad:
        print(f"  {year} {table}: {bad} malformed rows skipped (counted)", file=sys.stderr)


def session_frame(year):
    sess = f"{year}{year + 1}"
    prefix = f"{sess}0"
    bills = {b["BILL_ID"]: b for b in rows(year, "BILL_TBL")
             if b["BILL_ID"].startswith(prefix) and b["MEASURE_TYPE"] in ("AB", "SB")}
    party = {}
    for lg in rows(year, "LEGISLATOR_TBL"):
        if lg["SESSION_YEAR"] == sess:
            party[(lg["HOUSE_TYPE"], lg["AUTHOR_NAME"])] = (PARTY.get(lg["PARTY"], lg["PARTY"]), lg["DISTRICT"])
    by_name = collections.defaultdict(set)
    for (h, n), (p, _d) in party.items():
        by_name[n].add(p)
    intro = {}
    for v in rows(year, "BILL_VERSION_TBL"):
        if v["BILL_ID"] in bills and v["BILL_VERSION_ACTION"] == "Introduced":
            intro[v["BILL_ID"]] = v
    authors = collections.defaultdict(list)
    iv = {v["BILL_VERSION_ID"]: k for k, v in intro.items()}
    for a in rows(year, "BILL_VERSION_AUTHORS_TBL"):
        if a["BILL_VERSION_ID"] in iv:
            authors[iv[a["BILL_VERSION_ID"]]].append(a)
    names = {r["LOCATION_CODE"]: r["LONG_DESCRIPTION"] or r["DESCRIPTION"] for r in rows(year, "LOCATION_CODE_TBL")
             if r["SESSION_YEAR"] == sess}
    hist = collections.defaultdict(list)
    for h in rows(year, "BILL_HISTORY_TBL"):
        if h["BILL_ID"] in bills and h["ACTION_STATUS"] != "Rescinded":
            hist[h["BILL_ID"]].append(h)
    passes = collections.defaultdict(set)
    for s in rows(year, "BILL_SUMMARY_VOTE_TBL"):
        if s["BILL_ID"] in bills and "PASS" in s["VOTE_RESULT"].upper():
            passes[s["BILL_ID"]].add(s["LOCATION_CODE"])
    out = []
    for bid, b in bills.items():
        mt = b["MEASURE_TYPE"]
        origin = "Assembly" if mt == "AB" else "Senate"
        hs = sorted(hist.get(bid, []), key=lambda h: (h["ACTION_DATE"], int(h["ACTION_SEQUENCE"] or 0)))
        v = intro.get(bid)
        intro_date = (v["BILL_VERSION_ACTION_DATE"] if v else (hs[0]["ACTION_DATE"] if hs else ""))[:10]
        first = None
        for h in hs:
            if h["PRIMARY_LOCATION"] == origin and h["SECONDARY_LOCATION"] == "Committee" and h["TERNARY_LOCATION"]:
                first = h
                break
        out_first = False
        if first is not None:
            fc = first["TERNARY_LOCATION"]
            if fc in passes[bid]:
                out_first = True
            else:
                after = False
                for h in hs:
                    if h is first:
                        after = True
                        continue
                    if after and h["PRIMARY_LOCATION"] == origin and (
                            h["SECONDARY_LOCATION"] == "Floor"
                            or (h["SECONDARY_LOCATION"] == "Committee" and h["TERNARY_LOCATION"] not in ("", fc))):
                        out_first = True
                        break
        auth = authors.get(bid, [])
        lead = [a for a in auth if a["CONTRIBUTION"].upper().startswith("LEAD")]
        lead_a = lead[0] if lead else None
        lead_name = lead_a["NAME"] if lead_a else ""
        lead_house = (lead_a["HOUSE"] or "")[:1].upper() if lead_a else ""
        is_committee_bill = bool(lead_a and lead_a["TYPE"].upper().startswith("COMMITTEE"))
        lp = party.get((lead_house, lead_name), ("", ""))[0] if lead_a else ""
        if not lp and lead_name in by_name and len(by_name[lead_name]) == 1:
            lp = next(iter(by_name[lead_name]))
        co = [a for a in auth if a not in lead]
        co_party = [party.get(((a["HOUSE"] or "")[:1].upper(), a["NAME"]), ("", ""))[0] for a in co]
        last = hs[-1] if hs else None
        out.append({
            "session": year, "bill": bid, "type": mt, "senate": int(mt == "SB"), "origin": origin,
            "intro_date": intro_date, "subject": (v["SUBJECT"] if v else "").strip(),
            "vote_2_3": int(bool(v) and v["VOTE_REQUIRED"].lower().startswith("two")),
            "appropriation": int(bool(v) and v["APPROPRIATION"] == "Yes"),
            "fiscal": int(bool(v) and v["FISCAL_COMMITTEE"] == "Yes"),
            "local_program": int(bool(v) and v["LOCAL_PROGRAM"] == "Yes"),
            "urgency": int(bool(v) and v["URGENCY"] == "Yes"), "taxlevy": int(bool(v) and v["TAXLEVY"] == "Yes"),
            "author": f"{lead_house}:{lead_name}", "author_name": lead_name, "author_party": lp,
            "committee_bill": int(is_committee_bill),
            "n_coauthors": len(co), "n_co_other_party": sum(1 for p in co_party if p and lp and p != lp),
            "n_co_other_house": sum(1 for a in co if (a["HOUSE"] or "")[:1].upper() and (a["HOUSE"] or "")[:1].upper() != lead_house),
            "referred": int(first is not None),
            "first_code": first["TERNARY_LOCATION"] if first is not None else "",
            "first_committee": f"{origin} {names.get(first['TERNARY_LOCATION'], first['TERNARY_LOCATION'])}" if first is not None else "",
            "referred_date": first["ACTION_DATE"][:10] if first is not None else "",
            "out_first": int(out_first), "law": int(bool(b["CHAPTER_NUM"])), "status": b["CURRENT_STATUS"],
            "last_house": last["PRIMARY_LOCATION"] if last else "", "last_secondary": last["SECONDARY_LOCATION"] if last else "",
            "last_code": last["TERNARY_LOCATION"] if last else "", "last_end": last["END_STATUS"] if last else "",
            "last_date": last["ACTION_DATE"][:10] if last else "",
            "last_committee": "",
        })
        # the last committee the bill sat in (for kill points), structural
        for h in reversed(hs):
            if h["SECONDARY_LOCATION"] == "Committee" and h["TERNARY_LOCATION"]:
                out[-1]["last_committee"] = f"{h['PRIMARY_LOCATION']} {names.get(h['TERNARY_LOCATION'], h['TERNARY_LOCATION'])}"
                out[-1]["last_committee_house"] = h["PRIMARY_LOCATION"]
                break
    return pd.DataFrame(out), party, names


def vote_frame(year, party, bills_set):
    by_name = collections.defaultdict(set)
    for (h, n), (p, _d) in party.items():
        by_name[n].add(p)
    out = []
    for r in rows(year, "BILL_DETAIL_VOTE_TBL"):
        if r["BILL_ID"] not in bills_set or r["VOTE_CODE"] not in ("AYE", "NOE", "ABS"):
            continue
        loc = r["LOCATION_CODE"]
        h = "A" if loc.startswith(("CX", "AF")) else "S" if loc.startswith(("CS", "SF")) else ""
        p = party.get((h, r["LEGISLATOR_NAME"]), ("", ""))[0]
        if not p and len(by_name.get(r["LEGISLATOR_NAME"], ())) == 1:
            p = next(iter(by_name[r["LEGISLATOR_NAME"]]))
        out.append((year, r["BILL_ID"], loc, r["LEGISLATOR_NAME"], r["VOTE_DATE_TIME"], int(r["VOTE_DATE_SEQ"] or 0),
                    r["MOTION_ID"], r["VOTE_CODE"], p, h))
    return pd.DataFrame(out, columns=["session", "bill", "loc", "member", "when", "seq", "motion", "vote", "mparty", "mhouse"])


def build(force=False):
    if os.path.exists(CACHE) and not force:
        return pickle.load(open(CACHE, "rb"))
    frames, votes = [], []
    for y in SESSIONS:
        f, party, _names = session_frame(y)
        frames.append(f)
        votes.append(vote_frame(y, party, set(f.bill)))
        print(y, len(f), "bills", len(votes[-1]), "member votes", file=sys.stderr)
    F = pd.concat(frames, ignore_index=True)
    V = pd.concat(votes, ignore_index=True)
    pickle.dump((F, V), open(CACHE, "wb"))
    return F, V


if __name__ == "__main__":
    F, V = build(force=True)
    print(F.groupby("session")[["referred", "out_first", "law"]].agg(["sum", "count"]))
    print("author party unknown:", (F.author_party == "").sum(), "of", len(F))
    print("votes with no member party:", (V.mparty == "").sum(), "of", len(V))
