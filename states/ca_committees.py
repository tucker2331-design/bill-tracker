"""California committees and meeting slots — shared by the bill intake (a bill's upcoming hearings) and the calendar.

Committee codes (LOCATION_CODE_TBL, `LOCATION_TYPE` B = a committee, V = a floor/vote location):
  * HOUSE OF A COMMITTEE. Legislative Counsel's committee codes carry the house in their first two letters — `CX…` an
    Assembly committee, `CS…` a Senate committee (COMMITTEE_HEARING_TBL's own `COMMITTEE_TYPE` column holds the same
    two letters). That is a documented heuristic, so it is CHECKED every run against the structural truth — the
    `PRIMARY_LOCATION` (Assembly / Senate) of every history row that names the committee in `TERNARY_LOCATION`. A
    disagreement is counted (`committee_house_prefix_disagrees`, a Health check, limit 0) and the history's house wins.
    A code with neither prefix nor history is counted (`committee_house_unknown`) and shown without a house.
  * FLOOR LOCATIONS. `AFLOOR` / `SFLOOR` are the two houses' floors (`FLOOR_HOUSE`). Any other V-type code except the
    conference-committee vote location is counted (`calendar_floor_code_unknown`, Health limit 0).

Meeting slots (COMMITTEE_AGENDA_TBL): one row per committee meeting or floor session, keyed (code, date), with the
source's own time text (`AGENDA_TIME`: "1:30 p.m.", "9 a.m.", "Upon Call of the Chair", "10 minutes prior to
Session") and room (`LINE1`). The time is DISPLAYED verbatim; `sort_time` only orders the day (a clock time at the
start of the text -> "HH:MM"; anything else sorts last) — the same rule as Pennsylvania's calendar.
"""
from __future__ import annotations

import collections
import re
from typing import Dict, List, Optional, Tuple

PREFIX_HOUSE = {"CX": "Assembly", "CS": "Senate"}
FLOOR_HOUSE = {"AFLOOR": "Assembly", "SFLOOR": "Senate"}
CONFERENCE_VOTE = "CONFCM"
_CLOCK = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?", re.I)


def sort_time(t: str) -> str:
    """'1:30 p.m.' -> '13:30', '9 a.m.' -> '09:00', '12 noon' -> '12:00'; relative or blank -> '' (sorts last)."""
    s = (t or "").strip()
    if s.lower().startswith("12 noon"):
        return "12:00"
    m = _CLOCK.match(s)
    if not m:
        return ""
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return f"{h:02d}:{m.group(2) or '00'}"


class Committees:
    """House + display name for every committee code, the prefix rule checked against the history's houses."""

    def __init__(self, names: Dict[str, str], history_house: Dict[str, Dict[str, int]]):
        self.names = names
        self.house: Dict[str, str] = {}
        self.disagrees: List[str] = []
        self.unknown = 0
        for code in sorted(set(names) | set(history_house)):
            by_prefix = PREFIX_HOUSE.get(code[:2])
            seen = history_house.get(code)
            by_history = max(seen.items(), key=lambda kv: kv[1])[0] if seen else None
            if by_history and by_prefix and by_history != by_prefix:
                self.disagrees.append(code)
            h = by_history or by_prefix
            if h:
                self.house[code] = h

    @property
    def stats(self) -> dict:
        return {"committee_house_prefix_disagrees": len(self.disagrees),
                "committee_house_prefix_disagrees_sample": self.disagrees[:10], "committee_house_unknown": self.unknown}

    def label(self, code: str) -> str:
        """'CX25' -> 'Assembly Appropriations'. A code with no known house keeps the source's name (counted)."""
        name = self.names.get(code, code)
        h = self.house.get(code)
        if h is None:
            self.unknown += 1
            return name
        return f"{h} {name}"


def agenda_index(rows, since: str) -> Tuple[Dict[Tuple[str, str], List[dict]], int]:
    """(code, YYYY-MM-DD) -> the distinct meeting slots the source lists that day (identical rows written once).
    Returns (index, duplicates_dropped). Rows dated before `since` (earlier sessions) are not read."""
    out: Dict[Tuple[str, str], List[dict]] = collections.defaultdict(list)
    dup = 0
    for r in rows:
        d = (r["AGENDA_DATE"] or "")[:10]
        if not d or d < since:
            continue
        slot = {"time": " ".join((r["AGENDA_TIME"] or "").split()), "room": " ".join((r["LINE1"] or "").split()),
                "desc": (r["COMMITTEE_DESC"] or "").strip()}
        key = (r["COMMITTEE_CODE"], d)
        if slot in out[key]:
            dup += 1
            continue
        out[key].append(slot)
    return out, dup


def slot_time(slots: Optional[List[dict]]) -> str:
    """The time to show for a (code, date): the one slot's time; two distinct slots the same day are shown together
    (the source does not say which one hears which bill — never a guess)."""
    if not slots:
        return ""
    return " · ".join(dict.fromkeys(s["time"] for s in slots if s["time"]))
