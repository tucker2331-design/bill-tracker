#!/usr/bin/env python3
"""A FORWARD test, frozen before the outcome exists. Every other number in this folder was scored in hindsight.

Owner, 2026-09-16: "recalculating every session is only good in retrospect." This is the answer for the one
claim that can be tested forward right now. As of the freeze date, every bill continued out of the 2026
session carries the tag `Continued · 12 of 1,348 came back` ([[testing/bill_states]]). The claim implied by
that tag, written down BEFORE the result:

    PREDICTION: of the bills continued out of 2026, at most ~1% get any committee action in the 2027
    session; the rest receive "Left in <committee>" before the session convenes.

The file written here is the prediction. It is committed with its SHA-256 printed so a later edit is
visible. Scoring (`--score`) reads the 2027 LIS history once it exists and compares -- nothing about the
prediction is recomputed at scoring time.

Source: Open States 2027 carryover records (CC0) cross-checked against cached LIS 20261 HISTORY.CSV (keyless
blob). No network access.
"""
from __future__ import annotations
import sys, os, re, json, gzip, csv, hashlib, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "frozen", "continued_2026_to_2027.json")
CONT = re.compile(r"continued to (?:next session|2027) in (.+?)(?: \(|$)", re.I)
SPSESS = re.compile(r"sp\.?\s*sess", re.I)


def freeze():
    if os.path.exists(OUT):
        raise SystemExit(f"already frozen: {OUT} -- a forward test is written ONCE; delete deliberately, never overwrite")
    path = os.path.join(HERE, "..", "historical_cache", "va", "20261", "HISTORY.CSV.gz")
    by = collections.defaultdict(list)
    with gzip.open(path, "rt", errors="replace") as f:
        for r in csv.DictReader(f):
            by[r["Bill_id"].strip()].append((r["History_date"].strip(), (r["History_description"] or "").strip()))
    rows = []
    for b, ev in sorted(by.items()):
        if not re.match(r"^[HS]B\d+$", b):
            continue
        hits = [(d, CONT.search(t).group(1)) for d, t in ev if CONT.search(t) and not SPSESS.search(t)]
        if hits:
            rows.append({"bill": b, "continued_on": hits[-1][0], "committee": hits[-1][1].strip()})
    doc = {"frozen_on": datetime.date.today().isoformat(),
           "claim": "bill_states: Continued - 12 of 1,348 came back",
           "prediction": "<= ~1% of these bills get any committee action in the 2027 session",
           "n": len(rows), "bills": rows}
    blob = json.dumps(doc, indent=1, sort_keys=True).encode()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "wb").write(blob)
    print(f"froze {len(rows)} continued bills -> {OUT}\nsha256 {hashlib.sha256(blob).hexdigest()}")


def score(history_2027):
    doc = json.load(open(OUT))
    by = collections.defaultdict(list)
    with gzip.open(history_2027, "rt", errors="replace") if history_2027.endswith(".gz") \
            else open(history_2027, errors="replace") as f:
        for r in csv.DictReader(f):
            by[r["Bill_id"].strip()].append((r["History_date"].strip(), (r["History_description"] or "").strip()))
    moved = [b["bill"] for b in doc["bills"]
             if any(d.endswith("2027") and not re.search(r"left in|continued from|impact statement", t, re.I)
                    for d, t in by.get(b["bill"], []))]
    print(f"frozen {doc['frozen_on']}: {len(moved)} of {doc['n']} moved in 2027 = {len(moved)/doc['n']:.1%}")
    print(f"prediction was: {doc['prediction']}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--score":
        score(sys.argv[2])
    else:
        freeze()
