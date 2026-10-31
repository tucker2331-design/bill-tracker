"""Virginia's SOURCE adapter for the bill pipeline: LIS session discovery, the authorization gate, the guarded
(counted, truncation-checked) blob fetch, and the structural committee resolver.

The machinery itself lives in calendar_worker + lis_authorization and is SHARED with the calendar worker (one
probe cache, one request counter — LIS-safety guardrails #1/#4). This module only names it, so bill_tracker asks
`STATE.adapter` for its source rather than importing Virginia's modules directly. A new state supplies a module
with the same names (see the list in __all__) or does not use bill_tracker's LIS-shaped pipeline at all — PA's
XML intake is its own adapter (states/pa_adapter.py) because its source contract is different.
"""
from calendar_worker import (  # noqa: F401  (re-exported — the adapter contract)
    safe_fetch_csv,
    get_armored_session,
    get_active_session_info,
    build_committee_maps,
    resolve_committee_from_refid,
    notify_slack,
    session_follow_gate,
    HEADERS,
    SPREADSHEET_ID,
)
from lis_authorization import normalize_session_code  # noqa: F401  (5-digit LIS session code, e.g. "20261")
import calendar_worker as _cw


def committee_name_for_code(code):
    """LIS committee CODE ("S01") -> chamber-qualified name ("Senate Agriculture, ..."), or "" when unknown.

    Reads calendar_worker.COMMITTEE_CODE_MAP at CALL time: build_committee_maps() REBINDS that global from the
    Committee API each cycle, so a name imported once at module load would keep serving the static fallback."""
    return _cw.COMMITTEE_CODE_MAP.get(str(code).strip().upper(), "")

__all__ = ["safe_fetch_csv", "get_armored_session", "get_active_session_info", "build_committee_maps",
           "resolve_committee_from_refid", "notify_slack", "session_follow_gate", "HEADERS", "SPREADSHEET_ID",
           "normalize_session_code", "committee_name_for_code"]
