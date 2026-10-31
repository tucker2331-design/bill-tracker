#!/usr/bin/env python3
"""DOCKET.CSV ingest — upcoming meetings per bill (assumptions_audit #152, open_anti_patterns #15).

LIS's real DOCKET header is `Com_no, Doc_date, Doc_no, Bill_no`. Before 2026-10-31 the bill lookup lacked
`bill_no`, so the block was skipped silently and every bill published `upcoming: []`. Runs the REAL
build_bill_records (via test_state_va_goldens' harness: cached 2026 LIS blobs, clock frozen at 2026-02-10 12:00 ET):

  1. real docket  -> every row read, upcoming meetings fill in, none before "today", every committee named
  2. unrecognised columns -> counted (docket_columns_unrecognised = 1) + a DATA_ANOMALY alert, upcoming empty
  3. an unknown committee code -> counted + listed + a COMMITTEE_DRIFT alert; the meeting is kept, committee blank

Run: python3 test_docket_ingest.py
"""
import datetime
import sys

import pandas as pd

import bill_tracker as bt
import test_state_va_goldens as harness

FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


def alerts_since(n):
    return [m for _sev, m in bt._ALERT_BUFFER[n:]]


TODAY = datetime.date(2026, 2, 10)

# 1) the real 2026 docket
n0 = len(bt._ALERT_BUFFER)
out, _ = harness.run()
recs, comp = out["records"], out["completeness"]
up = [r for r in recs if r["upcoming"]]
meetings = [m for r in up for m in r["upcoming"]]
check("every docket row read", comp["docket_rows_total"] == comp["docket_rows_raw"] == 2525,
      f"total={comp['docket_rows_total']} raw={comp['docket_rows_raw']}")
check("upcoming meetings fill in (was 0 bills)", len(up) == 1162, f"{len(up)} bills")
check("1,553 future meetings", len(meetings) == 1553, f"{len(meetings)}")
check("nothing before the frozen today",
      all(datetime.datetime.strptime(m["date"], "%m/%d/%Y").date() >= TODAY for m in meetings))
check("every committee named from Com_no", all(m["committee"] for m in meetings))
check("no unmatched codes", comp["docket_committee_unmatched"] == 0 and comp["docket_committee_unmatched_codes"] == [])
check("columns recognised", comp["docket_columns_unrecognised"] == 0)
hb1 = next(r for r in recs if r["bill"] == "HB1")
check("HB1 row exact", hb1["upcoming"] == [{"date": "02/23/2026", "committee": "Senate Commerce and Labor"},
                                          {"date": "03/03/2026", "committee": "Senate Finance and Appropriations"}],
      f"{hb1['upcoming']}")
check("no docket alert on healthy data", not any("DOCKET" in a for a in alerts_since(n0)))

# 2) rows arrive, but no recognisable bill/date column
n0 = len(bt._ALERT_BUFFER)
renamed = pd.DataFrame({"Cmte": ["S01"], "When": ["02/20/2026"], "Measure": ["SB11"]})
out, _ = harness.run({"DOCKET.CSV": renamed})
comp = out["completeness"]
check("unrecognised columns counted", comp["docket_columns_unrecognised"] == 1 and comp["docket_rows_raw"] == 1)
check("unrecognised columns -> no upcoming", not any(r["upcoming"] for r in out["records"]))
check("unrecognised columns -> DATA_ANOMALY alert",
      any(a.startswith("[WARN:DATA_ANOMALY]") and "DOCKET.CSV" in a for a in alerts_since(n0)))

# 3) a committee code the map cannot name
n0 = len(bt._ALERT_BUFFER)
odd = pd.DataFrame({"Com_no": ["S99", "S01"], "Doc_date": ["02/20/2026", "02/20/2026"],
                    "Doc_no": ["1", "1"], "Bill_no": ["SB11", "SB68"]})
out, _ = harness.run({"DOCKET.CSV": odd})
comp = out["completeness"]
by = {r["bill"]: r["upcoming"] for r in out["records"]}
check("unknown code counted + listed",
      comp["docket_committee_unmatched"] == 1 and comp["docket_committee_unmatched_codes"] == ["S99"], f"{comp}")
check("unknown code: meeting kept, committee blank", by["SB11"] == [{"date": "02/20/2026", "committee": ""}], f"{by['SB11']}")
check("known code still named", by["SB68"] == [{"date": "02/20/2026", "committee": "Senate Agriculture, Conservation and Natural Resources"}])
check("unknown code -> COMMITTEE_DRIFT alert", any(a.startswith("[WARN:COMMITTEE_DRIFT]") for a in alerts_since(n0)))

sys.exit(1 if FAILS else 0)
