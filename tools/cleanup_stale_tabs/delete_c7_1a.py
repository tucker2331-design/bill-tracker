#!/usr/bin/env python3
"""One-shot: delete the stale PR-C7.1a audit tabs to reclaim workbook cells.

CONTEXT: the `sustainability_audit` CAPACITY check found the Mastermind DB workbook
at ~79.7% of the 10M-cell cap. The `C7_1a_*` tabs are the DERIVED outputs of the
PR-C7.1a "derived-classifier viability" math-proof (a completed phase, 2026-05-11) —
read by NOTHING in production (only `tools/c7_1a_audit/audit.py`, which created them)
and fully regenerable from HISTORY.CSV + re-fetchable LIS data. Owner-authorized for
deletion on 2026-06-14 after that verification.

Mirrors `tools/cell_count_audit/trim_api_cache_cols.py` (one-shot `workflow_dispatch`
maintenance). Read-only by default — pass mode=delete to actually delete.

SAFETY:
  * Deletes ONLY worksheets whose title starts with the C7_1a audit prefix — refuses
    every other tab. The prefix is that audit's exclusive namespace.
  * `mode=dry-run` (default) lists exactly what WOULD be deleted (titles, rows, cells)
    and the projected workbook cell-count, and deletes nothing.
  * `mode=delete` deletes them, logging each, with the workbook cell-count before/after.
  * Never deletes the last remaining worksheet (a workbook must keep >=1 tab).
"""
from __future__ import annotations

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
PREFIX = "C7_1a"  # the PR-C7.1a audit's exclusive tab namespace
GOOGLE_SHEETS_CELL_CAP = 10_000_000
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def main() -> int:
    mode = (os.environ.get("MODE") or (sys.argv[1] if len(sys.argv) > 1 else "dry-run")).strip().lower()
    if mode not in ("dry-run", "delete"):
        print(f"ERROR: MODE must be 'dry-run' or 'delete', got {mode!r}.", file=sys.stderr)
        return 1

    creds = os.environ.get("GCP_CREDENTIALS")
    if not creds:
        print("ERROR: GCP_CREDENTIALS not set.", file=sys.stderr)
        return 1
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds), scopes=SCOPES))
    sheet = gc.open_by_key(SPREADSHEET_ID)

    all_ws = sheet.worksheets()
    total_before = sum(int(w.row_count) * int(w.col_count) for w in all_ws)
    targets = [w for w in all_ws if w.title.startswith(PREFIX)]

    print(f"Workbook: {sheet.title}")
    print(f"Cells before: {total_before:,} ({100.0 * total_before / GOOGLE_SHEETS_CELL_CAP:.1f}% of the 10M cap)")
    print(f"Tabs matching prefix {PREFIX!r}: {len(targets)}")
    if not targets:
        print("Nothing to delete.")
        return 0

    freed = 0
    for w in targets:
        cells = int(w.row_count) * int(w.col_count)
        freed += cells
        print(f"  • {w.title:24} {int(w.row_count):>8,} rows × {int(w.col_count):>3} cols = {cells:>11,} cells")

    if len(targets) >= len(all_ws):
        print("REFUSING: that would delete every worksheet; a workbook must keep at least one tab.", file=sys.stderr)
        return 1

    print(f"\nWould free {freed:,} cells → projected {total_before - freed:,} "
          f"({100.0 * (total_before - freed) / GOOGLE_SHEETS_CELL_CAP:.1f}% of cap).")

    if mode == "dry-run":
        print("\n[dry-run] No tabs deleted. Re-run with MODE=delete to apply.")
        return 0

    print("\n[delete] applying…")
    for w in targets:
        sheet.del_worksheet(w)
        print(f"  ✅ deleted {w.title}")
    after = sum(int(w.row_count) * int(w.col_count) for w in sheet.worksheets())
    print(f"\nCells after: {after:,} ({100.0 * after / GOOGLE_SHEETS_CELL_CAP:.1f}% of cap). Freed {total_before - after:,}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
