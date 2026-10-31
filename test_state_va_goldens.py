#!/usr/bin/env python3
"""VA byte-identical goldens for the multi-state split (Standard #6).

The split moved every Virginia assumption in the bill pipeline (session code, chamber map, LIS URLs, the status
vocabulary, the floor-passage phrases, the timezone, the stage list) behind `states/va.py`. Its promise is NO
behaviour change for Virginia. This test holds it to that: it runs the REAL `build_bill_records` on a real LIS
sample and compares a SHA-256 of the full output — every record, the completeness payload, and every URL the
pipeline asked for — against a hash captured from the code BEFORE the split.

INPUT (real, cached, authorized 2026 session — tools/historical_cache/va/20261/):
  HISTORY.CSV, DOCKET.CSV, Sponsors.csv  — LIS's own blobs, read as-is.
  The bill universe + BILLS.CSV are NOT cached for 20261, so they are SYNTHESIZED deterministically from the real
  HISTORY rows (bill id, last action as the status, a flag pattern keyed on the bill number). That keeps every code
  path live (structural flags, keyword fallback, patrons from both sources) without inventing any LIS fact the
  golden then claims to check — the golden checks that the code's OUTPUT did not move, nothing more.
Clock frozen at 2026-02-10 12:00 ET (crossover week), so DOCKET's future-meeting filter is exercised.

Re-capture ONLY when an output change is intended (and bump WORKER_OUTPUT_LOGIC_VERSION, audit #96):
    python3 test_state_va_goldens.py --write

Run: python3 test_state_va_goldens.py
"""
import datetime as _dt
import gzip
import hashlib
import io
import json
import os
import sys
from unittest import mock

import pandas as pd

import bill_tracker as bt

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "tools", "historical_cache", "va", "20261")
GOLDEN = os.path.join(HERE, "goldens", "va_bill_records_20261.json")
SESSION = "20261"
FROZEN = _dt.datetime(2026, 2, 10, 17, 0, 0, tzinfo=_dt.timezone.utc)   # 12:00 ET


def _read(name):
    with gzip.open(os.path.join(CACHE, name + ".gz"), "rb") as f:
        return pd.read_csv(io.BytesIO(f.read()), encoding="latin-1", dtype=str, keep_default_na=False)


def _inputs():
    hist = _read("HISTORY.CSV")
    docket = _read("DOCKET.CSV")
    sponsors = _read("Sponsors.csv")
    # Deterministic synthesized universe + BILLS.CSV from the real HISTORY (see the module docstring).
    last = {}
    for b, d in zip(hist["Bill_id"], hist["History_description"]):
        last[b.strip()] = d.strip()
    bills = sorted(last)
    universe = []
    for i, b in enumerate(bills):
        item = {"LegislationNumber": b, "Description": f"Catchline {b}", "LegislationStatus": last[b]}
        if i % 3 == 0:   # a third carry the universe's own Patrons list (full-name path)
            item["Patrons"] = [{"PatronTypeID": 1, "MemberDisplayName": f"Member {i}", "MemberNumber": f"H{i:04d}"}]
        universe.append(item)
    flags = ["vetoed", "approved", "carried_over", "failed", "passed", ""]
    rows = []
    for i, b in enumerate(bills):
        if i % 4 == 3:
            continue   # a quarter have no BILLS.CSV row -> keyword-fallback path
        f = flags[i % len(flags)]
        rows.append({"Bill_id": b, "Patron_name": f"Surname{i}", "Patron_id": f"S{i:04d}",
                     "Vetoed": "Y" if f == "vetoed" else "N", "Approved": "Y" if f == "approved" else "N",
                     "Chapter_id": "CHAP0001" if f == "approved" and i % 2 else "",
                     "Carried_over": "Y" if f == "carried_over" else "N", "Failed": "Y" if f == "failed" else "N",
                     "Passed": "Y" if f == "passed" else "N"})
    bills_csv = pd.DataFrame(rows)
    return {"HISTORY.CSV": hist, "DOCKET.CSV": docket, "Sponsors.csv": sponsors, "BILLS.CSV": bills_csv}, universe


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
        self.content = json.dumps(payload).encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self._p


class _Http:
    def __init__(self, universe, calls):
        self.universe, self.calls = universe, calls

    def get(self, url, **kw):
        self.calls.append(["GET", url, kw.get("params")])
        if "Session" in url:
            return _Resp([{"SessionCode": SESSION, "DisplayName": "Regular Session", "SessionYear": 2026}])
        return _Resp({"Legislations": self.universe})

    def post(self, url, **kw):
        self.calls.append(["POST", url, kw.get("json")])
        return _Resp({"Legislations": [{"LegislationNumber": u["LegislationNumber"], "LegislationClass": "Bill"}
                                       for u in self.universe[::2]]})


class _FrozenDT(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN.astimezone(tz) if tz else FROZEN.replace(tzinfo=None)


def run():
    blobs, universe = _inputs()
    calls = []

    def fake_fetch(url, **kw):
        calls.append(["BLOB", url])
        name = url.rsplit("/", 1)[-1]
        return blobs.get(name, pd.DataFrame()).copy()

    fake_datetime = mock.MagicMock(wraps=_dt)
    fake_datetime.datetime = _FrozenDT
    fake_datetime.timezone = _dt.timezone
    with mock.patch.object(bt, "safe_fetch_csv", fake_fetch), \
         mock.patch.object(bt, "build_committee_maps", lambda *a, **k: None), \
         mock.patch.object(bt, "datetime", fake_datetime):
        records, completeness = bt.build_bill_records(_Http(universe, calls), SESSION)
    out = {"records": records, "completeness": completeness, "calls": calls}
    blob = json.dumps(out, sort_keys=True, ensure_ascii=False, default=str).encode()
    return out, hashlib.sha256(blob).hexdigest()


def main():
    out, digest = run()
    summary = {
        "sha256": digest,
        "records": len(out["records"]),
        "calls": out["calls"],
        "outcomes": {k: sum(1 for r in out["records"] if r["outcome"] == k)
                     for k in sorted({r["outcome"] for r in out["records"]})},
        "sample": out["records"][:2],
    }
    if "--write" in sys.argv:
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        with open(GOLDEN, "w") as f:
            json.dump(summary, f, indent=1, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {GOLDEN}: {digest} ({summary['records']} records)")
        return 0
    with open(GOLDEN) as f:
        want = json.load(f)
    fails = 0
    for k in ("records", "calls", "outcomes", "sample", "sha256"):
        ok = json.dumps(summary[k], sort_keys=True, default=str) == json.dumps(want[k], sort_keys=True, default=str)
        print(("PASS " if ok else "FAIL ") + f"VA {SESSION} {k} byte-identical to the pre-split capture")
        fails += 0 if ok else 1
    if summary["records"] < 3000:
        print(f"FAIL sample too small to mean anything: {summary['records']} records")
        fails += 1
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
