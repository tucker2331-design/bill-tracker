"""
PR-C7.1b — the deterministic, dictionary-free calendar-vs-ledger router.

Pure function. No I/O. No per-code dictionary. Routes each LIS event to
"meeting" (timed calendar) or "admin" (ledger) using ONLY LIS's own
structural fields — the source of truth classifies; we consume it.

Decision tree (ordered; first match wins), derived from the authoritative
ReferenceType measurement (37 bills / 1,068 events, file-captured
2026-05-31 — see assumptions_audit #57). This is a HYPOTHESIS to be
validated by validate_router.py against live data, NOT an assertion.

  1. VoteTally present                       → meeting  (recorded_vote)
       A recorded vote happened → it happened in a convened body.
       266/1068 events; the single cleanest meeting signal.
  2. ReferenceType in {LegislationText,
     LegislationFile}                         → admin    (document)
       Engrossed text, fiscal-impact files, prefiled/acts text. 201
       events, the H5601/S5601 false-positive family. Off-hours
       doc-batch timestamps, never a real meeting.
  3. ReferenceType in {Committee, Subcommittee} → admin  (referral_assignment)
       "Referred to Committee...", "Assigned ... sub" — these reference a
       committee ASSIGNMENT (a routing/clerical act), not the meeting.
  4. ActorType == Governor OR EventCode prefix G → admin (executive)
       Governor's recommendation received, approved, action deadline.
       Executive actions, not legislative meetings. (Floor VOTES on a
       governor's recommendation carry a VoteTally and are already
       caught by rule 1.)
  5. EventDate has a real wall-clock time     → meeting  (timed_action)
       Remaining bucket (<blank> ReferenceType, Vote-without-tally):
       readings, passages happening in session at a specific minute.
  6. else                                     → admin    (untimed)
       Date-only / midnight remainder: enrolled, signed, clerical.

NOTE: this routes; it does NOT label for display. The lobbyist always
sees the event's `Description` (LIS's plain English) regardless of route.
An unmapped/never-seen EventCode routes by these fields and displays its
Description — zero dictionary, zero maintenance, no KeyError surface.
"""
from __future__ import annotations

from dataclasses import dataclass

DOCUMENT_REFTYPES = frozenset({"LegislationText", "LegislationFile"})
REFERRAL_REFTYPES = frozenset({"Committee", "Subcommittee"})


def _s(v) -> str:
    if v is None:
        return ""
    try:
        return str(v).strip()
    except Exception:
        return ""


def _votetally_present(v) -> bool:
    # VoteTally may arrive as a string ("21-Y 19-N"), a list, a dict, or
    # None/"". Present == any non-empty, non-whitespace content.
    if v is None:
        return False
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return bool(_s(v))


def _has_real_time(eventdate_raw) -> bool:
    s = _s(eventdate_raw)
    if "T" in s:
        t = s.split("T", 1)[1]
    elif " " in s:
        t = s.split(" ", 1)[1]
    else:
        return False
    t = t.strip()[:8]
    return bool(t) and t not in ("00:00:00", "00:00", "0:00:00", "0:00")


@dataclass(frozen=True)
class RouteVerdict:
    route: str     # "meeting" | "admin"
    reason: str    # which rule fired


def route_event(event: dict) -> RouteVerdict:
    """Route one LIS LegislationEvent dict. Never raises (defensive)."""
    if not isinstance(event, dict):
        return RouteVerdict("admin", "non_dict_event")

    if _votetally_present(event.get("VoteTally")):
        return RouteVerdict("meeting", "recorded_vote")

    reftype = _s(event.get("ReferenceType"))
    if reftype in DOCUMENT_REFTYPES:
        return RouteVerdict("admin", "document")
    if reftype in REFERRAL_REFTYPES:
        return RouteVerdict("admin", "referral_assignment")

    actor = _s(event.get("ActorType")).lower()
    code = _s(event.get("EventCode"))
    if actor == "governor" or (code[:1] == "G"):
        return RouteVerdict("admin", "executive")

    if _has_real_time(event.get("EventDate")):
        return RouteVerdict("meeting", "timed_action")
    return RouteVerdict("admin", "untimed")
