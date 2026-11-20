"""California intake adapter — Legislative Counsel's pubinfo export -> the bill contract.

Same record keys as Virginia and Pennsylvania (bill, title, status_lis, stage, pipeline, outcome, outcome_origin,
patron, patron_id, chamber, crossed_over, floor_house, floor_senate, last_committee, referral_count, latest_vote,
upcoming, last_action_date, history, data_as_of_utc, source, legislation_class, copatrons). The site's House/Senate
columns map to Assembly/Senate (floor_house = Assembly).

STRUCTURAL, NOT TEXT (Standard #3). Every routing decision reads a FIELD of BILL_HISTORY_TBL, never the prose:
  * PRIMARY_LOCATION (Assembly / Senate / Governor / Secretary of State), SECONDARY_LOCATION (Committee / Floor /
    Desk / E&E / Rules), TERNARY_LOCATION (the committee's location code, named via LOCATION_CODE_TBL) and
    END_STATUS (the bill's status after the action — a closed vocabulary, matched EXACTLY in END_CLASS);
  * ACTION_STATUS 'Rescinded' rows are history but never move a bill;
  * an END_STATUS not in END_CLASS is COUNTED (`end_status_unclassified`) and never moves a bill;
  * ACTION (the prose line) is displayed verbatim in `history`, never parsed.
Outcomes come from BILL_TBL fields (chapter number = law; CURRENT_STATUS 'Vetoed'), never inferred from silence.
"""
from __future__ import annotations

import collections
import datetime
from typing import Any, Dict, List, Optional, Tuple

from .ca import CA
from .ca_committees import Committees, agenda_index, slot_time
from .ca_pubinfo import Export, bill_id_parts

# END_STATUS vocabulary -> structural class (exact values; measured on the 2025-26 export, docs/knowledge/ca_pubinfo.md)
END_CLASS: Dict[str, str] = {
    "Pending Referral": "desk", "In Desk Process": "desk",
    "In Committee Process": "committee",
    "In Floor Process": "floor",
    "Passed": "passed",
    "Enrolled": "enrolled",
    "Signed by Governor": "signed", "Chaptered": "chaptered",
    "Vetoed": "vetoed",
    # a recorded end: Art. IV §10(c) / Joint Rules 56, 61, 62 (measured: 1,229 rows on 2025-26) — never inferred
    "Died": "died",
    # a failed vote that can be reconsidered: recorded, does not end the bill
    "Failed": "failed", "Failed Passage in Committee": "committee_failed",
}
# Where each history action happened, for the site's What's new (action_where.py codes), from PRIMARY_LOCATION —
# measured on 2025-26: Assembly 44,035 · Senate 38,192 · Governor 3,904 · Secretary of State 2,668 · blank 32. The
# Secretary of State (chaptering, filing) is not a chamber and the blank rows name none: both are "0" (the source lists
# no chamber). Any other value is "-" and counted (`action_where_unknown`, a Health check).
WHERE_CODE = {"Assembly": "H", "Senate": "S", "Governor": "G", "Secretary of State": "0", "": "0"}
# A blank END_STATUS (32 rows on 2025-26: rescissions, "Plan takes effect", a refused passage) is history only —
# counted as `end_status_blank`, never routed.
PARTY = {"DEM": "D", "REP": "R"}
HOUSES = {"Assembly", "Senate"}
# Measures the Governor never acts on (Joint Rules; Cal. Const. Art. XVIII): concurrent and joint resolutions and
# constitutional amendments are filed with the Secretary of State and given a RESOLUTION chapter number — that number
# means "adopted", never "signed into law" (Codex #274: 414 resolutions + 5 ACAs on 2025-26 carry one).
NO_GOVERNOR = {"ACR", "SCR", "AJR", "SJR", "HR", "SR", "ACA", "SCA"}
# One-house resolutions end on their own house's vote: BILL_TBL CURRENT_STATUS 'Passed' (267 on 2025-26).
ONE_HOUSE = {"HR", "SR"}
# Malformed rows in these tables mean a bill (or one of its actions) is missing from the build: refuse to publish.
# Measured 0 on the full 2025-26 export, so any count is an upstream anomaly, never routine (Codex #274).
UNIVERSE_TABLES = ("BILL_TBL", "BILL_HISTORY_TBL")
# pubinfo names the lower chamber "Assembly"; the contract calls it "House" (states/ca.py CHAMBER_DISPLAY shows it).
TO_CONTRACT = {"Assembly": "House", "Senate": "Senate"}
STAGE_RANK = {s.id: i for i, s in enumerate(CA.stages)}
TYPE_NAME = {"AB": "Assembly Bill", "SB": "Senate Bill", "ACA": "Assembly Constitutional Amendment",
             "SCA": "Senate Constitutional Amendment", "ACR": "Assembly Concurrent Resolution",
             "SCR": "Senate Concurrent Resolution", "AJR": "Assembly Joint Resolution", "SJR": "Senate Joint Resolution",
             "HR": "House Resolution", "SR": "Senate Resolution"}


