"""Pennsylvania calendar — committee meetings and session days, written in the layout the Calendar screen already reads
(the calendar subsystem's Sheet1: Date, Time, SortTime, Status, Committee, Bill, Outcome, AgendaOrder, Source, Origin,
DiagnosticHint, LegEventRoute, RefidClass, ScheduleClass, TimeClass, AgendaURL, MeetingURL; freshness at AA1).

A SMALL job of its own (owner 2026-11-01: do not split calendar_worker.py). Two sources, both already fetched by the
PA intake under the bulk-feed rules — no new request:

  * COMMITTEE MEETINGS — the House/Senate committee-schedule RSS. Every field is a parss: element. A meeting's bills
    come ONLY from its own `Bills` field; an empty field is written as a meeting with no bill rows and the Calendar
    says "no bills listed" (never an unexplained empty card). "Call of Chair" is PA's to-be-announced time and is shown
    as the source says it. The same agency meeting is listed in both chambers' feeds; it is written once.
  * SESSION DAYS (past only) — the Bill History export: a day on which a chamber recorded a floor action (consideration,
    final passage, adoption, concurrence, reconsideration) is a day that chamber sat. Read from `@actionChamber`, the
    `<verb>` class and `<date>` — never from prose. Journal-remarks rows are excluded (their date is a filing date).
    PA publishes no feed of FUTURE session days (checked 2026-11-01: the data page lists none; the session-calendar
    RSS lists the bills for "the next session day" without its date), so future session days are not invented.

Committee display names: a schedule entry "HOUSE APPROPRIATIONS" is shown as "House Appropriations" when it equals a
roster committee's key (states/pa_roster.committee_key, exact); otherwise the source's own text is kept verbatim
(the legislative agencies — IRRC, the Center for Rural Pennsylvania — are not committees and keep their names).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Tuple

from . import pa_adapter as A

SHEET1_HEADER = ["Date", "Time", "SortTime", "Status", "Committee", "Bill", "Outcome", "AgendaOrder", "Source", "Origin",
                 "DiagnosticHint", "LegEventRoute", "RefidClass", "ScheduleClass", "TimeClass", "AgendaURL", "MeetingURL"]
# The verb classes that only happen on a chamber floor (pa_adapter.VERB_CLASS). Referrals, committee reports,
# introductions, the Governor and record-keeping are not floor business.
FLOOR_CLASSES = {"floor", "passed", "defeated", "adopted", "reconsidered", "concurred"}
# Automatic tablings under a chamber rule are dated without a sitting: measured on 2025_0, 13 House "days" carried
# ONLY a Rule 71 tabling, one of them a Sunday (2025-05-04). They are not evidence of a session day.
NOT_A_SITTING = {"Laid on the table (Pursuant to House Rule 71),", "Laid on the table (Pursuant to Senate Rule 9),"}
SESSION_DAY_TIME = "Session day"      # shown in the time slot: the export dates the day, never the hour
ORIGIN_MEETING, ORIGIN_SESSION = "pa_schedule_rss", "pa_export_floor"
_ID = re.compile(r"^([HS][BR])(\d+)$")


def _bill_sort_key(bill: str):
    m = _ID.match(bill)
    return (m.group(1), int(m.group(2))) if m else (bill, 0)


def _sort_time(t: str) -> str:
    """'10:00 AM' -> '10:00'; anything else (Call of Chair) -> '' so the screen sorts it last."""
    m = re.match(r"^(\d{1,2}):(\d{2})\s*([AP])\.?M\.?$", t.strip(), re.I)
    if not m:
        return ""
    h = int(m.group(1)) % 12 + (12 if m.group(3).upper() == "P" else 0)
    return f"{h:02d}:{m.group(2)}"


def _row(**kw) -> List[str]:
    return [str(kw.get(k, "")) for k in SHEET1_HEADER]


def meeting_rows(meetings: Iterable[dict], roster_display: Dict[str, str], bill_ids: set) -> Tuple[List[List[str]], dict]:
    rows: List[List[str]] = []
    stats = {"calendar_meetings": 0, "calendar_meetings_without_bills": 0, "calendar_meetings_duplicate": 0,
             "calendar_meeting_dates_unreadable": 0, "calendar_agenda_bills_unmatched": 0,
             "calendar_meetings_not_a_committee": 0}
    seen = set()
    for m in meetings:
        if not m["date"]:
            stats["calendar_meeting_dates_unreadable"] += 1
            continue   # counted: an undatable meeting cannot be placed on a day
        name = roster_display.get(m["committee"].upper())
        key = (m["date"], name or m["committee"], m["time"])
        if key in seen:
            stats["calendar_meetings_duplicate"] += 1   # the same agency meeting in both chambers' feeds
            continue   # counted: written once
        seen.add(key)
        if name is None:
            stats["calendar_meetings_not_a_committee"] += 1   # an agency, or a committee the roster does not list
            name = m["committee"]
        stats["calendar_meetings"] += 1
        base = dict(Date=m["date"], Time=m["time"], SortTime=_sort_time(m["time"]), Committee=name,
                    Source="PA committee schedule RSS", Origin=ORIGIN_MEETING, ScheduleClass="committee")
        bills = []
        for ref in m["bills"]:
            b = A.normalize_bill_ref(ref)
            if b is None or b not in bill_ids:
                stats["calendar_agenda_bills_unmatched"] += 1   # counted; written as the source spells it
            bills.append(b or ref)
        if not bills:
            stats["calendar_meetings_without_bills"] += 1
            rows.append(_row(**base, DiagnosticHint="no_bills_listed"))
        for i, b in enumerate(bills, 1):
            rows.append(_row(**base, Bill=b, AgendaOrder=i, LegEventRoute="meeting"))
    return rows, stats


def session_day_rows(export: ET.Element) -> Tuple[List[List[str]], dict]:
    """(chamber, date) pairs with floor business, one row per bill acted on that day (its own <fullAction>)."""
    days: Dict[Tuple[str, str], Dict[str, str]] = {}
    session_el = export.find("session")
    if session_el is None:
        raise ValueError("PA export has no <session> element — refusing to build the calendar (fail closed)")
    for b in session_el.iter("bill"):
        bill = A.bill_key(*((b.findtext(k) or "").strip() for k in ("body", "type", "number")))
        for a in b.iter("action"):
            verb = (a.findtext("verb") or "").strip()
            cls = A.VERB_CLASS.get(verb)
            chamber = A.PA.chambers.get((a.get("actionChamber") or "").strip())
            date = A._iso(a.findtext("date") or "")
            if cls not in FLOOR_CLASSES or verb in NOT_A_SITTING or not chamber or not date:
                continue   # not floor business in a chamber (or undatable: counted by the intake's own check)
            days.setdefault((chamber, date), {})[bill] = (a.findtext("fullAction") or "").strip()
    rows = []
    for (chamber, date), bills in sorted(days.items()):
        for i, (bill, action) in enumerate(sorted(bills.items(), key=lambda x: _bill_sort_key(x[0])), 1):
            rows.append(_row(Date=date, Time=SESSION_DAY_TIME, Committee=f"{chamber} Convened", Bill=bill,
                             Outcome=action, AgendaOrder=i, Source="PA Bill History export", Origin=ORIGIN_SESSION,
                             LegEventRoute="meeting", ScheduleClass="floor"))
    return rows, {"calendar_session_days": len(days),
                  "calendar_session_days_house": sum(1 for c, _ in days if c == "House"),
                  "calendar_session_days_senate": sum(1 for c, _ in days if c == "Senate")}


def build_calendar(export: ET.Element, meetings: List[dict], roster: Optional[List[dict]],
                   bill_ids: set) -> Tuple[List[List[str]], dict]:
    # roster committee "House APPROPRIATIONS" (its key) -> display "House Appropriations"
    display = {x["key"].upper(): f"{x['chamber']} {x['committee']}" for x in (roster or [])}
    mrows, mstats = meeting_rows(meetings, display, bill_ids)
    srows, sstats = session_day_rows(export)
    rows = sorted(mrows + srows, key=lambda r: (r[0], r[2] or "99", r[4], r[7].zfill(4)))
    return [SHEET1_HEADER] + rows, {**mstats, **sstats, "calendar_rows": len(rows),
                                    "calendar_roster_used": roster is not None}
