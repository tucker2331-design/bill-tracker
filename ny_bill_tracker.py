"""ny_bill_tracker.py - New York OpenLegislation bill-record pipeline.

This is the first New York retune of the Virginia product backend. It keeps the
same lobbyist-facing output shape as `bill_tracker.py` where the data exists,
but swaps the source contract to New York State Senate OpenLegislation:

    https://legislation.nysenate.gov/api/3

The important source difference is explicit: OpenLeg's bill API carries a rich
bill record (status, actions, votes, sponsor, committees, summary), while its
public calendar/committee docs are Senate-centered and state that Assembly
calendar/committee data is not currently sent to OpenLeg. This module therefore
does NOT invent Assembly meeting coverage. It writes bill rows and a
machine-readable completeness object that names the current gaps.

Required env:
  NY_OPENLEG_API_KEY - free OpenLeg API key, passed as `key=` query param.

Optional env:
  NY_OPENLEG_SESSION_YEAR - odd-numbered NY session year, e.g. 2025.
  NY_OPENLEG_LIMIT - page size, max 1000 per docs; default 1000.
  NY_OPENLEG_MAX_PAGES - local/testing cap; unset means all pages.
  NY_BILL_TRACKER_TAB - destination tab; default NY_Bill_Tracker.
  NY_SPREADSHEET_ID - destination workbook for NY writes.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import gspread
import requests
from google.oauth2.service_account import Credentials


OPENLEG_BASE_URL = "https://legislation.nysenate.gov/api/3"
NY_BILL_TRACKER_TAB = os.environ.get("NY_BILL_TRACKER_TAB", "NY_Bill_Tracker")
DEFAULT_TIMEOUT_SECONDS = 30


class NYOpenLegError(RuntimeError):
    """Raised for source-contract or API failures that should keep last-known-good."""


def _alert(severity: str, category: str, message: str) -> None:
    """Visible alert path. Slack is best-effort; stdout is always written."""
    line = f"{severity} [NY_BILL_TRACKER/{category}] {message}"
    print(line)
    try:
        from calendar_worker import notify_slack

        notify_slack(line)
    except Exception as slack_err:
        print(f"WARN [NY_BILL_TRACKER/ALERT_PATH] Slack alert not delivered: {slack_err}")


def _clean_bill(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace(" ", "").upper().strip()


def _items(container: Any) -> List[Any]:
    """OpenLeg list wrappers are usually {'items': list|dict, 'size': n}."""
    if not container:
        return []
    if isinstance(container, list):
        return container
    if isinstance(container, dict):
        raw = container.get("items", [])
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return list(raw.values())
    return []


def _size(container: Any) -> int:
    if not container:
        return 0
    if isinstance(container, dict) and isinstance(container.get("size"), int):
        return int(container["size"])
    return len(_items(container))


def _parse_date(value: Any) -> Optional[_dt.date]:
    if not value:
        return None
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _sort_key_for_action(action: Dict[str, Any]) -> Tuple[str, int]:
    date = str(action.get("date", "") or "")
    try:
        seq = int(action.get("sequenceNo", 0) or 0)
    except (TypeError, ValueError):
        seq = 0
    return date, seq


def _status_text(status: Dict[str, Any]) -> str:
    status_type = str(status.get("statusType", "") or "").strip()
    status_desc = str(status.get("statusDesc", "") or "").strip()
    return status_desc or status_type


def _norm_chamber(value: Any) -> str:
    text = str(value or "").upper()
    if text.startswith("SEN"):
        return "Senate"
    if text.startswith("ASM") or text.startswith("ASS"):
        return "Assembly"
    return str(value or "").strip()


def _member_name(member: Any) -> str:
    if not isinstance(member, dict):
        return ""
    return str(member.get("fullName") or member.get("shortName") or "").strip()


def _vote_tally(vote: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize OpenLeg memberVotes without classifying the vote result."""
    buckets: Dict[str, int] = {}
    member_votes = vote.get("memberVotes", {})
    raw_items = member_votes.get("items", {}) if isinstance(member_votes, dict) else {}
    if isinstance(raw_items, dict):
        for code, bucket in raw_items.items():
            if isinstance(bucket, dict) and isinstance(bucket.get("size"), int):
                buckets[str(code)] = int(bucket["size"])
            else:
                buckets[str(code)] = len(_items(bucket))
    aye = buckets.get("AYE", 0) + buckets.get("AYEWR", 0)
    nay = buckets.get("NAY", 0)
    tally = f"{aye}-Y {nay}-N" if buckets else ""
    return {"tally": tally, "breakdown": buckets}


