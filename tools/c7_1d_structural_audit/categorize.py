"""
PR-C7.1d — Structural categorization of X-Ray Section 9 flagged rows.

Pure functions. No I/O. Testable in isolation.

The question this answers
-------------------------
The X-Ray flags N rows as "meeting actions without times" (Section 9
bug count). We don't yet know what those rows ACTUALLY are. This module
categorizes each flagged row against the LIS LegislationEvent structural
data so the breakdown is MEASURED, not guessed.

Production-faithful matching
----------------------------
`match_events_for_row` mirrors `_resolve_via_legislation_event_api` in
`calendar_worker.py`:
  1. Filter events to (bill, date) — date match on first 10 chars.
  2. Filter to events whose ChamberCode matches the row's acting chamber
     (extracted from the outcome's leading "H "/"S " prefix, falling
     back to the bill-number prefix). Tolerates empty ChamberCode (some
     joint-action events lack it).
  3. Among real-time events (EventDate has a real wall-clock time, not
     midnight or date-only), require non-zero token overlap between the
     row's Outcome and the event's Description.

Codex P2 review-fix (2026-05-13): without 2+3, a same-day cross-chamber
or unrelated event would mark a row as "worker should have recovered"
when the production resolver correctly abstained. That would overstate
Class B and corrupt the B/C/D breakdown this audit is meant to produce.

Classes (per the experiment design)
-----------------------------------
Each flagged row falls in exactly one LINKAGE class:

  D  — no LegEvent event matching (bill, date, chamber). LIS may have
       events for the bill that day in the other chamber, but nothing
       the production resolver would have used for this row's action.

  E  — matched at least one event but EventCode is null/empty on all
       matches. FRAGILE-DATA case — owner constraint 2026-05-12.

  C  — matched + EventCode present, but the production resolver would
       NOT have recovered a time (no real-time event in matched set, OR
       real-time events exist but zero token overlap with the outcome).
       Genuine residue from the lobbyist's perspective.

  B  — matched + EventCode present + production resolver WOULD have
       recovered (real-time event present AND token overlap > 0).
       A non-trivial B count is a worker-side recovery bug.

Class A (false positive) is read off the EventCode histogram across
matched rows, not hardcoded here (no EventCode→category map yet).
"""
from __future__ import annotations

import re
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
# simply don't know yet. Same root lesson as the PR-C7.1a Codex P1
# fold-in (FAILED != EMPTY). The orchestrator assigns this class
# directly; categorize_row never returns it.
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
    """True iff the EventDate carries a real (non-midnight) wall-clock time.

    Accepts the LIS shape "YYYY-MM-DDTHH:MM:SS" and tolerates:
      - None / empty            → False
      - date-only "YYYY-MM-DD"  → False
      - midnight encoded as
        "T00:00:00", "T00:00",  → False
        "T00:00:00.000",
        "T00:00:00Z",
        "T00:00:00+05:00", etc.
      - malformed / unexpected  → False

    Gemini medium review-fix (2026-05-13): the prior version did an
    exact-string compare against ("00:00:00", "00:00", ...) which fails
    if LIS adds fractional seconds (.fff) or a timezone suffix (Z, ±HH:MM).
    We now extract HH:MM:SS strictly from the leading 8 chars of the
    time portion before the midnight comparison.
    """
    s = safe_str(eventdate_raw)
    if not s:
        return False
    # Locate the time component defensively.
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
    # Strip fractional seconds and any timezone suffix.
    # "00:00:00.000Z"   → "00:00:00"
    # "00:00:00+05:00"  → "00:00:00"
    # "00:00:00Z"       → "00:00:00"
    # "00:00:00"        → "00:00:00"
    # "00:00"           → "00:00"
    leading = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)", time_part)
    if not leading:
        # Time portion present but not in a recognizable HH:MM(:SS) shape.
        # Defensive: do not claim it's a real time.
        return False
    hhmmss = leading.group(1)
    if hhmmss in ("00:00:00", "00:00", "0:00:00", "0:00"):
        return False
    return True


