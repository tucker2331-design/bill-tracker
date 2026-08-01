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

# This module is executed as a script (`python3 tools/session_archive/archive.py`), which puts its own
# directory on sys.path — but NOT when it is imported from elsewhere. Insert explicitly so both work; the
# sentinel's _ledger_api documents the same trap, where the bare import raised ModuleNotFoundError and a
# fail-open handler swallowed it into silence.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capacity      # noqa: E402  (path must be set first)
import registry      # noqa: E402

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
    return gc, main, archive


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


def _registry_ws(gc):
    """The Archive_Registry worksheet in VA·Ops, created with its header on first use.

    Ops, not an archive workbook: the archives are the things that fill up and get replaced, so an index
    living inside one would roll away with it and the chain would lose its head."""
    ops = gc.open_by_key(OPS_ID)
    try:
        return ops.worksheet(registry.REGISTRY_TAB)
    except gspread.exceptions.WorksheetNotFound:
        ws = ops.add_worksheet(title=registry.REGISTRY_TAB, rows=200, cols=len(registry.REGISTRY_HEADER))
        ws.update(values=[registry.REGISTRY_HEADER], range_name="A1")
        print(f"📒 Created {registry.REGISTRY_TAB} in {ops.title}.")
        return ws


def _used_cells(book):
    """Allocated cells across every tab of a workbook — what Sheets actually bills against the 10M cap."""
    return capacity.workbook_cells((w.row_count, w.col_count) for w in book.worksheets())


def _create_next_archive(gc, title, share_with):
    """Create the next workbook in the chain and share it so a HUMAN can still open it.

    UNVERIFIED FROM HERE: this repo has no credentials in the dev environment, so the create call has never
    been executed. The known risk is that a service account may have no Drive storage quota of its own, in
    which case `gc.create` fails — so the caller treats failure as a hard stop with a specific remedy, and
    never as "carry on with the full workbook".

    The share is NOT optional. A workbook created by the service account is owned by the service account and
    is invisible to the owner until shared — an archive nobody can open is not an archive.
    """
    book = gc.create(title)
    book.share(share_with, perm_type="user", role="writer", notify=False)
    print(f"🆕 Created archive workbook '{title}' ({book.id}) and shared it with {share_with}.")
    return book


def snapshot_session(main, archive, gc=None):
    code = (os.environ.get("SESSION_CODE") or "").strip()
    if not code:
        print("ERROR: SESSION_CODE not set (e.g. 20261).", file=sys.stderr)
        return 1
    juris = (os.environ.get("JURISDICTION") or "VA").strip().upper()
    sheet1 = main.worksheet("Sheet1")
    name = f"Session_{code}"

    # Pre-registry path: without a gspread client we cannot read the chain, so behave exactly as before
    # rather than guessing. Callers that want rollover pass gc.
    if gc is None:
        verified_rows = _copy_tab(sheet1, archive, name)
        print(f"✅ Snapshotted live Sheet1 -> archive '{name}' (~{verified_rows:,} rows, snapshot verified).")
        return 0

    reg_ws = _registry_ws(gc)
    records, malformed = registry.parse_rows(reg_ws.get_all_values())
    if malformed:
        # Counted and surfaced, never silently skipped (Standard #4). Not fatal: a malformed row cannot
        # make a VALID row wrong, and refusing to archive would be the worse failure.
        print(f"⚠️  {registry.REGISTRY_TAB}: {malformed} malformed row(s) ignored — they name no "
              f"jurisdiction/session/workbook. Archiving continues on the valid rows.")

    if registry.already_archived(records, juris, code):
        where = registry.find_session(records, juris, code)
        print(f"✅ {juris} session {code} is already archived in {where} — nothing to do (idempotent).")
        return 0

    # Where should it go? The registry is the authority; GENESIS_ARCHIVE seeds an EMPTY registry only.
    active_id = registry.resolve_active(records, juris)
    if active_id is None:
        genesis = registry.GENESIS_ARCHIVE.get(juris)
        if not genesis:
            print(f"ERROR: no archive is registered for jurisdiction {juris} and there is no genesis "
                  f"workbook for it. Refusing to guess a destination.", file=sys.stderr)
            return 1
        active_id, active_title = genesis
        print(f"📒 Registry has no {juris} rows yet — seeding the chain from {active_title} ({active_id}).")
    else:
        active_title = next((r.get("WorkbookTitle") for r in records
                             if r.get("WorkbookId") == active_id and r.get("WorkbookTitle")), active_id)

    dest = archive if active_id == archive.id else gc.open_by_key(active_id)

    # THE ROLL DECISION — "does the incoming session fit?", not "is it 80% full?" (see capacity.py).
    incoming = capacity.cells(sheet1.row_count, sheet1.col_count)
    used = _used_cells(dest)
    print(f"📏 {capacity.describe(used, incoming)}")
    if capacity.should_roll(used, incoming):
        share_with = (os.environ.get("ARCHIVE_SHARE_WITH") or "").strip()
        if not share_with:
            # Fail closed: creating a workbook nobody can open would "succeed" while losing the archive
            # to a service account's private Drive.
            print("ERROR: the active archive is full and ARCHIVE_SHARE_WITH is not set, so a new archive "
                  "workbook would be invisible to you. Set it to the account that should own access.",
                  file=sys.stderr)
            return 1
        title = registry.next_title(records, juris, f"{juris} · Archive")
        try:
            dest = _create_next_archive(gc, title, share_with)
        except Exception as exc:
            print(f"ERROR: could not create the next archive workbook '{title}': {exc}\n"
                  f"       The current archive cannot fit session {code}, so this is a HARD STOP — "
                  f"writing anyway would fail at the 10M cell cap mid-copy.\n"
                  f"       If this is a Drive storage-quota error, the service account cannot own files; "
                  f"create '{title}' manually, share it with the service account as Editor, and add a "
                  f"{registry.REGISTRY_TAB} row for it.", file=sys.stderr)
            return 1
        active_id, active_title = dest.id, title

    verified_rows = _copy_tab(sheet1, dest, name)   # copies AND confirms it landed intact (raises otherwise)
    # Only NOW is the session safely archived, so only now does the registry claim it exists.
    reg_ws.append_row(registry.new_row(juris, code, active_id, active_title,
                                       sheet1.row_count, sheet1.col_count),
                      value_input_option="RAW")
    print(f"✅ Snapshotted live Sheet1 -> '{active_title}' tab '{name}' "
          f"(~{verified_rows:,} rows, snapshot verified, registry updated).")
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
    gc, main, archive = _open()
    dispatch = {"verify": verify, "migrate-c7": migrate_c7, "shard-witness": shard_witness}
    # snapshot-session is the only mode that needs the CLIENT (to read the registry and, when the active
    # archive is full, to create the next workbook in the chain). Passed explicitly rather than widening
    # every handler's signature with a parameter three of them would ignore.
    if mode == "snapshot-session":
        return snapshot_session(main, archive, gc)
    fn = dispatch.get(mode)
    if not fn:
        print(f"ERROR: unknown MODE {mode!r} (verify | snapshot-session | migrate-c7 | shard-witness).",
              file=sys.stderr)
        return 1
    return fn(main, archive)


if __name__ == "__main__":
    sys.exit(main_())
