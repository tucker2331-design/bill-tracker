#!/usr/bin/env python3
"""Virginia campaign-finance filings from ELECT — the agency, not an aggregator.

SOURCE AND TERMS. `https://apps.elections.virginia.gov/SBE_CSV/CF/<YYYY_MM>/` — the Virginia Department
of Elections, where candidates and committees actually file. No key, no registration, no attestation;
monthly directories from 1999. The reasoning for using the agency rather than VPAP is already settled in
[[knowledge/campaign_finance_source]]: an aggregator's terms govern their compilation, not the underlying
public records.

WHICH FILES MATTER, AND WHY ScheduleH IS THE ONE TO REACH FOR FIRST
  Report.csv     6 MB   filing metadata: CandidateName, Party, OfficeSought, District, ElectionCycle
  ScheduleH.csv  0.8 MB SUMMARY — carries `TotalReceiptsThisElectionCycle`, i.e. the whole race in one
                        small file. Use this for money totals instead of summing 30 MB of ScheduleA.
  ScheduleA.csv 20-30 MB every individual contribution: donor name, EMPLOYER, OCCUPATION, amount.
                        Only needed when you want WHO gave, not HOW MUCH.

TWO FIELD TRAPS, BOTH MEASURED
  * `IsGeneralAssembly` is **always False** in these files — a dead column. Filtering on it returns zero
    rows. `OfficeSought` ("Member, House Of Delegates" / "Member, Senate Of Virginia") is the only route.
  * `OfficeSought` is itself BLANK on ~1,000 reports per month, so filtering on it silently drops real
    legislators (Ebbin, Rouse, Lopez all vanish). Matching only 34% of sitting legislators is the
    consequence, and closing it means joining on committee identity rather than office text — the
    "real engineering work" flagged in [[knowledge/campaign_finance_source]], still open.

  `District` is free text: "93", "#59", "086" all appear. Normalise before joining.

Run:  python3 tools/historical_cache/finance.py <YYYY_MM> [<YYYY_MM> ...]
"""
from __future__ import annotations
import gzip, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "va_finance")
BASE = "https://apps.elections.virginia.gov/SBE_CSV/CF"
FILES = ("Report.csv", "ScheduleH.csv", "ScheduleA.csv")
DELAY = 1.5
UA = "va-bill-tracker/1.0 (research)"


def fetch(month, files=FILES):
    os.makedirs(CACHE, exist_ok=True)
    got = 0
    for name in files:
        path = os.path.join(CACHE, f"{month}_{name}.gz")
        if os.path.exists(path):
            print(f"  cached  {month}/{name}")
            continue
        req = urllib.request.Request(f"{BASE}/{month}/{name}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r:
            if r.status != 200:
                print(f"  FAIL {month}/{name}: HTTP {r.status}")
                return 1
            raw = r.read()
        with gzip.open(path, "wb") as fh:
            fh.write(raw)
        print(f"  fetched {month}/{name}: {len(raw):,}B")
        got += 1
        time.sleep(DELAY)
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    for m in argv[1:]:
        if fetch(m):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
