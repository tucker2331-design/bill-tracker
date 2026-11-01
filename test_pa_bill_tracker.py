#!/usr/bin/env python3
"""PA scheduled job smoke test — the real 2025_0 sample through pa_bill_tracker.build + write into a fake sheet.

Proves the PA site can read PA exactly the way the VA site reads VA: the SAME Bill_Tracker header (bill_rows.py), every
row the header's width, the completeness payload at AA1 carrying the keys the site's header/Health read
(universe_count == records_written), and one Metrics_History heartbeat under the bill worker's origin. No network.

Run: python3 test_pa_bill_tracker.py
"""
import datetime
import json
import sys

import bill_rows
import pa_bill_tracker as J
import test_pa_intake as S

FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


class WS:
    def __init__(self):
        self.row_count, self.col_count, self.cells, self.appended = 10, 5, {}, []

    def resize(self, rows, cols): self.row_count, self.col_count = rows, cols
    def batch_clear(self, ranges): self.cells.clear()
    def update(self, values, range_name): self.cells[range_name] = values
    def batch_update(self, data): self.cells.update({d["range"]: d["values"] for d in data})
    def append_rows(self, rows): self.appended += rows


class Sheet:
    def __init__(self): self.tabs = {"Bill_Tracker": WS(), "Metrics_History": WS()}
    def worksheet(self, name): return self.tabs[name]


records, comp = J.build(S.SampleFetcher(), now=datetime.datetime(2026, 10, 31, 23, 36, tzinfo=datetime.timezone.utc))
sheet = Sheet()
J.write(records, comp, sheet)
bt = sheet.tabs["Bill_Tracker"]
rows = bt.cells["A1"]
check("same header as Virginia's Bill_Tracker", rows[0] == bill_rows.BILL_TRACKER_HEADER)
check("every row is the header's width", all(len(r) == len(rows[0]) for r in rows))
check("one row per PA record (5,269)", len(rows) - 1 == len(records) == 5269)
payload = json.loads(bt.cells["AA1"][0][0])
check("completeness at AA1: universe_count == records_written", payload["universe_count"] == payload["records_written"] == 5269)
check("session label from the export, not guessed", payload["session_display"] == "2025-2026 Regular Session"
      and payload["session_code"] == "2025_0")
check("grid grown to reach AA (col 27)", bt.col_count >= 27 and bt.row_count >= len(rows))
beat = sheet.tabs["Metrics_History"].appended
check("one heartbeat under the bill worker's origin", len(beat) == 1 and beat[0][1:3] == ["OK", "bill_system_metrics"])
hb17 = next(r for r in rows if r[0] == "HB17")
check("HB17 row: signed, LDPC source, both floors passed", hb17[3] == "signed" and hb17[15] == J.PA.source_name
      and hb17[16] == hb17[17] == "passed")
check("nothing written for Virginia (no VA sheet id read)", "SPREADSHEET_ID" not in J.__dict__)
sys.exit(1 if FAILS else 0)
