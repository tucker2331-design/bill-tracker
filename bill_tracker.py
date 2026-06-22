"""bill_tracker.py — structural bill-record pipeline for the lobbyist product (B0/B1).

The forward-build backend for the new product (NOT the old text-driven `backend_worker`). It
REUSES calendar_worker's hardened machinery — the LIS-authorization gate, the counted/guarded
session (guardrail #4), the completeness/truncation-guarded blob fetch (guardrail #1), the
structural committee resolvers, and the Slack alerter — and emits one record per bill to a
`Bill_Tracker` tab that the React/Vite front end reads via gviz.

PR 1 = the SPINE: universe + title + raw LIS status + a derived outcome (raw status always kept) +
the action/date history + the FREE completeness check + the freshness/provenance fields.

PR 2 = STRUCTURAL POSITION, from refids (no text classification, no probabilistic guess): chamber +
crossed-over + last committee + referral count; latest vote WITH its location; upcoming meetings
(DOCKET). LIS's own `status` remains the authoritative "where it is".

PR 3 (this file) = BILLS.CSV ingest (ONE bulk blob — never per-bill, which over 3,645 bills would be
a ban risk): chief PATRON (name + id); a STRUCTURAL-first `outcome` from LIS's OWN boolean flags
(Vetoed/Approved/Carried_over/Failed/Passed — more reliable than the status keyword, and it fixes
"Continued"→carried_over which the keyword missed); and the true STATUS-DRIFT check (every live bill
status validated against the known vocabulary → categorized alert on drift, zero extra LIS calls).
SUBJECT is DEFERRED: LIS publishes NO bulk subject blob (BILLS/HISTORY/DOCKET/VOTE are the only ones)
and the LegislationSubject endpoint is per-bill (a 3,645-call ban risk) — needs a confirmed bulk-safe
source before ingest (see docs/ideas/lis_data_inventory.md §6).

See docs/ideas/product_vision.md, docs/ideas/product_roadmap.md §B0, docs/ideas/lis_data_inventory.md.
"""
import os
import re
import json
import datetime

import gspread
import pytz
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
    """Parse a DOCKET meeting date. Returns a `date`, or None on anything unparseable (never raises).

    Heuristic (Standard #1):
      - ASSUMES LIS publishes DOCKET dates in one of `%m/%d/%Y`, `%Y-%m-%d`, `%m/%d/%y`.
      - BREAKS if LIS introduces a new date format → that row returns None.
      - RUNTIME CHECK: every None is counted into `completeness.docket_unparseable_dates`
        (with its `docket_rows_total` denominator) so a format change surfaces as a rising
        rate instead of silently dropping upcoming meetings.
    """
    s = str(s).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue   # try the next format; exhausting all of them → None, counted by the caller
    return None


# Outcome is a CONVENIENCE label; the RAW LIS status is ALWAYS kept on the record. PR3 makes it
# STRUCTURAL-first: `_outcome_from_flags` reads LIS's OWN boolean flags from BILLS.CSV; the keyword
# path below is the FALLBACK for a bill absent from BILLS.CSV (consuming the controlled Status string,
# never free description text). "carried_over" is distinct from "dead": a continued bill returns next
# session — the PR1 keyword set wrongly folded "Continued" into in_progress/dead.
_OUTCOME_SIGNED = ("approved", "acts of assembly", "chapter")
_OUTCOME_VETOED = ("veto",)
_OUTCOME_CARRIED = ("carried over", "continued")   # carried over to the next session — NOT dead/failed
_OUTCOME_DEAD = ("passed by indefinitely", "stricken", "left in", "failed", "tabled",
                 "incorporated", "withdrawn", "no action")
_OUTCOME_AWAITING = ("enrolled", "pending governor", "awaiting governor", "communicated to governor",
                     "governor's action", "passed")   # passed the legislature, awaiting the Governor


def _outcome_from_flags(meta):
    """STRUCTURAL outcome (Standard #3) from BILLS.CSV's OWN Y/N flags; None if no terminal flag is set
    (→ caller falls back to the keyword path). Precedence is most-terminal-first, validated against
    every status×flag combo in the live 2026 data: a vetoed bill also flags Passed (Vetoed wins), an
    Incorporated bill flags Failed, a Continued bill flags Carried_over (returns next session)."""
    if not meta:
        return None
    if meta.get("vetoed"):       return "vetoed"
    if meta.get("approved"):     return "signed"
    if meta.get("carried_over"): return "carried_over"
    if meta.get("failed"):       return "dead"            # covers Failed + Incorporated
    if meta.get("passed"):       return "awaiting_governor"
    return None


