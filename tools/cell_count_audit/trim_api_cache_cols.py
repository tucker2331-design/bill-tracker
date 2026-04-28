"""
One-shot maintenance: trim API_Cache from 26 cols to 6 to reclaim quota.

PR-C6.1 audit (PR #36, Actions run 25037905960) showed:
  API_Cache: 353,811 rows × 26 cols = 9,199,086 cells (92.0% of workbook,
  92.0% of the 10M Google Sheets per-workbook cap).
  Workbook headroom: 3,377 cells.

API_Cache's logical schema is 6 columns:
  [Date, Committee, Time, SortTime, Status, Location]
See `calendar_worker.py:2819` (canonical header in compaction path).
The worker writes 6-col rows via `cache_sheet.append_rows(...)` at
`calendar_worker.py:2801` and reads by header via `get_all_records()`
at `calendar_worker.py:1522`. Cols 7-26 are empty padding inherited
from the worksheet's default grid size; nothing in the code path
populates them.

Math: 353,811 rows × 20 padding cols = 7,076,220 wasted cells (70.8%
of the workbook cap consumed by allocated-but-empty cells).

This script trims those padding columns. After the resize:
  - API_Cache: 353,811 × 6 = 2,122,866 cells
  - Workbook total: ~2.9M / 10M cap (29%)
  - Headroom: ~7.1M cells (>2,000x current)
The next full-session worker writeback at `calendar_worker.py:2972`
will succeed.

# Safety
The resize is irreversible — cells in cols 7-26 are deleted by the
Google Sheets API when col_count is reduced. To prevent data loss
this script aborts UNLESS:

1. Cols A-F (1-6) match the exact 6-label schema [Date, Committee,
   Time, SortTime, Status, Location].
2. EVERY cell in cols 7..col_count across ALL rows is empty.

Both checks must pass before `worksheet.resize(cols=6)` is called.

# Usage
Triggered manually via .github/workflows/trim_api_cache_cols.yml
(workflow_dispatch). Two-step pattern:
  1. First run: dry_run=true (default). Validates safety checks
     against live data, prints what would change, no write.
  2. Second run: dry_run=false. Performs the resize.

This split is intentional. The dry run is the second safety net
behind the in-code checks: a human reviews the workflow log before
permitting the destructive operation.
"""

from __future__ import annotations

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
TARGET_SHEET = "API_Cache"
EXPECTED_SCHEMA = ["Date", "Committee", "Time", "SortTime", "Status", "Location"]
TARGET_COL_COUNT = len(EXPECTED_SCHEMA)
GOOGLE_SHEETS_CELL_CAP = 10_000_000
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
NON_EMPTY_REPORT_LIMIT = 10


