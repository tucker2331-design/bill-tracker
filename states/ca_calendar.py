"""California calendar — committee hearings and floor sessions, written in the layout the Calendar screen already reads
(Sheet1: Date, Time, SortTime, Status, Committee, Bill, Outcome, AgendaOrder, Source, Origin, DiagnosticHint,
LegEventRoute, RefidClass, ScheduleClass, TimeClass, AgendaURL, MeetingURL; freshness at AA1) — the same layout as
Pennsylvania's (states/pa_calendar.SHEET1_HEADER, shared).

Every value comes from the daily pubinfo export the intake already downloaded — no new request:

  * MEETING SLOTS — COMMITTEE_AGENDA_TBL: one row per committee meeting or floor session (code, date, the source's own
    time text, room). Future and past. Floor rows (AFLOOR / SFLOOR) carry a closed set of descriptions, matched
    EXACTLY in FLOOR_KIND (a floor session, a check-in session, a recess); an unknown description is COUNTED
    (`calendar_floor_desc_unclassified`, Health limit 0) and shown as the source wrote it. Recesses are not meetings:
    counted, not drawn.
  * WHICH BILLS — COMMITTEE_HEARING_TBL (bill x committee code x date): joined to its slot on (code, date) — a
    structural key, measured 923 of 923 hearing days joined on 2025-26. A committee slot with no bills is written as
    "no bills listed" (informational and budget hearings), never an unexplained empty card. Floor bills are the bills
    VOTED on that floor that day (BILL_SUMMARY_VOTE_TBL at AFLOOR/SFLOOR) — future floor agendas are not listed.
  * WHAT HAPPENED — BILL_SUMMARY_VOTE_TBL: a vote at the same location on the same date is the row's Outcome — the
    motion's own text (BILL_MOTION_TBL) + the source's result + the tally, verbatim. No vote = no outcome (never one
    inferred).
  * TIMES — displayed exactly as the source wrote them; `ca_committees.sort_time` only orders the day. A blank time is
    written "Time TBA" and counted (`calendar_time_blank`).
Bills outside the site's universe are counted, never silently dropped: an extraordinary-session bill
(`calendar_bills_extraordinary_session` — those sessions are not on the site yet, see docs/knowledge/ca_pubinfo.md)
and an unknown regular-session id (`calendar_agenda_bills_unmatched`).
"""
from __future__ import annotations

import collections
from typing import Any, Counter, Dict, List, Optional, Tuple

from .ca_committees import CONFERENCE_VOTE, FLOOR_HOUSE, Committees, agenda_index, sort_time
from .ca_pubinfo import Export, bill_id_parts
from .pa_calendar import SHEET1_HEADER

ORIGIN_MEETING, ORIGIN_FLOOR = "ca_pubinfo_agenda", "ca_pubinfo_floor"
SOURCE = "California pubinfo export"
TIME_TBA = "Time TBA"     # the site's honest marker when the source lists a meeting with no time (counted)
# Floor-row descriptions (COMMITTEE_AGENDA_TBL.COMMITTEE_DESC for AFLOOR/SFLOOR) — measured, 2025-26.
FLOOR_KIND = {
    "Assembly Floor Session": "session", "Senate Floor Session": "session",
    "Asm. Check-in Session": "checkin", "Sen. Check-in Session": "checkin",
    "Assembly Recess": "recess", "Senate Interim Recess": "recess", "Senate Summer Recess": "recess",
    "Senate Spring Recess": "recess",
}


def _row(**kw) -> List[str]:
    return [str(kw.get(k, "")) for k in SHEET1_HEADER]


def _outcome(v: dict, motions: Dict[str, str]) -> str:
    return " ".join(f"{motions.get(v['MOTION_ID'], '')} {v['VOTE_RESULT']} {v['AYES']}-{v['NOES']}".split())