def _derive_outcome(raw_status):
    """KEYWORD-fallback outcome over the controlled Status string (used only when BILLS.CSV lacks the
    bill). The raw status is the authoritative field on the record; this is a convenience label."""
    s = str(raw_status).lower()
    if any(k in s for k in _OUTCOME_VETOED):
        return "vetoed"
    if any(k in s for k in _OUTCOME_SIGNED):
        return "signed"
    if any(k in s for k in _OUTCOME_CARRIED):   # before DEAD: "continued to" must not read as dead
        return "carried_over"
    if any(k in s for k in _OUTCOME_DEAD):      # before AWAITING: "passed by indefinitely" is dead, not awaiting
        return "dead"
    if any(k in s for k in _OUTCOME_AWAITING):
        return "awaiting_governor"
    return "in_progress"


# Bill-level LIS status vocabulary this product understands. DISTINCT from the calendar's action-status
# vocabulary (structural_router.CLASSIFIED_STATUSES): the bill feed uses bare "Continued" where the
# calendar classifies the ACTION "Continued to …", so they are different axes — hence a local set.
# Heuristic (Standard #1): ASSUMES LIS's bill-status vocabulary is this set; BREAKS if LIS adds one;
# RUNTIME CHECK = the `unknown_bill_statuses` drift list in completeness + a WARN/DATA_ANOMALY alert,
# so a never-seen status surfaces instead of silently riding the "in_progress" default.
_KNOWN_BILL_STATUSES = frozenset({
    "", "Introduced", "In Committee", "In Subcommittee", "In House", "In Senate", "In Conference",
    "Reported", "Passed House", "Passed Senate", "Passed Both", "Passed",
    "Engrossed", "Enrolled", "Continued", "Failed", "Incorporated", "Stricken", "Tabled",
    "Left in Committee", "Acts of Assembly Chapter", "Approved", "Governor's Veto", "Vetoed",
    "Awaiting Signature", "With Governor", "Withdrawn",
})


def _build_bills_meta(blob_code):
    """BULK ingest of BILLS.CSV (one guarded blob — NEVER per-bill) → {clean_bill: {patron_name,
    patron_id, vetoed, approved, carried_over, failed, passed}} + the row count. Enrichment only: on an
    empty/failed fetch or a missing bill column, returns ({}, 0) and the caller fails soft (keyword-only
    outcome, empty patron) — never sinks the spine."""
    df = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/BILLS.CSV")
    if df.empty:
        return {}, 0
    cols = {c.lower(): c for c in df.columns}
    bill_col = next((cols[c] for c in ("bill_id", "billnumber", "bill_number") if c in cols), None)
    if not bill_col:
        return {}, 0

    def series(name):   # NA-safe column or all-empty placeholder (no iterrows, no `… or ''` on pd.NA)
        c = cols.get(name)
        return df[c].fillna("").astype(str) if c else [""] * len(df)

    def is_y(v):
        return str(v).strip().upper() == "Y"

    meta = {}
    for b, pnm, pid, vet, app, car, fail, pas in zip(
            df[bill_col].map(_clean_bill), series("patron_name"), series("patron_id"),
            series("vetoed"), series("approved"), series("carried_over"), series("failed"), series("passed")):
        if not b:
            continue   # malformed BILLS.CSV row with no bill id — nothing to key on (enrichment, skip)
        meta[b] = {
            "patron_name": pnm.strip(), "patron_id": pid.strip(),
            "vetoed": is_y(vet), "approved": is_y(app), "carried_over": is_y(car),
            "failed": is_y(fail), "passed": is_y(pas),
        }
    return meta, len(df)


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
            continue   # non-committee action (floor/admin) — no position info; the row is still kept in `history`
        chamber = "House" if refid[:1].upper() == "H" else "Senate"
        current_chamber, last_committee = chamber, name
        if chamber != origin:
            crossed = True
        if source == "refid_direct" and (not referred or referred[-1] != name):
            referred.append(name)   # a new committee it was referred TO
    return {"current_chamber": current_chamber, "crossed_over": crossed,
            "last_committee": last_committee, "referral_count": len(referred)}


