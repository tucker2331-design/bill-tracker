#!/usr/bin/env python3
"""CA scheduled job smoke test — the real 2025-26 sample through ca_bill_tracker.build + write into a fake sheet.

Proves the CA site reads California exactly the way the VA and PA sites read theirs: the SAME Bill_Tracker header,
the completeness payload at AA1 (universe_count == records_written), the calendar at Sheet1 (+ its AA1 clock), the
committee roster at Committee_Roster, and one Metrics_History heartbeat. Plus the failure paths: a missing roster
checkout never holds back the bills or the calendar, and leaves the old roster tab alone. No network.

Run: python3 test_ca_bill_tracker.py
"""
import datetime
import json
import os
import sys

import gspread

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bill_rows  # noqa: E402
import ca_bill_tracker as J  # noqa: E402
from states.pa_calendar import SHEET1_HEADER  # noqa: E402
from states.pa_roster import ROSTER_HEADER  # noqa: E402

SAMPLE = os.path.join(HERE, "tools", "historical_cache", "ca", "sample")
OS_DIR = os.path.join(HERE, "tools", "historical_cache", "ca", "openstates_sample")
FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


INDEX = ('<tr><td><a href="pubinfo_2025.zip">pubinfo_2025.zip</a></td><td align="right">2026-11-15 21:26  </td></tr>\n'
         '<tr><td><a href="pubinfo_daily_Wed.zip">pubinfo_daily_Wed.zip</a></td><td align="right">2026-11-18 04:23  </td></tr>\n'
         '<tr><td><a href="pubinfo_daily_Tue.zip">pubinfo_daily_Tue.zip</a></td><td align="right">2026-11-17 21:23  </td></tr>\n')


class SampleFetcher:
    """Serves the committed real sample for the daily export; records which URLs were asked for."""
    requests_made = 0

    def __init__(self):
        self.asked = []

    def get(self, url):
        self.asked.append(url)
        if url == J.CA.urls["index"]:
            return INDEX.encode()
        if url.endswith("pubinfo_load.zip"):
            return open(os.path.join(SAMPLE, "pubinfo_load.zip"), "rb").read()
        raise AssertionError(f"unexpected get {url}")

    def path(self, url):
        self.asked.append(url)
        return os.path.join(SAMPLE, "pubinfo_sample.zip")

    def published_utc(self, url):
        return "2026-11-18T12:23:47Z"

    def prune_untouched(self):
        return 0


class WS:
    def __init__(self):
        self.row_count, self.col_count, self.cells, self.appended = 10, 5, {}, []

    def resize(self, rows, cols): self.row_count, self.col_count = rows, cols
    def batch_clear(self, ranges): self.cells.clear()
    def update(self, values, range_name): self.cells[range_name] = values
    def batch_update(self, data): self.cells.update({d["range"]: d["values"] for d in data})
    def append_row(self, row): self.appended.append(row)


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


NOW = datetime.datetime(2026, 11, 19, 6, 41, tzinfo=datetime.timezone.utc)
J.PEOPLE_DIR = OS_DIR
f = SampleFetcher()
records, comp, calendar, roster = J.build(f, now=NOW)
check("the job reads the newest DAILY export, never the Sunday yearly file",
      any(u.endswith("pubinfo_daily_Wed.zip") for u in f.asked) and not any(u.endswith("pubinfo_2025.zip") for u in f.asked))
check("records are stamped as of the export's own date", all(r["data_as_of_utc"] == "2026-11-18T12:23:47Z" for r in records)
      and comp["source_published_utc"] == "2026-11-18T12:23:47Z" and comp["source_file"] == "pubinfo_daily_Wed.zip")
sheet = Sheet()
J.write(records, comp, sheet, calendar, roster)
bt = sheet.tabs["Bill_Tracker"]
rows = bt.cells["A1"]
check("same columns as Virginia's Bill_Tracker; column C names California's source",
      rows[0][:2] + rows[0][3:21] == bill_rows.BILL_TRACKER_HEADER[:2] + bill_rows.BILL_TRACKER_HEADER[3:]
      and rows[0][2] == "Status (California Legislature)")