def build_calendar(ex: Export, extras: dict) -> Tuple[List[List[str]], dict]:
    coms: Committees = extras["committees"]
    bill_name: Dict[str, str] = extras["bill_name"]
    since: str = extras["session_start"]
    if not since:
        raise ValueError("CA calendar: the universe has no dated action — refusing to guess the session (fail closed)")
    session_prefix = next(iter(bill_name), "")[:8]      # '20252026' — every universe id starts with it
    stats: Counter[str] = collections.Counter()
    samples: Dict[str, List[str]] = collections.defaultdict(list)
    loc_type = {r["LOCATION_CODE"]: r["LOCATION_TYPE"] for r in ex.rows("LOCATION_CODE_TBL")
                if r["SESSION_YEAR"] == session_prefix}
    for code, t in loc_type.items():
        if t == "V" and code not in FLOOR_HOUSE and code != CONFERENCE_VOTE:
            stats["calendar_floor_code_unknown"] += 1
            samples["calendar_floor_code_unknown_sample"].append(code)
    slots, stats["calendar_duplicate_slots_dropped"] = agenda_index(ex.rows("COMMITTEE_AGENDA_TBL"), since)
    motions = {m["MOTION_ID"]: m["MOTION_TEXT"] for m in ex.rows("BILL_MOTION_TBL")}
    votes: Dict[Tuple[str, str, str], dict] = {}
    floor_votes: Dict[Tuple[str, str], Dict[str, dict]] = collections.defaultdict(dict)
    for v in ex.rows("BILL_SUMMARY_VOTE_TBL"):
        d = (v["VOTE_DATE_TIME"] or "")[:10]
        if not v["BILL_ID"].startswith(session_prefix) or d < since:
            continue
        key = (v["BILL_ID"], v["LOCATION_CODE"], d)
        if key not in votes or int(v["VOTE_DATE_SEQ"] or 0) >= int(votes[key]["VOTE_DATE_SEQ"] or 0):
            votes[key] = v                                    # the day's LAST vote at that place is the outcome
        if v["LOCATION_CODE"] in FLOOR_HOUSE:
            floor_votes[(v["LOCATION_CODE"], d)][v["BILL_ID"]] = votes[key]
    hearing_bills: Dict[Tuple[str, str], List[str]] = collections.defaultdict(list)
    for h in ex.rows("COMMITTEE_HEARING_TBL"):
        d = (h["HEARING_DATE"] or "")[:10]
        if h["BILL_ID"].startswith(session_prefix) and d >= since and h["BILL_ID"] not in hearing_bills[(h["LOCATION_CODE"], d)]:
            hearing_bills[(h["LOCATION_CODE"], d)].append(h["BILL_ID"])

    def bill_label(bid: str) -> str:
        if bid in bill_name:
            return bill_name[bid]
        parts = bill_id_parts(bid)
        if parts is not None and parts[0][-1] != "0":
            stats["calendar_bills_extraordinary_session"] += 1
            return f"{parts[1]}{parts[2]} (Extraordinary Session {parts[0][-1]})"
        stats["calendar_agenda_bills_unmatched"] += 1
        return bid

    def time_of(raw: str) -> Tuple[str, str]:
        if not raw:
            stats["calendar_time_blank"] += 1
            return TIME_TBA, ""
        st = sort_time(raw)
        if not st:
            stats["calendar_time_relative"] += 1        # the source's own words ("Upon Call of the Chair"), shown as is
        return raw, st

    rows: List[List[str]] = []
    for (code, d), day_slots in sorted(slots.items()):
        if code in FLOOR_HOUSE:
            house = FLOOR_HOUSE[code]
            kinds = [(s, FLOOR_KIND.get(s["desc"])) for s in day_slots]
            for s, k in kinds:
                if k is None:
                    stats["calendar_floor_desc_unclassified"] += 1
                    samples["calendar_floor_desc_unclassified_sample"].append(s["desc"])
                elif k == "recess":
                    stats["calendar_recess_rows"] += 1
            meetings = [(s, k) for s, k in kinds if k != "recess"]
            if len(meetings) > 1:
                stats["calendar_two_slots_same_day"] += 1
            day_votes = floor_votes.pop((code, d), {})
            for i, (s, k) in enumerate(meetings):
                name = (f"{house} Convenes" if k == "session" else f"{house} Convenes (check-in session)" if k == "checkin"
                        else s["desc"] if s["desc"].startswith(house) else f"{house}: {s['desc']}")
                t, st = time_of(s["time"])
                stats["calendar_floor_sessions" if k == "session" else "calendar_checkin_sessions"] += 1
                base = dict(Date=d, Time=t, SortTime=st, Committee=name, Source=SOURCE, Origin=ORIGIN_FLOOR,
                            ScheduleClass="floor")
                # the day's floor votes ride on the day's first floor meeting (a session before a check-in)
                these = day_votes if i == 0 else {}
                if not these:
                    rows.append(_row(**base, DiagnosticHint="no_bills_listed"))
                for n, (bid, v) in enumerate(sorted(these.items(), key=lambda kv: int(kv[1]["VOTE_DATE_SEQ"] or 0)), 1):
                    stats["calendar_bill_rows_with_vote"] += 1
                    rows.append(_row(**base, Bill=bill_label(bid), Outcome=_outcome(v, motions), AgendaOrder=n,
                                     LegEventRoute="meeting"))
            continue
        if loc_type.get(code) != "B" and code[:2] not in ("CX", "CS"):
            stats["calendar_slot_code_unknown"] += 1
            samples["calendar_slot_code_unknown_sample"].append(code)
        if len(day_slots) > 1:
            stats["calendar_two_slots_same_day"] += 1
        t, st = time_of(" · ".join(dict.fromkeys(s["time"] for s in day_slots if s["time"])))
        stats["calendar_meetings"] += 1
        base = dict(Date=d, Time=t, SortTime=st, Committee=coms.label(code), Source=SOURCE, Origin=ORIGIN_MEETING,
                    ScheduleClass="committee")
        bids = hearing_bills.pop((code, d), [])
        if not bids:
            stats["calendar_meetings_without_bills"] += 1
            rows.append(_row(**base, DiagnosticHint="no_bills_listed"))
        for n, bid in enumerate(bids, 1):
            vote: Optional[dict] = votes.get((bid, code, d))
            if vote is not None:
                stats["calendar_bill_rows_with_vote"] += 1
            rows.append(_row(**base, Bill=bill_label(bid), Outcome=_outcome(vote, motions) if vote else "",
                             AgendaOrder=n, LegEventRoute="meeting"))
    # hearings / floor votes on a day the agenda lists no slot for: still written (never dropped), time unknown
    for (code, d), bids in sorted(hearing_bills.items()):
        stats["calendar_hearings_without_agenda"] += 1
        t, st = time_of("")
        for n, bid in enumerate(bids, 1):
            late: Optional[dict] = votes.get((bid, code, d))
            rows.append(_row(Date=d, Time=t, SortTime=st, Committee=coms.label(code), Bill=bill_label(bid),
                             Outcome=_outcome(late, motions) if late else "", AgendaOrder=n, Source=SOURCE,
                             Origin=ORIGIN_MEETING, ScheduleClass="committee", LegEventRoute="meeting"))
    for (code, d), these in sorted(floor_votes.items()):
        stats["calendar_floor_votes_without_session"] += 1
        t, st = time_of("")
        for n, (bid, v) in enumerate(sorted(these.items(), key=lambda kv: int(kv[1]["VOTE_DATE_SEQ"] or 0)), 1):
            rows.append(_row(Date=d, Time=t, SortTime=st, Committee=f"{FLOOR_HOUSE[code]} Convenes", Bill=bill_label(bid),
                             Outcome=_outcome(v, motions), AgendaOrder=n, Source=SOURCE, Origin=ORIGIN_FLOOR,
                             ScheduleClass="floor", LegEventRoute="meeting"))
    rows.sort(key=lambda r: (r[0], r[2] or "99", r[4], r[7].zfill(4)))
    out: Dict[str, Any] = {k: stats.get(k, 0) for k in (
        "calendar_meetings", "calendar_meetings_without_bills", "calendar_floor_sessions", "calendar_checkin_sessions",
        "calendar_recess_rows", "calendar_floor_desc_unclassified", "calendar_floor_code_unknown",
        "calendar_slot_code_unknown", "calendar_hearings_without_agenda", "calendar_floor_votes_without_session",
        "calendar_two_slots_same_day", "calendar_duplicate_slots_dropped", "calendar_time_blank",
        "calendar_time_relative", "calendar_bills_extraordinary_session", "calendar_agenda_bills_unmatched",
        "calendar_bill_rows_with_vote")}
    out.update({k: v[:10] for k, v in samples.items()})
    out.update({"calendar_rows": len(rows), "calendar_since": since,
                "committee_house_unknown": coms.stats["committee_house_unknown"]})
    return [SHEET1_HEADER] + rows, out