def _latest_vote(rows):
    """Most recent recorded vote → {tally, location, date}. The location is STRUCTURAL (the committee
    from the vote refid, else Floor). The tally is a DISPLAY of LIS's OWN published tally string —
    showing it, never classifying on it.

    Granularity note (re: the calendar's meeting-time rule): this carries the vote's DATE, not a
    meeting TIME, on purpose. The card's "latest vote" summarises a PAST vote, for which date +
    location + tally is the complete, decision-relevant record. Meeting-TIME accuracy is the calendar
    subsystem's domain (X-Ray Section 9) — that separate, 100%-accurate engine owns the time lens; we
    do not duplicate its convene-time resolution here.

    Heuristic (Standard #1):
      - ASSUMES LIS writes tallies in its published `N-Y N-N [N-A...]` form (the `_TALLY_RE` shape).
      - BREAKS if LIS changes that surface form → a real vote could read as no-vote (empty tally).
      - RUNTIME CHECK: a structural cross-check (votes present in VOTE.CSV vs. tallies surfaced) is a
        future follow-up; until then the LIS bill-page link on the card is the authoritative backstop.
    """
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
            # Normalize the refid at this ingestion boundary — resolve_committee_from_refid matches
            # case-sensitive `^[HS]…` regexes, so a lowercase/mixed-case refid from LIS would silently
            # fail to resolve (Gemini #161). Upper-case once here so every downstream read is clean.
            hist_by_bill.setdefault(b, []).append(
                {"action": act, "date": dt.strip(), "refid": rf.strip().upper()})

    # 3) Committee maps (populates the global COMMITTEE_CODE_MAP for resolve_committee_from_refid).
    #    Enrichment only: build_committee_maps already has its OWN static fallback, so this broad
    #    catch is a deliberate belt-and-suspenders guard for a truly unexpected failure — it must
    #    never sink the spine. Kept broad ON PURPOSE (any failure here is acceptable to absorb), but
    #    the alert carries the exception TYPE so an unexpected mode is still diagnosable, not hidden.
    try:
        build_committee_maps(http_session, blob_code)
    except Exception as _cm_err:
        _alert("WARN", "API_FAILURE",
               f"committee map build failed ({type(_cm_err).__name__}: {_cm_err}); using static fallback.")

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
    # 5) BILLS.CSV (one guarded BULK blob) → chief patron + structural outcome flags for every bill.
    bills_meta, bills_meta_rows = _build_bills_meta(blob_code)

    # Virginia-local (ET) date — NOT the runner's UTC date. An evening run on a UTC CI box would
    # otherwise treat tomorrow as "today" and drop a meeting still scheduled for today in ET
    # (Gemini/Qodo #161). Matches the repo's America/New_York convention (calendar_worker).
    today = datetime.datetime.now(pytz.timezone("America/New_York")).date()

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records, universe_bills, skipped_universe = [], set(), 0
    docket_unparseable, docket_rows_total = 0, 0   # the metric + its denominator (Standard #7)
    outcome_structural, outcome_keyword, patron_present = 0, 0, 0   # trust counters (coverage of the bulk join)
    unknown_statuses = set()                                        # status-drift: bill statuses outside the vocabulary
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
            docket_rows_total += 1         # the denominator for the unparseable-rate metric
            meeting_day = _parse_date(d["date"])
            if meeting_day is None:
                docket_unparseable += 1    # counted (over docket_rows_total), not silently dropped
                continue                   # malformed date → skip this meeting; surfaced as a rate
            if meeting_day >= today:       # future meetings only (empty off-season, correctly)
                upcoming.append(d)

        raw_status = str(item.get("LegislationStatus", "") or "").strip()
        if raw_status not in _KNOWN_BILL_STATUSES:
            unknown_statuses.add(raw_status)   # drift — surfaced + alerted, never silently defaulted
        meta = bills_meta.get(bill)
        structural_outcome = _outcome_from_flags(meta)   # STRUCTURAL-first (Standard #3)
        if structural_outcome:
            outcome, outcome_structural = structural_outcome, outcome_structural + 1
        else:
            outcome, outcome_keyword = _derive_outcome(raw_status), outcome_keyword + 1
        patron = meta["patron_name"] if meta else ""
        if patron:
            patron_present += 1
        records.append({
            "bill": bill,
            "title": str(item.get("Description", "") or "").strip(),
            "status_lis": raw_status,                                # authoritative, always shown
            "outcome": outcome,                                      # structural-first, keyword fallback
            "patron": patron,                                        # chief patron (BILLS.CSV) — "by patron"
            "patron_id": meta["patron_id"] if meta else "",
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
        # Unparseable DOCKET dates as a RATE with its explicit denominator (Standard #7), not a bare
        # count — so a format change reads as a rising fraction regardless of docket size.
        "docket_unparseable_dates": docket_unparseable,
        "docket_rows_total": docket_rows_total,
        "docket_unparseable_rate": round(docket_unparseable / docket_rows_total, 4) if docket_rows_total else 0.0,
        # BILLS.CSV bulk-join coverage (trust: did the patron/outcome enrichment actually reach the bills?)
        "bills_meta_rows": bills_meta_rows,
        "outcome_structural": outcome_structural,
        "outcome_keyword_fallback": outcome_keyword,
        "patron_present": patron_present,
        "patron_missing": len(records) - patron_present,
        # Status-drift canary: bill statuses LIS published that are outside our known vocabulary.
        "unknown_bill_statuses": sorted(s for s in unknown_statuses if s),
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

    header = ["Bill", "Title", "Status (LIS)", "Outcome", "Patron", "Patron ID", "Chamber",
              "Crossed Over", "Last Committee", "Referrals", "Last Action", "Latest Vote (JSON)",
              "Upcoming (JSON)", "History (JSON)", "Data As Of (UTC)", "Source"]
    rows = [header] + [[
        r["bill"], r["title"], r["status_lis"], r["outcome"], r["patron"], r["patron_id"], r["chamber"],
        "yes" if r["crossed_over"] else "no", r["last_committee"], r["referral_count"], r["last_action_date"],
        json.dumps(r["latest_vote"], ensure_ascii=False), json.dumps(r["upcoming"], ensure_ascii=False),
        json.dumps(r["history"], ensure_ascii=False), r["data_as_of_utc"], r["source"],
    ] for r in records]
    # 16 data cols (A..P); the completeness summary lives at R1 (col 18), clear of the data.
    completeness_cell, need_rows, need_cols = "R1", len(rows) + 50, 18

    try:
        ws = sheet.worksheet(BILL_TRACKER_TAB)
        if ws.row_count < need_rows or ws.col_count < need_cols:   # grow to fit (update won't auto-expand)
            ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=BILL_TRACKER_TAB, rows=need_rows, cols=need_cols)

    ws.clear()
    # One batched write (rows + the completeness summary the front end reads for its trust header).
    ws.batch_update([
        {"range": "A1", "values": rows},
        {"range": completeness_cell, "values": [[json.dumps(completeness, ensure_ascii=False)]]},
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
              f"({completeness['prefiled_no_history']} prefiled-no-history, {crossed} crossed over, "
              f"{completeness['patron_present']} with patron). "
              f"Completeness: {completeness['records_written']}/{completeness['universe_count']} of the "
              f"universe; {len(completeness['in_history_not_in_universe'])} in-history-not-in-universe; "
              f"{completeness['skipped_malformed_universe']} skipped. "
              f"Outcome: {completeness['outcome_structural']} structural / "
              f"{completeness['outcome_keyword_fallback']} keyword-fallback.")
        if completeness["in_history_not_in_universe"]:
            _alert("WARN", "DATA_ANOMALY",
                   f"{len(completeness['in_history_not_in_universe'])} bills in HISTORY but absent from "
                   f"the universe: {completeness['in_history_not_in_universe'][:10]}")
        # Status-drift canary (Standard #1 runtime check): a never-seen bill status must surface, not
        # silently default to "in_progress". Extend _KNOWN_BILL_STATUSES when this fires legitimately.
        if completeness["unknown_bill_statuses"]:
            _alert("WARN", "DATA_ANOMALY",
                   f"{len(completeness['unknown_bill_statuses'])} unknown bill status(es) outside the known "
                   f"vocabulary: {completeness['unknown_bill_statuses'][:10]} — extend _KNOWN_BILL_STATUSES.")
        # Bulk-join coverage: a large keyword-fallback share means BILLS.CSV under-covered the universe.
        if completeness["patron_missing"] > 0.05 * max(1, completeness["records_written"]):
            _alert("WARN", "DATA_ANOMALY",
                   f"patron missing for {completeness['patron_missing']}/{completeness['records_written']} "
                   f"bills — BILLS.CSV may have under-covered the universe (fetch/schema issue).")
    except Exception as e:
        _alert("CRITICAL", "API_FAILURE", f"bill_tracker cycle failed: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    run_bill_tracker()
