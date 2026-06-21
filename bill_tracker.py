"""bill_tracker.py — structural bill-record pipeline for the lobbyist product (B0/B1).

The forward-build backend for the new product (NOT the old text-driven `backend_worker`). It
REUSES calendar_worker's hardened machinery — the LIS-authorization gate, the counted/guarded
session (guardrail #4), and the completeness/truncation-guarded blob fetch (guardrail #1) — and
emits one record per bill to a `Bill_Tracker` tab that the React/Vite front end reads via gviz.

PR 1 (this file) = the correct, low-risk SPINE: the bill universe + title + raw LIS status +
the action/date history + a derived outcome (raw status always kept — never hide it) + the FREE
completeness check (records vs the authoritative universe) + the freshness/provenance fields.

DEFERRED to PR 2 (the intricate, structural part — built with care, reusing the STM):
  - current committee / position (chamber lane, crossover side, referral count) via
    build_committee_maps + resolve_committee_from_refid / the STM's per-bill location state,
  - latest vote WITH its location (VOTE.CSV refid join), upcoming meetings (DOCKET),
  - patron + subject ingests.

See docs/ideas/product_vision.md, docs/ideas/product_roadmap.md §B0, docs/ideas/lis_data_inventory.md.
"""
import os
import json
import datetime

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# Reuse the worker's proven, guarded primitives — single source of truth, inherits the
# LIS-safety guardrails (request cap via the counted session, blob cache + truncation guard
# via safe_fetch_csv) rather than re-implementing fetch logic.
from calendar_worker import (
    safe_fetch_csv,
    get_armored_session,
    get_active_session_info,
    HEADERS,
    SPREADSHEET_ID,
)
from lis_authorization import is_authorized_session

BILL_TRACKER_TAB = "Bill_Tracker"
BILL_LIST_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"


def _blob_code(active_session):
    """5-digit blob/session form (the blobs + MVC endpoints want 20261, not 261)."""
    s = str(active_session)
    return f"20{s}" if len(s) == 3 else s


def _clean_bill(bill):
    """Match the worker's CleanBill convention so the universe and HISTORY join 1:1."""
    return str(bill).replace(" ", "").upper().strip()


# Outcome is a CONVENIENCE derivation over LIS's OWN controlled Status vocabulary (consuming the
# source, not parsing free description text). The RAW LIS status is always kept on the record, so
# nothing is hidden; an unrecognized status yields outcome "in_progress" and is FLAGGED (the trust
# layer surfaces it rather than silently bucketing). These sets are LIS Status `Name`s; a drift
# check (a status outside all sets) is reported, mirroring the worker's validate_status_grouping.
_OUTCOME_SIGNED = ("approved", "acts of assembly", "chapter")
_OUTCOME_VETOED = ("veto",)
_OUTCOME_DEAD = ("passed by indefinitely", "stricken", "left in", "failed", "tabled",
                 "incorporated", "continued to", "carried over", "withdrawn", "no action")
_OUTCOME_AWAITING = ("enrolled", "pending governor", "awaiting governor", "communicated to governor",
                     "governor's action")


def _derive_outcome(raw_status):
    """Clearly-derived convenience label; the raw status is the authoritative field on the record."""
    s = str(raw_status).lower()
    if any(k in s for k in _OUTCOME_VETOED):
        return "vetoed", True
    if any(k in s for k in _OUTCOME_SIGNED):
        return "signed", True
    if any(k in s for k in _OUTCOME_DEAD):
        return "dead", True
    if any(k in s for k in _OUTCOME_AWAITING):
        return "awaiting_governor", True
    return "in_progress", False  # second value = "recognized as a terminal outcome?"


