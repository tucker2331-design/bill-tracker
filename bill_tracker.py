"""bill_tracker.py — structural bill-record pipeline for the lobbyist product (B0/B1).

The forward-build backend for the new product (NOT the old text-driven `backend_worker`). It
REUSES calendar_worker's hardened machinery — the LIS-authorization gate, the counted/guarded
session (guardrail #4), the completeness/truncation-guarded blob fetch (guardrail #1), the
structural committee resolvers, and the Slack alerter — and emits one record per bill to a
`Bill_Tracker` tab that the React/Vite front end reads via gviz.

PR 1 = the SPINE: universe + title + raw LIS status + a derived outcome (raw status always kept) +
the action/date history + the FREE completeness check + the freshness/provenance fields.

PR 2 (this file) = STRUCTURAL POSITION, from refids (no text classification, no probabilistic
guess): chamber + crossed-over + last committee + referral count (via resolve_committee_from_refid,
which reports whether a refid is a direct committee referral vs a committee vote); latest vote WITH
its location (committee from the vote refid; tally is a DISPLAY of LIS's own published tally);
upcoming meetings (DOCKET). LIS's own `status` remains the authoritative "where it is" — these are
*certain* structural facts layered on top, never a re-guessed location state machine.

DEFERRED to PR 3: patron + subject ingests (check for a bulk endpoint first — per-bill calls over
3,645 bills would be a ban risk), and the true status-drift check (reuse validate_status_grouping).

See docs/ideas/product_vision.md, docs/ideas/product_roadmap.md §B0, docs/ideas/lis_data_inventory.md.
"""
import os
import re
import json
import datetime

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# Reuse the worker's proven, guarded primitives + structural resolvers — single source of truth.
from calendar_worker import (
    safe_fetch_csv,
    get_armored_session,
    get_active_session_info,
    build_committee_maps,           # populates the global COMMITTEE_CODE_MAP …
    resolve_committee_from_refid,   # … which this reads (refid -> committee name + direct/vote source)
    notify_slack,
    HEADERS,
    SPREADSHEET_ID,
)
from lis_authorization import is_authorized_session, normalize_session_code

BILL_TRACKER_TAB = "Bill_Tracker"
BILL_LIST_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"
_TALLY_RE = re.compile(r'(\d+-Y\s+\d+-N(?:\s+\d+-A\w*)?)', re.IGNORECASE)


def _alert(severity, category, message):
    """Categorized, self-describing alert (Standard #4) → Slack if configured; always printed."""
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


def _parse_date(s):
    """Best-effort date parse for DOCKET dates; None on anything unparseable (never raises)."""
    s = str(s).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


# Outcome is a CONVENIENCE label over LIS's OWN controlled Status vocabulary (consuming the source,
# not parsing free description text). The RAW LIS status is ALWAYS kept on the record.
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


def _derive_position(rows, bill):
    """STRUCTURAL position from refids only (rows oldest→newest). All CERTAIN facts — never a guess:
      - chamber: the chamber of the most recent committee action (origin until it crosses).
      - crossed_over: it had a committee action in the chamber OPPOSITE its origin (the crossover fact).
      - last_committee: the committee of its most recent committee-bearing refid.
      - referral_count: distinct sequential committees it was REFERRED to (refid_direct), i.e. how many
        committees it has moved through (the 1st/2nd/3rd-referral badge)."""
    origin = "House" if bill.startswith("H") else "Senate"
    last_committee, current_chamber, crossed = "", origin, False
    referred = []
    for r in rows:
        refid = str(r.get("refid", "")).strip()
        name, source = resolve_committee_from_refid(refid)
        if not name:
            continue
        chamber = "House" if refid[:1].upper() == "H" else "Senate"
        current_chamber, last_committee = chamber, name
        if chamber != origin:
            crossed = True
        if source == "refid_direct" and (not referred or referred[-1] != name):
            referred.append(name)   # a new committee it was referred TO
    return {"current_chamber": current_chamber, "crossed_over": crossed,
            "last_committee": last_committee, "referral_count": len(referred)}


