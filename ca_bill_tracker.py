"""California scheduled job — the CA intake written to California's OWN spreadsheet, read by the CA site the same way
the Virginia and Pennsylvania sites read theirs (same Bill_Tracker layout, completeness payload at AA1, one
Metrics_History heartbeat row).

  * Fetching: states/ca_fetch.BulkFetcher — pubinfo bulk files only (the interactive leginfo site is never
    fetched), streamed to disk, at most once per URL per 20 h, honest User-Agent, a 401/403/429 stops the run.
  * Session: the newest `pubinfo_<year>.zip` named on the download index (discovered, never hardcoded). That file is
    rebuilt each Sunday; Legislative Counsel publishes daily — the site says "as of" the export, never faster.
  * Building: states/ca_adapter.run_intake (fail closed on a partial universe).

Usage:  python3 ca_bill_tracker.py --dry-run   # fetch + build, print the completeness payload, write nothing
        python3 ca_bill_tracker.py             # also write (needs CA_SPREADSHEET_ID + GCP_CREDENTIALS)
"""
import datetime
import json
import os
import re
import sys

import pytz

from bill_rows import BILL_TRACKER_HEADER, bill_tracker_rows
from states import ca_adapter, ca_pubinfo, get_state
from states.ca_fetch import BulkFetcher

CA = get_state("CA")
TAB = "Bill_Tracker"
COMPLETENESS_CELL = "AA1"
if len(BILL_TRACKER_HEADER) >= 27:
    raise RuntimeError(f"Bill_Tracker data ({len(BILL_TRACKER_HEADER)} cols) would reach {COMPLETENESS_CELL}")
STATUS_HEADER = "Status (California Legislature)"
METRICS_TAB, METRICS_HEADER = "Metrics_History", ["RunTimestampUTC", "Status", "Origin", "Outcome"]
ORIGIN = "bill_system_metrics"
CACHE = os.environ.get("CA_CACHE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ca_cache"))


def current_session_year(index_html: str) -> str:
    years = sorted(set(re.findall(r'href="pubinfo_(\d{4})\.zip"', index_html)))
    if not years:
        raise ValueError("CA download index lists no pubinfo_<year>.zip — refusing to guess a session (fail closed)")
    return years[-1]


def build(fetcher: BulkFetcher, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.astimezone(pytz.timezone(CA.timezone)).date()
    year = current_session_year(fetcher.get(CA.urls["index"]).decode("utf-8", "replace"))
    schema = ca_pubinfo.load_schema(fetcher.get(CA.urls["index"] + "pubinfo_load.zip"))
    ex = ca_pubinfo.Export(fetcher.path(CA.urls["session_zip"].format(year=year)), schema)
    records, comp = ca_adapter.run_intake(ex, today, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    comp["requests_made"] = fetcher.requests_made
    return records, comp


def write(records, comp, sheet):
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
    try:
        mh = sheet.worksheet(METRICS_TAB)
    except gspread.exceptions.WorksheetNotFound:
        mh = sheet.add_worksheet(title=METRICS_TAB, rows=1000, cols=4)
        mh.update(values=[METRICS_HEADER], range_name="A1")
    status = "OK" if comp["end_status_unclassified"] == 0 and not comp["rows_with_wrong_field_count"] else "WARN"
    mh.append_row([comp["checked_at_utc"], status, ORIGIN, json.dumps({k: comp[k] for k in (
        "records_written", "end_status_unclassified", "actions_rescinded", "end_status_blank")})])


def main(argv):
    fetcher = BulkFetcher(CACHE)
    records, comp = build(fetcher)
    print(json.dumps(comp, indent=1))
    if "--dry-run" in argv:
        return 0
    sid = os.environ.get("CA_SPREADSHEET_ID")
    creds = os.environ.get("GCP_CREDENTIALS")
    if not sid or not creds:
        print("::error::CA_SPREADSHEET_ID and GCP_CREDENTIALS are required to write (owner step)")
        return 1
    import gspread
    gc = gspread.service_account_from_dict(json.loads(creds))
    write(records, comp, gc.open_by_key(sid))
    print(f"CA: wrote {len(records)} bills")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
