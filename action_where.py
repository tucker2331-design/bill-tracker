"""Action_Where — for each bill, WHERE each history action happened, one code per history row (same order as the
bill's `history` in Bill_Tracker). Read by the site's What's new feed to show `SB509 (In the House) Referred to …`.

A SEPARATE tab (owner 2026-11-01): Virginia's Bill_Tracker output stays byte-identical; this is additive.
Codes: H = House, S = Senate, G = the Governor, 0 = the source lists no chamber, "-" = unknown (never guessed).

  Bill | Where (one code per history row, e.g. "HHHSS") | Short (JSON list of a state's own short action line per
  history row, built from structural fields; "" when the state has none and the site shows the source's text)

Each state's job derives the codes from STRUCTURAL fields only (Standard #3):
  * Virginia (bill_tracker.py): the action's own committee refid first; else LIS's own fixed-position chamber code
    (owner 2026-11-01: 100% coverage), validated against the refid every run (2026: 10,011/10,011 agree).
  * Pennsylvania (states/pa_adapter.py): each action's own `@actionChamber` (H / S / E = the Governor).
"""
import json

ACTION_WHERE_TAB = "Action_Where"
ACTION_WHERE_HEADER = ["Bill", "Where", "Short"]
CODE = {"House": "H", "Senate": "S", "Governor": "G"}
UNKNOWN = "-"
NO_CHAMBER = "0"   # the source itself lists no chamber for this action (VA: LIS's blank chamber code)


def rows_for(where_by_bill, short_by_bill=None):
    out = [ACTION_WHERE_HEADER]
    for bill in sorted(where_by_bill):
        short = (short_by_bill or {}).get(bill)
        out.append([bill, where_by_bill[bill], json.dumps(short, ensure_ascii=False) if short else ""])
    return out


def write(sheet, grid):
    """Replace the tab: overwrite in place, then blank any stale tail (never clear first — Codex #240)."""
    import gspread
    need = len(grid) + 20
    try:
        ws = sheet.worksheet(ACTION_WHERE_TAB)
        if ws.row_count < need:
            ws.resize(rows=need, cols=len(ACTION_WHERE_HEADER))
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=ACTION_WHERE_TAB, rows=need, cols=len(ACTION_WHERE_HEADER))
    ws.update(values=grid, range_name="A1")
    if ws.row_count > len(grid):
        ws.batch_clear([f"A{len(grid) + 1}:C{ws.row_count}"])
