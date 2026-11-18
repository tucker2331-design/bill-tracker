#!/usr/bin/env python3
"""The Pennsylvania analysis corpus — ONE parse of every Bill History export, shared by every PA test.

Owner, 2026-11-17: "run VA-style stats on PA ... should we collect all the data and then run the tests all at
once or batch them by type?" Answer built here: collect each SOURCE once, normalise it into one bill table, then
run the tests in batches by the source they need (docs/testing/pa_predictive_plan.md). Every test imports
`load()`; none re-reads the XML.

SOURCE: PA's own Bill History exports (www.palegis.us/data, bulk ZIP per two-year session, no use restriction),
cached with headers under tools/historical_cache/pa/<session>/. Sessions 2009_0 .. 2025_0 (regular only).

STRUCTURAL ONLY (Standard #3): every field below is an XML element or attribute; the only text-derived field is
`title_form` (the official title's opening words, "An Act amending" vs "An Act providing for"), used for
INTERNAL analysis exactly as Virginia's enacting-clause test used its own bill text.

Each bill record (HB/SB only for the tests; resolutions are counted and kept aside):
  session, sid (e.g. "2023_HB1"), body (H/S), number, subtype, title, title_form,
  prime {surname, party, district, body}, cosponsors [{...}], n_cosponsors, n_majority_cosp, n_minority_cosp,
  majority (the chamber majority party that session, from the session's own sponsor roll), prime_in_majority,
  memo (a co-sponsorship memo preceded it), pn_count (printer's numbers = text versions),
  actions [(date, chamber, verb, cls, committee, tally)], first_cmte, intro_date,
  reported1 (reported out of its first committee in the origin chamber), reported_amended1,
  recommitted, passed_origin, passed_second, defeated_origin, law, vetoed, first_tally (yeas, nays) on passage.
"""
from __future__ import annotations

import collections
import datetime
import glob
import os
import pickle
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
from states import pa_adapter as A  # noqa: E402  (PA's verb classes: the structural vocabulary)

CACHE = os.path.join(HERE, ".cache_corpus.pkl")
SESSIONS = ["2009_0", "2011_0", "2013_0", "2015_0", "2017_0", "2019_0", "2021_0", "2023_0", "2025_0"]
_TALLY = re.compile(r"\((\d+)\s*-\s*(\d+)\)")


def _date(s):
    try:
        return datetime.datetime.strptime((s or "").strip(), "%m/%d/%y").date()
    except ValueError:
        return None


def _title_form(t):
    t = (t or "").strip().lower()
    if t.startswith("a joint resolution"):
        return "joint_resolution"
    m = re.match(r"an act (amending|providing|establishing|creating|repealing|relating|authorizing|designating|"
                 r"making|reenacting|regulating|requiring|prohibiting|further|to|for|in)\b", t)
    if not m:
        return "other"
    w = m.group(1)
    return {"amending": "amend", "further": "amend", "reenacting": "amend", "providing": "provide",
            "establishing": "establish", "creating": "establish", "repealing": "repeal",
            "making": "appropriate"}.get(w, "other_act")


def _sponsor(s):
    return {"surname": (s.text or "").strip().upper(), "party": (s.get("party") or "").strip(),
            "district": (s.get("districtNumber") or s.get("distictNumber") or "").strip(),
            "body": (s.get("body") or "").strip(), "seq": (s.get("sequenceNumber") or "").strip()}


def _export_path(session):
    files = glob.glob(os.path.join(ROOT, "tools", "historical_cache", "pa", session, "PA-Bill-History-*.zip"))
    if len(files) != 1:
        raise FileNotFoundError(f"{session}: expected one export ZIP, found {files}")
    return files[0]


