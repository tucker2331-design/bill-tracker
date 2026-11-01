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

import urllib.error

import gspread

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
    def worksheet(self, name):
        if name not in self.tabs:
            raise gspread.exceptions.WorksheetNotFound(name)
        return self.tabs[name]
    def add_worksheet(self, title, rows, cols):
        ws = self.tabs[title] = WS()
        ws.row_count, ws.col_count = rows, cols
        return ws


NOW = datetime.datetime(2026, 10, 31, 23, 36, tzinfo=datetime.timezone.utc)
records, comp, roster, calendar = J.build(S.SampleFetcher(), now=NOW)
sheet = Sheet()
J.write(records, comp, sheet, roster, calendar)
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
# Committee roster (the PA War Room's member list)
rt = sheet.tabs.get("Committee_Roster")
check("Committee_Roster tab created with its header", rt is not None and rt.cells["A1"][0] == J.pa_roster.ROSTER_HEADER)
check("roster: 1,026 seats, 250 members, every bill's committee found",
      len(rt.cells["A1"]) - 1 == 1026 and payload["roster_members"] == 250 and payload["roster_status"] == "ok"
      and payload["bills_committee_without_roster"] == 0, json.dumps({k: payload.get(k) for k in ("roster_rows", "roster_status")}))
check("heartbeat carries the roster check", json.loads(beat[0][3]).get("bills_committee_without_roster") == 0)


class RosterDown(S.SampleFetcher):
    def get(self, url):
        if "assignments" in url:
            raise urllib.error.URLError("unreachable")
        return super().get(url)


r2, c2, ro2, cal2 = J.build(RosterDown(), now=NOW)
check("a broken roster feed never holds back the bills (published as roster_status)",
      len(r2) == 5269 and ro2 is None and c2["roster_status"] == "unavailable: URLError")
s2 = Sheet()
J.write(r2, c2, s2, ro2)
check("... and the previous roster tab is left alone (not cleared)", "Committee_Roster" not in s2.tabs)


class Refused(S.SampleFetcher):
    def get(self, url):
        if "members" in url:
            raise J.pa_fetch.FeedRefused("403")
        return super().get(url)


try:
    J.build(Refused(), now=NOW)
    check("a 403 on a roster feed still stops the whole run (owner rule)", False)
except J.pa_fetch.FeedRefused:
    check("a 403 on a roster feed still stops the whole run (owner rule)", True)
# Calendar (Sheet1 in the layout the Calendar screen reads)
ct = sheet.tabs.get("Sheet1")
check("Sheet1 calendar tab written in the calendar subsystem's header",
      ct is not None and ct.cells["A1"][0] == J.pa_calendar.SHEET1_HEADER and ct.cells["AA1"] == [[payload["checked_at_utc"]]])
check("calendar: 5 meetings (7 listed, 2 duplicates), none with bills, 214 past session days",
      (payload["calendar_meetings"], payload["calendar_meetings_duplicate"], payload["calendar_meetings_without_bills"],
       payload["calendar_session_days"]) == (5, 2, 5, 214))
check("a roster outage keeps the calendar (source names instead of display names)",
      cal2 is not None and any(r[4] == "HOUSE APPROPRIATIONS" for r in cal2[1:]))
check("nothing written for Virginia (no VA sheet id read)", "SPREADSHEET_ID" not in J.__dict__)
sys.exit(1 if FAILS else 0)
