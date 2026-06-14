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

Never deletes from the live workbook unless the copy is confirmed present in the archive.
"""
from __future__ import annotations

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

MAIN_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
ARCHIVE_ID = "1AA-dCUDAPvq59Hv01DqteEquBJ1kkqI0QR5ECd10QeA"
C7_PREFIX = "C7_1a"  # the dead PR-C7.1a audit namespace
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _open():
    creds = os.environ.get("GCP_CREDENTIALS")
    if not creds:
        print("ERROR: GCP_CREDENTIALS not set.", file=sys.stderr)
        sys.exit(1)
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds), scopes=SCOPES))
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


def _copy_tab(src_ws, archive, target_name):
    """Copy src_ws into the archive workbook as `target_name`, replacing any existing
    tab of that name (so re-runs are idempotent). Copy FIRST, then delete the old
    same-named tab, then rename — so the archive never momentarily drops to 0 sheets
    (a single-sheet workbook cannot have its only tab deleted) (Gemini #131)."""
    props = src_ws.copy_to(ARCHIVE_ID)  # Sheets copyTo -> {'sheetId':..., 'title':'Copy of ...'}
    new = archive.get_worksheet_by_id(props["sheetId"])
    try:
        old = archive.worksheet(target_name)
        if old.id != new.id:
            archive.del_worksheet(old)
    except gspread.WorksheetNotFound:
        pass
    new.update_title(target_name)
    return new


def verify(main, archive):
    print(f"MAIN:    {main.title}  ({len(main.worksheets())} tabs)")
    print(f"ARCHIVE: {archive.title}  ({len(archive.worksheets())} tabs)")
    print("Archive tabs:", [w.title for w in archive.worksheets()])
    print("✅ Service account can open BOTH workbooks — the share is correct.")
    return 0


def snapshot_session(main, archive):
    code = (os.environ.get("SESSION_CODE") or "").strip()
    if not code:
        print("ERROR: SESSION_CODE not set (e.g. 20261).", file=sys.stderr)
        return 1
    sheet1 = main.worksheet("Sheet1")
    name = f"Session_{code}"
    _copy_tab(sheet1, archive, name)
    print(f"✅ Snapshotted live Sheet1 -> archive '{name}' (~{int(sheet1.row_count):,} allocated rows).")
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


def main_():
    mode = (os.environ.get("MODE") or (sys.argv[1] if len(sys.argv) > 1 else "verify")).strip().lower()
    main, archive = _open()
    dispatch = {"verify": verify, "snapshot-session": snapshot_session, "migrate-c7": migrate_c7}
    fn = dispatch.get(mode)
    if not fn:
        print(f"ERROR: unknown MODE {mode!r} (verify | snapshot-session | migrate-c7).", file=sys.stderr)
        return 1
    return fn(main, archive)


if __name__ == "__main__":
    sys.exit(main_())
