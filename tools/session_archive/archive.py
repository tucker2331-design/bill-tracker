#!/usr/bin/env python3
"""Session archive — preserve each session's output (and the one-time C7_1a audit
corpus) in a SEPARATE archive workbook, so the live workbook stays under the 10M-cell
cap and every session is kept, organized and labelled, for later trend analysis.

The archive workbook is its own 10M-cell budget; one clearly-named tab per session
(`Session_<code>`). This module is the mechanism; a worker rollover hook will call
`snapshot-session` automatically on session change (follow-up). For now it is run via
workflow_dispatch to (a) verify access, (b) take the first 2026 snapshot, (c) migrate
the dead C7_1a tabs out of the live workbook (preserved in the archive, not deleted).

Modes (MODE env or argv[1]):
  verify            — open BOTH workbooks, print titles + archive tabs. Confirms the
                      share landed on the service account. Read-only.
  snapshot-session  — copy the live `Sheet1` -> archive tab `Session_<SESSION_CODE>`
                      (the session's calendar output). Idempotent: replaces an existing
                      snapshot of the same session.
  migrate-c7        — copy the `C7_1a_*` audit tabs -> archive (PRESERVE), verify the
                      copies exist, then ONLY IF CONFIRM=delete remove them from the
                      live workbook to reclaim cap. Copy-only by default.
  shard-witness     — A-2 Part 2: copy `Schedule_Witness` VA·Live -> VA·Ops (verify),
                      then ONLY IF CONFIRM=delete remove it from VA·Live. Afterwards set
                      the worker variable WITNESS_WORKBOOK=ops. Copy-only by default.

Never deletes from the live workbook unless the copy is confirmed present in the archive.
"""
from __future__ import annotations

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

