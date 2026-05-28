"""
PR-C7.1d — Structural Audit of X-Ray Section 9 flagged rows (read-only).

Owner directive (2026-05-12):
  "Fetch the LegEvent data for the flagged rows and categorize them
   into Class A, B, C, and D. Stop guessing and show me the actual
   measured breakdown."
  "Government data is fragile. LIS frequently drops columns, changes
   headers, leaves fields null. Your structural logic must be highly
   defensive."

What this does
--------------
1. Read Sheet1. Find the EXACT rows the X-Ray flags as Section 9 bugs
   (in-window + Committee=="📋 Ledger Updates" + placeholder time +
   classify_action()=="meeting"). This replicates the X-Ray's logic
   verbatim — same patterns as tools/meeting_bug_triage.
2. Collect distinct bills among the flagged rows.
3. Fetch LIS LegislationEvent data per distinct bill (two-step lookup,
   exponential backoff, checkpointed every 25 bills so a mid-process
   interruption loses at most one batch).
4. Categorize each flagged row against its bill's events (see
   categorize.py for the precise rules):
     D — no LegEvent event for (bill, date)
     E — matched but EventCode null/empty (FRAGILE DATA signal)
     C — matched meeting event, no real wall-clock time (genuine gap)
     B — matched meeting event WITH a real time (worker should've recovered)
   Class A (false positive) is read off the EventCode histogram, not
   hardcoded — see categorize.py docstring.
5. Write three result tabs + print the measured breakdown:
     C7_1d_RowVerdicts  — one row per flagged Sheet1 row + its class
     C7_1d_DataQuality  — LIS structural-completeness stats (fragility)
     C7_1d_Summary      — class breakdown + EventCode histogram

Read-only w.r.t. Sheet1 / LegEvent cache. Writes ONLY to its own
C7_1d_* result tabs. Makes no LIS writes.

Defensive posture
-----------------
Every LIS field access tolerates missing keys / null / wrong type /
malformed dates (see categorize.safe_* + the data-quality counters
below). Every Sheet1 column lookup is header-index based (PR-C6.3.1
lesson). Nothing silently skips: failed bill fetches, null EventCodes,
malformed dates are all counted and surfaced.

Pre-push 15-point audit walk
----------------------------
1 verb-forms: copies the X-Ray patterns verbatim from the triage tool;
  drift risk acknowledged inline (same as that tool).
2 fn-scope: all defs module-level.  3 doc-sync: brain writeback in PR.
4 dup-file: untouched.  5 arch-conformance: read-only diagnostic,
  precedes architecture.  6 zero-trust: every failure path counted +
  surfaced.  7 cross-list: no new classification lists.  8 subpage
  import: not touching pages/.  9 source-miss: every skip is counted.
10 fn-scope-shadow: no local re-imports.  11 side-effect-gating:
  checkpoint writes incremental, ungated.  12 fallback-liveness: no
  try/fallback chains.  13 dead-path: nothing removed.  14 threshold-
  calibration: no production thresholds.  15 sentinel-collision: class
  labels are explicit string constants (categorize.py), FetchResult is
  an enum.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from enum import Enum

import gspread
import requests
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from categorize import (  # noqa: E402
    categorize_row,
    eventdate_has_real_time,
    event_date_only,
    safe_str,
    CLASS_B_HAS_TIME,
    CLASS_C_NO_TIME,
    CLASS_D_NO_EVENT,
    CLASS_E_EVENTCODE_MISSING,
    CLASS_X_ROW_MALFORMED,
    CLASS_F_FETCH_FAILED,
)

# Investigation window — single source of truth at the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from investigation_config import INVESTIGATION_START, INVESTIGATION_END  # noqa: E402

INVESTIGATION_START_DATE = datetime.strptime(INVESTIGATION_START, "%Y-%m-%d").date()
INVESTIGATION_END_DATE = datetime.strptime(INVESTIGATION_END, "%Y-%m-%d").date()

# === Constants (copied verbatim from sibling tools — do NOT re-derive;
# see assumptions_audit #48-equivalent "Sibling-Tool Constant Match") ===
SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"  # Mastermind DB (calendar_worker.py:25)
TARGET_SHEET = "Sheet1"
TARGET_COMMITTEE = "📋 Ledger Updates"  # worker writes this exact emoji-prefixed label (calendar_worker.py)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

LIS_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"
LIS_HEADERS = {"WebAPIKey": LIS_API_KEY}
SESSION_CODE_5D = "20261"
LEGISLATION_VERSION_URL = (
    "https://lis.virginia.gov/LegislationVersion/"
    "api/GetLegislationVersionbyBillNumberAsync"
)
LEGISLATION_EVENT_URL = (
    "https://lis.virginia.gov/LegislationEvent/"
    "api/GetPublicLegislationEventHistoryListAsync"
)
LIS_TIMEOUT_S = 15
LIS_RETRY_MAX = 3
LIS_RETRY_BACKOFF_S = 2.0

# === X-Ray classifier patterns — duplicated from pages/ray2.py via
# tools/meeting_bug_triage as of 2026-04-28. DRIFT RISK acknowledged;
# the lexicons/va.py extraction (deferred) consolidates these. We copy
# rather than import because pages/ray2.py has a Streamlit dependency. ===
PLACEHOLDER_TIMES = {
    "", "nan", "none", "time tba", "journal entry", "ledger",
    "⏱️ [no_schedule_match]", "⏱️ [no_convene_anchor]",
}
MEETING_ACTION_PATTERNS = [
    "reported", "recommends", "recommend", "committee substitute",
    "incorporate", "incorporated", "incorporates", "discharged", "stricken",
    "tabled", "continued",
    "passed", "failed", "defeated", "amended",
    "floor substitute", "rules suspended", "offered",
    "block vote", "voice vote", "roll call",
    "reading dispensed", "read first", "read second", "read third",
    "agreed to", "rejected", "reconsidered",
    "conference report agreed",
    "insisted", "taken up", "reconsideration of", "receded",
    "reading waived", "reading of substitute waived", "reading of amendment waived",
    "reading of amendments waived", "reading of amendment not waived",
    "elected by", "election by", "elected to by",
    "emergency clause", "requested second conference committee",
    "motion for", "vote:",
    "withdrawn", "concurred",
    "removed from the table",
]
ADMINISTRATIVE_PATTERNS = [
    "referred to", "assigned", "rereferred",
    "placed on",
    "impact statement", "fiscal impact", "substitute printed",
    "reprinted", "printed as engrossed",
    "enrolled", "signed by", "presented", "communicated",
    "received", "engrossed",
    "conferee", "conference report", "requested conference committee", "acceded to request",
    "approved by governor", "vetoed", "governor's recommendation",
    "governor's substitute", "governor:",
    "laid on speaker's table", "laid on clerk's desk",
    "effective -", "acts of assembly chapter",
    "governor's action deadline", "action deadline",
    "scheduled",
    "left in",
    "blank action",
    "moved from uncontested calendar",
    "no further action taken",
    "unanimous consent to introduce", "introduced at the request of",
    "budget amendments available",
    "recommitted",
    "fiscal impact review",
    "prefiled and ordered printed",
    "(view meeting)",
    "no agenda listed",
    "subcommittee info",
    "speaker's conference room",
    "[memory anchor: admin]",
]
ADMIN_OVERRIDE_PATTERNS = [
    "substitute printed",
    "committee substitute printed",
    "prefiled and ordered printed",
]

# Checkpoint + output tabs
BILLEVENTS_TAB = "C7_1d_BillEvents"          # per-bill event cache (checkpoint)
BILLEVENTS_HEADER = ["Bill", "LegislationEventID", "EventDate", "EventCode", "ChamberCode", "Description"]
CONFIRMED_EMPTY_SENTINEL = "_CONFIRMED_EMPTY_"
CHECKPOINT_BATCH = 25
ROWVERDICTS_TAB = "C7_1d_RowVerdicts"
ROWVERDICTS_HEADER = ["Bill", "Date", "Outcome", "LinkageClass", "MatchedEvents", "EventCodes", "HasRealTime", "Detail"]
DATAQUALITY_TAB = "C7_1d_DataQuality"
DATAQUALITY_HEADER = ["Metric", "Value"]
SUMMARY_TAB = "C7_1d_Summary"
SUMMARY_HEADER = ["Key", "Value"]


# ---------------------------------------------------------------------------
# Auth + tab helpers
# ---------------------------------------------------------------------------

def authenticate_sheets() -> gspread.Spreadsheet:
    raw = os.environ.get("GCP_CREDENTIALS")
    if not raw:
        raise RuntimeError("GCP_CREDENTIALS env var is empty.")
    creds = Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)


def get_or_create_tab(sheet, name, header, rows=2000):
    try:
        return sheet.worksheet(name)
    except WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows=rows, cols=len(header))
        ws.update(values=[header], range_name="A1")
        print(f"📝 Created {name} ({rows} rows x {len(header)} cols).")
        return ws


def write_tab(sheet, name, header, rows, last_col):
    ws = get_or_create_tab(sheet, name, header, rows=max(2000, len(rows) + 100))
    payload = [header] + rows
    ws.update(values=payload, range_name="A1")
    allocated = ws.row_count
    if allocated > len(payload):
        ws.batch_clear([f"A{len(payload) + 1}:{last_col}{allocated}"])
    print(f"📝 Wrote {len(rows)} rows to {name}.")


# ---------------------------------------------------------------------------
# X-Ray flagging logic (verbatim from triage tool)
# ---------------------------------------------------------------------------

def classify_action(outcome_text: str) -> str:
    lower = str(outcome_text).lower().strip()
    if not lower or lower in ("none", "nan"):
        return "administrative"
    if any(p in lower for p in ADMIN_OVERRIDE_PATTERNS):
        return "administrative"
    if any(p in lower for p in MEETING_ACTION_PATTERNS):
        return "meeting"
    if any(p in lower for p in ADMINISTRATIVE_PATTERNS):
        return "administrative"
    return "unclassified"


def in_window(date_str: str) -> bool:
    s = safe_str(date_str)
    if not s:
        return False
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return False
    return INVESTIGATION_START_DATE <= d <= INVESTIGATION_END_DATE


def find_flagged_rows(sheet) -> list[dict]:
    """Return the flagged Section 9 bug rows using the X-Ray's exact logic."""
    ws = sheet.worksheet(TARGET_SHEET)
    all_values = ws.get_all_values()
    if not all_values:
        raise RuntimeError("Sheet1 is empty.")
    header = all_values[0]
    required = ["Date", "Committee", "Time", "Outcome", "Bill"]
    col_idx = {}
    for col in required:
        if col not in header:
            raise RuntimeError(
                f"Sheet1 header missing {col!r}. Available: {[h for h in header if h]}"
            )
        col_idx[col] = header.index(col)
    idx_date, idx_comm = col_idx["Date"], col_idx["Committee"]
    idx_time, idx_outcome, idx_bill = col_idx["Time"], col_idx["Outcome"], col_idx["Bill"]

    flagged = []
    scanned = 0
    for r in all_values[1:]:
        n = len(r)
        d = r[idx_date] if idx_date < n else ""
        if not in_window(d):
            continue
        if safe_str(r[idx_comm] if idx_comm < n else "") != TARGET_COMMITTEE:
            continue
        t = safe_str(r[idx_time] if idx_time < n else "").lower()
        if t not in PLACEHOLDER_TIMES:
            continue
        outcome = r[idx_outcome] if idx_outcome < n else ""
        if classify_action(outcome) != "meeting":
            continue
        scanned += 1
        flagged.append({
            "bill": safe_str(r[idx_bill] if idx_bill < n else ""),
            "date": safe_str(d),
            "outcome": safe_str(outcome),
        })
    print(f"🔎 Flagged Section 9 bug rows (in-window, Ledger, placeholder, meeting): {len(flagged)}")
    return flagged


