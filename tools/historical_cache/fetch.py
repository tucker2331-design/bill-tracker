#!/usr/bin/env python3
"""Fetch-once cache of the legacy LIS CSVs, so a backtest never re-downloads them.

WHY A CACHE AT ALL
------------------
These files are STATIC — the 2024 session ended, its History.csv will never change again (verified:
`Last-Modified: Tue, 12 Nov 2024`). Re-pulling 25 MB from DLAS on every backtest run is load a public
help-desk should not absorb to tell us the same bytes each time, and it makes every analysis depend on a
third party being up.

WHY IN THE REPO, GZIPPED, NOT IN SHEETS
---------------------------------------
25.2 MB raw compresses to ~2.7 MB (measured: History.csv 241 is 3.68 MB -> 0.40 MB, ratio 0.108 — CSV is
extremely compressible). At that size the repo is the best home:
  - no Google cell budget (the archive workbook is the thing that FILLS UP — see architecture/session_archive)
  - no credentials, so a future session can read it with zero setup
  - git-versioned, so "which bytes did that number come from" has an answer
  - works offline
A Sheets tab would have cost ~700k cells for the same data and put static reference material into the
workbook we are actively trying to keep under a cap.

INTEGRITY
---------
`manifest.json` records url + bytes + sha256 + fetched_utc per file. `verify` re-hashes local files (no
network); `--check-remote` re-HEADs the source to confirm upstream has not changed. Content is verified by
HASH, never by "the file exists" — a truncated download is a file that exists.

COMPLIANCE
----------
`legacylis.virginia.gov` is the channel the LIS Developers Portal names for pre-2025 data; the 2025/2026-only
rule binds `lis.virginia.gov/*/api/*` and `lis.blob.core.windows.net/lisfiles/*`, which this never touches.
SESSIONS below is a PINNED allowlist for the same reason `LIS_HISTORICAL_AUTHORIZED` is pinned — so nobody
widens the set by editing a loop bound. See docs/knowledge/legacylis_csv_route.md.

Usage:
  python3 tools/historical_cache/fetch.py fetch    # download what is missing (idempotent)
  python3 tools/historical_cache/fetch.py verify   # re-hash local files
  python3 tools/historical_cache/fetch.py verify --check-remote
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://legacylis.virginia.gov/SiteInformation/csv"
UA = {"User-Agent": "Mozilla/5.0 (VA legislative bill tracker; one-time historical cache; "
                    "contact via github)"}
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "va")
MANIFEST = os.path.join(CACHE_DIR, "manifest.json")

# PINNED. Measured 2026-08-01 (docs/knowledge/legacylis_csv_route.md):
#   231 = 2023 regular, 3,029 bills — COMPLETE
#   241 = 2024 regular, 3,595 bills — COMPLETE
#   242 = 2024 special,   290 bills — complete for a special session
# DELIBERATELY EXCLUDED: 221 holds 363 bills where the 2022 regular session ran ~2,900. It is a PARTIAL
# file, and caching it would let a backtest silently treat a 12%-complete session as a whole one — every
# 2022 denominator would be wrong in the safe-looking direction. 211 and earlier return 404.
SESSIONS = {
    "231": "2023 Regular Session",
    "241": "2024 Regular Session",
    "242": "2024 Special Session I",
}

# Summaries.csv (~3 MB/session of bill text) is NOT cached: no calibration question needs it, and it is
# the single largest file. Add it deliberately if the text-similarity work ever wants historical depth.
FILES = ["Bills.csv", "History.csv", "Vote.csv", "Members.csv",
         "Committees.csv", "CommitteeMembers.csv", "Sponsors.csv",
         # SUBJECT LINKAGE — legacy-only. Measured 2026-08-01: CIBILLSUBJECTS.CSV 404s on the modern blob
         # (both cases), so the vault's "no subject blob exists" is correct for the CURRENT session but
         # wrong for history. These two files are the only bill->subject source we have anywhere, which
         # makes caching them the difference between a subject analysis being possible and impossible.
         "CiBillSubjects.csv", "CiParentChildSubjects.csv"]

POLITE_DELAY_S = 0.5


def _local(code: str, name: str) -> str:
    return os.path.join(CACHE_DIR, code, name + ".gz")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_manifest() -> dict:
    if not os.path.exists(MANIFEST):
        return {"jurisdiction": "VA", "source": BASE, "files": {}}
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def save_manifest(m: dict) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1, sort_keys=True)
        fh.write("\n")


def read_cached(code: str, name: str) -> str:
    """Decompressed text of one cached file. Raises if absent — a MISSING cache file must never read as an
    empty session (that would silently zero a denominator)."""
    path = _local(code, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} is not cached — run `fetch.py fetch` first.")
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def fetch() -> int:
    man = load_manifest()
    got = skipped = failed = absent = 0
    for code in SESSIONS:
        os.makedirs(os.path.join(CACHE_DIR, code), exist_ok=True)
        for name in FILES:
            key = f"{code}/{name}"
            rec = man["files"].get(key)
            if rec and rec.get("absent"):
                skipped += 1
                continue
            if os.path.exists(_local(code, name)) and rec:
                skipped += 1
                continue
            url = f"{BASE}/{code}/{name}"
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                    raw = r.read()
                    last_mod = r.headers.get("Last-Modified", "")
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    # A file the publisher simply does not produce for this session is NOT a failure —
                    # 242 (a special session) has no subject files. Recorded as absent so re-runs neither
                    # retry it nor report a permanent error. Distinguishing "not published" from "fetch
                    # broke" matters: conflating them makes the tool cry wolf until nobody reads its exit
                    # code, and THAT is how a real fetch failure gets ignored.
                    man["files"][key] = {"url": url, "absent": True, "http": 404,
                                         "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                    print(f"  --   {key}: not published for this session (404)")
                    absent += 1
                    time.sleep(POLITE_DELAY_S)
                    continue
                print(f"  FAIL {key}: {exc}")
                failed += 1
                continue
            except (urllib.error.URLError, TimeoutError) as exc:
                # Counted and named, never a silent skip (Standard #4).
                print(f"  FAIL {key}: {exc}")
                failed += 1
                continue
            with gzip.open(_local(code, name), "wb", compresslevel=9) as fh:
                fh.write(raw)
            man["files"][key] = {
                "url": url, "bytes": len(raw), "sha256": _sha256(raw),
                "last_modified": last_mod,
                "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            print(f"  ok   {key}: {len(raw):,} bytes -> {os.path.getsize(_local(code, name)):,} gz")
            got += 1
            time.sleep(POLITE_DELAY_S)
    man["sessions"] = SESSIONS
    save_manifest(man)
    print(f"\nfetched {got}, already cached {skipped}, not published {absent}, failed {failed}")
    return 1 if failed else 0


def verify(check_remote: bool = False) -> int:
    man = load_manifest()
    if not man["files"]:
        print("manifest is empty — nothing cached yet.")
        return 1
    bad = 0
    for key, rec in sorted(man["files"].items()):
        if rec.get("absent"):
            continue          # nothing to hash; its absence is a recorded fact, not a cached file
        code, name = key.split("/", 1)
        try:
            raw = read_cached(code, name).encode("utf-8", "replace")
        except FileNotFoundError as exc:
            print(f"  MISSING {key}: {exc}")
            bad += 1
            continue
        # Re-hash of the DECOMPRESSED bytes will not equal the original sha256 when the source had
        # non-UTF8 bytes, so compare on the raw gz round-trip instead.
        with gzip.open(_local(code, name), "rb") as fh:
            raw = fh.read()
        if _sha256(raw) != rec["sha256"]:
            print(f"  CORRUPT {key}: sha256 differs from manifest")
            bad += 1
            continue
        if len(raw) != rec["bytes"]:
            print(f"  SIZE   {key}: {len(raw):,} != manifest {rec['bytes']:,}")
            bad += 1
            continue
        if check_remote:
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(rec["url"], method="HEAD", headers=UA), timeout=30) as r:
                    n = int(r.headers.get("Content-Length") or 0)
                if n != rec["bytes"]:
                    # NOT a corruption — upstream changed. Loud, because a "static" file that moved
                    # invalidates every number derived from the cached copy.
                    print(f"  UPSTREAM-CHANGED {key}: source is now {n:,} bytes, cache has {rec['bytes']:,}")
                    bad += 1
            except Exception as exc:
                print(f"  remote check unavailable for {key}: {exc}")
            time.sleep(POLITE_DELAY_S)
    checked = sum(1 for r in man["files"].values() if not r.get("absent"))
    print(f"\n{checked - bad} of {checked} files verified"
          f"{' (incl. remote size check)' if check_remote else ''}")
    return 1 if bad else 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if mode == "fetch":
        return fetch()
    if mode == "verify":
        return verify("--check-remote" in sys.argv)
    print(f"unknown mode {mode!r} (fetch | verify [--check-remote])", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
