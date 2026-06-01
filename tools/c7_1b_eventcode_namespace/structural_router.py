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

# === Middle-bucket router: group LIS's OWN published Status vocabulary ===
# Source of truth: GET https://lis.virginia.gov/Legislation/api/
# GetLegislationStatusListAsync — returns 52 statuses (References[].Name).
# Owner-approved 2026-05-31: grouping LIS's published enum "counts as
# consuming the source," NOT a banned dictionary. The event's `Status`
# field carries one of these Names.
#
# These sets group the 52 published statuses into post-passage/clerical
# (admin) vs in-session legislative action (meeting). Validated on a
# 1,068-event live sample (file-captured); full-dataset validation
# pending. validate_status_grouping() below checks this grouping against
# the live published list every run so a NEW status (LIS adds a 53rd
# next year) is DETECTED, not silently mis-defaulted (Standard #1:
# static values must have runtime validation that alerts on drift).
ADMIN_PIPELINE_STATUSES = frozenset({
    "Introduced",
    "Awaiting Signature", "Communicated", "Pending Communciation",  # LIS's spelling
    "Pending Governor's Communication", "Pending Recommunication",
    "With Governor", "Awaiting Governor's Action",
    "Governor's Recommendation", "Governor's Veto", "Gov Recommendation Adopted",
    "Acts of Assembly Chapter", "Enacted", "Approved",
    "Enrolled-House", "Enrolled-Senate", "Reenrolled-House", "Reenrolled-Senate",
    "Committee Referral Pending", "Preview",
})
MEETING_INSESSION_STATUSES = frozenset({
    "In Committee", "In Subcommittee", "In House", "In Senate", "In Conference",
    "Reported Out-House", "Reported Out-Senate",
    "Engrossed", "Engrossed with Amendment", "Reengrossed with Amendment",
    "Passed House", "Passed Senate", "Passed Both", "Passed",
    "Failed", "Failed in Conference", "Left In Committee",
    "Continued To", "Continued From", "Continued to House", "Continued to Senate",
    "Continued to Conference", "Continued in Conference", "Continued in House",
    "Continued in Senate",
    "Conference Report Agreed", "Conference Report Rejected", "Conference Report Adopted",
    "Conference Requested", "Incorporated",
})
# Union = every status we've classified. validate_status_grouping() alerts
# on any live status Name absent from this union.
CLASSIFIED_STATUSES = ADMIN_PIPELINE_STATUSES | MEETING_INSESSION_STATUSES


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

    # === Middle bucket: consume LIS's own Status enum ===
    status = _s(event.get("Status"))
    if status in ADMIN_PIPELINE_STATUSES:
        return RouteVerdict("admin", "status_clerical")
    if status in MEETING_INSESSION_STATUSES or status == "":
        # In-session floor/committee action (or blank status, which the
        # sample showed on floor actions like "Read third time" / "Rules
        # suspended"). A reading/passage/offer done in a convened body.
        return RouteVerdict("meeting", "status_in_session")

    # DEFENSIVE FALLBACK — a status NOT in our grouping. This is the
    # "LIS invents a new status next year" path. Do NOT crash, do NOT
    # blank: fall through to the one remaining structural signal
    # (time-presence), and let validate_status_grouping() raise the
    # drift alert so the grouping gets extended. The Description always
    # displays regardless of route.
    if _has_real_time(event.get("EventDate")):
        return RouteVerdict("meeting", "status_unknown_timefallback")
    return RouteVerdict("admin", "status_unknown_timefallback")


def validate_status_grouping(live_status_names) -> list[str]:
    """Standard #1 runtime check: compare our grouping to LIS's published list.

    Pass the `Name` field of every entry from
    GetLegislationStatusListAsync. Returns the list of status Names LIS
    publishes that we have NOT classified (admin vs meeting). An empty
    list means our grouping fully covers LIS's current vocabulary. A
    non-empty list is DRIFT — the caller must raise a categorized alert
    (CRITICAL/DATA_ANOMALY) so the grouping is extended before the new
    status silently rides the time-presence fallback. Never raises.
    """
    unclassified = []
    for raw in (live_status_names or []):
        name = _s(raw)
        if name and name not in CLASSIFIED_STATUSES:
            unclassified.append(name)
    return sorted(set(unclassified))