def col_to_letter(n: int) -> str:
    """1-indexed column number to A1-style letter (handles AA, AB, ...)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def main() -> int:
    dry_run = os.environ.get("DRY_RUN", "true").strip().lower() in ("true", "1", "yes")

    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        print("ERROR: GCP_CREDENTIALS env var not set.", file=sys.stderr)
        return 1

    gc = gspread.authorize(
        Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    )
    sheet = gc.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(TARGET_SHEET)

    rows_before = int(ws.row_count)
    cols_before = int(ws.col_count)
    cells_before = rows_before * cols_before

    print(f"Workbook:        {sheet.title}")
    print(f"Spreadsheet ID:  {SPREADSHEET_ID}")
    print(f"Target sheet:    {TARGET_SHEET}")
    print(f"Mode:            {'DRY RUN' if dry_run else 'LIVE WRITE'}")
    print()
    print(f"Before: {rows_before:,} rows × {cols_before} cols = {cells_before:,} cells")
    print()

    # === Safety check 1: schema match in cols A-F ===
    header_full = ws.row_values(1)
    if len(header_full) < TARGET_COL_COUNT:
        print(
            f"ABORT: header row has only {len(header_full)} cells; "
            f"expected at least {TARGET_COL_COUNT}.",
            file=sys.stderr,
        )
        return 1
    header_target = header_full[:TARGET_COL_COUNT]
    if header_target != EXPECTED_SCHEMA:
        print("ABORT: cols A-F do not match expected schema.", file=sys.stderr)
        print(f"  Expected: {EXPECTED_SCHEMA}", file=sys.stderr)
        print(f"  Actual:   {header_target}", file=sys.stderr)
        return 1
    print(f"[check 1] PASSED: cols A-F match expected schema {EXPECTED_SCHEMA}")

    # === Early-exit: already trimmed ===
    if cols_before == TARGET_COL_COUNT:
        print(
            f"\nNothing to do: API_Cache is already at {TARGET_COL_COUNT} cols. "
            f"Exiting cleanly."
        )
        return 0
    if cols_before < TARGET_COL_COUNT:
        print(
            f"ABORT: API_Cache has {cols_before} cols, fewer than the schema "
            f"requires ({TARGET_COL_COUNT}). Manual investigation needed.",
            file=sys.stderr,
        )
        return 1

    # === Safety check 2: cols 7..col_count empty across all rows ===
    first_extra_letter = col_to_letter(TARGET_COL_COUNT + 1)
    last_extra_letter = col_to_letter(cols_before)
    extra_range = f"{first_extra_letter}1:{last_extra_letter}{rows_before}"
    extra_col_count = cols_before - TARGET_COL_COUNT
    print(
        f"[check 2] reading {extra_range} "
        f"({rows_before:,} rows × {extra_col_count} padding cols, "
        f"{rows_before * extra_col_count:,} cells)..."
    )
    extra_values = ws.get_values(extra_range)

    non_empty: list[tuple[int, int, str]] = []
    for row_idx, row in enumerate(extra_values, start=1):
        for col_offset, cell in enumerate(row, start=0):
            if cell != "":
                col_idx = TARGET_COL_COUNT + 1 + col_offset
                non_empty.append((row_idx, col_idx, cell))
                if len(non_empty) >= NON_EMPTY_REPORT_LIMIT:
                    break
        if len(non_empty) >= NON_EMPTY_REPORT_LIMIT:
            break

    if non_empty:
        print(
            f"ABORT: cols beyond {TARGET_COL_COUNT} contain non-empty cells. "
            f"Showing first {len(non_empty)} hit(s):",
            file=sys.stderr,
        )
        for r, c, v in non_empty:
            print(f"  row={r:,} col={c} ({col_to_letter(c)}) value={v!r}", file=sys.stderr)
        print(
            "\nManual investigation required before resize. Either the schema "
            "changed and EXPECTED_SCHEMA needs updating, or there is real data "
            "outside the documented schema that must be migrated first.",
            file=sys.stderr,
        )
        return 1
    print(
        f"[check 2] PASSED: all {rows_before * extra_col_count:,} cells "
        f"in cols {TARGET_COL_COUNT + 1}..{cols_before} are empty."
    )

    # === Resize ===
    cells_after = rows_before * TARGET_COL_COUNT
    cells_reclaimed = cells_before - cells_after
    cap_pct_reclaimed = 100.0 * cells_reclaimed / GOOGLE_SHEETS_CELL_CAP

    print()
    print(
        f"Plan: resize {TARGET_SHEET} from "
        f"{rows_before:,} × {cols_before} = {cells_before:,} cells to "
        f"{rows_before:,} × {TARGET_COL_COUNT} = {cells_after:,} cells."
    )
    print(
        f"Reclaim: {cells_reclaimed:,} cells "
        f"({cap_pct_reclaimed:.1f}% of the 10M cap)."
    )

    if dry_run:
        print()
        print("DRY RUN — no resize performed.")
        print("To apply, re-run the workflow with `dry_run` toggled to false.")
        return 0

    print()
    print(f"LIVE WRITE — calling worksheet.resize(rows={rows_before:,}, cols={TARGET_COL_COUNT})...")
    ws.resize(rows=rows_before, cols=TARGET_COL_COUNT)
    print("Resize call returned cleanly.")

    # === Post-resize verification ===
    ws_after = sheet.worksheet(TARGET_SHEET)
    rows_check = int(ws_after.row_count)
    cols_check = int(ws_after.col_count)
    print()
    print(
        f"After:  {rows_check:,} rows × {cols_check} cols = "
        f"{rows_check * cols_check:,} cells"
    )
    if cols_check != TARGET_COL_COUNT:
        print(
            f"WARN: post-resize col count is {cols_check}, expected {TARGET_COL_COUNT}.",
            file=sys.stderr,
        )
        return 1
    if rows_check != rows_before:
        print(
            f"WARN: row count changed during resize ({rows_before} → {rows_check}). "
            f"Investigate before next worker cycle.",
            file=sys.stderr,
        )
        return 1
    print()
    print(
        f"Reclaimed: {cells_reclaimed:,} cells. "
        f"Re-run the cell_count_audit workflow to confirm new workbook totals."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