def _advance(cur: str, new: str) -> str:
    return new if STAGE_RANK[new] > STAGE_RANK[cur] else cur


def _date(v: str) -> str:
    return (v or "")[:10]


def origin_house(measure_type: str) -> str:
    """The pubinfo house name ("Assembly"/"Senate") a measure starts in, from its type's first letter."""
    return {"House": "Assembly", "Senate": "Senate"}[CA.origin_chamber(measure_type)]


def committee_names(ex: Export) -> Dict[str, str]:
    out = {}
    for r in ex.rows("LOCATION_CODE_TBL"):
        out[r["LOCATION_CODE"]] = r["LONG_DESCRIPTION"] or r["DESCRIPTION"] or r["LOCATION_CODE"]
    return out


def current_session(bill_rows) -> Tuple[str, List[str]]:
    """The session the export is about: the NEWEST `SESSION_YEAR` on any bill, plus every year seen (sorted).
    Every export measured so far holds one session (2019, 2021, 2023, 2025 files; checked 2026-11-20), where newest
    and most-common agree. If a file ever carried two (e.g. at the December rollover), the newer session is the live
    one; the old session is over. Pure."""
    years = sorted({str(b.get("SESSION_YEAR", "")) for b in bill_rows if b.get("SESSION_YEAR")})
    return (years[-1] if years else ""), years