MAIN_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"       # VA · Live
ARCHIVE_ID = "1AA-dCUDAPvq59Hv01DqteEquBJ1kkqI0QR5ECd10QeA"   # VA · Archive
OPS_ID = "1X7wa4brFROP9Bn81Esf4z3zjlxTZvpKeUdPWpyBkD3c"        # VA · Ops (A-2 Part 2 shard target)
C7_PREFIX = "C7_1a"  # the dead PR-C7.1a audit namespace
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _open():
    creds = os.environ.get("GCP_CREDENTIALS")
    if not creds:
        print("ERROR: GCP_CREDENTIALS not set.", file=sys.stderr)
        sys.exit(1)
    try:
        info = json.loads(creds)
    except json.JSONDecodeError as exc:
        print(f"ERROR: GCP_CREDENTIALS is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)
    gc = gspread.authorize(Credentials.from_service_account_info(info, scopes=SCOPES))
    try:
        main = gc.open_by_key(MAIN_ID)
    except Exception as exc:
        print(f"ERROR: cannot open the MAIN workbook: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        archive = gc.open_by_key(ARCHIVE_ID)
    except Exception as exc:
        print(f"ERROR: cannot open the ARCHIVE workbook ({ARCHIVE_ID}). Is it shared with the "
              f"service account as Editor? Underlying error: {exc}", file=sys.stderr)
        sys.exit(1)
    return main, archive


def _snapshot_dim_mismatch(src_rows, src_cols, arch_rows, arch_cols):
    """Pure: '' if the archived grid dims equal the source, else a description. `copy_to` duplicates the
    full grid, so any inequality signals a partial snapshot. Kept in sync with calendar_worker.py."""
    if int(src_rows) != int(arch_rows) or int(src_cols) != int(arch_cols):
        return f"archived grid {arch_rows}x{arch_cols} != live {src_rows}x{src_cols}"
    return ""


def _verify_copy(archive, target_name, src_ws):
    """Confirm-before-trust: the archived tab exists by its canonical name, same grid dims + header row as
    the source. Raises on any mismatch (the caller must NOT treat the copy as good). Mirrors
    calendar_worker._verify_archived_snapshot so the worker's rollover hook and this tool agree."""
    try:
        arch_ws = archive.worksheet(target_name)
    except gspread.exceptions.WorksheetNotFound as exc:
        raise RuntimeError(f"archived tab '{target_name}' not found after copy — rename did not land") from exc
    mismatch = _snapshot_dim_mismatch(src_ws.row_count, src_ws.col_count, arch_ws.row_count, arch_ws.col_count)
    if mismatch:
        raise RuntimeError(f"snapshot '{target_name}' {mismatch} — looks partial")
    if (src_ws.row_values(1) or []) != (arch_ws.row_values(1) or []):   # `or []`: gspread None-safe (Gemini #202)
        raise RuntimeError(f"snapshot '{target_name}' header row differs from source — content mismatch")
    return int(arch_ws.row_count)


def _copy_tab(src_ws, dest_book, target_name):
    """Copy src_ws into `dest_book` (the ARCHIVE workbook for snapshot/migrate; the OPS workbook for the A-2
    shard) as `target_name`, replacing any existing tab of that name (idempotent). Uses copy_to + ONE atomic
    batch_update (delete-old-then-rename, in that order so there's no title collision and the dest never
    drops to 0 sheets). No full worksheet-list fetch in the loop, and no reliance on the gspread Worksheet
    constructor / get_worksheet_by_id typing — version-robust (Gemini #131). VERIFIES the copy landed intact
    before returning (confirm-before-trust); raises on mismatch."""
    try:
        old_id = dest_book.worksheet(target_name).id  # a pre-existing same-named target, if any
    except gspread.exceptions.WorksheetNotFound:
        old_id = None
    props = src_ws.copy_to(dest_book.id)  # dest ID from the book itself — can't mismatch dest_book (Gemini #208)
    requests = []
    if old_id is not None:
        requests.append({"deleteSheet": {"sheetId": int(old_id)}})  # drop the stale target first
    requests.append({"updateSheetProperties": {
        "properties": {"sheetId": int(props["sheetId"]), "title": target_name},
        "fields": "title"}})
    dest_book.batch_update({"requests": requests})
    return _verify_copy(dest_book, target_name, src_ws)   # raises unless the copy is confirmed intact


def verify(main, archive):
    main_tabs = main.worksheets()
    arch_tabs = archive.worksheets()  # fetch once, reuse (Gemini #131)
    print(f"MAIN:    {main.title}  ({len(main_tabs)} tabs)")
    print(f"ARCHIVE: {archive.title}  ({len(arch_tabs)} tabs)")
    print("Archive tabs:", [w.title for w in arch_tabs])
    print("✅ Service account can open BOTH workbooks — the share is correct.")
    return 0


def snapshot_session(main, archive):
    code = (os.environ.get("SESSION_CODE") or "").strip()
    if not code:
        print("ERROR: SESSION_CODE not set (e.g. 20261).", file=sys.stderr)
        return 1
    sheet1 = main.worksheet("Sheet1")
    name = f"Session_{code}"
    verified_rows = _copy_tab(sheet1, archive, name)   # copies AND confirms it landed intact (raises otherwise)
    print(f"✅ Snapshotted live Sheet1 -> archive '{name}' (~{verified_rows:,} rows, snapshot verified).")
    return 0


def migrate_c7(main, archive):
    targets = [w for w in main.worksheets() if w.title.startswith(C7_PREFIX)]
    if not targets:
        print(f"No {C7_PREFIX}* tabs in the live workbook — nothing to migrate.")
        return 0
    for w in targets:
        _copy_tab(w, archive, w.title)
        print(f"  ✅ copied {w.title} -> archive ({int(w.row_count):,} rows)")
    # Verify EVERY copy is present in the archive before any deletion from live.
    arch_titles = {w.title for w in archive.worksheets()}
    missing = [w.title for w in targets if w.title not in arch_titles]
    if missing:
        print(f"ABORT: archive is missing {missing} after copy — NOT deleting from live.", file=sys.stderr)
        return 1
    if (os.environ.get("CONFIRM") or "").lower() != "delete":
        print(f"[copy-only] {len(targets)} tab(s) now preserved in the archive. Re-run with "
              f"CONFIRM=delete to remove them from the live workbook and reclaim cap.")
        return 0
    main.batch_update({"requests": [{"deleteSheet": {"sheetId": int(w.id)}} for w in targets]})
    print(f"✅ removed {len(targets)} {C7_PREFIX}* tab(s) from the live workbook (preserved in the archive).")
    return 0


def shard_witness(main, archive):
    """A-2 Part 2: relocate `Schedule_Witness` from VA·Live → VA·Ops (copy-verify-then-delete), then the
    worker keeps the witness lean in VA·Ops. Copy-only by default (safe); re-run with CONFIRM=delete to
    remove it from VA·Live once the copy is verified present. AFTER a confirmed delete, set the worker
    variable WITNESS_WORKBOOK=ops so it writes/reads the witness in VA·Ops. Never deletes before the copy
    verifies (the same confirm-before-destroy ethic as migrate-c7)."""
    tab = "Schedule_Witness"
    try:
        src = main.worksheet(tab)
    except gspread.exceptions.WorksheetNotFound:
        print(f"{tab} not in VA·Live — nothing to shard (already moved, or none created yet).")
        return 0
    ops = main.client.open_by_key(OPS_ID)
    rows = _copy_tab(src, ops, tab)   # copies AND verifies (raises on mismatch)
    print(f"✅ Copied {tab} → VA·Ops ({rows:,} rows, verified present).")
    if (os.environ.get("CONFIRM") or "").lower() != "delete":
        print(f"[copy-only] {tab} is now in VA·Ops. Re-run with CONFIRM=delete to remove it from VA·Live "
              f"and reclaim its cells, THEN set the worker variable WITNESS_WORKBOOK=ops.")
        return 0
    main.batch_update({"requests": [{"deleteSheet": {"sheetId": int(src.id)}}]})
    print(f"✅ Removed {tab} from VA·Live (reclaimed its cells; preserved + verified in VA·Ops). "
          f"NOW set the worker variable WITNESS_WORKBOOK=ops so it uses VA·Ops going forward.")
    return 0


def main_():
    mode = (os.environ.get("MODE") or (sys.argv[1] if len(sys.argv) > 1 else "verify")).strip().lower()
    main, archive = _open()
    dispatch = {"verify": verify, "snapshot-session": snapshot_session, "migrate-c7": migrate_c7,
                "shard-witness": shard_witness}
    fn = dispatch.get(mode)
    if not fn:
        print(f"ERROR: unknown MODE {mode!r} (verify | snapshot-session | migrate-c7).", file=sys.stderr)
        return 1
    return fn(main, archive)


if __name__ == "__main__":
    sys.exit(main_())