# ---------------------------------------------------------------------------
# LIS fetch (mirrors tools/c7_1a_audit; LIS contract is stable)
# ---------------------------------------------------------------------------

class FetchResult(Enum):
    OK = "OK"
    EMPTY = "EMPTY"
    FAILED = "FAILED"


def lis_fetch_with_retry(url, params, kind):
    last = None
    for attempt in range(LIS_RETRY_MAX):
        try:
            r = requests.get(url, headers=LIS_HEADERS, params=params, timeout=LIS_TIMEOUT_S)
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(LIS_RETRY_BACKOFF_S * (2 ** attempt))
            continue
        if r.status_code != 200:
            last = f"HTTP {r.status_code}"
            if r.status_code != 429 and 400 <= r.status_code < 500:
                break
            time.sleep(LIS_RETRY_BACKOFF_S * (2 ** attempt))
            continue
        try:
            return FetchResult.OK, r.json()
        except Exception as e:
            last = f"JSON parse: {type(e).__name__}: {e}"
            break
    print(f"⚠️ {kind} FAILED after {LIS_RETRY_MAX} attempts: {last}")
    return FetchResult.FAILED, None


def fetch_events_for_bill(bill_num):
    v_status, vj = lis_fetch_with_retry(
        LEGISLATION_VERSION_URL,
        {"billNumber": bill_num, "sessionCode": SESSION_CODE_5D},
        kind=f"LegislationVersion[{bill_num}]",
    )
    if v_status == FetchResult.FAILED or not isinstance(vj, dict):
        return FetchResult.FAILED, []
    versions = vj.get("LegislationsVersion") or []
    if not versions:
        return FetchResult.EMPTY, []
    first = versions[0]
    if not isinstance(first, dict):
        return FetchResult.FAILED, []
    lid = first.get("LegislationID")
    if not lid:
        return FetchResult.EMPTY, []
    e_status, ej = lis_fetch_with_retry(
        LEGISLATION_EVENT_URL,
        {"legislationID": lid, "sessionCode": SESSION_CODE_5D},
        kind=f"LegislationEvent[{bill_num}/{lid}]",
    )
    if e_status == FetchResult.FAILED or not isinstance(ej, dict):
        return FetchResult.FAILED, []
    events = ej.get("LegislationEvents") or []
    if not isinstance(events, list):
        return FetchResult.FAILED, []
    if not events:
        return FetchResult.EMPTY, []
    return FetchResult.OK, events


