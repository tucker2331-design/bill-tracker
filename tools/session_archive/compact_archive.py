"""
Automated storage management for the session archive — compact every tab to its real
data width, reclaiming the empty column padding that `copy_to` carries over.

WHY: the rollover hook archives a session by `copy_to`-ing the live Sheet1, which copies
Sheet1's FULL allocated grid. Sheet1 carries ~26 columns but only ~10 hold data, so each
`Session_<code>` snapshot is ~2x its real size in empty padding. Left alone, the archive
workbook (its own 10M-cell budget) fills in ~9 years; trimming each snapshot to its real
width ~doubles that — no new workbook, no Drive scope, no data loss (only empty cells go).

This is the archive analogue of `trim_api_cache_cols.py`, generalized to every archive
tab and run on a schedule so storage manages itself. The `sustainability_audit` CAPACITY
`archive-cells` check is the backstop that watches the cap years ahead.

For EACH tab in the archive workbook:
  target_cols = the populated width of the HEADER row (row 1).
  Safety: EVERY cell in cols (target_cols+1 .. col_count) must be empty (chunked scan) —
  abort that tab otherwise (never delete real data). Then resize(cols=target_cols).
Two-run protocol: DRY_RUN=true (default) reports; DRY_RUN=false applies. Irreversible.
"""
from __future__ import annotations

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

ARCHIVE_SPREADSHEET_ID = "1AA-dCUDAPvq59Hv01DqteEquBJ1kkqI0QR5ECd10QeA"
GOOGLE_SHEETS_CELL_CAP = 10_000_000
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
NON_EMPTY_REPORT_LIMIT = 10
CHUNK_SIZE = 50_000
MIN_WASTED_COLS = 2  # only act when there's something meaningful to reclaim


def col_to_letter(n: int) -> str:
    """1-indexed column number to A1 letter (handles AA, AB, ...)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def compact_tab(ws, dry_run) -> int:
    """Col-trim one tab to its header width. Returns cells reclaimed (0 if skipped)."""
    cols_before = int(ws.col_count)
    rows_before = int(ws.row_count)
    header = ws.row_values(1)
    target_cols = len(header)
    if target_cols <= 0:
        print(f"  • {ws.title}: empty header — skipped.")
        return 0
    if cols_before - target_cols < MIN_WASTED_COLS:
        print(f"  • {ws.title}: {cols_before} cols, header {target_cols} — already tight, skipped.")
        return 0

    # Safety: cols (target+1 .. col_count) must be empty across ALL rows.
    first_extra = col_to_letter(target_cols + 1)
    last_col = col_to_letter(cols_before)
    non_empty = []
    for chunk_start in range(1, rows_before + 1, CHUNK_SIZE):
        chunk_end = min(chunk_start + CHUNK_SIZE - 1, rows_before)
        for r_off, row in enumerate(ws.get_values(f"{first_extra}{chunk_start}:{last_col}{chunk_end}") or []):
            for c_off, cell in enumerate(row):
                if cell != "":
                    non_empty.append((chunk_start + r_off, target_cols + 1 + c_off, cell))
                    if len(non_empty) >= NON_EMPTY_REPORT_LIMIT:
                        break
            if len(non_empty) >= NON_EMPTY_REPORT_LIMIT:
                break
        if len(non_empty) >= NON_EMPTY_REPORT_LIMIT:
            break
    if non_empty:
        print(f"  ⚠️  {ws.title}: cols beyond header are NOT empty (e.g. {non_empty[:3]}) — SKIPPED (no trim).")
        return 0

    reclaimed = rows_before * (cols_before - target_cols)
    print(f"  • {ws.title}: {cols_before} -> {target_cols} cols; reclaim {reclaimed:,} cells.")
    if dry_run:
        return reclaimed
    ws.resize(cols=target_cols)
    print(f"    ✅ trimmed {ws.title}.")
    return reclaimed


def main() -> int:
    dry_run = os.environ.get("DRY_RUN", "true").strip().lower() in ("true", "1", "yes")
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        print("ERROR: GCP_CREDENTIALS not set.", file=sys.stderr)
        return 1
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES))
    archive = gc.open_by_key(ARCHIVE_SPREADSHEET_ID)

    tabs = archive.worksheets()
    before = sum(int(w.row_count) * int(w.col_count) for w in tabs)
    print(f"Archive: {archive.title}  ({len(tabs)} tabs)")
    print(f"Mode:    {'DRY RUN' if dry_run else 'LIVE WRITE'}")
    print(f"Before:  {before:,} cells ({100.0 * before / GOOGLE_SHEETS_CELL_CAP:.1f}% of cap)")
    print()

    total_reclaimed = sum(compact_tab(w, dry_run) for w in tabs)
    print()
    if dry_run:
        print(f"[DRY RUN] would reclaim {total_reclaimed:,} cells "
              f"({100.0 * total_reclaimed / GOOGLE_SHEETS_CELL_CAP:.1f}% of cap). Re-run with DRY_RUN=false to apply.")
    else:
        # Compaction is lossless (only empty cells removed), so the post-count is exact
        # arithmetic — no extra worksheets() API call (Gemini #136).
        after = before - total_reclaimed
        print(f"✅ Reclaimed {total_reclaimed:,} cells. After: {after:,} "
              f"({100.0 * after / GOOGLE_SHEETS_CELL_CAP:.1f}% of cap).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
