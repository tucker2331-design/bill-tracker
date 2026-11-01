"""Pennsylvania scheduled job — the PA intake written to PA's OWN spreadsheet, read by the PA site the same way the
Virginia site reads Virginia's (owner 2026-11-01: a fully separate site, same code).

  * Fetching: states/pa_fetch.PoliteFetcher (bulk feeds only, <=1 request per URL per hour, one at a time, honest
    User-Agent, a 403 stops the run). The cache directory persists between runs (actions/cache), so the hourly cap
    holds across runs, not just within one.
  * Building: states/pa_adapter.run_intake (session discovered from the data page; fail closed on a partial universe).
  * Writing: the SAME Bill_Tracker layout as Virginia (bill_rows.py) + the completeness payload at AA1, and one
    Metrics_History heartbeat row, to the sheet in PA_SPREADSHEET_ID. Nothing touches Virginia's sheet.

Usage:  python3 pa_bill_tracker.py            # fetch, build, write (needs PA_SPREADSHEET_ID + GCP_CREDENTIALS)
        python3 pa_bill_tracker.py --dry-run  # fetch + build, print the completeness payload, write nothing
"""
import datetime
import json
import os
import sys

import urllib.error
import xml.etree.ElementTree as ET

import pytz

from bill_rows import BILL_TRACKER_HEADER, bill_tracker_rows
from states import get_state
from states import pa_adapter, pa_fetch, pa_roster

PA = get_state("PA")
TAB = "Bill_Tracker"
COMPLETENESS_CELL = "AA1"            # same reserved cell as Virginia (the site finds it by content anyway)
# The data columns must never reach the metadata cell (the VA layout's rule, checked at import like bill_tracker.py).
if len(BILL_TRACKER_HEADER) >= 27:
    raise RuntimeError(f"Bill_Tracker data ({len(BILL_TRACKER_HEADER)} cols) would reach {COMPLETENESS_CELL}")
ROSTER_TAB = "Committee_Roster"     # the War Room's committee members (no vote calls in PA: no model)
METRICS_TAB, METRICS_HEADER = "Metrics_History", ["RunTimestampUTC", "Status", "Origin", "Outcome"]
ORIGIN = "bill_system_metrics"       # the bill worker's heartbeat origin, so Health reads PA the same way


def build(fetcher, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.astimezone(pytz.timezone(PA.timezone)).date()
    records, comp = pa_adapter.run_intake(fetcher, None, today, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    year = int(comp["session_code"].split("_")[0])
    comp.update({
        # the keys the site's header + Health already read for Virginia
        "universe_count": comp["universe_declared"],
        "in_history_not_in_universe": [],
        "session_display": f"{year}-{year + 1} Regular Session" if comp["session_code"].endswith("_0")
                           else f"{year}-{year + 1} Special Session {comp['session_code'].split('_')[1]}",
    })
    # Committee rosters. A refusal (FeedRefused) still stops the whole run (owner rule); a broken or unreachable
    # roster feed does NOT hold back the bills — it is published as roster_status and the old tab is left alone.
    roster = None
    try:
        roster, rstats = pa_roster.run_roster(fetcher, PA.urls)
        comp.update(rstats)
        comp.update(pa_roster.coverage(records, roster))
        comp["roster_status"] = "ok"
    except (urllib.error.URLError, ET.ParseError, OSError) as e:
        comp["roster_status"] = f"unavailable: {type(e).__name__}"
        print(f"::error::PA committee roster not refreshed ({type(e).__name__}: {e}); the previous tab stays")
    comp["requests_made"] = getattr(fetcher, "requests_made", None)
    return records, comp, roster


def write(records, comp, sheet, roster=None):
    import gspread
    rows = bill_tracker_rows(records)
    need_rows, need_cols = len(rows) + 50, 27   # AA = column 27
    try:
        ws = sheet.worksheet(TAB)
        if ws.row_count < need_rows or ws.col_count < need_cols:
            ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
        ws.batch_clear([f"A1:U{max(ws.row_count, need_rows)}"])   # old rows past today's universe must go
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=TAB, rows=need_rows, cols=need_cols)   # new tab: nothing to clear
    # one call for the table + the completeness payload (Gemini #255)
    ws.batch_update([{"range": "A1", "values": rows},
                     {"range": COMPLETENESS_CELL, "values": [[json.dumps(comp, ensure_ascii=False)]]}])
    if roster is not None:
        rrows = pa_roster.roster_rows(roster)
        try:
            rw = sheet.worksheet(ROSTER_TAB)
            if rw.row_count < len(rrows) + 20:
                rw.resize(rows=len(rrows) + 20, cols=len(pa_roster.ROSTER_HEADER))
            rw.batch_clear([f"A1:H{rw.row_count}"])
        except gspread.exceptions.WorksheetNotFound:
            rw = sheet.add_worksheet(title=ROSTER_TAB, rows=len(rrows) + 20, cols=len(pa_roster.ROSTER_HEADER))
        rw.update(values=rrows, range_name="A1")
    try:
        mh = sheet.worksheet(METRICS_TAB)
    except gspread.exceptions.WorksheetNotFound:
        mh = sheet.add_worksheet(title=METRICS_TAB, rows=1000, cols=4)
        mh.update(values=[METRICS_HEADER], range_name="A1")
    beat = {k: comp[k] for k in ("records_written", "universe_count", "verbs_unclassified", "undefined_actions",
                                 "action_dates_unreadable", "schedule_bill_refs_unmatched", "requests_made")}
    beat.update({k: comp[k] for k in ("roster_status", "bills_committee_without_roster") if k in comp})
    mh.append_rows([[comp["checked_at_utc"], "OK", ORIGIN, json.dumps(beat, ensure_ascii=False)]])


def main(argv):
    fetcher = pa_fetch.PoliteFetcher(os.environ.get("PA_CACHE_DIR", ".pa_cache"))
    records, comp, roster = build(fetcher)
    print(json.dumps({k: v for k, v in comp.items() if k != "verbs_unclassified_sample"}, ensure_ascii=False))
    if comp["verbs_unclassified"]:
        # Counted and published, never guessed — but a new verb is PA changing its vocabulary: say so loudly.
        print(f"::warning::PA export has {comp['verbs_unclassified']} actions with unclassified verbs "
              f"{comp['verbs_unclassified_sample']} — add them to states/pa_adapter.VERB_CLASS")
    if "--dry-run" in argv:
        return 0
    sid, creds = os.environ.get("PA_SPREADSHEET_ID"), os.environ.get("GCP_CREDENTIALS")
    if not sid or not creds:
        print("::error::PA_SPREADSHEET_ID and GCP_CREDENTIALS must both be set to write; nothing was written")
        return 1
    import gspread
    from google.oauth2.service_account import Credentials
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(creds), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    write(records, comp, gc.open_by_key(sid), roster)
    print(f"wrote {len(records)} PA records to {TAB} (sheet {sid[:6]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
