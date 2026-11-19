"""California scheduled job — the CA intake written to California's OWN spreadsheet, read by the CA site the same way
the Virginia and Pennsylvania sites read theirs (same Bill_Tracker layout, completeness payload at AA1, one
Metrics_History heartbeat row).

  * Fetching: states/ca_fetch.BulkFetcher — pubinfo bulk files only (the interactive leginfo site is never
    fetched), streamed to disk, at most once per URL per 20 h, honest User-Agent, a 401/403/429 stops the run.
  * Source file: the newest `pubinfo_daily_<Day>.zip` on the download index, by the index's own Last-modified column
    (discovered, never hardcoded). It is the FULL current session (every table the bill contract reads) rebuilt each
    day; the yearly `pubinfo_<year>.zip` is rebuilt only on Sunday, so reading it would miss Monday–Saturday (Codex
    #274). Records are stamped "as of" the file's own HTTP Last-Modified, never our clock — a source that stops
    publishing shows its true age on Health.
  * Building: states/ca_adapter.run_intake (fail closed on a partial universe); states/ca_calendar.build_calendar
    (committee hearings + floor sessions, from the same export) -> Sheet1, the layout the Calendar screen reads;
    states/ca_roster.build_roster (Open States' public-domain committee data, a git checkout) -> Committee_Roster.

Usage:  python3 ca_bill_tracker.py --dry-run   # fetch + build, print the completeness payload, write nothing
        python3 ca_bill_tracker.py             # also write (needs CA_SPREADSHEET_ID + GCP_CREDENTIALS)
"""
import datetime
import json
import os
import re
import sys

import pytz
import yaml

import action_where

from bill_rows import BILL_TRACKER_HEADER, bill_tracker_rows
from states import ca_adapter, ca_calendar, ca_pubinfo, ca_roster, get_state
from states.ca_fetch import BulkFetcher, newest_daily

CA = get_state("CA")
TAB = "Bill_Tracker"
COMPLETENESS_CELL = "AA1"
if len(BILL_TRACKER_HEADER) >= 27:
    raise RuntimeError(f"Bill_Tracker data ({len(BILL_TRACKER_HEADER)} cols) would reach {COMPLETENESS_CELL}")
STATUS_HEADER = "Status (California Legislature)"
ROSTER_TAB = "Committee_Roster"     # the War Room's committee members (the same tab Pennsylvania writes)
PEOPLE_DIR = os.environ.get("CA_PEOPLE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                          ".openstates_people", "data", "ca"))
CALENDAR_TAB = "Sheet1"              # the layout the Calendar screen reads (shared with Virginia and Pennsylvania)
# every count that must be 0 on a healthy run (the same keys the site's Health screen checks, web/src/states/ca.ts)
CHECKS_AT_ZERO = ("end_status_unclassified", "rows_with_wrong_field_count_total", "committee_house_prefix_disagrees",
                  "calendar_floor_desc_unclassified", "calendar_slot_code_unknown", "calendar_agenda_bills_unmatched",
                  "calendar_hearings_without_agenda", "bills_committee_without_roster", "roster_files_unreadable",
                  "action_where_unknown")
METRICS_TAB, METRICS_HEADER = "Metrics_History", ["RunTimestampUTC", "Status", "Origin", "Outcome"]
ORIGIN = "bill_system_metrics"
CACHE = os.environ.get("CA_CACHE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ca_cache"))