def _latest_vote(rows):
    """Most recent recorded vote: the tally is a DISPLAY of LIS's own published tally (allowed — it
    is showing, not classifying); the location is STRUCTURAL (the committee from the refid, else Floor)."""
    for r in reversed(rows):   # newest first
        m = _TALLY_RE.search(str(r.get("action", "")))
        if m:
            name, _src = resolve_committee_from_refid(str(r.get("refid", "")).strip())
            return {"tally": m.group(1).strip(), "location": name or "Floor", "date": r.get("date", "")}
    return {"tally": "", "location": "", "date": ""}


def build_bill_records(http_session, session_code):
    """Build one structural record per bill. Returns (records, completeness)."""
    blob_code = normalize_session_code(session_code)   # 5-digit (reuse, don't re-implement)

    # 1) Authoritative bill UNIVERSE (titles + status + the completeness source).
    resp = http_session.get(BILL_LIST_URL, headers=HEADERS,
                            params={"sessionCode": blob_code}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict):   # explicit, not precedence-dependent (Qodo #159)
        raise RuntimeError("bill universe response was not a JSON object — refusing to overwrite "
                           "(fail-safe: keep last-known-good).")
    universe = payload.get("Legislations") or []
    if not universe:
        raise RuntimeError("bill universe came back empty — refusing to overwrite with nothing "
                           "(fail-safe: keep last-known-good).")

    # 2) HISTORY (guarded) → per-bill rows WITH the refid (needed for the structural position).
    hist_df = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
    if hist_df.empty:
        raise RuntimeError("HISTORY.CSV came back empty — refusing to overwrite with empty histories "
                           "(fail-safe: keep last-known-good).")
    cols = {c.lower(): c for c in hist_df.columns}
    bill_col = next((cols[c] for c in ("billnumber", "bill_number", "bill_id") if c in cols), None)
    desc_col = next((cols[c] for c in ("description", "history_description", "action") if c in cols), None)
    date_col = next((cols[c] for c in ("historydate", "history_date", "date") if c in cols), None)
    refid_col = next((cols[c] for c in ("history_refid", "refid") if c in cols), None)
    if not (bill_col and desc_col):
        raise RuntimeError(f"HISTORY.CSV missing the bill/description columns (cols={list(hist_df.columns)}) "
                           "— refusing to overwrite with empty histories (fail-safe).")
    hist_by_bill = {}
    bills = hist_df[bill_col].map(_clean_bill)
    descs = hist_df[desc_col].fillna("").astype(str)
    dates = hist_df[date_col].fillna("").astype(str) if date_col else [""] * len(hist_df)
    refids = hist_df[refid_col].fillna("").astype(str) if refid_col else [""] * len(hist_df)
    for b, act, dt, rf in zip(bills, descs, dates, refids):
        act = act.strip()
        if b and act:
            hist_by_bill.setdefault(b, []).append({"action": act, "date": str(dt).strip(), "refid": str(rf).strip()})

    # 3) Committee maps (populates the global COMMITTEE_CODE_MAP for resolve_committee_from_refid).
    #    Enrichment only — on failure it falls back to the static map; never hard-fail the spine.
    try:
        build_committee_maps(http_session, blob_code)
    except Exception as _cm_err:
        _alert("WARN", "API_FAILURE", f"committee map build failed ({_cm_err}); using static fallback.")

    # 4) DOCKET (guarded) → upcoming committee meetings per bill. Empty off-season is correct, not an error.
    docket_by_bill = {}
    doc_df = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/DOCKET.CSV")
    if not doc_df.empty:
        dcols = {c.lower(): c for c in doc_df.columns}
        dbill = next((dcols[c] for c in ("billnumber", "bill_number", "bill_id", "bill") if c in dcols), None)
        ddate = next((dcols[c] for c in ("meetingdate", "meeting_date", "docketdate", "date", "doc_date") if c in dcols), None)
        dcomm = next((dcols[c] for c in ("committeename", "committee_name", "committee", "ownername", "description") if c in dcols), None)
        if dbill and ddate:
            dbills = doc_df[dbill].map(_clean_bill)
            ddates = doc_df[ddate].fillna("").astype(str)
            dcomms = doc_df[dcomm].fillna("").astype(str) if dcomm else [""] * len(doc_df)
            for b, dt, cm in zip(dbills, ddates, dcomms):
                if b:
                    docket_by_bill.setdefault(b, []).append({"date": str(dt).strip(), "committee": str(cm).strip()})
    today = datetime.date.today()

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records, universe_bills, skipped_universe, docket_unparseable = [], set(), 0, 0
    for item in universe:
        bill = _clean_bill(item.get("LegislationNumber", ""))
        if not bill:
            skipped_universe += 1   # surfaced in completeness (source-miss visibility), never silent
            continue
        universe_bills.add(bill)
        rows = hist_by_bill.get(bill, [])
        position = _derive_position(rows, bill)
        upcoming = []
        for d in docket_by_bill.get(bill, []):
            meeting_day = _parse_date(d["date"])
            if meeting_day is None:
                docket_unparseable += 1   # counted, not silently dropped (source-miss visibility)
                continue
            if meeting_day >= today:       # future meetings only (empty off-season, correctly)
                upcoming.append(d)
        records.append({
            "bill": bill,
            "title": str(item.get("Description", "") or "").strip(),
            "status_lis": str(item.get("LegislationStatus", "") or "").strip(),  # authoritative, always shown
            "outcome": _derive_outcome(item.get("LegislationStatus", "")),
            "chamber": position["current_chamber"],
            "crossed_over": position["crossed_over"],
            "last_committee": position["last_committee"],
            "referral_count": position["referral_count"],
            "latest_vote": _latest_vote(rows),                       # {tally, location, date}
            "upcoming": upcoming,                                    # [{date, committee}] (empty off-season)
            "last_action_date": rows[-1]["date"] if rows else "",
            "history": [{"action": r["action"], "date": r["date"]} for r in rows],  # UI doesn't need refids
            "data_as_of_utc": now_utc,                               # trust: freshness
            "source": "LIS",                                         # trust: provenance
        })

    # 5) COMPLETENESS (the top trust signal, free).
    history_bills = set(hist_by_bill)
    completeness = {
        "universe_count": len(universe_bills),
        "records_written": len(records),
        "history_bills": len(history_bills),
        "prefiled_no_history": len(universe_bills - history_bills),
        "in_history_not_in_universe": sorted(history_bills - universe_bills),  # should be empty
        "skipped_malformed_universe": skipped_universe,
        "docket_unparseable_dates": docket_unparseable,   # upcoming-meeting dates LIS gave in an unknown format
        "checked_at_utc": now_utc,
    }
    return records, completeness


