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

import re as _re
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


# Times LIS stamps on document/clerical batch events that are NOT a real
# meeting wall-clock time. 00:00:00 is the date-only marker; 04:00:00 is the
# overnight document-processing artifact observed on "Enrolled"/"Bill text"
# events (measured 2026-06-03 — see assumptions_audit #67). Kept separate from
# `_has_real_time` so the router's existing time-presence fallback (rule 5) is
# unchanged; this stricter view is used ONLY to derive ministerial types.
_NON_MEETING_TIMES = frozenset({"00:00:00", "00:00", "0:00:00", "0:00", "04:00:00", "04:00", "4:00:00"})


def _has_meeting_time(eventdate_raw) -> bool:
    """Stricter than _has_real_time: also rejects the 04:00 doc-batch artifact."""
    s = _s(eventdate_raw)
    if "T" in s:
        t = s.split("T", 1)[1]
    elif " " in s:
        t = s.split(" ", 1)[1]
    else:
        return False
    t = t.strip()[:8]
    return bool(t) and t not in _NON_MEETING_TIMES


# Default occurrence floor before an EventCode may be judged "ministerial".
# A genuine meeting type is ~40-100% timed-or-voted, so P(N occurrences all
# untimed AND unvoted) collapses fast; 20 is comfortably past the noise floor
# while still capturing low-volume ledger types ("Left in Committee X").
MINISTERIAL_MIN_SAMPLES = 20


def compute_ministerial_eventcodes(events_iterable, min_samples: int = MINISTERIAL_MIN_SAMPLES) -> frozenset:
    """Derive the ministerial (non-deliberative) EventCode set from the data.

    A *ministerial* event type is one whose EVERY occurrence — over at least
    ``min_samples`` occurrences this session — carries NEITHER a recorded vote
    NOR a real meeting timestamp. Structurally these are ledger records (Signed
    by, Enrolled, Placed on Calendar, Assigned sub, Received, Communicated to
    Governor): they describe a milestone, not a meeting you attend, and LIS
    itself stamps them date-only. Pass the result to ``route_event(...,
    ministerial_codes=...)`` so those rows route to the ledger instead of riding
    the empty-status → meeting default and surfacing as "meeting action without
    a time" (X-Ray Section 9).

    This is the dictionary-free, self-calibrating answer to the empty-status
    ambiguity: "Signed by President" (S5620) and "Read third time" (S4130) are
    indistinguishable on every per-event field, but in AGGREGATE the reading
    type demonstrably carries real timestamps while the signing type never does.
    The per-TYPE view is what makes it safe — a single midnight "Read third
    time" is still a meeting because its type is known-timed elsewhere.

    Recomputed each run from the live cache: a new state's codes, or a new LIS
    event type next session, are classified from their own observed behavior
    with zero human maintenance (Standard #3 + #5). The min-sample floor means a
    sparse early-session cache simply yields a smaller set (graceful — unmatched
    types keep normal routing), never a false positive.

    ``events_iterable``: any iterable of LIS event dicts (e.g. a generator over
    the flattened ``legislation_event_cache`` values). Never raises.
    """
    from collections import defaultdict
    # [count, any_meeting_time, any_vote]
    stat = defaultdict(lambda: [0, False, False])
    try:
        for e in events_iterable:
            if not isinstance(e, dict):
                continue
            code = _s(e.get("EventCode"))
            if not code:
                continue
            s = stat[code]
            s[0] += 1
            if not s[1] and _has_meeting_time(e.get("EventDate")):
                s[1] = True
            if not s[2] and _votetally_present(e.get("VoteTally")):
                s[2] = True
    except Exception:
        # Derivation is an optimization layer; on any iteration error fall back
        # to the empty set (no-op) rather than risk a bad partial set.
        return frozenset()
    return frozenset(
        code for code, (n, timed, voted) in stat.items()
        if n >= min_samples and not timed and not voted
    )


@dataclass(frozen=True)
class RouteVerdict:
    route: str     # "meeting" | "admin"
    reason: str    # which rule fired


