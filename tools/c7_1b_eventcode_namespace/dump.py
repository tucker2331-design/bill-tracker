"""
PR-C7.1b prerequisite — dump the COMPLETE EventCode namespace + verify
the PR-C7.0.6 persist landed.

Why this runs BEFORE any classifier code
----------------------------------------
PR-C7.1b replaces the X-Ray's substring text classifier with a
deterministic EventCode → category function. To design that function
WITHOUT guessing, we need the full EventCode alphabet — not the top-25
the C7.1d audit dumped. This tool reads the production LegEvent_Events
cache (now EventCode-aware post-PR-C7.0.6) and produces:

  1. Verification: did EventCode actually populate? did the EventID
     fix (open_anti_patterns #9) take? Coverage %s.
  2. The complete EventCode namespace: every distinct code, count,
     up to 3 sample descriptions, chambers seen, how many carry a real
     wall-clock time.
  3. Cross-tab vs the CURRENT text classifier: for each EventCode, how
     many of its events the X-Ray's classify_action() would call
     meeting / administrative / unclassified. This pinpoints exactly
     which codes the text classifier mislabels (e.g. H5601 "Bill text
     as passed" → text says meeting, but it's an admin document) — the
     concrete evidence for the EventCode→category mapping.

Read-only. Writes ONLY to its own C7_1b_* result tabs. No worker/cache
mutation.

Defensive per the fragile-data mandate (owner 2026-05-12): every field
via safe_str/.get; header-index lookup; non-dict rows skipped + counted;
nothing raises.

Coverage caveat: EventCode backfills ~500 bills/cycle on TTL refresh
(only freshly-hydrated events carry it; rows loaded from the pre-C7.0.6
tab have blank EventCode until re-hydrated). So on the first cycle or
two after C7.0.6, expect partial EventCode coverage that climbs toward
full over ~7 cycles. Partial coverage still yields a substantially
complete namespace because hydrated bills carry their FULL event
history. The tool reports coverage explicitly so the namespace's
completeness is self-describing.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"  # Mastermind DB (calendar_worker.py:25)
EVENTS_TAB = "LegEvent_Events"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Output tabs
NAMESPACE_TAB = "C7_1b_EventCodeNamespace"
NAMESPACE_HEADER = [
    "EventCode", "Count", "Chambers", "HasRealTime", "TextMeeting",
    "TextAdmin", "TextUnclassified", "SampleDesc1", "SampleDesc2", "SampleDesc3",
]
SUMMARY_TAB = "C7_1b_NamespaceSummary"
SUMMARY_HEADER = ["Key", "Value"]

# === X-Ray classifier patterns (verbatim from tools/meeting_bug_triage /
# pages/ray2.py, as of 2026-05-31). Copied, not imported (Streamlit dep).
# DRIFT RISK acknowledged; lexicons extraction is the consolidation. ===
ADMIN_OVERRIDE_PATTERNS = [
    "substitute printed", "committee substitute printed", "prefiled and ordered printed",
]
MEETING_ACTION_PATTERNS = [
    "reported", "recommends", "recommend", "committee substitute",
    "incorporate", "incorporated", "incorporates", "discharged", "stricken",
    "tabled", "continued", "passed", "failed", "defeated", "amended",
    "floor substitute", "rules suspended", "offered", "block vote", "voice vote",
    "roll call", "reading dispensed", "read first", "read second", "read third",
    "agreed to", "rejected", "reconsidered", "conference report agreed",
    "insisted", "taken up", "reconsideration of", "receded", "reading waived",
    "reading of substitute waived", "reading of amendment waived",
    "reading of amendments waived", "reading of amendment not waived",
    "elected by", "election by", "elected to by", "emergency clause",
    "requested second conference committee", "motion for", "vote:",
    "withdrawn", "concurred", "removed from the table",
]
ADMINISTRATIVE_PATTERNS = [
    "referred to", "assigned", "rereferred", "placed on", "impact statement",
    "fiscal impact", "substitute printed", "reprinted", "printed as engrossed",
    "enrolled", "signed by", "presented", "communicated", "received", "engrossed",
    "conferee", "conference report", "requested conference committee",
    "acceded to request", "approved by governor", "vetoed",
    "governor's recommendation", "governor's substitute", "governor:",
    "laid on speaker's table", "laid on clerk's desk", "effective -",
    "acts of assembly chapter", "governor's action deadline", "action deadline",
    "scheduled", "left in", "blank action", "moved from uncontested calendar",
    "no further action taken", "unanimous consent to introduce",
    "introduced at the request of", "budget amendments available", "recommitted",
    "fiscal impact review", "prefiled and ordered printed", "(view meeting)",
    "no agenda listed", "subcommittee info", "speaker's conference room",
    "[memory anchor: admin]",
]


def safe_str(v) -> str:
    if v is None:
        return ""
    try:
        return str(v).strip()
    except Exception:
        return ""


def classify_action(outcome_text: str) -> str:
    """Verbatim from pages/ray2.py classify_action."""
    lower = safe_str(outcome_text).lower()
    if not lower or lower in ("none", "nan"):
        return "administrative"
    if any(p in lower for p in ADMIN_OVERRIDE_PATTERNS):
        return "administrative"
    if any(p in lower for p in MEETING_ACTION_PATTERNS):
        return "meeting"
    if any(p in lower for p in ADMINISTRATIVE_PATTERNS):
        return "administrative"
    return "unclassified"


def eventdate_has_real_time(raw) -> bool:
    s = safe_str(raw)
    if not s:
        return False
    tp = ""
    if "T" in s:
        tp = s.split("T", 1)[1]
    elif " " in s:
        tp = s.split(" ", 1)[1]
    else:
        return False
    tp = tp.strip()[:8]
    return bool(tp) and tp not in ("00:00:00", "00:00", "0:00:00", "0:00")


def authenticate():
    raw = os.environ.get("GCP_CREDENTIALS")
    if not raw:
        raise RuntimeError("GCP_CREDENTIALS env var is empty.")
    creds = Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)


def get_or_create(sheet, name, header, rows=2000):
    try:
        return sheet.worksheet(name)
    except WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows=rows, cols=len(header))
        ws.update(values=[header], range_name="A1")
        return ws


def write_tab(sheet, name, header, rows, last_col):
    ws = get_or_create(sheet, name, header, rows=max(2000, len(rows) + 100))
    payload = [header] + rows
    ws.update(values=payload, range_name="A1")
    allocated = ws.row_count
    if allocated > len(payload):
        ws.batch_clear([f"A{len(payload) + 1}:{last_col}{allocated}"])
    print(f"📝 Wrote {len(rows)} rows to {name}.")


def main() -> int:
    start = datetime.now(timezone.utc)
    print(f"🚀 PR-C7.1b EventCode namespace dump {start.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    sheet = authenticate()
    try:
        ws = sheet.worksheet(EVENTS_TAB)
    except WorksheetNotFound:
        print(f"❌ {EVENTS_TAB} not found — has the worker created it?")
        return 1
    values = ws.get_all_values()
    if not values or len(values) <= 1:
        print(f"❌ {EVENTS_TAB} empty.")
        return 1
    header = values[0]
    # header-index lookup; EventCode optional (may be absent if read pre-C7.0.6)
    def idx(col):
        return header.index(col) if col in header else -1
    i_code, i_desc = idx("EventCode"), idx("Description")
    i_chamber, i_date, i_id = idx("ChamberCode"), idx("EventDate"), idx("EventID")
    if i_desc < 0:
        print(f"❌ {EVENTS_TAB} header missing Description. Got: {header}")
        return 1
    if i_code < 0:
        print(f"⚠️ {EVENTS_TAB} header has NO EventCode column — PR-C7.0.6 persist "
              f"has not run yet, or the tab predates it. Cannot dump namespace.")
        return 1

    rows = values[1:]
    total = len(rows)
    with_code = with_id = with_time = nondict = 0
    code_count: Counter = Counter()
    code_chambers: dict = defaultdict(set)
    code_realtime: Counter = Counter()
    code_samples: dict = defaultdict(list)
    code_textcls: dict = defaultdict(lambda: Counter())
    for r in rows:
        n = len(r)
        code = safe_str(r[i_code]) if i_code < n else ""
        desc = safe_str(r[i_desc]) if i_desc < n else ""
        chamber = safe_str(r[i_chamber]) if (i_chamber >= 0 and i_chamber < n) else ""
        edate = safe_str(r[i_date]) if (i_date >= 0 and i_date < n) else ""
        eid = safe_str(r[i_id]) if (i_id >= 0 and i_id < n) else ""
        if eid:
            with_id += 1
        if not code:
            continue  # blank EventCode = pre-C7.0.6 row not yet refreshed
        with_code += 1
        code_count[code] += 1
        if chamber:
            code_chambers[code].add(chamber)
        if eventdate_has_real_time(edate):
            with_time += 1
            code_realtime[code] += 1
        if len(code_samples[code]) < 3 and desc and desc not in code_samples[code]:
            code_samples[code].append(desc)
        code_textcls[code][classify_action(desc)] += 1

    cov = with_code / max(1, total)
    idcov = with_id / max(1, total)
    print(f"=== VERIFICATION ===")
    print(f"  total event rows:            {total}")
    print(f"  rows with EventCode:         {with_code}  ({cov:.1%})  <-- PR-C7.0.6 persist landed if > 0")
    print(f"  rows with EventID (non-blank): {with_id}  ({idcov:.1%})  <-- open_anti_patterns #9 fix if high")
    print(f"  rows with real wall-clock time: {with_time}")
    print(f"  distinct EventCodes:         {len(code_count)}")
    print()
    print(f"=== EVENTCODE NAMESPACE (every code; sorted by count) ===")
    print(f"  {'code':<8} {'count':>6} {'cham':<6} {'rt':>5}  txt(meet/adm/uncl)  sample")
    ns_rows = []
    for code, n in code_count.most_common():
        tc = code_textcls[code]
        cham = "/".join(sorted(code_chambers[code]))
        samples = code_samples[code]
        meet, adm, uncl = tc.get("meeting", 0), tc.get("administrative", 0), tc.get("unclassified", 0)
        print(f"  {code:<8} {n:>6} {cham:<6} {code_realtime[code]:>5}  {meet:>4}/{adm:>4}/{uncl:>4}  {samples[0][:50] if samples else ''}")
        ns_rows.append([
            code, n, cham, code_realtime[code], meet, adm, uncl,
            samples[0][:120] if len(samples) > 0 else "",
            samples[1][:120] if len(samples) > 1 else "",
            samples[2][:120] if len(samples) > 2 else "",
        ])
    print()
    write_tab(sheet, NAMESPACE_TAB, NAMESPACE_HEADER, ns_rows, "J")
    end = datetime.now(timezone.utc)
    summary = {
        "run_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_seconds": round((end - start).total_seconds(), 1),
        "total_event_rows": total,
        "rows_with_eventcode": with_code,
        "eventcode_coverage_pct": f"{cov:.4f}",
        "rows_with_eventid": with_id,
        "eventid_coverage_pct": f"{idcov:.4f}",
        "distinct_eventcodes": len(code_count),
        "rows_with_real_time": with_time,
    }
    write_tab(sheet, SUMMARY_TAB, SUMMARY_HEADER, [[k, str(v)] for k, v in summary.items()], "B")
    print(f"✅ Done in {summary['elapsed_seconds']}s. EventCode coverage {cov:.1%}, "
          f"{len(code_count)} distinct codes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
