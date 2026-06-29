#!/usr/bin/env python3
"""Metrics_History retention prune — the out-of-band bound for the Health-tab trend store.

WHY THIS EXISTS
---------------
calendar_worker.py appends THIS cycle's SYSTEM_ALERT / SYSTEM_METRICS rows to the
append-only Metrics_History tab every cycle, so the Health tab can show alert HISTORY
+ metric TRENDS (sparklines) instead of only the latest Sheet1 snapshot. Like
Schedule_Witness, the in-cycle path deliberately does NOT prune (append + col_values +
delete_rows on the same tab in one cycle races the Sheets API and can delete rows it
just wrote). Without an out-of-band prune the tab would climb toward the 10M-cell cap
with no automated bound — a Standard #8 violation (routine human maintenance).

This job is that prune: it deletes Metrics_History rows older than the retention horizon
so the tab stays bounded with ZERO human action.

EXCLUSIVITY (no race with the 15-min/3-hour worker)
---------------------------------------------------
The workflow shares the `calendar-worker` GitHub Actions concurrency group with the
worker (cancel-in-progress: false), so the prune and the worker NEVER touch the tab at
the same time — the same exclusivity Schedule_Witness's prune relies on.

SAFETY (identical contract to tools/witness_retention/prune.py)
---------------------------------------------------------------
  * Rows are append-only with a monotonic ISO `RunTimestampUTC` in column 1, so expired
    rows are a CONTIGUOUS prefix at the top. We delete only that leading prefix, in ONE
    delete_rows call, and STOP at the first row that is NOT expired — never deleting an
    interleaved newer row, never the header.
  * If column 1 is not parseable ISO timestamps, we ABORT (exit 1) instead of deleting
    blindly — a schema drift must alert, not prune the wrong rows.
  * No-op (exit 0) when nothing is expired, or when the tab does not exist yet.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
METRICS_HISTORY_TAB = "Metrics_History"
# 45 days: long enough for a multi-week trend sparkline + recent alert history, short
# enough that the denser (~1-6 rows/cycle) feed stays a rounding error against the cap.
# Mirrors calendar_worker's append cadence; the front-end never assumes a fixed window.
RETENTION_DAYS = 45
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _parse_run_ts(s):
    """Parse RunTimestampUTC at FULL precision (the worker writes '%Y-%m-%dT%H:%M:%SZ').
    Full precision matters: truncating to the date and comparing against a time-precise
    cutoff would prune a boundary-day row up to a day early. Returns an aware UTC datetime,
    or None if unparseable."""
    s = str(s).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    # Degraded/legacy fallback: a leading bare date (midnight). Guard the parse so a
    # regex-shaped-but-invalid calendar date returns None instead of crashing.
    m = re.match(r'(\d{4}-\d{2}-\d{2})$', s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def main() -> int:
    creds = os.environ.get("GCP_CREDENTIALS")
    if not creds:
        print("ERROR: GCP_CREDENTIALS not set.", file=sys.stderr)
        return 1
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds), scopes=SCOPES))
    sheet = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sheet.worksheet(METRICS_HISTORY_TAB)
    except gspread.WorksheetNotFound:
        print(f"{METRICS_HISTORY_TAB} tab does not exist yet — nothing to prune.")
        return 0

    col1 = ws.col_values(1)
    n_data = len(col1) - 1  # row 1 is the header
    if n_data <= 0:
        print(f"{METRICS_HISTORY_TAB}: {max(0, n_data)} data rows — nothing to prune.")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    expired = 0
    for i, v in enumerate(col1[1:], start=2):  # i = 1-based sheet row number
        s = str(v).strip()
        if s == "" or s.lower() in ("none", "nan", "null", "<na>"):
            # Empty / null-repr cell (trailing padding) — STOP the prefix here. Never delete
            # past an unknown boundary, never abort on a benign blank.
            break
        ts = _parse_run_ts(s)
        if ts is None:
            print(f"ERROR: {METRICS_HISTORY_TAB} column 1 at row {i} is not an ISO timestamp ({v!r}). "
                  f"Schema drift — ABORTING prune, no rows deleted.", file=sys.stderr)
            return 1
        if ts < cutoff:
            expired += 1
        else:
            break  # first non-expired row — stop; we only delete the contiguous old prefix

    if expired == 0:
        print(f"{METRICS_HISTORY_TAB}: {n_data:,} data rows, oldest within {RETENTION_DAYS}d — nothing to prune.")
        return 0

    ws.delete_rows(2, expired + 1)  # sheet rows 2 .. expired+1 (header is row 1)
    print(f"✅ {METRICS_HISTORY_TAB}: pruned {expired:,} rows older than {RETENTION_DAYS}d "
          f"({n_data:,} → {n_data - expired:,} data rows).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