def route_event(event: dict, ministerial_codes: frozenset = frozenset()) -> RouteVerdict:
    """Route one LIS LegislationEvent dict. Never raises (defensive).

    ``ministerial_codes`` (PR-C7.1l): a runtime-derived set of EventCodes that
    are structurally NON-DELIBERATIVE — every occurrence across the session
    carries NEITHER a recorded vote NOR a real meeting timestamp (computed by
    ``compute_ministerial_eventcodes`` over a min-sample floor). These are
    ledger records — "Signed by President", "Enrolled", "Placed on Calendar",
    "Assigned … sub", "Received", "Communicated to Governor" — never a timed
    meeting. The set is derived from the data each run, so it self-calibrates to
    any state's published EventCodes: zero dictionary, zero maintenance
    (Standard #3 structural-determinism + #5 dynamic-config). Default empty =
    no-op, preserving back-compat for validation tools / older callers.

    Why this is safe (and not a banned per-state list): the membership test is
    on LIS's own structural identifier (EventCode), and a code only qualifies by
    an OBSERVED data property (never timed, never voted, over many occurrences)
    — not by any human-authored mapping of code→category. A genuine meeting
    action is impossible to admit here: committee reports/floor votes always
    carry a VoteTally (caught by rule 1 above this check) and readings always
    carry real timestamps, so neither can ever land in ministerial_codes.
    """
    if not isinstance(event, dict):
        return RouteVerdict("admin", "non_dict_event")

    if _votetally_present(event.get("VoteTally")):
        return RouteVerdict("meeting", "recorded_vote")

    code = _s(event.get("EventCode"))
    if code and code in ministerial_codes:
        return RouteVerdict("admin", "ministerial_eventtype")

    reftype = _s(event.get("ReferenceType"))
    if reftype in DOCUMENT_REFTYPES:
        return RouteVerdict("admin", "document")
    if reftype in REFERRAL_REFTYPES:
        return RouteVerdict("admin", "referral_assignment")

    actor = _s(event.get("ActorType")).lower()
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


# === EventType-reference admin recovery (PR-C7.1n) ==========================
# LIS publishes a full EventType reference (GetLegislationEventTypeReferences
# Async): EventCode <-> canonical descriptions. We use it to recover the
# structural route for a row whose event could NOT be matched by date — the
# HISTORY.CSV action date and the LegislationEvent date drift by 1-9 days for
# reconvene/conference/governor actions, so the exact-date matcher returns blank
# and the row falls to text classification (which reads "Governor's
# Recommendation" as a meeting). Instead of a hand-authored "governor -> admin"
# text pattern (a per-state dictionary), we look the outcome up in LIS's OWN
# published descriptions, recover the EventCode(s), and route by them.
# Asserts ADMIN ONLY (G-prefix executive or ministerial) and ONLY when EVERY
# candidate code agrees — so it can only move a blank route to admin, never
# manufacture a false meeting. See assumptions_audit #69.

def normalize_event_description(s) -> str:
    """Normalize a HISTORY outcome / reference description to a comparable key.

    Strips a leading emoji-tag block (e.g. "📝 [Memory Anchor: admin] "), a
    chamber prefix ("S "/"H "), a trailing vote tally "(13-Y 0-N)", then reduces
    to space-joined alnum tokens. Used ONLY to recover LIS's structural EventCode
    from its own published vocabulary — never to classify by text.
    """
    s = _s(s)
    s = _re.sub(r'^[^A-Za-z0-9]*\[[^\]]*\]\s*', '', s)   # leading [tag] block (+ any emoji)
    s = _re.sub(r'^\s*[HS]\s+', '', s)                   # chamber prefix
    s = _re.sub(r'\s*\([^)]*\)\s*$', '', s)              # trailing (vote tally)
    s = _re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
    return s


def build_admin_recovery_index(reference_items, ministerial_codes=frozenset()) -> frozenset:
    """From LIS's EventType reference, the set of normalized descriptions whose
    EVERY EventCode routes admin (G-prefix executive OR ministerial).

    A description qualifies only if all EventCodes LIS maps it to are admin —
    so recovering an admin route from it can never mislabel a deliberative
    action. ``reference_items`` is the list from
    GetLegislationEventTypeReferencesAsync; ``ministerial_codes`` is the
    runtime-derived ministerial set. Never raises.
    """
    desc2codes: dict = {}
    try:
        for it in reference_items or []:
            if not isinstance(it, dict):
                continue
            ec = _s(it.get("EventCode"))
            if not ec:
                continue
            for fld in ("LegislationDescription", "CalendarDescription", "JournalDescription"):
                d = it.get(fld)
                if d:
                    desc2codes.setdefault(normalize_event_description(d), set()).add(ec)
    except Exception:
        return frozenset()
    def _is_admin_code(ec: str) -> bool:
        return ec[:1] == "G" or ec in ministerial_codes
    return frozenset(
        nd for nd, codes in desc2codes.items()
        if nd and codes and all(_is_admin_code(ec) for ec in codes)
    )


def recover_admin_route(outcome, admin_recovery_index) -> str:
    """Return "admin" if the outcome's normalized description is a known
    all-admin LIS description, else "". Safe fallback for a blank route."""
    if not admin_recovery_index:
        return ""
    return "admin" if normalize_event_description(outcome) in admin_recovery_index else ""


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