# Strict YYYY-MM-DD validator: 4 digits, '-', 2 digits, '-', 2 digits.
_DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def event_date_only(eventdate_raw) -> str:
    """Return the date portion (YYYY-MM-DD) if structurally valid, else ''.

    Gemini HIGH / Codex P2 review-fix (2026-05-13): the prior version
    returned the first 10 chars of any non-empty string, so "not-a-date"
    became "not-a-dat" (truthy), bypassing both the malformed-date
    counter in the orchestrator and the date-match check in
    `match_events_for_row` (where it could spuriously match by prefix).
    Now we validate the YYYY-MM-DD shape before returning.
    """
    s = safe_str(eventdate_raw)
    if not s:
        return ""
    date_side = s.split("T", 1)[0].split(" ", 1)[0].strip()
    part = date_side[:10]
    if _DATE_SHAPE.match(part):
        return part
    return ""


# ---------------------------------------------------------------------------
# Production-faithful matching: chamber filter + token overlap
# ---------------------------------------------------------------------------

# Mirrors `_legislation_event_token_set` at calendar_worker.py:579.
# Lowercased 3+ letter alphabetic tokens. Same tokenizer means same
# overlap semantics as the production resolver.
_TOKEN_PATTERN = re.compile(r"[A-Za-z]{3,}")


def _tokens(text: str) -> set:
    if not text:
        return set()
    return {w.lower() for w in _TOKEN_PATTERN.findall(text)}


def chamber_from_outcome(outcome: str) -> str:
    """Extract the acting chamber from the outcome's leading "H "/"S " prefix.

    Mirrors `acting_chamber_prefix.strip()[:1].upper()` in calendar_worker.py.
    Returns "H", "S", or "" (empty if no prefix — caller may fall back to
    bill-number prefix).
    """
    s = safe_str(outcome)
    if not s:
        return ""
    head = s[:2]
    if head in ("H ", "S "):
        return head[0]
    return ""


def chamber_from_bill(bill: str) -> str:
    """Fallback chamber derivation from the bill-number prefix.

    HB / HJR / HR / HBR → H. SB / SJR / SR / SBR → S. Otherwise "".
    """
    s = safe_str(bill).upper()
    if not s:
        return ""
    if s.startswith("H"):
        return "H"
    if s.startswith("S"):
        return "S"
    return ""


def match_events_for_row(
    row_bill: str,
    row_date: str,
    row_outcome: str,
    events_for_bill: list,
) -> tuple[list, dict]:
    """Production-faithful filter: (bill, date, chamber) + token overlap.

    Returns (matched_events, signals) where:
      matched_events: events that passed (bill, date, chamber). Subset
                      that the production resolver would CONSIDER. Token
                      overlap is recorded in signals for the categorizer
                      to use, but does NOT prune the matched_events list
                      itself — we want the categorizer to see all
                      chamber-matched events for the EventCode reporting.
      signals: {
        "chamber_used": str,                  # "H"/"S"/"" — chamber filter applied
        "had_other_chamber_events": bool,     # date matched but only other chamber
        "real_time_events": list,             # subset with real wall-clock time
        "best_token_overlap": int,            # max overlap across real_time_events
      }

    The orchestrator's class assignment uses:
      - len(matched_events) == 0 → D (no match for chamber)
      - all matched have null EventCode → E
      - signals["real_time_events"] non-empty AND best_token_overlap > 0 → B
      - else → C  (no real time, OR real time but resolver would refuse)
    """
    target = event_date_only(row_date)
    if not target:
        return [], {
            "chamber_used": "",
            "had_other_chamber_events": False,
            "real_time_events": [],
            "best_token_overlap": 0,
        }

    # Date-matched candidates (regardless of chamber yet).
    date_matched = []
    for e in events_for_bill:
        if not isinstance(e, dict):
            continue
        if event_date_only(e.get("EventDate")) == target:
            date_matched.append(e)

    # Chamber: outcome prefix preferred, bill prefix as fallback.
    chamber = chamber_from_outcome(row_outcome) or chamber_from_bill(row_bill)

    # Chamber filter: keep events whose ChamberCode matches OR is empty
    # (joint-action events). If the row's chamber is unknown ("") keep all
    # date-matched events (degrades to date-only, the prior behavior).
    chamber_matched = []
    had_other_chamber = False
    for e in date_matched:
        ev_chamber = safe_str(e.get("ChamberCode")).upper()
        if chamber and ev_chamber and ev_chamber != chamber:
            had_other_chamber = True
            continue
        chamber_matched.append(e)

    # Token-overlap scoring against real-time events only (the resolver
    # ignores midnight/date-only events when timing a meeting).
    real_time_events = [
        e for e in chamber_matched if eventdate_has_real_time(e.get("EventDate"))
    ]
    outcome_tokens = _tokens(safe_str(row_outcome))
    best_overlap = 0
    for e in real_time_events:
        ev_tokens = _tokens(safe_str(e.get("Description")))
        overlap = len(outcome_tokens & ev_tokens)
        if overlap > best_overlap:
            best_overlap = overlap

    return chamber_matched, {
        "chamber_used": chamber,
        "had_other_chamber_events": had_other_chamber,
        "real_time_events": real_time_events,
        "best_token_overlap": best_overlap,
    }