def write_bill_tracker(records, completeness):
    """Write records + a completeness summary to the Bill_Tracker tab (create if missing).
    Resizes the grid first — gspread.update does NOT auto-expand and errors past the grid."""
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GCP_CREDENTIALS not set")
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)

    header = ["Bill", "Title", "Status (LIS)", "Outcome", "Chamber", "Crossed Over", "Last Committee",
              "Referrals", "Last Action", "Latest Vote (JSON)", "Upcoming (JSON)", "History (JSON)",
              "Data As Of (UTC)", "Source"]
    rows = [header] + [[
        r["bill"], r["title"], r["status_lis"], r["outcome"], r["chamber"],
        "yes" if r["crossed_over"] else "no", r["last_committee"], r["referral_count"], r["last_action_date"],
        json.dumps(r["latest_vote"], ensure_ascii=False), json.dumps(r["upcoming"], ensure_ascii=False),
        json.dumps(r["history"], ensure_ascii=False), r["data_as_of_utc"], r["source"],
    ] for r in records]
    need_rows, need_cols = len(rows) + 50, 16   # A..N data + the P1 completeness summary

    try:
        ws = sheet.worksheet(BILL_TRACKER_TAB)
        if ws.row_count < need_rows or ws.col_count < need_cols:   # grow to fit (update won't auto-expand)
            ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=BILL_TRACKER_TAB, rows=need_rows, cols=need_cols)

    ws.clear()
    # One batched write (rows + the P1 completeness summary the front end reads for its trust header).
    ws.batch_update([
        {"range": "A1", "values": rows},
        {"range": "P1", "values": [[json.dumps(completeness, ensure_ascii=False)]]},
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
        crossed = sum(1 for r in records if r["crossed_over"])
        print(f"✅ Bill_Tracker written: {len(records)} bills "
              f"({completeness['prefiled_no_history']} prefiled-no-history, {crossed} crossed over). "
              f"Completeness: {completeness['records_written']}/{completeness['universe_count']} of the "
              f"universe; {len(completeness['in_history_not_in_universe'])} in-history-not-in-universe; "
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