def build_bill_records(http_session, session_code):
    """Fetch the bill universe + HISTORY and build one spine record per bill. Returns
    (records, completeness) — completeness is the trust signal (universe vs HISTORY coverage)."""
    blob_code = _blob_code(session_code)

    # 1) The authoritative bill UNIVERSE (also titles + status, and the completeness source).
    resp = http_session.get(BILL_LIST_URL, headers=HEADERS,
                            params={"sessionCode": session_code}, timeout=30)
    resp.raise_for_status()
    universe = resp.json().get("Legislations", []) or []
    if not universe:
        raise RuntimeError("bill universe came back empty — refusing to overwrite with nothing "
                           "(fail-safe: keep last-known-good).")

    # 2) HISTORY (guarded fetch: truncation/completeness checked, blob-cache-aware) → per-bill rows.
    hist_df = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
    hist_by_bill = {}
    if not hist_df.empty:
        cols = {c.lower(): c for c in hist_df.columns}
        bill_col = next((cols[c] for c in ("billnumber", "bill_number", "bill_id") if c in cols), None)
        desc_col = next((cols[c] for c in ("description", "history_description", "action") if c in cols), None)
        date_col = next((cols[c] for c in ("historydate", "history_date", "date") if c in cols), None)
        if bill_col and desc_col:
            for _bill, grp in hist_df.groupby(hist_df[bill_col].astype(str).map(_clean_bill)):
                rows = []
                for _, r in grp.iterrows():
                    action = str(r.get(desc_col, "") or "").strip()
                    when = str(r.get(date_col, "") or "").strip() if date_col else ""
                    if action:
                        rows.append({"action": action, "date": when})
                hist_by_bill[_bill] = rows

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records, universe_bills, unrecognized_status = [], set(), set()
    for item in universe:
        bill = _clean_bill(item.get("LegislationNumber", ""))
        if not bill:
            continue
        universe_bills.add(bill)
        title = str(item.get("Description", "") or "").strip()
        raw_status = str(item.get("LegislationStatus", "") or "").strip()
        outcome, recognized = _derive_outcome(raw_status)
        if not recognized and raw_status:
            unrecognized_status.add(raw_status)
        history = hist_by_bill.get(bill, [])
        last_date = history[-1]["date"] if history else ""
        records.append({
            "bill": bill,
            "title": title,
            "status_lis": raw_status,          # authoritative, always shown
            "outcome": outcome,                # derived convenience label
            "last_action_date": last_date,
            "history": history,                # [{action, date}] — newest handling is the UI's job
            "data_as_of_utc": now_utc,         # trust: freshness
            "source": "LIS",                   # trust: provenance
        })

    # 3) COMPLETENESS (the top trust signal, free): the universe is authoritative. Any bill in
    #    HISTORY but NOT the universe is an anomaly to surface; bills in the universe with no
    #    HISTORY are simply prefiled-not-yet-acted (expected, counted).
    history_bills = set(hist_by_bill)
    missing_from_universe = sorted(history_bills - universe_bills)
    completeness = {
        "universe_count": len(universe_bills),
        "records_written": len(records),
        "history_bills": len(history_bills),
        "prefiled_no_history": len(universe_bills - history_bills),
        "in_history_not_in_universe": missing_from_universe,   # should be empty
        "unrecognized_statuses": sorted(unrecognized_status),  # trust: surface, don't bucket silently
        "checked_at_utc": now_utc,
    }
    return records, completeness


def write_bill_tracker(records, completeness):
    """Write the records + a completeness summary to the Bill_Tracker tab (create if missing)."""
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GCP_CREDENTIALS not set")
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sheet.worksheet(BILL_TRACKER_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=BILL_TRACKER_TAB, rows=max(1000, len(records) + 100), cols=8)

    header = ["Bill", "Title", "Status (LIS)", "Outcome", "Last Action", "History (JSON)",
              "Data As Of (UTC)", "Source"]
    rows = [header] + [[
        r["bill"], r["title"], r["status_lis"], r["outcome"], r["last_action_date"],
        json.dumps(r["history"], ensure_ascii=False), r["data_as_of_utc"], r["source"],
    ] for r in records]
    ws.clear()
    ws.update(values=rows, range_name="A1")

    # completeness summary in a far cell the front end can read for the trust header
    ws.update(values=[[json.dumps(completeness, ensure_ascii=False)]], range_name="J1")


def run_bill_tracker():
    http_session = get_armored_session()   # counted/guarded (guardrail #4)

    # Session derived at runtime from the Session API (Standard #5 — never hardcoded).
    info, ok, _auth_failed = get_active_session_info(http_session)
    if not ok or not info or not info.get("code"):
        print("🛑 could not derive the active session; skipping (fail-safe — keep last-known-good).")
        return
    session_code = str(info["code"])

    # LIS-authorization gate (ban-safe): never pull data for an unauthorized session.
    if not is_authorized_session(session_code):
        print(f"🛑 LIS authorization halt — session {session_code} not authorized; skipping.")
        return

    records, completeness = build_bill_records(http_session, session_code)
    write_bill_tracker(records, completeness)
    print(f"✅ Bill_Tracker written: {len(records)} bills "
          f"({completeness['prefiled_no_history']} prefiled-no-history). "
          f"Completeness: {completeness['records_written']}/{completeness['universe_count']} of the "
          f"universe; {len(completeness['in_history_not_in_universe'])} in-history-not-in-universe; "
          f"{len(completeness['unrecognized_statuses'])} unrecognized statuses.")
    if completeness["in_history_not_in_universe"]:
        print(f"⚠️ COMPLETENESS ANOMALY — bills in HISTORY but absent from the universe: "
              f"{completeness['in_history_not_in_universe'][:10]}")


if __name__ == "__main__":
    run_bill_tracker()