def build(fetcher: BulkFetcher, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.astimezone(pytz.timezone(CA.timezone)).date()
    name = newest_daily(fetcher.get(CA.urls["index"]).decode("utf-8", "replace"))
    url = CA.urls["index"] + name
    schema = ca_pubinfo.load_schema(fetcher.get(CA.urls["index"] + "pubinfo_load.zip"))
    ex = ca_pubinfo.Export(fetcher.path(url), schema)
    published = fetcher.published_utc(url)
    if not published:
        raise ValueError(f"{name} came with no Last-Modified — the export's own date is unknown; refusing to stamp it "
                         f"with our clock (fail closed)")
    extras: dict = {}
    records, comp = ca_adapter.run_intake(ex, today, now.strftime("%Y-%m-%dT%H:%M:%SZ"), as_of_utc=published,
                                          extras=extras)
    # Calendar: committee hearings + floor sessions from the same export (no new request)
    calendar, cstats = ca_calendar.build_calendar(ex, extras)
    comp.update(cstats)
    # the calendar reads tables the intake did not (motions, meeting slots): re-publish the malformed-row counts so a
    # source error first met there reaches Health and the heartbeat (Codex #275)
    comp["rows_with_wrong_field_count"] = dict(ex.bad_rows)
    comp["rows_with_wrong_field_count_total"] = sum(ex.bad_rows.values())
    # Committee rosters: Open States' public-domain people data (a git checkout the workflow makes). A missing or
    # broken checkout never holds back the bills: roster_status says why and the previous tab stays.
    roster = None
    try:
        roster, rstats = ca_roster.build_roster(PEOPLE_DIR, extras["committees"], today)
        comp.update(rstats)
        comp.update(ca_roster.coverage(records, roster))
        comp["roster_status"] = "ok"
    except (OSError, KeyError, yaml.YAMLError) as e:  # missing checkout, a file without a field, unparseable YAML
        comp["roster_status"] = f"unavailable: {type(e).__name__}"
        print(f"::error::CA committee roster not refreshed ({type(e).__name__}: {e}); the previous tab stays")
    comp.update({"source_file": name, "source_published_utc": published, "requests_made": fetcher.requests_made})
    where_grid = action_where.rows_for(extras["action_where"])     # What's new: where each action happened
    return records, comp, calendar, roster, where_grid


def write(records, comp, sheet, calendar=None, roster=None, where_grid=None):
    import gspread
    rows = bill_tracker_rows(records, status_label=STATUS_HEADER, pipeline=True)
    need_rows, need_cols = len(rows) + 50, 27
    try:
        ws = sheet.worksheet(TAB)
        if ws.row_count < need_rows or ws.col_count < need_cols:
            ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
        ws.batch_clear([f"A1:V{max(ws.row_count, need_rows)}"])
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=TAB, rows=need_rows, cols=need_cols)
    ws.batch_update([{"range": "A1", "values": rows},
                     {"range": COMPLETENESS_CELL, "values": [[json.dumps(comp, ensure_ascii=False)]]}])
    if calendar is not None:
        need = len(calendar) + 50
        try:
            cw = sheet.worksheet(CALENDAR_TAB)
            if cw.row_count < need or cw.col_count < 27:
                cw.resize(rows=max(cw.row_count, need), cols=max(cw.col_count, 27))
            cw.batch_clear([f"A1:Q{max(cw.row_count, need)}"])     # old rows past today's calendar must go
        except gspread.exceptions.WorksheetNotFound:
            cw = sheet.add_worksheet(title=CALENDAR_TAB, rows=need, cols=27)
        # AA1 = the calendar's freshness clock. It is the EXPORT's publication time, not our check time: a source that
        # stops publishing must show its real age on the calendar too, as it does on the bills (Codex #275)
        cw.batch_update([{"range": "A1", "values": calendar},
                         {"range": COMPLETENESS_CELL, "values": [[comp["source_published_utc"]]]}])
    if where_grid is not None:
        try:
            action_where.write(sheet, where_grid)   # enrichment: never blocks the roster or the heartbeat (as for PA)
            comp["action_where_status"] = "ok"
        except (gspread.exceptions.APIError, gspread.exceptions.GSpreadException) as e:
            comp["action_where_status"] = f"write failed: {type(e).__name__}"   # rides in the heartbeat below
            print(f"::warning::CA {action_where.ACTION_WHERE_TAB} write failed ({type(e).__name__}: {e}); "
                  f"What's new shows actions without where they happened")
    if roster is not None:
        rrows = ca_roster.roster_rows(roster)
        try:
            rw = sheet.worksheet(ROSTER_TAB)
            if rw.row_count < len(rrows) + 20:
                rw.resize(rows=len(rrows) + 20, cols=len(rrows[0]))
            rw.batch_clear([f"A1:H{rw.row_count}"])
        except gspread.exceptions.WorksheetNotFound:
            rw = sheet.add_worksheet(title=ROSTER_TAB, rows=len(rrows) + 20, cols=len(rrows[0]))
        rw.update(values=rrows, range_name="A1")
    try:
        mh = sheet.worksheet(METRICS_TAB)
    except gspread.exceptions.WorksheetNotFound:
        mh = sheet.add_worksheet(title=METRICS_TAB, rows=1000, cols=4)
        mh.update(values=[METRICS_HEADER], range_name="A1")
    status = "OK" if not any(comp.get(k) for k in CHECKS_AT_ZERO) else "WARN"
    mh.append_row([comp["checked_at_utc"], status, ORIGIN, json.dumps({k: comp[k] for k in (
        "records_written", "end_status_unclassified", "actions_rescinded", "end_status_blank", "calendar_meetings",
        "calendar_floor_sessions", "calendar_bill_rows_with_vote", "roster_status", "roster_seats",
        "bills_committee_without_roster", "action_where_status", "action_where_unknown") if k in comp})])


def sheet_id() -> str:
    """CA_SPREADSHEET_ID if set, else wrangler.ca.toml's SPREADSHEET_ID (not a secret: the sheet's sharing and the
    Worker's sign-in check guard it, as for Pennsylvania). Empty = refuse to write."""
    sid = os.environ.get("CA_SPREADSHEET_ID", "").strip()
    if sid:
        return sid
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wrangler.ca.toml"), encoding="utf-8") as f:
            m = re.search(r'^SPREADSHEET_ID\s*=\s*"([^"]*)"', f.read(), re.M)
        return m.group(1).strip() if m else ""
    except OSError:
        return ""


def main(argv):
    fetcher = BulkFetcher(CACHE)
    try:
        records, comp, calendar, roster, where_grid = build(fetcher)
    finally:
        print(f"CA fetch cache: removed {fetcher.prune_untouched()} file(s) this run did not use")
    print(json.dumps(comp, indent=1))
    if "--dry-run" in argv:
        return 0
    sid = sheet_id()
    creds = os.environ.get("GCP_CREDENTIALS")
    if not sid or not creds:
        print("::error::the CA sheet id (wrangler.ca.toml) and GCP_CREDENTIALS are required to write")
        return 1
    import gspread
    gc = gspread.service_account_from_dict(json.loads(creds))
    write(records, comp, gc.open_by_key(sid), calendar, roster, where_grid)
    print(f"CA: wrote {len(records)} bills and {len(calendar) - 1} calendar rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