@dataclass(frozen=True)
class RowCategory:
    """The structural verdict on one flagged row."""
    linkage_class: str
    matched_event_count: int
    event_codes: tuple
    has_real_time: bool         # any chamber-matched event had a real time
    detail: str


def categorize_row(
    row_bill: str,
    row_date: str,
    row_outcome: str,
    events_for_bill: list,
) -> RowCategory:
    """Categorize one flagged row against its bill's LegEvent events.

    Decision order (each row lands in exactly one linkage class):
      1. Row malformed (no bill or no valid YYYY-MM-DD date)    → X
      2. No event matches (bill, date, chamber)                 → D
      3. Matched events but ALL have null/empty EventCode       → E
      4. Matched + EventCode present, production resolver WOULD
         have recovered (real-time event + token overlap > 0)   → B
      5. Otherwise (matched, EventCode present, no real-time OR
         zero token overlap with outcome)                       → C
    """
    bill = safe_str(row_bill)
    date = safe_str(row_date)
    if not bill or not event_date_only(date):
        return RowCategory(
            linkage_class=CLASS_X_ROW_MALFORMED,
            matched_event_count=0,
            event_codes=(),
            has_real_time=False,
            detail=f"flagged row missing bill or has invalid date (bill={bill!r}, date={date!r})",
        )

    matched, signals = match_events_for_row(bill, date, row_outcome, events_for_bill)
    other_chamber_note = (
        f"; other-chamber events on date={signals['had_other_chamber_events']}"
    )

    if not matched:
        return RowCategory(
            linkage_class=CLASS_D_NO_EVENT,
            matched_event_count=0,
            event_codes=(),
            has_real_time=False,
            detail=f"no LegEvent event matching (bill={bill}, date={date}, "
                   f"chamber={signals['chamber_used'] or '?'})"
                   + other_chamber_note,
        )

    # Distinct non-empty EventCodes among chamber-matched events.
    codes = []
    for e in matched:
        code = safe_str(e.get("EventCode"))
        if code and code not in codes:
            codes.append(code)
    codes_tuple = tuple(codes)
    any_real_time = bool(signals["real_time_events"])

    if not codes_tuple:
        return RowCategory(
            linkage_class=CLASS_E_EVENTCODE_MISSING,
            matched_event_count=len(matched),
            event_codes=(),
            has_real_time=any_real_time,
            detail=f"matched {len(matched)} event(s) for (bill={bill}, "
                   f"date={date}, chamber={signals['chamber_used'] or '?'}) "
                   f"but EventCode null/empty on all — FRAGILE DATA",
        )

    if any_real_time and signals["best_token_overlap"] > 0:
        return RowCategory(
            linkage_class=CLASS_B_HAS_TIME,
            matched_event_count=len(matched),
            event_codes=codes_tuple,
            has_real_time=True,
            detail=f"matched {len(matched)} chamber-event(s); real time + "
                   f"token overlap={signals['best_token_overlap']}; "
                   f"codes={','.join(codes_tuple)} — production resolver would have recovered",
        )

    # Class C — matched, EventCode present, but resolver would NOT have
    # used a time. Distinguish sub-reason in the detail for triage.
    if not any_real_time:
        sub = "no real-time event for chamber"
    else:
        sub = f"real-time events exist but zero token overlap with outcome (best={signals['best_token_overlap']})"
    return RowCategory(
        linkage_class=CLASS_C_NO_TIME,
        matched_event_count=len(matched),
        event_codes=codes_tuple,
        has_real_time=any_real_time,
        detail=f"matched {len(matched)} chamber-event(s); resolver would NOT recover ({sub}); "
               f"codes={','.join(codes_tuple)}",
    )
