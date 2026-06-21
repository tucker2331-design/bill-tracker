"""bill_tracker.py — structural bill-record pipeline for the lobbyist product (B0/B1).

The forward-build backend for the new product (NOT the old text-driven `backend_worker`). It
REUSES calendar_worker's hardened machinery — the LIS-authorization gate, the counted/guarded
session (guardrail #4), the completeness/truncation-guarded blob fetch (guardrail #1), and the
Slack alerter — and emits one record per bill to a `Bill_Tracker` tab that the React/Vite front
end reads via gviz.

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
# via safe_fetch_csv) and the Slack alerter rather than re-implementing any of it.
from calendar_worker import (
    safe_fetch_csv,
    get_armored_session,
    get_active_session_info,
    notify_slack,
    HEADERS,
    SPREADSHEET_ID,
)
from lis_authorization import is_authorized_session, normalize_session_code

BILL_TRACKER_TAB = "Bill_Tracker"
BILL_LIST_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"


def _alert(severity, category, message):
    """Categorized, self-describing alert (Standard #4) → Slack if configured; always printed.
    Terminal failures must never be silent prints."""
    line = f"🚨 {severity} [BILL_TRACKER/{category}] {message}"
    print(line)
    try:
        notify_slack(line)
    except Exception as _slack_err:   # never swallow silently — the alert path itself must be visible
        print(f"⚠️ notify_slack failed for the above alert: {_slack_err}")


def _clean_bill(bill):
    """Match the worker's CleanBill convention so the universe and HISTORY join 1:1.
    NA/None-safe so a missing id reads as '' (and is skipped), never the literal 'NONE'/'<NA>'."""
    if bill is None or (not isinstance(bill, str) and pd.isna(bill)):
        return ""
    return str(bill).replace(" ", "").upper().strip()


# Outcome is a CONVENIENCE label over LIS's OWN controlled Status vocabulary (consuming the source,
# not parsing free description text). The RAW LIS status is ALWAYS kept on the record, so nothing is
# hidden and "in_progress" is a legitimate label (not "unrecognized"). NOTE (Codex #159): a true
# status-DRIFT check — flagging a status LIS has never published — is DEFERRED to PR2, where it
# reuses the worker's validate_status_grouping against the live LIS status list; flagging every
# non-terminal status here would flood the trust signal with normal in-session statuses.
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
        return "vetoed"
    if any(k in s for k in _OUTCOME_SIGNED):
        return "signed"
    if any(k in s for k in _OUTCOME_DEAD):
        return "dead"
    if any(k in s for k in _OUTCOME_AWAITING):
        return "awaiting_governor"
    return "in_progress"


def build_bill_records(http_session, session_code):
    """Fetch the bill universe + HISTORY and build one spine record per bill. Returns
    (records, completeness) — completeness is the trust signal (universe vs HISTORY coverage)."""
    blob_code = normalize_session_code(session_code)   # 5-digit (reuse, don't re-implement)

    # 1) The authoritative bill UNIVERSE (also titles + status, and the completeness source).
    #    Pass the 5-digit code — the Legislation MVC endpoints reject the 3-digit form.
    resp = http_session.get(BILL_LIST_URL, headers=HEADERS,
                            params={"sessionCode": blob_code}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    universe = payload.get("Legislations", []) or [] if isinstance(payload, dict) else []
    if not universe:
        raise RuntimeError("bill universe came back empty/non-dict — refusing to overwrite with "
                           "nothing (fail-safe: keep last-known-good).")

    # 2) HISTORY (guarded fetch: truncation/completeness checked, blob-cache-aware) → per-bill rows.
    #    Fail-safe: an empty frame (transient fetch issue) must NOT overwrite the tab with empty
    #    histories — keep last-known-good.
    hist_df = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
    if hist_df.empty:
        raise RuntimeError("HISTORY.CSV came back empty — refusing to overwrite with empty histories "
                           "(fail-safe: keep last-known-good).")
    hist_by_bill = {}
    cols = {c.lower(): c for c in hist_df.columns}
    bill_col = next((cols[c] for c in ("billnumber", "bill_number", "bill_id") if c in cols), None)
    desc_col = next((cols[c] for c in ("description", "history_description", "action") if c in cols), None)
    date_col = next((cols[c] for c in ("historydate", "history_date", "date") if c in cols), None)
    if not (bill_col and desc_col):
        # Schema drift fail-safe: missing the bill/desc columns would give EVERY bill an empty
        # history and overwrite the tab with blanks — refuse (LIS likely renamed a column).
        raise RuntimeError(f"HISTORY.CSV missing the bill/description columns (cols={list(hist_df.columns)}) "
                           "— refusing to overwrite with empty histories (fail-safe).")
    # Column-zip with fillna — fast (no per-row iterrows) and NA-safe (no `… or ''` on pd.NA).
    bills = hist_df[bill_col].map(_clean_bill)
    descs = hist_df[desc_col].fillna("").astype(str)
    dates = hist_df[date_col].fillna("").astype(str) if date_col else [""] * len(hist_df)
    for b, act, dt in zip(bills, descs, dates):
        act = act.strip()
        if b and act:
            hist_by_bill.setdefault(b, []).append({"action": act, "date": str(dt).strip()})

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records, universe_bills, skipped_universe = [], set(), 0
    for item in universe:
        bill = _clean_bill(item.get("LegislationNumber", ""))
        if not bill:
            skipped_universe += 1   # surfaced in completeness (source-miss visibility), never silent
            continue
        universe_bills.add(bill)
        title = str(item.get("Description", "") or "").strip()
        raw_status = str(item.get("LegislationStatus", "") or "").strip()
        outcome = _derive_outcome(raw_status)
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
    completeness = {
        "universe_count": len(universe_bills),
        "records_written": len(records),
        "history_bills": len(history_bills),
        "prefiled_no_history": len(universe_bills - history_bills),
        "in_history_not_in_universe": sorted(history_bills - universe_bills),  # should be empty
        "skipped_malformed_universe": skipped_universe,
        "checked_at_utc": now_utc,
    }
    return records, completeness


def write_bill_tracker(records, completeness):
    """Write the records + a completeness summary to the Bill_Tracker tab (create if missing).
    Resizes the grid first — gspread.update does NOT auto-expand and errors past the grid."""
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GCP_CREDENTIALS not set")
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)

    header = ["Bill", "Title", "Status (LIS)", "Outcome", "Last Action", "History (JSON)",
              "Data As Of (UTC)", "Source"]
    rows = [header] + [[
        r["bill"], r["title"], r["status_lis"], r["outcome"], r["last_action_date"],
        json.dumps(r["history"], ensure_ascii=False), r["data_as_of_utc"], r["source"],
    ] for r in records]
    need_rows, need_cols = len(rows) + 50, 10   # A..H data + the J1 completeness summary

    try:
        ws = sheet.worksheet(BILL_TRACKER_TAB)
        if ws.row_count < need_rows or ws.col_count < need_cols:   # grow to fit (update won't auto-expand)
            ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=BILL_TRACKER_TAB, rows=need_rows, cols=need_cols)

    ws.clear()
    # One batched write (rows + the J1 completeness summary the front end reads for its trust
    # header) — one API round-trip instead of two (Sheets rate limits).
    ws.batch_update([
        {"range": "A1", "values": rows},
        {"range": "J1", "values": [[json.dumps(completeness, ensure_ascii=False)]]},
    ])


def run_bill_tracker():
    try:
        http_session = get_armored_session()   # counted/guarded (guardrail #4)

        # Session derived at runtime from the Session API (Standard #5 — never hardcoded).
        info, ok, _auth_failed = get_active_session_info(http_session)
        if not ok or not info or not info.get("code"):
            _alert("CRITICAL", "API_FAILURE",
                   "could not derive the active session; skipped (kept last-known-good).")
            return
        session_code = str(info["code"])

        # LIS-authorization gate (ban-safe): never pull data for an unauthorized session.
        if not is_authorized_session(session_code):
            print(f"🛑 LIS authorization halt — session {session_code} not authorized; skipping.")
            return

        records, completeness = build_bill_records(http_session, session_code)
        write_bill_tracker(records, completeness)
        print(f"✅ Bill_Tracker written: {len(records)} bills "
              f"({completeness['prefiled_no_history']} prefiled-no-history). Completeness: "
              f"{completeness['records_written']}/{completeness['universe_count']} of the universe; "
              f"{len(completeness['in_history_not_in_universe'])} in-history-not-in-universe; "
              f"{completeness['skipped_malformed_universe']} skipped.")
        if completeness["in_history_not_in_universe"]:
            _alert("WARN", "DATA_ANOMALY",
                   f"{len(completeness['in_history_not_in_universe'])} bills in HISTORY but absent from "
                   f"the universe: {completeness['in_history_not_in_universe'][:10]}")
    except Exception as e:
        _alert("CRITICAL", "API_FAILURE", f"bill_tracker cycle failed: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    run_bill_tracker()
