"""
PR-C7.1b — FULL-SCALE validation of the structural router.

The decisive test: run structural_router.route_event() against the ACTUAL
X-Ray Section-9 flagged rows (the production target) and measure how many
collapse to admin (false positives resolved) vs stay meeting (genuine
residue). If ~942 → admin and ~100 → meeting, the router does exactly
what the C7.1d audit predicted, at full scale.

Also (re-)confirms at scale:
  - validate_status_grouping() vs LIS's live published status list → drift
  - the complete distribution of Status values actually seen across all
    flagged bills' events (catches any status that the per-bill data
    carries) cross-checked against our grouping
  - a sample of each (route, reason) bucket for eyeball validation
  - the edge-status groupings (Left In Committee, Introduced, Continued*)
    surfaced with their real frequencies + routes

Method (mirrors tools/c7_1d_structural_audit/audit.py — same flagged-row
detection + checkpointed fetch + (bill,date)+token-overlap match):
  1. Read Sheet1, find flagged Section-9 rows (X-Ray logic verbatim).
  2. Per distinct flagged bill: fetch LegEvent fresh, capturing the
     router's fields (Status, ReferenceType, VoteTally, ActorType,
     EventCode, EventDate). Checkpoint every 25 bills (resumable).
  3. Per flagged row: match the (bill,date) event with best token overlap
     to the row Outcome (production-resolver style), apply route_event.
  4. Report + write tabs. Numbers are READ FROM THE SHEET, never
     transcribed from a terminal (assumptions_audit #57 lesson).

Read-only w.r.t. Sheet1 / worker cache. Writes only C7_1b_FV_* tabs.
Defensive throughout (fragile-data mandate): safe_str/.get, header-index
lookup, non-dict skips, nothing raises.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from enum import Enum

import gspread
import requests
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from structural_router import route_event, validate_status_grouping, _s  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from investigation_config import INVESTIGATION_START, INVESTIGATION_END  # noqa: E402

INV_START = datetime.strptime(INVESTIGATION_START, "%Y-%m-%d").date()
INV_END = datetime.strptime(INVESTIGATION_END, "%Y-%m-%d").date()

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
TARGET_SHEET = "Sheet1"
TARGET_COMMITTEE = "📋 Ledger Updates"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
LIS_HEADERS = {"WebAPIKey": "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"}
SESSION_5D = "20261"
VURL = "https://lis.virginia.gov/LegislationVersion/api/GetLegislationVersionbyBillNumberAsync"
EURL = "https://lis.virginia.gov/LegislationEvent/api/GetPublicLegislationEventHistoryListAsync"
STATUS_LIST_URL = "https://lis.virginia.gov/Legislation/api/GetLegislationStatusListAsync"
TIMEOUT, RETRY, BACKOFF = 15, 3, 2.0
CHECKPOINT_BATCH = 25

CKPT_TAB = "C7_1b_FV_BillEvents"
CKPT_HEADER = ["Bill", "EventID", "EventDate", "EventCode", "ChamberCode",
               "ReferenceType", "VoteTally", "ActorType", "Status", "Description"]
EMPTY_SENTINEL = "_CONFIRMED_EMPTY_"
VERDICTS_TAB = "C7_1b_FV_Verdicts"
VERDICTS_HEADER = ["Bill", "Date", "Outcome", "Route", "Reason",
                   "MatchedStatus", "MatchedRefType", "MatchedEventCode"]
SUMMARY_TAB = "C7_1b_FV_Summary"
SUMMARY_HEADER = ["Key", "Value"]

# X-Ray classifier (verbatim, for flagged-row detection)
PLACEHOLDER_TIMES = {"", "nan", "none", "time tba", "journal entry", "ledger",
                     "⏱️ [no_schedule_match]", "⏱️ [no_convene_anchor]"}
ADMIN_OVERRIDE = ["substitute printed", "committee substitute printed", "prefiled and ordered printed"]
MEETING_PATTERNS = ["reported", "recommends", "recommend", "committee substitute", "incorporate",
    "incorporated", "incorporates", "discharged", "stricken", "tabled", "continued", "passed",
    "failed", "defeated", "amended", "floor substitute", "rules suspended", "offered", "block vote",
    "voice vote", "roll call", "reading dispensed", "read first", "read second", "read third",
    "agreed to", "rejected", "reconsidered", "conference report agreed", "insisted", "taken up",
    "reconsideration of", "receded", "reading waived", "reading of substitute waived",
    "reading of amendment waived", "reading of amendments waived", "reading of amendment not waived",
    "elected by", "election by", "elected to by", "emergency clause",
    "requested second conference committee", "motion for", "vote:", "withdrawn", "concurred",
    "removed from the table"]
ADMIN_PATTERNS = ["referred to", "assigned", "rereferred", "placed on", "impact statement",
    "fiscal impact", "substitute printed", "reprinted", "printed as engrossed", "enrolled",
    "signed by", "presented", "communicated", "received", "engrossed", "conferee",
    "conference report", "requested conference committee", "acceded to request",
    "approved by governor", "vetoed", "governor's recommendation", "governor's substitute",
    "governor:", "laid on speaker's table", "laid on clerk's desk", "effective -",
    "acts of assembly chapter", "governor's action deadline", "action deadline", "scheduled",
    "left in", "blank action", "moved from uncontested calendar", "no further action taken",
    "unanimous consent to introduce", "introduced at the request of", "budget amendments available",
    "recommitted", "fiscal impact review", "prefiled and ordered printed", "(view meeting)",
    "no agenda listed", "subcommittee info", "speaker's conference room", "[memory anchor: admin]"]

_STOP = frozenset({"the", "a", "an", "of", "to", "by", "from", "in", "on", "and", "or", "with", "for"})


def classify_action(o):
    l = _s(o).lower()
    if not l or l in ("none", "nan"):
        return "administrative"
    if any(p in l for p in ADMIN_OVERRIDE):
        return "administrative"
    if any(p in l for p in MEETING_PATTERNS):
        return "meeting"
    if any(p in l for p in ADMIN_PATTERNS):
        return "administrative"
    return "unclassified"


def in_window(d):
    s = _s(d)
    try:
        return INV_START <= datetime.strptime(s, "%Y-%m-%d").date() <= INV_END
    except ValueError:
        return False


def toks(t):
    import re
    return {w for w in re.findall(r"[a-z0-9]+", _s(t).lower()) if len(w) >= 3 and w not in _STOP}


def date10(x):
    s = _s(x)
    return s.split("T", 1)[0].split(" ", 1)[0][:10]


class FR(Enum):
    OK = 1
    EMPTY = 2
    FAILED = 3


def auth():
    raw = os.environ.get("GCP_CREDENTIALS")
    if not raw:
        raise RuntimeError("GCP_CREDENTIALS empty")
    return gspread.authorize(Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)).open_by_key(SPREADSHEET_ID)


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
    if ws.row_count < len(payload):
        ws.resize(rows=len(payload) + 100)
    ws.update(values=payload, range_name="A1")
    if ws.row_count > len(payload):
        ws.batch_clear([f"A{len(payload)+1}:{last_col}{ws.row_count}"])
    print(f"📝 wrote {len(rows)} to {name}")


def lis_get(url, params, kind):
    for a in range(RETRY):
        try:
            r = requests.get(url, headers=LIS_HEADERS, params=params, timeout=TIMEOUT)
        except Exception:
            if a < RETRY - 1:
                time.sleep(BACKOFF * (2 ** a))
            continue
        if r.status_code != 200:
            if r.status_code != 429 and 400 <= r.status_code < 500:
                return FR.FAILED, None
            if a < RETRY - 1:
                time.sleep(BACKOFF * (2 ** a))
            continue
        try:
            return FR.OK, r.json()
        except Exception:
            return FR.FAILED, None
    return FR.FAILED, None


def fetch_bill(bill):
    st, vj = lis_get(VURL, {"billNumber": bill, "sessionCode": SESSION_5D}, "ver")
    if st == FR.FAILED or not isinstance(vj, dict):
        return FR.FAILED, []
    vs = vj.get("LegislationsVersion")
    if not isinstance(vs, list) or not vs or not isinstance(vs[0], dict):
        return FR.EMPTY, []
    lid = vs[0].get("LegislationID")
    if not lid:
        return FR.EMPTY, []
    st, ej = lis_get(EURL, {"legislationID": lid, "sessionCode": SESSION_5D}, "evt")
    if st == FR.FAILED or not isinstance(ej, dict):
        return FR.FAILED, []
    ev = ej.get("LegislationEvents") or []
    if not isinstance(ev, list):
        return FR.FAILED, []
    return (FR.OK, ev) if ev else (FR.EMPTY, [])


def read_ckpt(ws):
    vals = ws.get_all_values()
    if not vals or len(vals) <= 1:
        return {}
    hdr = vals[0]
    try:
        ci = {c: hdr.index(c) for c in CKPT_HEADER}
    except ValueError:
        return {}
    out = defaultdict(list)
    for r in vals[1:]:
        n = len(r)
        bill = _s(r[ci["Bill"]] if ci["Bill"] < n else "")
        if not bill:
            continue
        if bill not in out:
            out[bill] = []
        if _s(r[ci["EventCode"]] if ci["EventCode"] < n else "") == EMPTY_SENTINEL:
            continue
        out[bill].append({k: (r[ci[k]] if ci[k] < n else "") for k in CKPT_HEADER if k != "Bill"})
    return out


def main():
    start = datetime.now(timezone.utc)
    print(f"🚀 PR-C7.1b FULL validation {start.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    sheet = auth()

    # status-grouping drift check (authoritative)
    st, sj = lis_get(STATUS_LIST_URL, {}, "statuslist")
    live_status_names = [x.get("Name") for x in sj.get("References", [])] if (st == FR.OK and isinstance(sj, dict)) else []
    drift = validate_status_grouping(live_status_names)
    print(f"📋 published statuses: {len(live_status_names)}; grouping drift: {drift if drift else 'NONE ✅'}")

    # flagged Section-9 rows
    ws = sheet.worksheet(TARGET_SHEET)
    vals = ws.get_all_values()
    hdr = vals[0]
    ci = {c: hdr.index(c) for c in ["Date", "Committee", "Time", "Outcome", "Bill"] if c in hdr}
    flagged = []
    for r in vals[1:]:
        n = len(r)
        if not in_window(r[ci["Date"]] if ci["Date"] < n else ""):
            continue
        if _s(r[ci["Committee"]] if ci["Committee"] < n else "") != TARGET_COMMITTEE:
            continue
        if _s(r[ci["Time"]] if ci["Time"] < n else "").lower() not in PLACEHOLDER_TIMES:
            continue
        o = r[ci["Outcome"]] if ci["Outcome"] < n else ""
        if classify_action(o) != "meeting":
            continue
        flagged.append({"bill": _s(r[ci["Bill"]] if ci["Bill"] < n else ""), "date": _s(r[ci["Date"]] if ci["Date"] < n else ""), "outcome": _s(o)})
    print(f"🔎 flagged Section-9 rows: {len(flagged)}")
    bills = sorted({f["bill"] for f in flagged if f["bill"]})
    print(f"🔎 distinct flagged bills: {len(bills)}")

    # fetch (checkpointed)
    ck = get_or_create(sheet, CKPT_TAB, CKPT_HEADER, rows=40000)
    cached = read_ckpt(ck)
    print(f"📚 checkpoint: {len(cached)} bills cached")
    events_by_bill = dict(cached)
    failed = set()
    todo = [b for b in bills if b not in cached]
    pending = []
    for i, bill in enumerate(todo, 1):
        st, evs = fetch_bill(bill)
        if st == FR.FAILED:
            failed.add(bill)
            events_by_bill[bill] = []
        elif st == FR.EMPTY:
            pending.append([bill, "", "", EMPTY_SENTINEL, "", "", "", "", "", ""])
            events_by_bill[bill] = []
        else:
            lst = []
            for e in evs:
                if not isinstance(e, dict):
                    continue
                row = [bill, _s(e.get("LegislationEventID")), _s(e.get("EventDate"))[:25],
                       _s(e.get("EventCode")), _s(e.get("ChamberCode")), _s(e.get("ReferenceType")),
                       _s(e.get("VoteTally"))[:40], _s(e.get("ActorType")), _s(e.get("Status")),
                       _s(e.get("Description"))[:400]]
                pending.append(row)
                lst.append({"EventID": row[1], "EventDate": row[2], "EventCode": row[3],
                            "ChamberCode": row[4], "ReferenceType": row[5], "VoteTally": row[6],
                            "ActorType": row[7], "Status": row[8], "Description": row[9]})
            events_by_bill[bill] = lst
        if i % CHECKPOINT_BATCH == 0 and pending:
            ck.append_rows(pending, value_input_option="RAW")
            print(f"  💾 {i}/{len(todo)} (failed={len(failed)})")
            pending = []
    if pending:
        ck.append_rows(pending, value_input_option="RAW")

    # route each flagged row via its best-matching event
    route_counts = Counter()
    reason_counts = Counter()
    status_seen = Counter()
    verdict_rows = []
    samples = defaultdict(list)
    no_event = 0
    for f in flagged:
        evs = events_by_bill.get(f["bill"], [])
        if f["bill"] in failed:
            route_counts["FAILED_REFETCH"] += 1
            continue
        # match (bill,date) + best token overlap with outcome
        cands = [e for e in evs if date10(e.get("EventDate")) == date10(f["date"])]
        if not cands:
            no_event += 1
            route_counts["no_event"] += 1
            verdict_rows.append([f["bill"], f["date"], f["outcome"][:160], "no_event", "no_legevent_match", "", "", ""])
            continue
        ot = toks(f["outcome"])
        best = max(cands, key=lambda e: len(ot & toks(e.get("Description"))))
        v = route_event(best)
        route_counts[v.route] += 1
        reason_counts[(v.route, v.reason)] += 1
        status_seen[_s(best.get("Status")) or "<blank>"] += 1
        verdict_rows.append([f["bill"], f["date"], f["outcome"][:160], v.route, v.reason,
                             _s(best.get("Status")), _s(best.get("ReferenceType")), _s(best.get("EventCode"))])
        if len(samples[(v.route, v.reason)]) < 6:
            samples[(v.route, v.reason)].append(f"{_s(best.get('EventCode')):<7}{f['outcome'][:50]}")

    total = len(flagged)
    meeting = route_counts.get("meeting", 0)
    admin = route_counts.get("admin", 0)
    print(f"\n=== FLAGGED-ROW ROUTING ({total} rows) ===")
    print(f"  → admin (false-positive collapse): {admin}  ({admin/max(1,total):.1%})")
    print(f"  → meeting (genuine residue):       {meeting}  ({meeting/max(1,total):.1%})")
    print(f"  → no_event (no LegEvent match):    {route_counts.get('no_event',0)}")
    print(f"  → FAILED refetch:                  {route_counts.get('FAILED_REFETCH',0)}")
    print(f"\n  reason breakdown:")
    for (rt, rs), n in reason_counts.most_common():
        print(f"    {rt:<8} {rs:<28} {n:>5}")
    print(f"\n  samples:")
    for key in sorted(samples, key=lambda k: -reason_counts[k]):
        print(f"  [{key[0]}/{key[1]}]")
        for s in samples[key]:
            print(f"      {s}")

    write_tab(sheet, VERDICTS_TAB, VERDICTS_HEADER, verdict_rows, "H")
    end = datetime.now(timezone.utc)
    summary = {
        "run_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_s": round((end - start).total_seconds(), 1),
        "flagged_rows": total,
        "distinct_bills": len(bills),
        "routed_admin": admin,
        "routed_meeting": meeting,
        "no_event_match": route_counts.get("no_event", 0),
        "failed_refetch": route_counts.get("FAILED_REFETCH", 0),
        "admin_pct": f"{admin/max(1,total):.4f}",
        "meeting_pct": f"{meeting/max(1,total):.4f}",
        "published_statuses": len(live_status_names),
        "status_grouping_drift": json.dumps(drift),
        "reason_breakdown": json.dumps({f"{r}/{s}": n for (r, s), n in reason_counts.items()}),
        "status_seen_on_flagged": json.dumps(dict(status_seen.most_common())),
    }
    write_tab(sheet, SUMMARY_TAB, SUMMARY_HEADER, [[k, str(v)] for k, v in summary.items()], "B")
    print(f"\n✅ done {summary['elapsed_s']}s. admin={admin} meeting={meeting} drift={'NONE' if not drift else drift}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
