"""
PR-C2.1: Playwright-based recovery scraper for LIS Meeting Schedule.

Triggered by `calendar_worker.py` Part C reconciliation when CONFIRMED
BLIND-WINDOW LOSS is emitted for a historical date — the Schedule API only
returns current-window meetings, so this module fetches the LIS web page
(a React SPA) to recover times and locations for past meetings the API
has dropped.

Design constraints (Gemini round-2 concerns #2 and #3):
- Uses `wait_for_selector()` bound to the schedule-table DOM, NOT
  `wait_for_load_state("networkidle")`. Bloated government sites rarely
  reach true network idle (broken background trackers / analytics);
  networkidle hangs indefinitely.
- Per-date timeout ≥ 15s. The earlier 5s budget was too tight for LIS
  during peak session and produced false-positive timeouts on slow
  historical-database queries.

Architectural guarantees:
- Never raises into the worker. All failures are categorized and returned
  via the `errors` field for the caller to log via `push_system_alert`.
- Idempotent: same date + same LIS state → same output.
- Self-validating: empty selector match on a date that should have meetings
  is treated as a SCRAPE FAILURE (not "no meetings"), and the caller is
  expected to alert.

Tagged in:
- docs/architecture/calendar_pipeline.md (PR-C2.1 section)
- docs/ideas/future_improvements.md (PR-C2.1 entry + Location backfill)
- CLAUDE.md Standard #1 (Zero Assumptions): the URL/selector constants
  below are documented heuristics, validated at runtime.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ============================================================================
# LIS DOM contract — VERIFY before first production run.
# ----------------------------------------------------------------------------
# These constants encode our assumptions about the LIS Meeting Schedule
# web page. They WILL drift if LIS rebuilds their frontend. The runtime
# validation in `_classify_scrape_result()` below treats an empty selector
# match as a SCRAPE FAILURE (not "no meetings"), so the caller alerts on
# selector drift.
#
# Alternative selectors are tried in order — the LIS page may render rows
# in either a `<table>` or a `<div>` grid depending on viewport / build
# version. The first selector that returns ≥1 row wins.
# ============================================================================

# Web URL — the API endpoint is /Schedule/api/getschedulelistasync, so the
# user-facing schedule lives under /Schedule/. Date is passed via query string;
# the SPA's date-picker mounts initial state from `?date=`.
SCHEDULE_URL_TEMPLATE = "https://lis.virginia.gov/Schedule?date={date}"

# Wait for the schedule-table container before scraping. Try multiple
# selectors in case the LIS frontend uses different markup in different
# states (loading vs. loaded vs. zero-meetings).
SCHEDULE_CONTAINER_SELECTORS = [
    "table.meeting-schedule",
    "div.meeting-schedule",
    "[data-component='meeting-schedule']",
    "main table",  # generic fallback
]

# Per-row selector. Must match within the container.
ROW_SELECTORS = [
    "tbody tr",
    "tr.meeting-row",
    "div.meeting-row",
    "[data-row='meeting']",
]

# Field selectors within a row. Each is tried in order; first non-empty wins.
COMMITTEE_FIELD_SELECTORS = [
    "[data-field='committee']",
    ".meeting-committee",
    "td:nth-child(2)",
]
TIME_FIELD_SELECTORS = [
    "[data-field='time']",
    ".meeting-time",
    "td:nth-child(1)",
]
LOCATION_FIELD_SELECTORS = [
    "[data-field='location']",
    ".meeting-location",
    ".meeting-room",
    "td:nth-child(3)",
]
STATUS_FIELD_SELECTORS = [
    "[data-field='status']",
    ".meeting-status",
    ".cancelled-marker",
]

# ============================================================================
# Timeouts (Gemini round-2 concern #3: ≥ 15s per date)
# ============================================================================
DEFAULT_SELECTOR_TIMEOUT_MS = 15_000
DEFAULT_NAVIGATION_TIMEOUT_MS = 20_000  # slightly more for goto() than for selectors


# ============================================================================
# Public API
# ============================================================================

def scrape_historical_schedule(
    date_str: str,
    selector_timeout_ms: int = DEFAULT_SELECTOR_TIMEOUT_MS,
    navigation_timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
) -> Dict[str, Any]:
    """Fetch and parse the LIS Meeting Schedule page for a historical date.

    Args:
        date_str: ISO date string `YYYY-MM-DD`.
        selector_timeout_ms: `wait_for_selector` budget. MUST be ≥ 15_000.
        navigation_timeout_ms: `page.goto` budget. Defaults to 20_000.

    Returns:
        {
            "date": "<date_str>",
            "url": "<resolved URL>",
            "meetings": [
                {
                    "committee": str,
                    "time": str,        # raw, e.g. "10:00 AM"
                    "sort_time": str,   # 24h normalized, e.g. "10:00"
                    "status": str,      # "" or "CANCELLED" or other LIS status
                    "location": str,
                    "raw_text": str,    # full row text for debugging
                },
                ...
            ],
            "errors": [str, ...],  # categorized failures; empty on success
        }

    Failure semantics:
        - Empty `meetings` + non-empty `errors` => SCRAPE FAILED. Caller
          MUST NOT interpret this as "no meetings that day" — Part C
          already established the date had meeting-verb HISTORY actions.
        - Empty `meetings` + empty `errors` => unreachable; would imply
          the LIS page rendered with the schedule-table container but
          zero rows, which we treat as a categorized failure
          ("container_matched_no_rows").
    """
    if selector_timeout_ms < 15_000:
        # Hard contract — Gemini round-2 concern #3.
        raise ValueError(
            f"selector_timeout_ms must be ≥ 15000 (got {selector_timeout_ms}). "
            f"LIS historical-database queries can take > 5s during peak session; "
            f"a tighter budget produces false-positive timeouts."
        )

    if not _is_valid_iso_date(date_str):
        return {
            "date": date_str,
            "url": "",
            "meetings": [],
            "errors": [f"invalid_date_format: expected YYYY-MM-DD, got {date_str!r}"],
        }

    url = SCHEDULE_URL_TEMPLATE.format(date=date_str)
    result: Dict[str, Any] = {
        "date": date_str,
        "url": url,
        "meetings": [],
        "errors": [],
    }

    # Lazy import — Playwright is only needed when the recovery path actually
    # fires, which is rare. Importing at module top would force every worker
    # cycle (every 15min) to load Playwright even when no scrape happens.
    try:
        from playwright.sync_api import (
            Error as PlaywrightError,
            TimeoutError as PlaywrightTimeoutError,
            sync_playwright,
        )
    except ImportError as e:
        result["errors"].append(
            f"playwright_not_installed: {e}. "
            f"Install via `pip install playwright && python -m playwright install chromium`."
        )
        return result

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page()

                # PER-DATE TIMEOUT: navigation budget.
                try:
                    page.goto(url, timeout=navigation_timeout_ms, wait_until="domcontentloaded")
                except PlaywrightTimeoutError:
                    result["errors"].append(
                        f"navigation_timeout: page.goto({url!r}) exceeded "
                        f"{navigation_timeout_ms}ms"
                    )
                    return result
                except PlaywrightError as e:
                    result["errors"].append(f"navigation_error: {e}")
                    return result

                # SELECTOR WAIT (Gemini round-2 concern #2 — NOT networkidle).
                container_handle = None
                container_selector_used = ""
                for selector in SCHEDULE_CONTAINER_SELECTORS:
                    try:
                        container_handle = page.wait_for_selector(
                            selector, timeout=selector_timeout_ms, state="attached"
                        )
                        if container_handle is not None:
                            container_selector_used = selector
                            break
                    except PlaywrightTimeoutError:
                        # Try the next candidate; only alert if all fail.
                        continue

                if container_handle is None:
                    result["errors"].append(
                        f"container_selector_drift: none of "
                        f"{SCHEDULE_CONTAINER_SELECTORS!r} matched within "
                        f"{selector_timeout_ms}ms — verify LIS DOM contract."
                    )
                    return result

                # Locate row elements within the container.
                row_handles: List[Any] = []
                for row_selector in ROW_SELECTORS:
                    candidates = container_handle.query_selector_all(row_selector)
                    if candidates:
                        row_handles = candidates
                        break

                if not row_handles:
                    # Container matched but contains no rows — this is a
                    # SCRAPE FAILURE, not "no meetings": Part C only invokes
                    # us for dates that have meeting-verb HISTORY rows.
                    result["errors"].append(
                        f"container_matched_no_rows: {container_selector_used!r} "
                        f"is present but none of {ROW_SELECTORS!r} found rows. "
                        f"Verify LIS DOM contract for date {date_str}."
                    )
                    return result

                for row in row_handles:
                    parsed = _parse_meeting_row(row)
                    if parsed is not None:
                        result["meetings"].append(parsed)

                if not result["meetings"]:
                    result["errors"].append(
                        f"all_rows_unparseable: {len(row_handles)} row(s) found "
                        f"but none yielded a (committee, time) pair. Field "
                        f"selectors may have drifted."
                    )
            finally:
                browser.close()
    except Exception as e:
        result["errors"].append(f"playwright_unexpected: {type(e).__name__}: {e}")

    return result


# ============================================================================
# Internal helpers
# ============================================================================

def _is_valid_iso_date(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""))


def _parse_meeting_row(row_handle: Any) -> Optional[Dict[str, str]]:
    """Extract a single meeting from a row element handle.

    Returns None if the row lacks both a committee and a time — those rows
    are treated as header / spacer rows and silently skipped (caller will
    surface "all_rows_unparseable" if no rows yield data).
    """
    try:
        raw_text = (row_handle.inner_text() or "").strip()
    except Exception:
        raw_text = ""

    committee = _first_nonempty_field(row_handle, COMMITTEE_FIELD_SELECTORS)
    time_str = _first_nonempty_field(row_handle, TIME_FIELD_SELECTORS)
    location = _first_nonempty_field(row_handle, LOCATION_FIELD_SELECTORS)
    status = _first_nonempty_field(row_handle, STATUS_FIELD_SELECTORS)

    if not committee and not time_str:
        return None

    return {
        "committee": committee,
        "time": time_str,
        "sort_time": _normalize_sort_time(time_str),
        "status": _normalize_status(status, raw_text),
        "location": location,
        "raw_text": raw_text,
    }


def _first_nonempty_field(row_handle: Any, selectors: List[str]) -> str:
    for sel in selectors:
        try:
            el = row_handle.query_selector(sel)
        except Exception:
            continue
        if el is None:
            continue
        try:
            value = (el.inner_text() or "").strip()
        except Exception:
            continue
        if value:
            return value
    return ""


def _normalize_sort_time(time_str: str) -> str:
    """Convert '10:00 AM' / '1:45 PM' / '12:00 PM' to 24-hour 'HH:MM'.

    Returns "" if the input is empty or non-parseable. Mirrors the worker's
    own time-parsing semantics so recovered rows merge cleanly into
    `api_schedule_map` next cycle.
    """
    if not time_str:
        return ""
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?\s*$", time_str.strip())
    if not m:
        return ""
    hour = int(m.group(1))
    minute = int(m.group(2))
    meridiem = (m.group(3) or "").upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return ""
    return f"{hour:02d}:{minute:02d}"


def _normalize_status(status_str: str, raw_text: str) -> str:
    """Return 'CANCELLED' if the status field or row text indicates cancellation.

    Matches the worker's existing `IsCancelled` semantics from the live API
    branch so witness/cache rows from recovery look identical to live rows.
    """
    haystack = f"{status_str} {raw_text}".lower()
    if "cancel" in haystack:
        return "CANCELLED"
    return ""