def read_billevents_checkpoint(ws) -> dict[str, list]:
    """Return {bill: [event_dict, ...]} from the checkpoint tab.

    Sentinel rows (EventCode == CONFIRMED_EMPTY_SENTINEL) mark
    confirmed-empty bills so resume doesn't refetch; they map to [].
    """
    values = ws.get_all_values()
    if not values or len(values) <= 1:
        return {}
    header = values[0]
    try:
        ci = {c: header.index(c) for c in BILLEVENTS_HEADER}
    except ValueError:
        print(f"⚠️ {BILLEVENTS_TAB} header mismatch; discarding checkpoint.")
        return {}
    out: dict[str, list] = {}
    for r in values[1:]:
        n = len(r)
        bill = safe_str(r[ci["Bill"]] if ci["Bill"] < n else "")
        if not bill:
            continue
        code = safe_str(r[ci["EventCode"]] if ci["EventCode"] < n else "")
        out.setdefault(bill, [])
        if code == CONFIRMED_EMPTY_SENTINEL:
            continue  # confirmed-empty: bill present in dict with [] events
        out[bill].append({
            "LegislationEventID": r[ci["LegislationEventID"]] if ci["LegislationEventID"] < n else "",
            "EventDate": r[ci["EventDate"]] if ci["EventDate"] < n else "",
            "EventCode": r[ci["EventCode"]] if ci["EventCode"] < n else "",
            "ChamberCode": r[ci["ChamberCode"]] if ci["ChamberCode"] < n else "",
            "Description": r[ci["Description"]] if ci["Description"] < n else "",
        })
    return out