check("every row is the header's width", all(len(r) == len(rows[0]) for r in rows))
payload = json.loads(bt.cells["AA1"][0][0])
check("completeness at AA1: universe_count == records_written == 240",
      payload["universe_count"] == payload["records_written"] == len(records) == 240)
check("session label from the export", payload["session_display"] == "2025-2026 Regular Session")
ct = sheet.tabs.get("Sheet1")
check("calendar written to Sheet1 in the shared header, with its freshness clock at AA1",
      ct is not None and ct.cells["A1"][0] == SHEET1_HEADER and ct.cells["AA1"] == [[payload["source_published_utc"]]]
      and len(ct.cells["A1"]) - 1 == payload["calendar_rows"])
rt = sheet.tabs.get("Committee_Roster")
check("Committee_Roster written in the shared header, every sample bill's committee found",
      rt is not None and rt.cells["A1"][0] == ROSTER_HEADER and payload["roster_status"] == "ok"
      and payload["bills_committee_without_roster"] == 0 and len(rt.cells["A1"]) - 1 == payload["roster_seats"])
beat = sheet.tabs["Metrics_History"].appended
check("one OK heartbeat under the bill worker's origin, carrying the calendar and roster checks",
      len(beat) == 1 and beat[0][1:3] == ["OK", "bill_system_metrics"]
      and json.loads(beat[0][3]).get("bills_committee_without_roster") == 0
      and json.loads(beat[0][3]).get("calendar_meetings") == payload["calendar_meetings"])

# The site reads these payload keys as Health checks (web/src/states/ca.ts intakeChecks): each must be in the JOB's payload.
import re  # noqa: E402
_keys = re.findall(r'\{ key: "([a-z_]+)"', open(os.path.join(HERE, "web", "src", "states", "ca.ts"), encoding="utf-8").read())
check("every Health check on the CA site reads a key the job publishes", bool(_keys) and all(k in payload for k in _keys),
      str([k for k in _keys if k not in payload]))
check("the calendar's freshness clock is the export's publication time, not our check time (Codex #275)",
      ct.cells["AA1"] == [["2026-11-18T12:23:47Z"]])

# a malformed row in a table only the CALENDAR reads (motions) still reaches Health and the heartbeat (Codex #275)
import tempfile  # noqa: E402
import zipfile  # noqa: E402
_bad = os.path.join(tempfile.mkdtemp(prefix="ca_job_bad_"), "pubinfo_sample.zip")
with zipfile.ZipFile(os.path.join(SAMPLE, "pubinfo_sample.zip")) as zi, zipfile.ZipFile(_bad, "w", zipfile.ZIP_DEFLATED) as zo:
    for n in zi.namelist():
        data = zi.read(n)
        if n.upper() == "BILL_MOTION_TBL.DAT":
            lines = data.decode("utf-8").split("\n")
            lines[0] = "\t".join(lines[0].split("\t")[:-1])
            data = "\n".join(lines).encode("utf-8")
        zo.writestr(n, data)


class BadMotions(SampleFetcher):
    def path(self, url):
        return _bad


_r3, c3, _cal3, _ro3 = J.build(BadMotions(), now=NOW)
check("a malformed row first read by the calendar is counted in the published payload",
      c3["rows_with_wrong_field_count"] == {"BILL_MOTION_TBL": 1} and c3["rows_with_wrong_field_count_total"] == 1,
      str(c3["rows_with_wrong_field_count"]))

J.PEOPLE_DIR = os.path.join(OS_DIR, "missing")
r2, c2, cal2, ro2 = J.build(SampleFetcher(), now=NOW)
check("a missing Open States checkout never holds back the bills or the calendar (roster_status says why)",
      len(r2) == 240 and cal2 is not None and ro2 is None and c2["roster_status"] == "unavailable: FileNotFoundError")
s2 = Sheet()
J.write(r2, c2, s2, cal2, ro2)
check("... and the previous roster tab is left alone (not cleared)", "Committee_Roster" not in s2.tabs)

print(f"\n{FAILS} failed" if FAILS else "\nall passed")
sys.exit(1 if FAILS else 0)
