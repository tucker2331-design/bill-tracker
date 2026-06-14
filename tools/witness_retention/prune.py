#!/usr/bin/env python3
"""Schedule_Witness retention prune — the "L3b nightly audit" the worker expects.

WHY THIS EXISTS
---------------
calendar_worker.py appends a change-feed row to the Schedule_Witness tab every
cycle and declares WITNESS_RETENTION_DAYS = 90, but the in-cycle prune was REMOVED
(append + col_values + delete_rows on the same tab in one cycle races the Sheets
API). What was left is only a WARN canary that, when the tab crosses
WITNESS_CANARY_ROW_THRESHOLD, asks a human to "manually compact." That is a
Standard #8 violation (routine human maintenance) and the workbook's one unbounded-
growth path — the tab climbs toward the 10M-cell cap with no automated bound.

This job is the missing prune: it deletes witness rows older than the retention
horizon so the tab stays bounded with ZERO human action.

EXCLUSIVITY (no race with the 15-min/3-hour worker)
---------------------------------------------------
The workflow shares the `calendar-worker` GitHub Actions concurrency group with the
worker (cancel-in-progress: false), so the prune and the worker NEVER touch the tab
at the same time — exactly the "runs outside the cycle path and has exclusive use
of the tab" the worker comment requires.

SAFETY
------
  * Rows are append-only with a monotonic ISO `seen_at_utc` in column 1, so expired
    rows are a CONTIGUOUS prefix at the top. We delete only that leading prefix, in
    ONE delete_rows call, and STOP at the first row that is NOT expired — never
    deleting an interleaved newer row, never the header.
  * If column 1 is not parseable ISO timestamps, we ABORT (exit 1) instead of
    deleting blindly — a schema drift must alert, not prune the wrong rows.
  * No-op (exit 0) when nothing is expired.

Verified continuously by tools/verification/sustainability_audit.py (CAPACITY
retention check: asserts no Schedule_Witness row is older than the horizon).
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
WITNESS_TAB = "Schedule_Witness"
RETENTION_DAYS = 90  # mirrors calendar_worker.WITNESS_RETENTION_DAYS; the sustainability
                     # audit cross-checks the live result, so any drift surfaces there.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _parse_seen_at(s):
    """Parse the witness seen_at_utc at FULL precision (the worker writes
    '%Y-%m-%dT%H:%M:%SZ'). Full precision matters: truncating to the date and
    comparing against a time-precise cutoff would prune a boundary-day row up to a
    day early (Gemini #126). Returns an aware UTC datetime, or None if unparseable.
    """
    s = str(s).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    # Degraded/legacy fallback: a leading bare date (midnight) — still better than
    # aborting. Wrap the parse so a regex-shaped-but-invalid calendar date (e.g.
    # "2026-13-99") returns None instead of crashing (Gemini #126).
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
        ws = sheet.worksheet(WITNESS_TAB)
    except gspread.WorksheetNotFound:
        print(f"{WITNESS_TAB} tab does not exist yet — nothing to prune.")
        return 0

    # One bulk read of the timestamp column. We need the exact expired-prefix
    # boundary (not just the oldest row), and this validates every cell is a real
    # date along the way; a single column read in a daily job is well within budget.
    col1 = ws.col_values(1)
    n_data = len(col1) - 1  # row 1 is the header
    if n_data <= 0:
        print(f"{WITNESS_TAB}: {max(0, n_data)} data rows — nothing to prune.")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    expired = 0
    for i, v in enumerate(col1[1:], start=2):  # i = 1-based sheet row number
        s = str(v).strip()
        if s == "" or s.lower() in ("none", "nan", "null", "<na>"):
            # Empty / null-repr cell (trailing padding or a null-like value) — STOP
            # the prefix here. We never delete past an unknown boundary and never
            # abort on a benign blank (Gemini #126): prune the contiguous expired
            # block found so far.
            break
        seen = _parse_seen_at(s)
        if seen is None:
            # A NON-empty, unparseable value is genuine schema drift — abort rather
            # than prune blindly.
            print(f"ERROR: {WITNESS_TAB} column 1 at row {i} is not an ISO timestamp ({v!r}). "
                  f"Schema drift — ABORTING prune, no rows deleted.", file=sys.stderr)
            return 1
        if seen < cutoff:  # full-precision comparison — no date truncation, no off-by-one
            expired += 1
        else:
            break  # first non-expired row — stop; we only delete the contiguous old prefix

    if expired == 0:
        print(f"{WITNESS_TAB}: {n_data:,} data rows, oldest within {RETENTION_DAYS}d — nothing to prune.")
        return 0

    # Delete the leading expired block: sheet rows 2 .. expired+1 (header is row 1).
    ws.delete_rows(2, expired + 1)
    print(f"✅ {WITNESS_TAB}: pruned {expired:,} rows older than {RETENTION_DAYS}d "
          f"({n_data:,} → {n_data - expired:,} data rows).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
