"""Pennsylvania intake adapter — LDPC's Bill History export (+ committee-schedule RSS) -> the bill contract.

Produces one record per bill with the SAME keys bill_tracker.py writes for Virginia (bill, title, status_lis,
outcome, outcome_origin, patron, patron_id, chamber, crossed_over, floor_house, floor_senate, last_committee,
referral_count, latest_vote, upcoming, last_action_date, history, data_as_of_utc, source, legislation_class,
copatrons) plus `stage` (PA's own stage list, states/pa.py). `status_lis` keeps its contract name and holds the
source's own words for the latest action.

STRUCTURAL, NOT TEXT (Standard #3). Every routing decision reads a FIELD of the export, never the prose:
  * each <action> carries its own <verb> (a closed, LDPC-generated vocabulary — 59 values on 2025_0), <committee>,
    @actionChamber (H / S / E = the Governor), <date>, <rollCallVote> and <printersNumber>;
  * the verb is matched EXACTLY against VERB_CLASS below (consuming the source's controlled vocabulary — the same
    doctrine as VA's status flags); a verb not in the map is COUNTED (`verbs_unclassified`) and never moves a bill.
  * <fullAction> (the prose line) is displayed verbatim in `history`, never parsed.
Schema, counts and samples: docs/knowledge/pa_bill_history_xml.md (measured on the real 2025_0 export).

NO PREDICTIONS. Outcomes come only from recorded events: a bill is never declared dead from silence inside an open
two-year session, and no veto verb exists in the 2025_0 export, so none is mapped — the first one will surface as an
unclassified verb, not as a guess.
"""
from __future__ import annotations

import calendar
import datetime
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from .pa import PA

# PA's verb vocabulary (exact <verb> values on the 2025_0 export, 2026-10-31) -> structural class.
VERB_CLASS: Dict[str, str] = {
    # into a committee (the <committee> field names it)
    "Referred to": "referral", "Re-referred to": "referral", "Re-committed to": "referral",
    # out of a committee
    "Reported as committed,": "reported", "Re-reported as committed,": "reported",
    "Reported as amended,": "reported", "Re-reported as amended,": "reported",
    "Reported with request to re-refer to": "reported", "Re-reported with request to re-refer to": "reported",
    "Reported as amended with Prior Printer's No.": "reported",
    "Re-reported on concurrence, as committed,": "reported", "Re-reported on concurrence, as amended,": "reported",
    "Amended in House Committee on": "committee_amended", "Amended in Senate Committee on": "committee_amended",
    # floor consideration in the acting chamber
    "First consideration,": "floor", "Second consideration,": "floor", "Second consideration, with amendments,": "floor",
    "Third consideration,": "floor", "Third consideration, with amendments,": "floor",
    "Amended on second consideration,": "floor", "Amended on third consideration,": "floor", "Amended,": "floor",
    "Laid on the table,": "floor", "Removed from table,": "floor",
    "Laid on the table (Pursuant to House Rule 71),": "floor", "Laid on the table (Pursuant to Senate Rule 9),": "floor",
    "Vote on final passage reconsidered,": "floor",
    "Vote by which this bill was defeated on final passage, reconsidered,": "floor",
    "Vote by which this resolution was adopted, reconsidered,": "floor",
    "Resolution to discharge committee from further consideration of this bill presented,": "floor",
    "Resolution to discharge committee from further consideration of this bill dropped from calendar,": "floor",
    "Motion to revert to Prior Printer's No.": "floor",
    "Third consideration and final passage,": "passed", "Final passage,": "passed",
    "Third consideration and defeated on final passage,": "defeated",
    # a resolution's end in one chamber
    "Adopted,": "adopted", "Introduced and adopted,": "adopted",
    # arrival in the second chamber
    "In the Senate": "arrived", "In the House": "arrived",
    # concurrence (origin chamber agrees to the other chamber's amendments)
    "House concurred in Senate amendments,": "concurred", "Senate concurred in House amendments,": "concurred",
    "Senate concurred in House amendments, as amended by the Senate,": "concurred",
    "House concurred in Senate amendments to House amendments,": "concurred",
    "Senate concurred in House amendments to Senate amendments,": "concurred",
    "House concurred in Senate amendments, as amended by the House,": "concurred",
    "House concurred in Senate amendments to House amendments, as amended by the House,": "concurred",
    "Senate concurred in House amendments to Senate amendments, as amended by the House,": "concurred",
    # enrolment and the Governor
    "Signed in House,": "signed_in_chamber", "Signed in Senate,": "signed_in_chamber",
    "Presented to the Governor,": "to_governor", "Approved by the Governor,": "approved", "Act No.": "act",
    # record-keeping (no movement)
    "Introduced,": "introduced", "INTRODUCED AS NONCONTROVERSIAL RESOLUTION UNDER RULE 35,": "introduced",
    "(Remarks see House Journal Page": "record", "(Remarks see Senate Journal Page": "record",
    "Corrective Reprint, Printer's No.": "record", "Transmitted as directed,": "record",
    # PA's OWN label for an action it did not classify — counted separately, never moves a bill
    "Undefined Action": "undefined",
}
_CHAMBER = PA.chambers   # {"H": "House", "S": "Senate"}; "E" (executive) is the Governor, not a chamber
# Stage order. A bill's stage only ever moves FORWARD: after both floors pass, an amended bill goes back to the
# origin chamber's Rules committee for a concurrence vote — measured on 2025_0 (HB257, HB559, HB1042, HB1667) —
# and that referral must not read as a fresh first-committee stage. Adopted resolutions end at `adopted`.
STAGE_RANK = {s.id: i for i, s in enumerate(PA.stages)}