def build_records(ex: Export, today: datetime.date, now_utc: str,
                  as_of_utc: Optional[str] = None, extras: Optional[dict] = None) -> Tuple[List[dict], dict]:
    """`now_utc` = when we checked; `as_of_utc` = when the source published the export (the job always passes it;
    the goldens, which have no publication time, stamp records with the check time). `extras`, when given, receives
    what the calendar reuses from this pass: bill_name {BILL_ID: "AB12"}, committee_house {code: Counter(house)},
    session_start (the earliest action date of the universe)."""
    data_as_of = as_of_utc or now_utc
    committee_house: Dict[str, Dict[str, int]] = collections.defaultdict(collections.Counter)
    bill_name: Dict[str, str] = {}
    names = committee_names(ex)
    bills = {r["BILL_ID"]: r for r in ex.rows("BILL_TBL")}
    session, years_seen = current_session(bills.values())
    bills = {k: v for k, v in bills.items() if v["SESSION_YEAR"] == session and v["SESSION_NUM"] == "0"}
    if not bills:
        # Between sessions (2026-11-20 rollover check): the 2025-26 session ends Nov 30 and the 2027-28 session's
        # bills appear only after it convenes (Dec 7, 2026). An export with no regular-session bill is that gap, or
        # an upstream fault; either way nothing is written and the sheet keeps the last published session. Said
        # plainly here instead of failing later on an empty session code in the calendar.
        raise ValueError(f"CA export holds no regular-session bills (session years seen: "
                         f"{', '.join(years_seen) if years_seen else 'none'}) — "
                         f"between sessions or an upstream fault; nothing written, the last published data stands")
    # Measures neither house originates (e.g. GRP, a Governor's Reorganization Plan) are COUNTED, not built: the
    # contract places every bill in a chamber.
    outside = collections.Counter(v["MEASURE_TYPE"] for v in bills.values() if v["MEASURE_TYPE"] not in TYPE_NAME)
    bills = {k: v for k, v in bills.items() if v["MEASURE_TYPE"] in TYPE_NAME}
    hist: Dict[str, List[dict]] = collections.defaultdict(list)
    prefix = f"{session}0"          # current session, regular (SESSION_NUM 0) — the same filter as the universe
    orphans = set()
    for h in ex.rows("BILL_HISTORY_TBL"):
        if h["BILL_ID"] in bills:
            hist[h["BILL_ID"]].append(h)
        elif h["BILL_ID"].startswith(prefix):
            parts = bill_id_parts(h["BILL_ID"])
            if parts is None or parts[1] in TYPE_NAME:   # GRP and other no-house measures are counted elsewhere
                orphans.add(h["BILL_ID"])
    # latest version per bill: subject (title) + authors
    subject = {}
    has_text = set()
    for v in ex.rows("BILL_VERSION_TBL"):
        subject[v["BILL_VERSION_ID"]] = v["SUBJECT"]
        has_text.add(v["BILL_ID"])
    # A history-only id WITH a published version is a real measure missing from BILL_TBL (an anomaly, Health limit 0).
    # One with NO version ever published is a stray history row (2025-26: SB2510-2512, one "Introduced" row each,
    # no text) — counted separately so a permanent upstream stray never holds the Health check red.
    strays = sorted(o for o in orphans if o not in has_text)
    orphans = {o for o in orphans if o in has_text}
    authors: Dict[str, List[dict]] = collections.defaultdict(list)
    latest_ver = {b["LATEST_BILL_VERSION_ID"]: k for k, b in bills.items()}
    for a in ex.rows("BILL_VERSION_AUTHORS_TBL"):
        if a["BILL_VERSION_ID"] in latest_ver:
            authors[latest_ver[a["BILL_VERSION_ID"]]].append(a)
    party = {}
    for lg in ex.rows("LEGISLATOR_TBL"):
        if lg["SESSION_YEAR"] == session:
            party[(lg["HOUSE_TYPE"], lg["AUTHOR_NAME"])] = (lg["PARTY"], lg["DISTRICT"])
    votes: Dict[str, dict] = {}
    for sv in ex.rows("BILL_SUMMARY_VOTE_TBL"):
        k = sv["BILL_ID"]
        if k in bills and sv["VOTE_DATE_TIME"] >= votes.get(k, {}).get("VOTE_DATE_TIME", ""):
            votes[k] = sv
    # a committee's house, from every history row that names it (the structural truth the code-prefix rule is checked on)
    for rows_ in hist.values():
        for h in rows_:
            if h["SECONDARY_LOCATION"] == "Committee" and h["TERNARY_LOCATION"] and h["PRIMARY_LOCATION"] in HOUSES:
                committee_house[h["TERNARY_LOCATION"]][h["PRIMARY_LOCATION"]] += 1
    coms = Committees(names, committee_house)
    agenda, _dup = agenda_index(ex.rows("COMMITTEE_AGENDA_TBL"), today.isoformat())
    hearings: Dict[str, List[dict]] = collections.defaultdict(list)
    for ch in ex.rows("COMMITTEE_HEARING_TBL"):
        d = _date(ch["HEARING_DATE"])
        if ch["BILL_ID"] in bills and d >= today.isoformat():
            hearings[ch["BILL_ID"]].append({"date": d, "committee": coms.label(ch["LOCATION_CODE"]),
                                            "time": slot_time(agenda.get((ch["LOCATION_CODE"], d)))})
    unclassified: Dict[str, int] = collections.Counter()
    rescinded = actions_total = blank = where_unknown = 0
    where_by_bill: Dict[str, str] = {}
    records: List[Dict[str, Any]] = []
    for bid, b in sorted(bills.items()):
        parts = bill_id_parts(bid)
        if parts is None:
            unclassified["<bill id unreadable>"] += 1
            continue
        _sess, mtype, num = parts
        origin = origin_house(mtype)
        is_res = mtype in ("ACR", "SCR", "AJR", "SJR", "HR", "SR")
        rows = sorted(hist.get(bid, []), key=lambda h: (_date(h["ACTION_DATE"]), int(h["ACTION_SEQUENCE"] or 0)))
        history, stage, chamber, crossed = [], "introduced", origin, False
        floor = {"Assembly": "", "Senate": ""}
        referred: List[str] = []
        last_committee, last_row = "", {"action": "", "date": ""}
        last_cls, vetoed_seen = "", False
        where = []
        for h in rows:
            actions_total += 1
            code = WHERE_CODE.get(h["PRIMARY_LOCATION"], "-")
            where_unknown += code == "-"
            where.append(code)
            row = {"action": " ".join(h["ACTION"].split()), "date": _date(h["ACTION_DATE"])}
            history.append(row)
            last_row = row
            if h["ACTION_STATUS"] == "Rescinded":
                rescinded += 1
                continue
            if not h["END_STATUS"]:
                blank += 1
                continue
            cls = END_CLASS.get(h["END_STATUS"])
            house = h["PRIMARY_LOCATION"]
            if cls is None:
                unclassified[h["END_STATUS"]] += 1
                continue
            last_cls = cls
            second = house in HOUSES and house != origin
            if house in HOUSES:
                chamber = house
                crossed = crossed or second
            if h["SECONDARY_LOCATION"] == "Committee" and h["TERNARY_LOCATION"]:
                # the source's own house word ("Assembly Health"): the contract's "House" is a chamber KEY, not a label
                com = f"{house} {names.get(h['TERNARY_LOCATION'], h['TERNARY_LOCATION'])}".strip()
                last_committee = com
                if not referred or referred[-1] != com:
                    referred.append(com)
            if cls == "committee" and house in HOUSES:
                stage = _advance(stage, "committee2" if second else "committee1")
            elif cls == "floor" and house in HOUSES:
                stage = _advance(stage, "floor2" if second else "floor1")
            elif cls == "passed" and house in HOUSES:
                floor[house] = "passed"
                stage = _advance(stage, "floor2" if second else "floor1")
            elif cls == "enrolled":
                stage = _advance(stage, "concurrence")
            elif cls in ("signed", "chaptered"):
                stage = _advance(stage, "law")
            elif cls == "vetoed":
                stage = _advance(stage, "governor")
                vetoed_seen = True        # a later "veto override pending" floor row does not undo the veto
            elif cls == "failed" and house in HOUSES and h["SECONDARY_LOCATION"] in ("Floor", "Desk"):
                if floor[house] != "passed":
                    floor[house] = "defeated"
            if house == "Governor" and cls not in ("signed", "chaptered", "vetoed"):
                stage = _advance(stage, "governor")
        status = b["CURRENT_STATUS"]
        if mtype in NO_GOVERNOR and (b["CHAPTER_NUM"] or status == "Chaptered"
                                     or (mtype in ONE_HOUSE and status == "Passed")):
            outcome, stage = "adopted", _advance(stage, "adopted")
        elif mtype in NO_GOVERNOR:
            outcome = "dead" if last_cls == "died" else "in_progress"
        elif b["CHAPTER_NUM"]:
            outcome, stage = "signed", _advance(stage, "law")
        elif status == "Vetoed" or vetoed_seen:
            outcome = "vetoed"
        elif last_cls == "died":
            outcome = "dead"
        elif stage == "governor":
            outcome = "awaiting_governor"
        else:
            outcome = "in_progress"
        if not is_res and floor["Assembly"] == "passed" and floor["Senate"] == "passed":
            stage = _advance(stage, "concurrence")
        lead = [a for a in authors.get(bid, []) if a["CONTRIBUTION"].upper().startswith("LEAD")]
        others = [a for a in authors.get(bid, []) if a not in lead]
        chief = lead[0] if lead else None
        last_vote = votes.get(bid)       # Optional: a bill with no recorded vote has none
        rec_bill = f"{mtype}{num}"
        bill_name[bid] = rec_bill
        where_by_bill[rec_bill] = "".join(where)
        records.append({
            "bill": rec_bill,
            "title": subject.get(b["LATEST_BILL_VERSION_ID"], ""),
            "status_lis": last_row["action"],
            "stage": stage,
            "pipeline": {"stage": stage, "parked": False},
            "outcome": outcome,
            "outcome_origin": "structural_end_status",
            "patron": chief["NAME"] if chief else "",
            "patron_id": "",
            "chamber": TO_CONTRACT.get(chamber, chamber),
            "crossed_over": crossed,
            "floor_house": floor["Assembly"],
            "floor_senate": floor["Senate"],
            "last_committee": last_committee,
            "referral_count": len(referred),
            "latest_vote": ({"tally": f"{last_vote['AYES']}-{last_vote['NOES']}",
                             "location": names.get(last_vote["LOCATION_CODE"], last_vote["LOCATION_CODE"]),
                             "date": _date(last_vote["VOTE_DATE_TIME"])} if last_vote else {"tally": "", "location": "", "date": ""}),
            "upcoming": sorted(hearings.get(bid, []), key=lambda x: x["date"]),
            "last_action_date": last_row["date"],
            "history": history,
            "data_as_of_utc": data_as_of,
            "source": CA.source_name,
            "legislation_class": TYPE_NAME.get(mtype, mtype),
            "copatrons": [{"name": a["NAME"], "member_id": "", "role": a["CONTRIBUTION"].title(),
                           "party": PARTY.get(party.get((a["HOUSE"].upper()[:1] if a["HOUSE"] else "", a["NAME"]), ("", ""))[0], ""),
                           "district": ""} for a in others],
        })
    completeness = {
        "state": CA.code,
        "session_code": session,
        "universe_declared": len(bills),
        # the key the site's header + Health read for every state (web/src/data/gviz.ts findCompleteness)
        "universe_count": len(bills),
        # history rows naming a bill BILL_TBL does not hold (current session, regular) — a structural join miss
        "in_history_not_in_universe": sorted(orphans)[:50],
        "in_history_not_in_universe_count": len(orphans),
        "history_only_no_text": strays[:50],
        "history_only_no_text_count": len(strays),
        "measures_outside_both_houses": dict(outside),
        "records_written": len(records),
        "actions_total": actions_total,
        "actions_rescinded": rescinded,
        "end_status_blank": blank,
        "titles_blank": sum(1 for r in records if not r["title"]),
        "end_status_unclassified": sum(unclassified.values()),
        "end_status_unclassified_sample": sorted(unclassified)[:10],
        "rows_with_wrong_field_count": dict(ex.bad_rows),
        "rows_with_wrong_field_count_total": sum(ex.bad_rows.values()),
        "action_where_unknown": where_unknown,
        "committee_house_prefix_disagrees": coms.stats["committee_house_prefix_disagrees"],
        "committee_house_prefix_disagrees_sample": coms.stats["committee_house_prefix_disagrees_sample"],
        "session_display": f"{session[:4]}-{session[4:]} Regular Session" if len(session) == 8 else "",
        "checked_at_utc": now_utc,
    }
    if extras is not None:
        dates = [h["date"] for r in records for h in r["history"] if h["date"]]
        extras.update({"bill_name": bill_name, "committees": coms, "action_where": where_by_bill,
                       "session_start": min(dates) if dates else "", "names": names})
    return records, completeness


def run_intake(export: Export, today: datetime.date, now_utc: str,
               as_of_utc: Optional[str] = None, extras: Optional[dict] = None) -> Tuple[List[dict], dict]:
    records, comp = build_records(export, today, now_utc, as_of_utc, extras)
    broken = {t: n for t, n in export.bad_rows.items() if t in UNIVERSE_TABLES and n}
    if broken:
        raise ValueError(f"CA export has rows with the wrong field count in {broken} — a bill or action would be "
                         f"missing; refusing to publish (fail closed)")
    if comp["records_written"] != comp["universe_declared"]:
        raise ValueError(f"CA export holds {comp['universe_declared']} bills but {comp['records_written']} built — "
                         f"refusing to publish a partial universe (fail closed)")
    return records, comp

