#!/usr/bin/env python3
"""Does being PULLED FROM A BLOCK predict a contested vote? (Gemini suggestion, owner 2026-10-27: "complete 2".)

What the data allows (measured on LIS HISTORY.CSV, 2025 + 2026 only -- the authorized years):
  * "Block Vote" is recorded ONLY on Senate FLOOR actions. No committee action carries it and committee report votes
    never share a vote id across bills, so Gemini's committee version ("pulled off the committee's block") is not
    observable in any source we may use.
  * The floor version IS observable and is forward-looking: a Senate bill's second reading ("Constitutional reading
    dispensed ... (on 2nd reading)") is either part of a Block Vote or taken on its own, on an EARLIER day than its
    passage vote. So "read on its own at second reading" is known before the passage roll call.

Test, per bill with both: second-reading form (block / own) -> was the Senate passage roll call contested (any No)?
Also inside bills whose committee report was unanimous (the case a lobbyist would otherwise read as safe).
Counts are natural frequencies (k of n), per docs/design/information_display.md P26.

  python3 block_vote.py
"""
from __future__ import annotations
import os, re, csv, io, gzip, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS = ("20251", "20261")                       # authorized years only (assert_lis_authorized scope)
TALLY = re.compile(r"\((\d+)-Y (\d+)-N")
SECOND = re.compile(r"^S Constitutional reading dispensed.*\(on 2nd reading\)", re.I)
PASSAGE = re.compile(r"^S (Read third time and passed Senate|Passed Senate)", re.I)
REPORT = re.compile(r"^S Reported from ", re.I)


def _history(code):
    p = os.path.join(HERE, "..", "historical_cache", "va", code, "HISTORY.CSV.gz")
    return list(csv.DictReader(io.StringIO(gzip.open(p).read().decode("latin-1"))))


def _d(s):
    m, d, y = s.split("/"); return datetime.date(int(y), int(m), int(d))


def collect():
    out, skipped = [], collections.Counter()
    for code in SESSIONS:
        by = collections.defaultdict(list)
        for r in _history(code):
            by[r["Bill_id"]].append((_d(r["History_date"]), r["History_description"].strip()))
        for bill, acts in by.items():
            acts.sort(key=lambda a: a[0])
            sec = [(d, t) for d, t in acts if SECOND.match(t)]
            pas = [(d, t, TALLY.search(t)) for d, t in acts if PASSAGE.match(t)]
            pas = [(d, t, m) for d, t, m in pas if m]
            if not sec:
                skipped["no second reading on the Senate floor"] += 1; continue
            if not pas:
                skipped["no Senate passage roll call with a tally"] += 1; continue
            d2, t2 = sec[-1]
            later = [(d, t, m) for d, t, m in pas if d > d2]
            if not later:
                skipped["passage on the same day as second reading (not forward-looking)"] += 1; continue
            dp, tp, mp = later[0]
            y, n = int(mp.group(1)), int(mp.group(2))
            rep = [TALLY.search(t) for d, t in acts if REPORT.match(t) and d < d2 and TALLY.search(t)]
            rep_unan = (int(rep[-1].group(2)) == 0) if rep else None
            out.append({"session": code, "bill": bill, "block": "Block Vote" in t2, "contested": n > 0,
                        "failed": y <= n, "rep_unanimous": rep_unan})
    return out, skipped


def main():
    rows, skipped = collect()
    print(f"bills with a Senate second reading and a LATER Senate passage roll call: {len(rows):,}")
    print("not usable:", dict(skipped))
    def line(lab, sub):
        for blk in (True, False):
            g = [r for r in sub if r["block"] == blk]
            c = sum(r["contested"] for r in g); f = sum(r["failed"] for r in g)
            print(f"  {lab:34s} {'in the block' if blk else 'read on its own':16s} contested {c:,} of {len(g):,}"
                  f"   failed {f:,} of {len(g):,}")
    for code in SESSIONS + ("both",):
        sub = [r for r in rows if code == "both" or r["session"] == code]
        print(f"\n{code}")
        line("all", sub)
        line("committee report was unanimous", [r for r in sub if r["rep_unanimous"] is True])
        line("committee report had a No", [r for r in sub if r["rep_unanimous"] is False])


if __name__ == "__main__":
    main()
