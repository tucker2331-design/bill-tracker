"""Provision the NEXT session-archive workbook: create it, share it with the owner,
and record it as the active archive in a registry cell the worker reads.

This is the auto-create half of "full-fidelity archive that never needs a manual book
add." When the active archive nears its 10M-cell cap (~once a decade), this creates the
next book ("Mastermind Archive N"), shares it with the owner (Editor), and writes its id
to the registry cell `Sheet1!U1` in the MAIN workbook. The worker reads `U1` for the
archive target, so future rollovers land in the new book automatically.

REQUIRES Drive scope + the Drive API enabled for the service account's GCP project (the
worker's normal Sheets-only scope cannot create files). If creation fails with an
auth/permission error, the message says exactly what to enable.

Modes (MODE env): `test` creates a throwaway book, shares it, prints the URL, then
DELETES it (proves the capability without littering). `provision` creates the real next
archive book and updates the registry. Owner email is the share target.
"""
from __future__ import annotations

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

MAIN_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
OWNER_EMAIL = "tucker2331@gmail.com"
REGISTRY_CELL = "U1"  # Sheet1!U1 in MAIN holds the ACTIVE archive workbook id
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",  # needed to CREATE + SHARE a new workbook
]


def main() -> int:
    mode = (os.environ.get("MODE") or "test").strip().lower()
    name = os.environ.get("ARCHIVE_NAME") or ("Provisioning Test (safe to delete)" if mode == "test"
                                              else "Mastermind Archive 2")
    creds = os.environ.get("GCP_CREDENTIALS")
    if not creds:
        print("ERROR: GCP_CREDENTIALS not set.", file=sys.stderr)
        return 1
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds), scopes=SCOPES))

    try:
        sh = gc.create(name)
    except Exception as exc:
        print(f"ERROR: could not CREATE a new workbook: {exc}\n\n"
              f"This almost always means the Drive API is not enabled for the service account's GCP\n"
              f"project (or the service account lacks Drive access). One-time fix: open\n"
              f"https://console.cloud.google.com/apis/library/drive.googleapis.com , select the project\n"
              f"the service account belongs to (the `project_id` in GCP_CREDENTIALS), and click Enable.\n"
              f"Then re-run this. Nothing else changes — the worker keeps its Sheets-only scope.",
              file=sys.stderr)
        return 1

    try:
        sh.share(OWNER_EMAIL, perm_type="user", role="writer", notify=False)
    except Exception as exc:
        print(f"⚠️ Created workbook {sh.id} but could not share it with {OWNER_EMAIL}: {exc}", file=sys.stderr)
        return 1

    url = f"https://docs.google.com/spreadsheets/d/{sh.id}/edit"
    print(f"✅ Created + shared '{name}' (Editor → {OWNER_EMAIL})")
    print(f"   id:  {sh.id}")
    print(f"   url: {url}")

    if mode == "test":
        gc.del_spreadsheet(sh.id)
        print("   (test mode: deleted the throwaway book — capability CONFIRMED.)")
        return 0

    # provision mode: record the new book as the active archive in the registry.
    try:
        main_wb = gc.open_by_key(MAIN_ID)
        main_wb.worksheet("Sheet1").update_acell(REGISTRY_CELL, sh.id)
        print(f"   registry: wrote new archive id to MAIN Sheet1!{REGISTRY_CELL} — the worker now "
              f"archives to this book.")
    except Exception as exc:
        print(f"⚠️ Created+shared the book but could not write the registry cell {REGISTRY_CELL}: {exc}. "
              f"Set Sheet1!{REGISTRY_CELL} = {sh.id} manually so the worker uses it.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
