"""
PR-C7.1d — Structural categorization of X-Ray Section 9 flagged rows.

Pure functions. No I/O. Testable in isolation.

The question this answers
-------------------------
The X-Ray flags N rows as "meeting actions without times" (Section 9
bug count). We don't yet know what those rows ACTUALLY are. This module
categorizes each flagged row against the LIS LegislationEvent structural
data so the breakdown is MEASURED, not guessed.

Classes (per the experiment design, 2026-05-12)
-----------------------------------------------
The classes are determined by structural facts, NOT by a pre-built
EventCode→category mapping (we don't have one yet — that's PR-C7.1b).
Each flagged row falls in exactly one LINKAGE class:

  D  — no LegEvent event for (bill, date). The row exists in Sheet1 /
       HISTORY but LIS's structured event log has nothing for that
       (bill, date). Likely a clerical annotation LegEvent doesn't
       track (e.g., "Bill text as passed Senate (SR###ER)").

  E  — matched a LegEvent event, but EventCode is null/empty/missing.
       This is the FRAGILE-DATA case (owner constraint 2026-05-12:
       "LIS frequently drops columns, changes headers, leaves fields
       null"). Surfaced as its own class so we measure LIS's structural
       completeness directly — if E is large, the whole structural
       architecture has a known hole and must be defensive about it.

  C  — matched, EventCode present, but EventDate has NO real wall-clock
       time (date-only, or midnight 00:00:00). Genuine time gap: LIS
       knows the event happened but didn't timestamp it.

  B  — matched, EventCode present, EventDate HAS a real wall-clock time.
       The time WAS available structurally; the worker should have
       recovered it. A non-trivial B count is a worker-side recovery
       bug worth fixing, not a data gap.

Class A (false positive) is NOT a linkage class — it's an overlay.
A row is a "false positive" if its EventCode maps to a non-meeting
category (e.g., Governor's Recommendation). Since we have no mapping
yet, this module does NOT decide A. Instead the orchestrator reports
the EventCode histogram across matched rows; the non-meeting clusters
(e.g., one code accounting for 122 rows, all "Governor's
Recommendation") are visible in that histogram. A is read off the
histogram by a human / the next PR, not hardcoded here.

Defensive posture (owner mandate 2026-05-12)
--------------------------------------------
Government data is fragile. Every field access tolerates missing keys,
null values, wrong types, and malformed dates. Nothing raises; every
unparseable / missing input maps to an explicit, named outcome that the
orchestrator counts. No silent skips (CLAUDE.md Standard #4 +
source_miss_visibility).
"""
from __future__ import annotations

from dataclasses import dataclass


# Linkage class labels — explicit string constants (no sentinel encoding).
CLASS_D_NO_EVENT = "D_no_legevent_event"
CLASS_E_EVENTCODE_MISSING = "E_eventcode_null_or_missing"
CLASS_C_NO_TIME = "C_meeting_event_no_time"
CLASS_B_HAS_TIME = "B_meeting_event_has_time"

# A flagged row can also fail to categorize for a reason worth surfacing
# rather than silently bucketing — e.g., the row itself is malformed.
CLASS_X_ROW_MALFORMED = "X_flagged_row_malformed"

# The bill's LIS fetch FAILED (network / 5xx / malformed JSON). This is
# NOT the same as "LIS has no event for (bill, date)" (Class D) — we
# simply don't know yet. Conflating the two would inflate Class D with
# transient fetch failures and corrupt the measurement. Same root lesson
# as the PR-C7.1a Codex P1 fold-in (FAILED != EMPTY). The orchestrator
# assigns this class directly; categorize_row never returns it.
CLASS_F_FETCH_FAILED = "F_bill_fetch_failed_indeterminate"


def safe_str(value) -> str:
    """Coerce any value (incl. None) to a stripped string. Never raises."""
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def eventdate_has_real_time(eventdate_raw) -> bool:
    """True iff the EventDate carries a real wall-clock time.

    Accepts the LIS shape "YYYY-MM-DDTHH:MM:SS" and tolerates:
      - None / empty            → False
      - date-only "YYYY-MM-DD"  → False (no time component)
      - midnight "...T00:00:00" → False (date-only encoded as midnight;
                                   LIS uses this for untimed actions)
      - malformed / unexpected  → False (defensive; never raises)

    We deliberately treat midnight as "no real time" because LIS stamps
    genuinely-untimed actions (filings, date-only records) at T00:00:00.
    A real meeting vote has a non-midnight time. This matches the
    resolver's own logic at calendar_worker.py (`[11:] not in
    ("", "00:00:00")`).
    """
    s = safe_str(eventdate_raw)
    if not s:
        return False
    # Expect an ISO-ish "<date>T<time>" or "<date> <time>". Find the
    # time component defensively.
    time_part = ""
    if "T" in s:
        time_part = s.split("T", 1)[1]
    elif " " in s:
        time_part = s.split(" ", 1)[1]
    else:
        # date-only, no separator → no time
        return False
    time_part = time_part.strip()
    if not time_part:
        return False
    # Normalize "HH:MM:SS" / "HH:MM" — midnight in any of these forms is
    # "no real time".
    if time_part in ("00:00:00", "00:00", "0:00:00", "0:00"):
        return False
    # Any other non-empty time component counts as a real time. We do not
    # strictly validate HH:MM:SS bounds here — a malformed-but-present
    # time is surfaced by the orchestrator's data-quality counters, not
    # silently reinterpreted.
    return True