def _advance(cur: str, new: str) -> str:
    return new if STAGE_RANK[new] > STAGE_RANK[cur] else cur


_RC_RE = re.compile(r"^\(?\s*(\d+)\s*-\s*(\d+)\s*\)?$")   # PA's own tally wire format "(195-8)"
_BILL_RE = re.compile(r"^([HS])([BR])0*(\d+)$")            # parss:Bills entries, e.g. "HB2639"


_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})$")


def _iso(d: str) -> str:
    """PA's MM/DD/YY (export) or MM/DD/YYYY (RSS) -> YYYY-MM-DD; "" when unreadable — the CALLER counts it
    (action_dates_unreadable / schedule_dates_unreadable). Validated by shape + calendar, so no exception is
    swallowed (house rule bare-except-pass). Two-digit years follow strptime's %y pivot: 69-99 -> 19xx, else 20xx
    (the export reaches back to 1969)."""
    m = _DATE_RE.match(d.strip())
    if not m:
        return ""
    mo, dy, yr = int(m.group(1)), int(m.group(2)), m.group(3)
    year = int(yr) if len(yr) == 4 else (1900 + int(yr) if int(yr) >= 69 else 2000 + int(yr))
    if not (1 <= mo <= 12 and 1 <= dy <= calendar.monthrange(year, mo)[1]):
        return ""
    return f"{year:04d}-{mo:02d}-{dy:02d}"


def bill_key(body: str, typ: str, number: str) -> str:
    """("H", "B", "0017") -> "HB17" — the same clean-id shape as VA's ("HB1")."""
    return f"{body}{typ}{int(number)}"


def sessions_from_index(html: str) -> List[str]:
    """Session codes the data page itself lists (structural: the export link's own query value), oldest first."""
    found = set(re.findall(r"documentType=BillHistoryData&(?:amp;)?session=(\d{4}_\d)", html))
    return sorted(found)


def current_regular_session(html: str) -> str:
    """The newest REGULAR session (index 0) listed on the data page; special sessions are `_1`, `_2`."""
    regular = [s for s in sessions_from_index(html) if s.endswith("_0")]
    if not regular:
        raise ValueError("PA data page lists no regular session export — the page changed shape; halting")
    return regular[-1]


def read_export(blob: bytes) -> ET.Element:
    """The export arrives as a ZIP (content-type says XML) holding one XML file."""
    if blob[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".xml")]
            if len(names) != 1:
                raise ValueError(f"PA export ZIP should hold exactly one XML, found {names}")
            blob = z.read(names[0])
    return ET.fromstring(blob)


def parse_schedule(rss: bytes, chamber: str) -> List[dict]:
    """Committee-schedule RSS -> meetings. Every field is a parss: element (no prose read)."""
    ns = "{https://www.legis.state.pa.us/RSS}"
    out = []
    for it in ET.fromstring(rss).iter("item"):
        g = lambda k: (it.findtext(ns + k) or "").strip()   # noqa: E731
        bills = [b.strip() for b in g("Bills").split(",") if b.strip()]
        out.append({"chamber": chamber, "date": _iso(g("MeetingDate")), "date_raw": g("MeetingDate"),
                    "time": g("MeetingTime"), "committee": g("Committee"), "location": g("Location"),
                    "bills": bills})
    return out