def _latest_vote(votes_container: Any) -> Dict[str, Any]:
    votes = [v for v in _items(votes_container) if isinstance(v, dict)]
    if not votes:
        return {"tally": "", "location": "", "date": ""}
    votes.sort(key=lambda v: str(v.get("voteDate", "") or ""))
    latest = votes[-1]
    committee = latest.get("committee") if isinstance(latest.get("committee"), dict) else {}
    tally = _vote_tally(latest)
    location = committee.get("name") or latest.get("voteType") or ""
    if committee.get("chamber") and committee.get("name"):
        location = f"{_norm_chamber(committee.get('chamber'))} {committee.get('name')}"
    return {
        "tally": tally["tally"],
        "location": str(location).strip(),
        "date": str(latest.get("voteDate", "") or "").strip(),
        "breakdown": tally["breakdown"],
        "vote_type": str(latest.get("voteType", "") or "").strip(),
    }


def _derive_position(item: Dict[str, Any]) -> Dict[str, Any]:
    bill_type = item.get("billType") if isinstance(item.get("billType"), dict) else {}
    origin_chamber = _norm_chamber(bill_type.get("chamber"))
    status = item.get("status") if isinstance(item.get("status"), dict) else {}
    past_committees = [c for c in _items(item.get("pastCommittees")) if isinstance(c, dict)]

    last_committee = str(status.get("committeeName") or "").strip()
    if not last_committee and past_committees:
        past_committees.sort(key=lambda c: str(c.get("referenceDate", "") or ""))
        last_committee = str(past_committees[-1].get("name") or "").strip()

    distinct = []
    for committee in sorted(past_committees, key=lambda c: str(c.get("referenceDate", "") or "")):
        name = str(committee.get("name") or "").strip()
        if name and (not distinct or distinct[-1] != name):
            distinct.append(name)

    other = "ASSEMBLY" if origin_chamber == "Senate" else "SENATE"
    status_markers = [
        str(status.get("statusType", "") or "").upper(),
        str(status.get("statusDesc", "") or "").upper(),
    ]
    for milestone in _items(item.get("milestones")):
        if isinstance(milestone, dict):
            status_markers.append(str(milestone.get("statusType", "") or "").upper())
            status_markers.append(str(milestone.get("statusDesc", "") or "").upper())
    crossed = bool(origin_chamber and any(other in marker for marker in status_markers))

    return {
        "current_chamber": origin_chamber,
        "crossed_over": crossed,
        "last_committee": last_committee,
        "referral_count": len(distinct),
    }


def _derive_outcome(item: Dict[str, Any]) -> Tuple[str, str]:
    """Return (outcome, source). Raw OpenLeg status is always kept on the record."""
    status = item.get("status") if isinstance(item.get("status"), dict) else {}
    status_blob = " ".join([
        str(status.get("statusType", "") or ""),
        str(status.get("statusDesc", "") or ""),
    ]).lower()

    if bool(item.get("signed")):
        return "signed", "signed_boolean"
    if _size(item.get("vetoMessages")) and "veto" in status_blob:
        return "vetoed", "veto_messages"

    if any(k in status_blob for k in ("signed", "chapter", "adopted")):
        return "signed", "status"
    if "veto" in status_blob:
        return "vetoed", "status"
    if any(k in status_blob for k in ("lost", "defeated", "stricken", "died", "failed")):
        return "dead", "status"
    if any(k in status_blob for k in ("governor", "delivered")):
        return "awaiting_governor", "status"
    return "in_progress", "default"