def event_date_only(eventdate_raw) -> str:
    """Extract the date portion (YYYY-MM-DD) defensively. '' on failure."""
    s = safe_str(eventdate_raw)
    if not s:
        return ""
    # Split on T or space; take the first 10 chars of the date side.
    date_side = s.split("T", 1)[0].split(" ", 1)[0].strip()
    return date_side[:10]


def match_events_for_row(row_date: str, events_for_bill: list) -> list:
    """Return the subset of a bill's events whose EventDate matches row_date.

    row_date is the Sheet1 row's Date (YYYY-MM-DD). events_for_bill is a
    list of event dicts (possibly empty, possibly containing malformed
    entries). Never raises; non-dict entries are skipped (and the caller
    can detect the discrepancy via len mismatch if it cares).
    """
    target = safe_str(row_date)[:10]
    if not target:
        return []
    matched = []
    for e in events_for_bill:
        if not isinstance(e, dict):
            continue
        if event_date_only(e.get("EventDate")) == target:
            matched.append(e)
    return matched


@dataclass(frozen=True)
class RowCategory:
    """The structural verdict on one flagged row."""
    linkage_class: str            # one of CLASS_* above
    matched_event_count: int      # how many LegEvent events matched (bill, date)
    event_codes: tuple            # distinct EventCodes among matched events ("" if missing)
    has_real_time: bool           # True iff any matched event had a real wall-clock time
    detail: str                   # human-readable note for the results tab


def categorize_row(
    row_bill: str,
    row_date: str,
    events_for_bill: list,
) -> RowCategory:
    """Categorize one flagged row against its bill's LegEvent events.

    Decision order (each row lands in exactly one linkage class):
      1. Row malformed (no bill or no parseable date)   → X
      2. No matched event for (bill, date)              → D
      3. Matched, but NO matched event has a usable
         (non-empty) EventCode                          → E
      4. Matched + EventCode present, any matched event
         has a real wall-clock time                     → B
      5. Matched + EventCode present, none has a real
         time                                           → C

    The B-before-C ordering means: if LIS published the time on ANY of
    the events matching (bill, date), we call it recoverable (B). C is
    reserved for the case where LIS has the event(s) but NONE carries a
    real time — the genuine gap.
    """
    bill = safe_str(row_bill)
    date = safe_str(row_date)
    if not bill or not event_date_only(date):
        return RowCategory(
            linkage_class=CLASS_X_ROW_MALFORMED,
            matched_event_count=0,
            event_codes=(),
            has_real_time=False,
            detail=f"flagged row missing bill or parseable date (bill={bill!r}, date={date!r})",
        )

    matched = match_events_for_row(date, events_for_bill)
    if not matched:
        return RowCategory(
            linkage_class=CLASS_D_NO_EVENT,
            matched_event_count=0,
            event_codes=(),
            has_real_time=False,
            detail=f"no LegEvent event for ({bill}, {date}); "
                   f"bill had {len([e for e in events_for_bill if isinstance(e, dict)])} total events",
        )

    # Distinct, non-empty EventCodes among the matched events.
    codes = []
    for e in matched:
        code = safe_str(e.get("EventCode"))
        if code and code not in codes:
            codes.append(code)
    codes_tuple = tuple(codes)

    if not codes_tuple:
        # Matched an event but every match has null/empty EventCode.
        return RowCategory(
            linkage_class=CLASS_E_EVENTCODE_MISSING,
            matched_event_count=len(matched),
            event_codes=(),
            has_real_time=any(eventdate_has_real_time(e.get("EventDate")) for e in matched),
            detail=f"matched {len(matched)} event(s) for ({bill}, {date}) but EventCode "
                   f"null/empty on all — FRAGILE DATA",
        )

    has_time = any(eventdate_has_real_time(e.get("EventDate")) for e in matched)
    if has_time:
        return RowCategory(
            linkage_class=CLASS_B_HAS_TIME,
            matched_event_count=len(matched),
            event_codes=codes_tuple,
            has_real_time=True,
            detail=f"matched {len(matched)} event(s); real time present; "
                   f"codes={','.join(codes_tuple)} — worker should have recovered",
        )
    return RowCategory(
        linkage_class=CLASS_C_NO_TIME,
        matched_event_count=len(matched),
        event_codes=codes_tuple,
        has_real_time=False,
        detail=f"matched {len(matched)} event(s); NO real time; "
               f"codes={','.join(codes_tuple)} — genuine LIS time gap",
    )