def parse_session(session):
    z = zipfile.ZipFile(_export_path(session))
    x = ET.fromstring(z.read(z.namelist()[0]))
    year = int(session.split("_")[0])
    bills, resolutions = [], 0
    roll = collections.defaultdict(set)          # body -> {(party, district)} who sponsored anything this session
    raw = []
    for b in x.iter("bill"):
        body, typ, num = ((b.findtext(k) or "").strip() for k in ("body", "type", "number"))
        sps = [_sponsor(s) for s in b.iter("sponsor")]
        for s in sps:
            if s["body"] and s["party"] and s["district"]:
                roll[s["body"]].add((s["party"], s["district"]))
        if typ != "B":
            resolutions += 1
            continue
        raw.append((b, body, num, sps))
    majority = {}
    for body, mem in roll.items():
        c = collections.Counter(p for p, _ in mem)
        majority[body] = c.most_common(1)[0][0]
    for b, body, num, sps in raw:
        prime = next((s for s in sps if s["seq"] == "01"), sps[0] if sps else None)
        cos = [s for s in sps if s is not prime]
        maj = majority.get(body)
        acts = []
        for a in b.iter("action"):
            verb = (a.findtext("verb") or "").strip()
            tally = _TALLY.search(a.findtext("rollCallVote") or "")
            acts.append((_date(a.findtext("date")), (a.get("actionChamber") or "").strip(), verb,
                         A.VERB_CLASS.get(verb, "unclassified"), (a.findtext("committee") or "").strip(),
                         (int(tally.group(1)), int(tally.group(2))) if tally else None))
        other = "S" if body == "H" else "H"
        first_ref = next((i for i, a in enumerate(acts) if a[3] == "referral" and a[2] == "Referred to" and a[1] == body), None)
        first_cmte = acts[first_ref][4] if first_ref is not None else ""
        rep1 = None
        if first_ref is not None:
            rep1 = next((a for a in acts[first_ref + 1:] if a[1] == body and a[3] == "reported"), None)
        pass_o = next((a for a in acts if a[1] == body and a[3] == "passed"), None)
        pass_s = next((a for a in acts if a[1] == other and a[3] == "passed"), None)
        dates = [a[0] for a in acts if a[0]]
        memo_el = b.find("cosponsorshipMemo")
        title = (b.findtext("shortTitle") or "").strip()
        bills.append({
            "session": session, "year": year, "sid": f"{year}_{body}B{int(num)}", "body": body, "number": int(num),
            "subtype": (b.findtext("subType") or "").strip(), "title": title, "title_form": _title_form(title),
            "prime": prime, "cosponsors": cos, "n_cosponsors": len(cos),
            "n_majority_cosp": sum(1 for s in cos if s["party"] == maj),
            "n_minority_cosp": sum(1 for s in cos if s["party"] and s["party"] != maj),
            "majority": maj, "prime_in_majority": bool(prime and prime["party"] == maj),
            "memo": bool(memo_el is not None and (memo_el.get("memoUrl") or "").strip()),
            "pn_count": len(list(b.iter("number"))) - 1 if b.find("printersNumberHistory") is not None else 0,
            "actions": acts, "first_cmte": first_cmte, "intro_date": min(dates) if dates else None,
            "reported1": rep1 is not None, "reported_amended1": bool(rep1 and "amended" in rep1[2].lower()),
            "recommitted": any(a[2] == "Re-committed to" for a in acts),
            "passed_origin": pass_o is not None, "passed_second": pass_s is not None,
            "defeated_origin": any(a[1] == body and a[3] == "defeated" for a in acts),
            "law": any(a[3] in ("approved", "act") or a[2].startswith("Became Law without") for a in acts),
            "vetoed": any(a[2].startswith("Vetoed by the Governor") for a in acts),
            "first_tally": pass_o[5] if pass_o else None,
        })
    return {"bills": bills, "resolutions": resolutions, "majority": majority,
            "members": {k: len(v) for k, v in roll.items()}}


def load(refresh=False):
    """{session: parse_session(session)} for every cached session, pickled (rebuilt when an export changes)."""
    stamp = {s: os.path.getmtime(_export_path(s)) for s in SESSIONS}
    if not refresh and os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            got = pickle.load(f)
        if got.get("_stamp") == stamp:
            return got["data"]
    data = {s: parse_session(s) for s in SESSIONS}
    with open(CACHE, "wb") as f:
        pickle.dump({"_stamp": stamp, "data": data}, f)
    return data


if __name__ == "__main__":
    D = load(refresh="--refresh" in sys.argv)
    for s, d in D.items():
        B = d["bills"]
        print(f"{s}: {len(B):,} bills ({d['resolutions']:,} resolutions aside) · majority H={d['majority'].get('H')} "
              f"S={d['majority'].get('S')} · sponsoring members H={d['members'].get('H')} S={d['members'].get('S')} · "
              f"reported1 {sum(b['reported1'] for b in B):,} · passed origin {sum(b['passed_origin'] for b in B):,} · "
              f"law {sum(b['law'] for b in B):,}")