def build_records(export: ET.Element, meetings: List[dict], today: datetime.date,
                  now_utc: str) -> Tuple[List[dict], dict]:
    session_el = export.find("session")
    if session_el is None:
        raise ValueError("PA export has no <session> element — refusing to build (fail closed)")
    declared = int(export.get("totalDocuments", "-1"))
    verbs_unclassified: Dict[str, int] = {}
    undefined_actions = actions_total = bad_dates = 0
    records: List[Dict[str, Any]] = []
    for b in session_el.iter("bill"):
        body, typ, num = ((b.findtext(k) or "").strip() for k in ("body", "type", "number"))
        bill = bill_key(body, typ, num)
        origin = _CHAMBER.get(body, "")
        is_resolution = typ == "R"
        history, latest_vote = [], {"tally": "", "location": "", "date": ""}
        chamber, crossed, last_committee = origin, False, ""
        referred: List[str] = []
        floor = {"House": "", "Senate": ""}
        outcome, stage = "in_progress", "introduced"
        status = {"action": "", "date": ""}   # the latest action that is not journal bookkeeping
        for a in b.iter("action"):
            actions_total += 1
            verb = (a.findtext("verb") or "").strip()
            cls = VERB_CLASS.get(verb)
            ac = (a.get("actionChamber") or "").strip()
            act_ch = _CHAMBER.get(ac, "")
            com = (a.findtext("committee") or "").strip()
            date = _iso(a.findtext("date") or "")
            if not date:
                bad_dates += 1
            row = {"action": (a.findtext("fullAction") or "").strip(), "date": date}
            history.append(row)
            if cls != "record":
                # "(Remarks see … Journal Page)" rows are filed after the fact (their <date> is the filing date,
                # e.g. 2026-05-13 for a 2025-09-30 vote), so they are history but never the status.
                status = row
            rc = _RC_RE.match((a.findtext("rollCallVote") or "").strip())
            if rc:
                latest_vote = {"tally": f"{rc.group(1)}-{rc.group(2)}",
                               "location": f"{act_ch} {com}".strip() if com else "Floor", "date": date}
            if cls is None:
                verbs_unclassified[verb] = verbs_unclassified.get(verb, 0) + 1
                continue   # counted above; an unknown verb never moves a bill (no guessing)
            if cls == "undefined":
                undefined_actions += 1
                continue   # PA's own "Undefined Action" label — counted, displayed in history, never routed
            if act_ch:
                chamber = act_ch
                if act_ch != origin:
                    crossed = True
            second = bool(act_ch) and act_ch != origin
            if cls == "referral" and com:
                last_committee = f"{act_ch} {com}".strip()
                if not referred or referred[-1] != last_committee:
                    referred.append(last_committee)
                stage = _advance(stage, "committee2" if second else "committee1")
            elif cls in ("reported", "committee_amended") and com:
                last_committee = f"{act_ch} {com}".strip()
                if cls == "reported":
                    stage = _advance(stage, "floor2" if second else "floor1")
            elif cls == "floor" and act_ch:
                stage = _advance(stage, "floor2" if second else "floor1")
            elif cls == "passed" and act_ch:
                floor[act_ch] = "passed"
                stage = _advance(stage, "floor2" if second else "floor1")
            elif cls == "defeated" and act_ch:
                if floor[act_ch] != "passed":
                    floor[act_ch] = "defeated"
            elif cls == "adopted" and act_ch:
                floor[act_ch] = "passed"
                if is_resolution:
                    outcome, stage = "adopted", _advance(stage, "adopted")
            elif cls == "arrived" and act_ch:
                # arriving in the SECOND chamber starts its committee stage; arriving BACK in the origin chamber is
                # the concurrence round.
                stage = _advance(stage, "committee2" if second else "concurrence")
            elif cls in ("concurred", "signed_in_chamber"):
                stage = _advance(stage, "concurrence")
            elif cls == "to_governor":
                stage, outcome = _advance(stage, "governor"), "awaiting_governor"
            elif cls in ("approved", "act"):
                stage, outcome = _advance(stage, "law"), "signed"
        # Both floors passed = the bill is past floor2 even before any concurrence/enrolment action is recorded.
        if not is_resolution and floor["House"] == "passed" and floor["Senate"] == "passed":
            stage = _advance(stage, "concurrence")
        type_el = b.find("type")
        legislation_class = type_el.get("description", "") if type_el is not None else ""
        sponsors = sorted(b.iter("sponsor"), key=lambda s: s.get("sequenceNumber", ""))
        chief = sponsors[0] if sponsors else None
        last_action = status
        records.append({
            "bill": bill,
            "title": (b.findtext("shortTitle") or "").strip(),
            "status_lis": last_action["action"],                 # the source's own words (contract key name kept)
            "stage": stage,
            "outcome": outcome,
            "outcome_origin": "structural_verb",                 # every outcome comes from a <verb> field
            "patron": (chief.text or "").strip() if chief is not None else "",
            "patron_id": "",                                     # the export carries no member id
            "chamber": chamber,
            "crossed_over": crossed,                             # reached the second chamber (PA has no deadline)
            "floor_house": floor["House"],
            "floor_senate": floor["Senate"],
            "last_committee": last_committee,
            "referral_count": len(referred),
            "latest_vote": latest_vote,
            "upcoming": [],                                      # filled from the schedule join below
            "last_action_date": last_action["date"],
            "history": history,
            "data_as_of_utc": now_utc,
            "source": PA.source_name,
            "legislation_class": legislation_class,
            "copatrons": [{"name": (s.text or "").strip(), "member_id": "", "role": "Cosponsor",
                           "party": s.get("party", ""), "district": s.get("districtNumber", "")}
                          for s in sponsors[1:]],
        })
    # NEXT MEETING — joined ONLY on the schedule's structural agenda field (parss:Bills). A meeting of the bill's
    # committee with no listed bills is NOT evidence the bill is up, so committee-name matching is never used.
    by_bill = {r["bill"]: r for r in records}
    sched_with_bills = sched_unmatched = sched_bad_dates = 0
    for m in meetings:
        if not m["date"]:
            sched_bad_dates += 1
            continue   # counted; an undatable meeting is never placed on a bill
        if m["bills"]:
            sched_with_bills += 1
        for ref in m["bills"]:
            mm = _BILL_RE.match(ref.upper())
            r = by_bill.get(f"{mm.group(1)}{mm.group(2)}{int(mm.group(3))}") if mm else None
            if r is None:
                sched_unmatched += 1
                continue   # counted: an agenda entry that names no bill in this export
            if m["date"] >= today.isoformat():
                r["upcoming"].append({"date": m["date"], "committee": m["committee"], "time": m["time"]})
    for r in records:
        r["upcoming"].sort(key=lambda x: x["date"])
    completeness = {
        "state": PA.code,
        "session_code": f"{session_el.get('year')}_{session_el.get('session')}",
        "export_date": export.get("exportDate", ""),
        "universe_declared": declared,                  # the export's own totalDocuments …
        "records_written": len(records),                # … must equal what we parsed
        "actions_total": actions_total,
        "verbs_unclassified": sum(verbs_unclassified.values()),
        "verbs_unclassified_sample": sorted(verbs_unclassified)[:10],
        "undefined_actions": undefined_actions,          # PA's own "Undefined Action" label
        "action_dates_unreadable": bad_dates,
        "schedule_meetings": len(meetings),
        "schedule_meetings_with_bills": sched_with_bills,
        "schedule_bill_refs_unmatched": sched_unmatched,
        "schedule_dates_unreadable": sched_bad_dates,
        "checked_at_utc": now_utc,
    }
    return records, completeness


def run_intake(fetcher, session: Optional[str], today: datetime.date, now_utc: str):
    """Fetch (politely) and build. `session=None` discovers the current regular session from the data page."""
    if session is None:
        session = current_regular_session(fetcher.get(PA.urls["data_index"]).decode("utf-8", "replace"))
    export = read_export(fetcher.get(PA.urls["bill_history"].format(session=session)))
    meetings = []
    for ch in ("house", "senate"):
        meetings += parse_schedule(fetcher.get(PA.urls["committee_schedule"].format(chamber=ch)), ch)
    records, comp = build_records(export, meetings, today, now_utc)
    if comp["records_written"] != comp["universe_declared"]:
        raise ValueError(f"PA export declares {comp['universe_declared']} documents but {comp['records_written']} "
                         f"parsed — refusing to publish a partial universe (fail closed)")
    return records, comp
