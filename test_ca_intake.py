#!/usr/bin/env python3
"""California intake goldens — run on a REAL sample cut from the 2025-26 pubinfo export
(tools/historical_cache/ca/sample/pubinfo_sample.zip: every row of 240 bills chosen across outcomes, plus the
committee-code and legislator tables). Nothing here is synthetic.

    python3 test_ca_intake.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from states import get_state  # noqa: E402
from states import ca_adapter, ca_pubinfo  # noqa: E402
from states.ca_fetch import BulkFetcher  # noqa: E402
from states.pa_fetch import NotABulkFeed  # noqa: E402

SAMPLE = os.path.join(HERE, "tools", "historical_cache", "ca", "sample")
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


CA = get_state("CA")
check("CA registered with a crossover marker (house-of-origin deadline)", CA.has_crossover)
check("CA chambers use the contract names", set(CA.chambers.values()) == {"House", "Senate"})
check("CA bill numbers place their origin", CA.origin_chamber("AB12") == "House" and CA.origin_chamber("SB3") == "Senate"
      and CA.origin_chamber("HR5") == "House")
try:
    CA.origin_chamber("XB1")
    check("an unknown prefix raises", False)
except ValueError:
    check("an unknown prefix raises", True)

import tempfile  # noqa: E402
f = BulkFetcher(tempfile.mkdtemp(prefix="ca_fetch_test_"))
for bad in ("https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260AB1",
            "https://downloads.leginfo.legislature.ca.gov/../etc/passwd"):
    try:
        f.path(bad)
        check(f"fetcher refuses {bad[:50]}", False)
    except NotABulkFeed:
        check(f"fetcher refuses {bad[:50]}", True)
check("fetcher allows the session file", any(p.match("https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip")
                                              for p in __import__("states.ca_fetch", fromlist=["_ALLOWED"])._ALLOWED))

schema = ca_pubinfo.load_schema(open(os.path.join(SAMPLE, "pubinfo_load.zip"), "rb").read())
check("schema read from the source's load scripts (18 tables)", len(schema) == 18, str(len(schema)))
ex = ca_pubinfo.Export(os.path.join(SAMPLE, "pubinfo_sample.zip"), schema)
records, comp = ca_adapter.run_intake(ex, datetime.date(2026, 11, 18), "2026-11-18T21:00:00Z")
expected = json.load(open(os.path.join(SAMPLE, "expected.json")))
check("every bill in the sample becomes a record", comp["records_written"] == comp["universe_declared"] == expected["bills"],
      f"{comp['records_written']} / {comp['universe_declared']} / {expected['bills']}")
check("no END_STATUS outside the mapped vocabulary", comp["end_status_unclassified"] == 0, str(comp["end_status_unclassified_sample"]))
check("no row with the wrong field count", not comp["rows_with_wrong_field_count"], str(comp["rows_with_wrong_field_count"]))
stage_ids = {s.id for s in CA.stages}
check("every stage is one of CA's", all(r["stage"] in stage_ids for r in records))
check("every chamber is a contract name", all(r["chamber"] in ("House", "Senate") for r in records))
by = {r["bill"]: r for r in records}
for bill, want in expected["bills_checked"].items():
    r = by.get(bill)
    got = {k: (r or {}).get(k) for k in want}
    check(f"{bill}: {want}", got == want, f"got {got}")
outs = {}
for r in records:
    outs[r["outcome"]] = outs.get(r["outcome"], 0) + 1
check("outcome counts match the measured sample", outs == expected["outcomes"], f"{outs} vs {expected['outcomes']}")

print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
sys.exit(1 if FAILS else 0)
