"""
Read-only audit of the Mastermind DB workbook's cell consumption.

Triggered by .github/workflows/cell_count_audit.yml (workflow_dispatch).
Reports per-worksheet allocated rows × cols, sorted desc, with %-of-total
and %-of-10M-cap. Diagnoses which sheets dominate the workbook so the
follow-up architectural decision (Option A: shrink Sheet1, Option B:
split workbook, Option C: move bulk data off Sheets) can be made on
data, not vibes.

Context: the 2026-04-28 full-session worker run (Mastermind Ghost Worker
2 #825, Actions run 25036914465) crashed at calendar_worker.py:2972 on
`worksheet.update(values=sheet_data, range_name="A1")` with
`gspread.exceptions.APIError: [400]: This action would increase the
number of cells in the workbook above the limit of 10000000 cells.`
The pipeline ran through 64,891 HISTORY rows successfully; only the
final writeback hit the cap. This audit measures the post-rejection
cell distribution (the failed write did not commit, so the workbook
state seen here is the state at the moment of rejection).

Read-only. Does NOT mutate any worksheet, does NOT create or delete
worksheets, does NOT touch the workbook's grid dimensions.
"""

from __future__ import annotations

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

GOOGLE_SHEETS_CELL_CAP = 10_000_000
SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def main() -> int:
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        print("ERROR: GCP_CREDENTIALS env var not set.", file=sys.stderr)
        return 1

    gc = gspread.authorize(
        Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    )
    sheet = gc.open_by_key(SPREADSHEET_ID)

    # gspread's sheet.worksheets() returns each worksheet with row_count
    # and col_count properties. These are the *allocated* dimensions —
    # the dimensions Google bills against the 10M cap, NOT the populated
    # cell count. That is the right number for this audit; the cap
    # rejection was triggered by an attempted increase to allocated
    # dimensions, not by populated content.
    rows = []
    for ws in sheet.worksheets():
        rc = int(ws.row_count)
        cc = int(ws.col_count)
        rows.append({"title": ws.title, "rows": rc, "cols": cc, "cells": rc * cc})

    rows.sort(key=lambda r: r["cells"], reverse=True)
    total = sum(r["cells"] for r in rows)
    cap = GOOGLE_SHEETS_CELL_CAP
    pct_of_cap = 100.0 * total / cap if cap else 0.0
    headroom = cap - total

    print()
    print(f"Workbook:        {sheet.title}")
    print(f"Spreadsheet ID:  {SPREADSHEET_ID}")
    print(f"Worksheet count: {len(rows)}")
    print()
    header = f"{'#':>3}  {'rows':>9}  {'cols':>5}  {'cells':>13}  {'% wb':>6}  {'% cap':>6}  title"
    print(header)
    print("-" * len(header))
    for i, r in enumerate(rows, start=1):
        share = 100.0 * r["cells"] / total if total else 0.0
        cap_share = 100.0 * r["cells"] / cap if cap else 0.0
        print(
            f"{i:>3}  {r['rows']:>9,}  {r['cols']:>5,}  {r['cells']:>13,}  "
            f"{share:>5.1f}%  {cap_share:>5.1f}%  {r['title']}"
        )
    print("-" * len(header))
    print(f"{'TOTAL':>3}  {'':>9}  {'':>5}  {total:>13,}  100.0%  {pct_of_cap:>5.1f}%")
    print()
    print(f"Google Sheets per-workbook cap: {cap:,} cells")
    print(f"Used:                           {total:,} ({pct_of_cap:.2f}% of cap)")
    print(f"Headroom:                       {headroom:,} cells")
    print()

    if rows:
        biggest = rows[0]
        biggest_share = 100.0 * biggest["cells"] / total if total else 0.0
        biggest_cap_share = 100.0 * biggest["cells"] / cap if cap else 0.0
        print(
            f"Largest worksheet: '{biggest['title']}' "
            f"({biggest['cells']:,} cells, "
            f"{biggest_share:.1f}% of workbook, "
            f"{biggest_cap_share:.1f}% of cap)."
        )

        # If the top sheet alone is more than half the workbook, Option A
        # (shrink that sheet) is likely the right move. Otherwise the
        # workbook is broadly distributed and Option B/C deserve weight.
        # Codex (P2) review fix on PR-C6.1 / PR #36: reference the actual
        # dominant worksheet by name, not a hardcoded "Sheet1". The
        # measurement instrument must not pre-suppose which sheet is
        # the offender — that would steer PR-C6.2 toward the wrong target
        # whenever the dominant sheet happens to be (e.g.) API_Cache or
        # Schedule_Witness.
        if biggest_share > 50.0:
            print(
                f"Distribution: dominated by '{biggest['title']}' — "
                f"Option A (shrink '{biggest['title']}') is the natural first move."
            )
        else:
            print(
                "Distribution: spread across multiple sheets — "
                "Option B (split workbook) or Option C (move bulk data off Sheets) "
                "deserves equal weight against Option A."
            )
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