def _history(item: Dict[str, Any]) -> List[Dict[str, str]]:
    actions = [a for a in _items(item.get("actions")) if isinstance(a, dict)]
    actions.sort(key=_sort_key_for_action)
    return [
        {
            "action": str(a.get("text", "") or "").strip(),
            "date": str(a.get("date", "") or "").strip(),
            "chamber": _norm_chamber(a.get("chamber")),
        }
        for a in actions
        if str(a.get("text", "") or "").strip()
    ]


def _agenda_refs(item: Dict[str, Any]) -> List[Dict[str, str]]:
    refs = []
    for agenda_ref in _items(item.get("committeeAgendas")):
        if not isinstance(agenda_ref, dict):
            continue
        agenda_id = agenda_ref.get("agendaId") if isinstance(agenda_ref.get("agendaId"), dict) else {}
        committee_id = agenda_ref.get("committeeId") if isinstance(agenda_ref.get("committeeId"), dict) else {}
        refs.append({
            "year": str(agenda_id.get("year", "") or ""),
            "agenda_number": str(agenda_id.get("number", "") or ""),
            "committee": str(committee_id.get("name", "") or ""),
            "chamber": _norm_chamber(committee_id.get("chamber")),
        })
    return refs


def bill_to_record(item: Dict[str, Any], fetched_at_utc: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Flatten one OpenLeg bill response into the product row shape plus per-row counters."""
    bill = _clean_bill(item.get("basePrintNo") or item.get("printNo"))
    status = item.get("status") if isinstance(item.get("status"), dict) else {}
    sponsor = item.get("sponsor") if isinstance(item.get("sponsor"), dict) else {}
    sponsor_member = sponsor.get("member") if isinstance(sponsor.get("member"), dict) else {}
    position = _derive_position(item)
    outcome, outcome_source = _derive_outcome(item)
    history = _history(item)
    agenda_refs = _agenda_refs(item)

    last_action_date = ""
    if history:
        last_action_date = history[-1]["date"]
    elif status.get("actionDate"):
        last_action_date = str(status.get("actionDate") or "").strip()

    counters = {
        "has_actions": 1 if history else 0,
        "has_votes": 1 if _size(item.get("votes")) else 0,
        "has_sponsor": 1 if _member_name(sponsor_member) else 0,
        "has_summary": 1 if str(item.get("summary", "") or "").strip() else 0,
        "committee_agenda_refs": len(agenda_refs),
        f"outcome_source_{outcome_source}": 1,
    }
    record = {
        "bill": bill,
        "title": str(item.get("title", "") or "").strip(),
        "status_lis": _status_text(status),
        "outcome": outcome,
        "patron": _member_name(sponsor_member),
        "patron_id": str(sponsor_member.get("memberId", "") or "").strip() if sponsor_member else "",
        "chamber": position["current_chamber"],
        "crossed_over": position["crossed_over"],
        "last_committee": position["last_committee"],
        "referral_count": position["referral_count"],
        "latest_vote": _latest_vote(item.get("votes")),
        "upcoming": [],
        "last_action_date": last_action_date,
        "history": history,
        "data_as_of_utc": fetched_at_utc,
        "source": "NY OpenLegislation",
        "source_url": f"https://www.nysenate.gov/legislation/bills/{item.get('session')}/{bill}" if bill else "",
        "ny_summary": str(item.get("summary", "") or "").strip(),
        "ny_agenda_refs": agenda_refs,
    }
    return record, counters


@dataclass
class NYOpenLegClient:
    api_key: str
    base_url: str = OPENLEG_BASE_URL
    timeout: int = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "bill-tracker-ny-engine/0.1 (+https://github.com/tucker2331-design/bill-tracker)",
            "Accept": "application/json",
        })

    def get_json(self, path: str, **params: Any) -> Dict[str, Any]:
        if not self.api_key:
            raise NYOpenLegError("NY_OPENLEG_API_KEY is not set")
        merged = dict(params)
        merged["key"] = self.api_key
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=merged, timeout=self.timeout)
        if resp.status_code == 429:
            raise NYOpenLegError("OpenLeg returned 429 rate-limit response")
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict):
            raise NYOpenLegError(f"OpenLeg response for {path} was not a JSON object")
        if payload.get("success") is False:
            raise NYOpenLegError(f"OpenLeg reported failure for {path}: {payload.get('message')}")
        return payload

    def iter_bills(
        self,
        session_year: int,
        *,
        full: bool = True,
        limit: int = 1000,
        max_pages: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        limit = max(1, min(1000, int(limit)))
        offset = 1
        pages = 0
        while True:
            payload = self.get_json(
                f"/bills/{session_year}",
                limit=limit,
                offset=offset,
                full=str(bool(full)).lower(),
            )
            result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
            items = _items(result)
            total = int(payload.get("total") or len(items))
            if not items:
                break
            for item in items:
                if isinstance(item, dict):
                    yield item
            pages += 1
            offset_end = int(payload.get("offsetEnd") or (offset + len(items) - 1))
            if offset_end >= total:
                break
            if max_pages is not None and pages >= max_pages:
                break
            offset = offset_end + 1
            time.sleep(0.2)


def build_ny_bill_records(
    client: NYOpenLegClient,
    session_year: int,
    *,
    limit: int = 1000,
    max_pages: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    fetched_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records: List[Dict[str, Any]] = []
    counters: Dict[str, int] = {
        "bills_seen": 0,
        "skipped_malformed_bill": 0,
        "has_actions": 0,
        "has_votes": 0,
        "has_sponsor": 0,
        "has_summary": 0,
        "committee_agenda_refs": 0,
    }

    for item in client.iter_bills(session_year, full=True, limit=limit, max_pages=max_pages):
        counters["bills_seen"] += 1
        record, row_counters = bill_to_record(item, fetched_at)
        if not record["bill"]:
            counters["skipped_malformed_bill"] += 1
            continue
        for key, value in row_counters.items():
            counters[key] = counters.get(key, 0) + value
        records.append(record)

    if not records:
        raise NYOpenLegError("OpenLeg bill universe came back empty - refusing to overwrite")

    completeness = {
        "state": "NY",
        "source": "NY OpenLegislation",
        "session_year": session_year,
        "records_written": len(records),
        "bills_seen": counters["bills_seen"],
        "skipped_malformed_bill": counters["skipped_malformed_bill"],
        "has_actions": counters["has_actions"],
        "has_actions_rate": round(counters["has_actions"] / len(records), 4),
        "has_votes": counters["has_votes"],
        "has_votes_rate": round(counters["has_votes"] / len(records), 4),
        "patron_present": counters["has_sponsor"],
        "patron_missing": len(records) - counters["has_sponsor"],
        "summary_present": counters["has_summary"],
        "committee_agenda_refs": counters["committee_agenda_refs"],
        "outcome_sources": {
            key.replace("outcome_source_", ""): value
            for key, value in sorted(counters.items())
            if key.startswith("outcome_source_")
        },
        "calendar_scope_note": (
            "OpenLeg bill records include committeeAgendas references, but this engine does not yet "
            "claim full NY meeting coverage. Official OpenLeg docs describe Senate calendar/committee "
            "coverage and state Assembly calendar/committee data is not currently sent to OpenLeg."
        ),
        "checked_at_utc": fetched_at,
    }
    return records, completeness


def _spreadsheet_id() -> str:
    sheet_id = os.environ.get("NY_SPREADSHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError(
            "NY_SPREADSHEET_ID not set. Refusing to write New York output without an explicit "
            "NY workbook/sheet target."
        )
    return sheet_id


def runtime_requirements(*, write: bool) -> List[Dict[str, str]]:
    """Return missing/ready runtime inputs without making network calls."""
    checks = [
        {
            "name": "NY_OPENLEG_API_KEY",
            "required_for": "fetch/dry-run/write",
            "status": "ok" if os.environ.get("NY_OPENLEG_API_KEY", "").strip() else "missing",
            "how_to_get": "Create a free New York OpenLegislation API key and set this env var.",
        },
    ]
    if write:
        checks.extend([
            {
                "name": "NY_SPREADSHEET_ID",
                "required_for": "write",
                "status": "ok" if os.environ.get("NY_SPREADSHEET_ID", "").strip() else "missing",
                "how_to_get": "Create/choose the New York Google Sheet and set its spreadsheet ID.",
            },
            {
                "name": "GCP_CREDENTIALS",
                "required_for": "write",
                "status": "ok" if os.environ.get("GCP_CREDENTIALS", "").strip() else "missing",
                "how_to_get": "Use the same service-account JSON pattern as the Virginia workers, shared with the NY sheet.",
            },
        ])
    return checks


def print_runtime_requirements(*, write: bool) -> bool:
    checks = runtime_requirements(write=write)
    print(json.dumps({"write": write, "requirements": checks}, indent=2))
    return all(c["status"] == "ok" for c in checks)


def write_ny_bill_tracker(records: List[Dict[str, Any]], completeness: Dict[str, Any]) -> None:
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GCP_CREDENTIALS not set")
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    ))
    sheet = gc.open_by_key(_spreadsheet_id())

    header = ["Bill", "Title", "Status (LIS)", "Outcome", "Patron", "Patron ID", "Chamber",
              "Crossed Over", "Last Committee", "Referrals", "Last Action", "Latest Vote (JSON)",
              "Upcoming (JSON)", "History (JSON)", "Data As Of (UTC)", "Source"]
    rows = [header] + [[
        r["bill"], r["title"], r["status_lis"], r["outcome"], r["patron"], r["patron_id"],
        r["chamber"], "yes" if r["crossed_over"] else "no", r["last_committee"],
        r["referral_count"], r["last_action_date"],
        json.dumps(r["latest_vote"], ensure_ascii=False),
        json.dumps(r["upcoming"], ensure_ascii=False),
        json.dumps(r["history"], ensure_ascii=False),
        r["data_as_of_utc"], r["source"],
    ] for r in records]
    completeness_cell, need_rows, need_cols = "R1", len(rows) + 50, 18

    try:
        ws = sheet.worksheet(NY_BILL_TRACKER_TAB)
        if ws.row_count < need_rows or ws.col_count < need_cols:
            ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=NY_BILL_TRACKER_TAB, rows=need_rows, cols=need_cols)

    ws.clear()
    ws.batch_update([
        {"range": "A1", "values": rows},
        {"range": completeness_cell, "values": [[json.dumps(completeness, ensure_ascii=False)]]},
    ])


def run_ny_bill_tracker(*, write: bool = True) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    session_year = int(os.environ.get("NY_OPENLEG_SESSION_YEAR", "2025"))
    limit = int(os.environ.get("NY_OPENLEG_LIMIT", "1000"))
    raw_max_pages = os.environ.get("NY_OPENLEG_MAX_PAGES", "").strip()
    max_pages = int(raw_max_pages) if raw_max_pages else None
    client = NYOpenLegClient(api_key=os.environ.get("NY_OPENLEG_API_KEY", ""))
    records, completeness = build_ny_bill_records(
        client,
        session_year,
        limit=limit,
        max_pages=max_pages,
    )
    if write:
        write_ny_bill_tracker(records, completeness)
    print(
        f"NY_Bill_Tracker built: {len(records)} bills for {session_year}; "
        f"{completeness['patron_present']} with sponsor; "
        f"{completeness['has_actions']} with action history."
    )
    return records, completeness


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the New York bill tracker engine.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch/build records but do not write Google Sheets.")
    parser.add_argument("--check-config", action="store_true", help="Print required NY runtime inputs and exit.")
    args = parser.parse_args()
    if args.check_config:
        ok = print_runtime_requirements(write=not args.dry_run)
        raise SystemExit(0 if ok else 1)
    try:
        records, completeness = run_ny_bill_tracker(write=not args.dry_run)
        if args.dry_run:
            print(json.dumps({
                "sample": records[:3],
                "completeness": completeness,
            }, indent=2, ensure_ascii=False))
    except Exception as err:
        _alert("CRITICAL", "API_FAILURE", f"NY bill tracker cycle failed: {type(err).__name__}: {err}")
        raise


if __name__ == "__main__":
    main()