def fetch_all_bills(sheet, bills: list[str]) -> tuple[dict[str, list], dict, set]:
    """Fetch events for each distinct flagged bill, checkpointing.

    Returns (events_by_bill, dq, failed_bills) where dq is a data-quality
    dict counting LIS fragility and failed_bills is the set of bills whose
    LIS fetch FAILED this run. Failed bills are NOT checkpointed (retry
    next run) and their flagged rows are categorized Class F, never Class
    D — conflating "fetch failed" with "no event exists" would corrupt the
    measurement (PR-C7.1a Codex P1 lesson: FAILED != EMPTY).
    """
    ws = get_or_create_tab(sheet, BILLEVENTS_TAB, BILLEVENTS_HEADER, rows=20000)
    cached = read_billevents_checkpoint(ws)
    print(f"📚 Checkpoint: {len(cached)} bills already fetched.")

    dq = {"bills_total": len(bills), "bills_failed": 0, "bills_confirmed_empty": 0,
          "bills_from_checkpoint": 0, "bills_fetched_fresh": 0}
    failed_bills: set = set()
    events_by_bill: dict[str, list] = {}
    pending: list[list] = []
    to_fetch = []
    for b in bills:
        if b in cached:
            events_by_bill[b] = cached[b]
            dq["bills_from_checkpoint"] += 1
        else:
            to_fetch.append(b)

    print(f"📡 Fetching {len(to_fetch)} of {len(bills)} distinct flagged bills...")
    for i, bill in enumerate(to_fetch, start=1):
        status, events = fetch_events_for_bill(bill)
        if status == FetchResult.FAILED:
            dq["bills_failed"] += 1
            # Do NOT checkpoint failures (retry on next run). Mark the bill
            # as failed so its flagged rows become Class F, NOT Class D.
            failed_bills.add(bill)
            events_by_bill[bill] = []
        elif status == FetchResult.EMPTY:
            dq["bills_confirmed_empty"] += 1
            dq["bills_fetched_fresh"] += 1
            pending.append([bill, "", "", CONFIRMED_EMPTY_SENTINEL, "", ""])
            events_by_bill[bill] = []
        else:
            dq["bills_fetched_fresh"] += 1
            ev_list = []
            for e in events:
                if not isinstance(e, dict):
                    continue
                row = [
                    bill,
                    safe_str(e.get("LegislationEventID")),
                    safe_str(e.get("EventDate"))[:25],
                    safe_str(e.get("EventCode")),
                    safe_str(e.get("ChamberCode")),
                    safe_str(e.get("Description"))[:500],
                ]
                pending.append(row)
                ev_list.append({
                    "LegislationEventID": e.get("LegislationEventID"),
                    "EventDate": e.get("EventDate"),
                    "EventCode": e.get("EventCode"),
                    "ChamberCode": e.get("ChamberCode"),
                    "Description": e.get("Description"),
                })
            events_by_bill[bill] = ev_list
        if i % CHECKPOINT_BATCH == 0 and pending:
            ws.append_rows(pending, value_input_option="RAW")
            print(f"  💾 checkpoint {i}/{len(to_fetch)} (failed={dq['bills_failed']}, empty={dq['bills_confirmed_empty']})")
            pending = []
    if pending:
        ws.append_rows(pending, value_input_option="RAW")
    return events_by_bill, dq, failed_bills


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main() -> int:
    start = datetime.now(timezone.utc)
    print(f"🚀 PR-C7.1d structural audit start {start.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"   window {INVESTIGATION_START} → {INVESTIGATION_END}")
    sheet = authenticate_sheets()

    flagged = find_flagged_rows(sheet)
    if not flagged:
        print("✅ Zero flagged rows. Section 9 is clean for this window.")
        return 0

    distinct_bills = sorted({f["bill"] for f in flagged if f["bill"]})
    print(f"🔎 Distinct bills among flagged rows: {len(distinct_bills)}")

    events_by_bill, dq, failed_bills = fetch_all_bills(sheet, distinct_bills)

    # Categorize each flagged row + accumulate data-quality stats over events.
    class_counts: Counter = Counter()
    eventcode_hist: Counter = Counter()
    eventcode_sample_desc: dict[str, str] = {}
    verdict_rows: list[list] = []
    ev_null_code = ev_null_date = ev_malformed_date = ev_total = 0

    for f in flagged:
        if f["bill"] in failed_bills:
            # Bill fetch failed → indeterminate. Do NOT categorize against
            # empty events (that would be a false Class D). Surface as F.
            class_counts[CLASS_F_FETCH_FAILED] += 1
            verdict_rows.append([
                f["bill"], f["date"], f["outcome"][:200],
                CLASS_F_FETCH_FAILED, 0, "", "FALSE",
                "LIS fetch failed this run; retry next run before trusting any class",
            ])
            continue
        evs = events_by_bill.get(f["bill"], [])
        cat = categorize_row(f["bill"], f["date"], evs)
        class_counts[cat.linkage_class] += 1
        for code in cat.event_codes:
            eventcode_hist[code] += 1
        verdict_rows.append([
            f["bill"], f["date"], f["outcome"][:200],
            cat.linkage_class, cat.matched_event_count,
            ",".join(cat.event_codes), "TRUE" if cat.has_real_time else "FALSE",
            cat.detail[:300],
        ])

    # Data-quality scan over ALL fetched events (not just matched) —
    # measures LIS structural completeness directly.
    for bill, evs in events_by_bill.items():
        for e in evs:
            if not isinstance(e, dict):
                continue
            ev_total += 1
            code = safe_str(e.get("EventCode"))
            edate = safe_str(e.get("EventDate"))
            if not code:
                ev_null_code += 1
            else:
                if code not in eventcode_sample_desc:
                    eventcode_sample_desc[code] = safe_str(e.get("Description"))[:80]
            if not edate:
                ev_null_date += 1
            elif not event_date_only(edate):
                ev_malformed_date += 1

    total = len(flagged)
    print()
    print(f"=== MEASURED BREAKDOWN ({total} flagged rows) ===")
    for cls in (CLASS_B_HAS_TIME, CLASS_C_NO_TIME, CLASS_D_NO_EVENT,
                CLASS_E_EVENTCODE_MISSING, CLASS_F_FETCH_FAILED, CLASS_X_ROW_MALFORMED):
        n = class_counts.get(cls, 0)
        print(f"  {cls:<34} {n:>6}  ({n/total:.1%})")
    print()
    print(f"=== LIS DATA QUALITY (fragility) ===")
    print(f"  distinct flagged bills:        {dq['bills_total']}")
    print(f"  from checkpoint:               {dq['bills_from_checkpoint']}")
    print(f"  fetched fresh:                 {dq['bills_fetched_fresh']}")
    print(f"  bills LegEvent fetch FAILED:   {dq['bills_failed']}  (retry next run)")
    print(f"  bills confirmed empty:         {dq['bills_confirmed_empty']}")
    print(f"  total events examined:         {ev_total}")
    print(f"  events w/ null EventCode:      {ev_null_code}  ({ev_null_code/max(1,ev_total):.1%})")
    print(f"  events w/ null EventDate:      {ev_null_date}  ({ev_null_date/max(1,ev_total):.1%})")
    print(f"  events w/ malformed EventDate: {ev_malformed_date}")
    print()
    print(f"=== EVENTCODE HISTOGRAM among flagged rows (top 25) — reveals Class A clusters ===")
    for code, n in eventcode_hist.most_common(25):
        print(f"  {code:<10} {n:>6}  {eventcode_sample_desc.get(code,'')}")
    print()

    # Write result tabs.
    write_tab(sheet, ROWVERDICTS_TAB, ROWVERDICTS_HEADER, verdict_rows, "H")
    dq_rows = [[k, str(v)] for k, v in dq.items()]
    dq_rows += [["events_total", str(ev_total)],
                ["events_null_eventcode", str(ev_null_code)],
                ["events_null_eventdate", str(ev_null_date)],
                ["events_malformed_eventdate", str(ev_malformed_date)]]
    write_tab(sheet, DATAQUALITY_TAB, DATAQUALITY_HEADER, dq_rows, "B")

    end = datetime.now(timezone.utc)
    summary = {
        "run_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_seconds": round((end - start).total_seconds(), 1),
        "flagged_rows_total": total,
        "distinct_flagged_bills": len(distinct_bills),
        "class_B_has_time": class_counts.get(CLASS_B_HAS_TIME, 0),
        "class_C_no_time": class_counts.get(CLASS_C_NO_TIME, 0),
        "class_D_no_event": class_counts.get(CLASS_D_NO_EVENT, 0),
        "class_E_eventcode_missing": class_counts.get(CLASS_E_EVENTCODE_MISSING, 0),
        "class_F_fetch_failed": class_counts.get(CLASS_F_FETCH_FAILED, 0),
        "class_X_row_malformed": class_counts.get(CLASS_X_ROW_MALFORMED, 0),
        "distinct_eventcodes_among_flagged": len(eventcode_hist),
        "eventcode_histogram_json": json.dumps(eventcode_hist.most_common(50)),
    }
    write_tab(sheet, SUMMARY_TAB, SUMMARY_HEADER, [[k, str(v)] for k, v in summary.items()], "B")
    print(f"✅ PR-C7.1d complete in {summary['elapsed_seconds']}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
