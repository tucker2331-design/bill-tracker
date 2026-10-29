"""Golden: Sponsors.csv survives safe_fetch_csv and becomes co-patrons (Codex P1 on #239).

The guarded fetch rejects a 200 body without a schema marker. Its default markers (BillNumber / HistoryDate /
Committee) fit HISTORY/DOCKET/BILLS, but Sponsors.csv's header is MEMBER_NAME,MEMBER_ID,BILL_NUMBER,PATRON_TYPE,
so before the per-schema `markers` argument every live fetch returned an EMPTY frame and every co-patron cell
published blank. This feeds the REAL cached 20261 Sponsors bytes through the REAL fetch (requests.get stubbed).

Pure: no network, no gspread. Run: python3 test_copatrons_fetch.py
"""
import gzip
import os
import tempfile

os.environ["LIS_BLOB_CACHE"] = "0"                       # no on-disk ETag cache in a test
os.environ.setdefault("LIS_BLOB_CACHE_DIR", tempfile.mkdtemp())

import calendar_worker as cw
import bill_tracker as bt

BODY = gzip.open(os.path.join("tools", "historical_cache", "va", "20261", "Sponsors.csv.gz")).read()


class _Res:
    status_code = 200

    def __init__(self, body):
        self.content = body
        self.headers = {"Content-Length": str(len(body))}


def _get(url, timeout=None, headers=None):
    return _Res(BODY)


cw.requests.get = _get
bt.safe_fetch_csv = cw.safe_fetch_csv

# 1. the default markers still reject this schema (proves the test would have caught the bug)
assert cw.safe_fetch_csv("https://x/Sponsors.csv").empty, "default markers unexpectedly accept Sponsors.csv"
# 2. the copatron loader passes its own markers and gets real rows
cops, stats = bt._build_copatrons("20261")
assert stats["rows"] > 10000, stats                      # measured 2026-10-29: 15,875 rows on 20261
assert "missing_columns" not in stats, stats
hb1 = cops.get("HB1") or []
assert hb1 and all(c["role"] != "Chief Patron" for c in hb1), hb1[:3]
print(f"co-patrons fetch: OK ({stats['rows']} rows, {len(cops)} bills with co-patrons)")
