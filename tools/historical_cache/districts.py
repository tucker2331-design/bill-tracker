#!/usr/bin/env python3
"""Legislator -> district (LIS) and district -> demographics (Census ACS). Fetch once, cache, never again.

WHY
---
Owner, 2026-09-16: test whether district composition — race, income, education — influences how a
legislator behaves, beyond party.

COST AND AUTHORIZATION
----------------------
LIS: `Member/api/GetMemberListAsync` returns EVERY member of a session in ONE call
([[architecture/roster_and_votes_ingestion]] §2, probe-confirmed). Two sessions = **2 requests**, each
gated on `assert_lis_authorized` (2025/2026 only).

CENSUS: `api.census.gov/data/2023/acs/acs5`. **2 requests** (lower chamber, upper chamber). Public domain
under 17 USC §105 — no key required below 500 queries/day, no attribution requirement, no commercial
restriction. This is a cleaner dependency than either rejected aggregator
([[knowledge/legiscan_terms]], [[knowledge/campaign_finance_source]]).

FOUR REQUESTS TOTAL, then everything is local.

VINTAGE WARNING: Virginia redrew both chambers for the 2023 elections. ACS 2023 5-year is published on the
CURRENT district definitions, so joining it to a pre-2024 legislature is joining two different maps. Any
analysis built on this must stay inside 2024-2026.
"""
from __future__ import annotations
import gzip, json, os, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from lis_authorization import LIS_PUBLIC_API_KEY, assert_lis_authorized   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "va_districts")
SESSIONS = ("20251", "20261")
DELAY = 1.5
ACS_YEAR = "2023"
# B03002 = race/ethnicity; B19013 = median household income; B15003 = educational attainment
ACS_VARS = ("NAME", "B03002_001E", "B03002_003E", "B03002_004E", "B03002_012E",
            "B19013_001E", "B15003_001E", "B15003_022E", "B15003_023E",
            "B15003_024E", "B15003_025E")


def _get(url, headers=None, timeout=45):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def fetch_members():
    os.makedirs(CACHE, exist_ok=True)
    for code in SESSIONS:
        assert_lis_authorized(code)                    # halts on anything outside 2025/2026
        path = os.path.join(CACHE, f"members_{code}.json.gz")
        if os.path.exists(path):
            print(f"  cached members {code}")
            continue
        url = f"https://lis.virginia.gov/Member/api/GetMemberListAsync?sessionCode={code}"
        st, raw = _get(url, {"WebAPIKey": LIS_PUBLIC_API_KEY, "Accept": "application/json"})
        if st != 200:
            print(f"  FAIL members {code}: HTTP {st}")
            return 1
        body = json.loads(raw)
        rows = body if isinstance(body, list) else next(
            (v for v in body.values() if isinstance(v, list)), [])
        if not rows:
            print(f"  FAIL members {code}: no list in payload, keys={list(body)[:6]}")
            return 1
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(rows, fh)
        print(f"  {code}: {len(rows)} members cached")
        time.sleep(DELAY)
    return 0


def fetch_acs():
    os.makedirs(CACHE, exist_ok=True)
    for tag, layer in (("lower", "state legislative district (lower chamber)"),
                       ("upper", "state legislative district (upper chamber)")):
        path = os.path.join(CACHE, f"acs_{tag}.json.gz")
        if os.path.exists(path):
            print(f"  cached acs {tag}")
            continue
        q = urllib.parse.urlencode({"get": ",".join(ACS_VARS), "for": f"{layer}:*", "in": "state:51"})
        st, raw = _get(f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?{q}",
                       {"User-Agent": "va-bill-tracker/1.0 (research)"})
        if st != 200:
            print(f"  FAIL acs {tag}: HTTP {st}")
            return 1
        rows = json.loads(raw)
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(rows, fh)
        print(f"  acs {tag}: {len(rows) - 1} districts cached")
        time.sleep(DELAY)
    return 0


def main():
    print("LIS member lists (2 requests, authorization-gated):")
    if fetch_members():
        return 1
    print("Census ACS by state legislative district (2 requests, public domain):")
    return fetch_acs()


if __name__ == "__main__":
    raise SystemExit(main())
