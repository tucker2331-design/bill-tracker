"""LIS API authorization rule — SINGLE SOURCE OF TRUTH (import everywhere).

The LIS Developers Portal (lis.virginia.gov/developers) authorizes the API toolset
(lis.virginia.gov/*/api/* AND the lis.blob.core.windows.net/lisfiles/* CSVs) for the
**2025 and 2026 sessions ONLY**. Data prior to 2025 is NOT authorized through this API
and must be pulled from legacylis.virginia.gov via CSV. Calling the new API for an
unauthorized session risks an API BAN — so every code path that hits LIS must check the
session through here FIRST. Authoritative note: docs/knowledge/lis_api_authorization.md.

When the General Assembly authorizes a new session (the portal banner says "you will be
notified"), add its 5-digit code to LIS_API_AUTHORIZED_SESSIONS below — that is the ONLY
edit needed, and it is a deliberate, ban-safe annual checkpoint (NOT routine maintenance):
we would rather halt-and-alert on an unconfirmed session than risk the ban.
"""

# 5-digit MVC session codes. Regular sessions: "20" + YY + "1" (2025 -> 20251, 2026 -> 20261).
# Widen ONLY when LIS notifies that a new session is authorized.
LIS_API_AUTHORIZED_SESSIONS = frozenset({"20251", "20261"})


def normalize_session_code(session_code) -> str:
    """Best-effort 5-digit normalization so the check is robust to legacy 3-digit forms
    ("261" -> "20261"). Unknown shapes are returned stripped (and will fail the check)."""
    s = str(session_code or "").strip()
    if len(s) == 3 and s.isdigit():   # legacy 3-digit -> MVC 5-digit
        return "20" + s
    return s


def is_authorized_session(session_code) -> bool:
    return normalize_session_code(session_code) in LIS_API_AUTHORIZED_SESSIONS


def assert_lis_authorized(session_code) -> str:
    """Raise unless the session is LIS-authorized. Call this BEFORE any lis.virginia.gov
    or lisfiles request. Returns the normalized 5-digit code on success."""
    s = normalize_session_code(session_code)
    if s not in LIS_API_AUTHORIZED_SESSIONS:
        raise PermissionError(
            f"LIS API authorization violation: session {s!r} is not authorized "
            f"({sorted(LIS_API_AUTHORIZED_SESSIONS)} = 2025/2026 only). Pre-2025 data must "
            f"use legacylis.virginia.gov CSV. Calling the new API for an unauthorized session "
            f"risks an API ban. If LIS has authorized this session, add it to "
            f"LIS_API_AUTHORIZED_SESSIONS (docs/knowledge/lis_api_authorization.md)."
        )
    return s
