"""
One-shot maintenance: shrink the API_Cache grid's ALLOCATED ROW count to fit its
actual data, reclaiming workbook cells.

The companion `trim_api_cache_cols.py` reclaimed the column padding (26 -> 6 cols),
but the worksheet's ~353,811 ALLOCATED rows were never reduced — and only ~1,632 are
populated (verified 2026-06-15: 1,479 rows of 2026 data + 152 of 2025). The
~352,000 empty allocated rows × 6 cols = ~2.1M cells (~27% of the workbook) sit idle
against the 10M-cell cap. This is the row analogue of the column fix.

The sustainability audit's CAPACITY check flagged API_Cache by ALLOCATED row_count;
the actual DATA is small and bounded (one session's (Date,Committee) schedule entries),
so the fix is a grid RESIZE, not a data prune.

Mirrors trim_api_cache_cols.py's safety pattern:
  1. Header in cols A-F matches the expected schema.
  2. EVERY cell in rows beyond the target is empty (chunked scan) — so the resize
     cannot delete real data.
Both must pass before `worksheet.resize(rows=target)` is called. Two-run protocol:
DRY_RUN=true (default) reports; DRY_RUN=false performs the resize. Irreversible.
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
ROW_BUFFER = 5_000   # headroom above the populated extent so appends don't immediately re-grow
MIN_TARGET_ROWS = 2_000
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
NON_EMPTY_REPORT_LIMIT = 10
CHUNK_SIZE = 50_000


def main() -> int:
    dry_run = os.environ.get("DRY_RUN", "true").strip().lower() in ("true", "1", "yes")

    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        print("ERROR: GCP_CREDENTIALS env var not set.", file=sys.stderr)
        return 1
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES))
    sheet = gc.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(TARGET_SHEET)

    rows_before = int(ws.row_count)
    cols_before = int(ws.col_count)
    cells_before = rows_before * cols_before

    print(f"Workbook:        {sheet.title}")
    print(f"Target sheet:    {TARGET_SHEET}")
    print(f"Mode:            {'DRY RUN' if dry_run else 'LIVE WRITE'}")
    print(f"Before: {rows_before:,} rows × {cols_before} cols = {cells_before:,} cells")
    print()

    # === Safety check 1: header schema in cols A-F ===
    header_full = ws.row_values(1)
    if header_full[:TARGET_COL_COUNT] != EXPECTED_SCHEMA:
        print("ABORT: cols A-F do not match the expected schema.", file=sys.stderr)
        print(f"  Expected: {EXPECTED_SCHEMA}", file=sys.stderr)
        print(f"  Actual:   {header_full[:TARGET_COL_COUNT]}", file=sys.stderr)
        return 1
    print(f"[check 1] PASSED: cols A-F match {EXPECTED_SCHEMA}")

    # === Determine the populated extent + target row count ===
    # col A (Date) is the key — every data row has it, so its populated length is the
    # data extent. The check-2 scan independently confirms nothing lives below target.
    populated_rows = len(ws.col_values(1))  # includes the header row
    target_rows = max(populated_rows + ROW_BUFFER, MIN_TARGET_ROWS)
    print(f"[extent] {populated_rows:,} populated rows (col A); target after trim: "
          f"{target_rows:,} rows ({ROW_BUFFER:,} buffer).")

    if target_rows >= rows_before:
        print(f"\nNothing to do: target {target_rows:,} >= current {rows_before:,} rows. Exiting cleanly.")
        return 0

    # === Safety check 2: every cell in rows (target+1 .. row_count) is empty ===
    # Chunked scan (mirrors the cols tool) so we never pull millions of cells at once.
    first_extra = target_rows + 1
    print(f"[check 2] scanning A{first_extra}:F{rows_before} "
          f"({rows_before - target_rows:,} rows × {TARGET_COL_COUNT} cols) in {CHUNK_SIZE:,}-row chunks...")
    non_empty = []
    for chunk_start in range(first_extra, rows_before + 1, CHUNK_SIZE):
        chunk_end = min(chunk_start + CHUNK_SIZE - 1, rows_before)
        for r_offset, row in enumerate(ws.get_values(f"A{chunk_start}:F{chunk_end}")):
            for c_offset, cell in enumerate(row):
                if cell != "":
                    non_empty.append((chunk_start + r_offset, c_offset + 1, cell))
                    if len(non_empty) >= NON_EMPTY_REPORT_LIMIT:
                        break
            if len(non_empty) >= NON_EMPTY_REPORT_LIMIT:
                break
        if len(non_empty) >= NON_EMPTY_REPORT_LIMIT:
            break

    if non_empty:
        print(f"ABORT: rows beyond {target_rows:,} contain non-empty cells "
              f"(showing first {len(non_empty)}). NO resize.", file=sys.stderr)
        for r, c, v in non_empty:
            print(f"  row={r:,} col={c} value={v!r}", file=sys.stderr)
        print("Raise ROW_BUFFER or investigate before trimming.", file=sys.stderr)
        return 1
    print(f"[check 2] PASSED: all rows beyond {target_rows:,} are empty.")

    cells_after = target_rows * TARGET_COL_COUNT
    print(f"\nWould resize {rows_before:,} -> {target_rows:,} rows; reclaim "
          f"{cells_before - cells_after:,} cells (workbook drops by that much).")

    if dry_run:
        print("\n[DRY RUN] No changes. Re-run with DRY_RUN=false to apply.")
        return 0

    ws.resize(rows=target_rows)
    print(f"\n✅ Resized {TARGET_SHEET} to {target_rows:,} rows "
          f"({cells_before - cells_after:,} cells reclaimed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
