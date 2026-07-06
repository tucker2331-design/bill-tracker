"""LIS API authorization rule — SINGLE SOURCE OF TRUTH (import everywhere).

The LIS Developers Portal (lis.virginia.gov/developers) authorizes the API toolset
(lis.virginia.gov/*/api/* AND the lis.blob.core.windows.net/lisfiles/* CSVs) for the
**2025 and 2026 sessions ONLY**. Data prior to 2025 is NOT authorized through this API
and must be pulled from legacylis.virginia.gov via CSV. Calling the new API for an
unauthorized session risks an API BAN — so every code path that hits LIS must check the
session through here FIRST. Authoritative note: docs/knowledge/lis_api_authorization.md.

## A-1 (2026-07-05): self-extending authorization (zero-touch — Standard #8)
Previously the authorized set was a frozen `{20251, 20261}` that HALTED on any new session
(e.g. 20271), requiring an annual human edit. Per the owner (autonomy_upgrades A-1), the
live workers now **auto-follow the session LIS's own Session API declares active** — but
only after a one-time HTTP probe verifies the key is actually authorized for it (200 +
non-empty ⇒ proceed; 401/403 ⇒ halt, exactly as before). Two authorization scopes:

  * `LIS_HISTORICAL_AUTHORIZED` — the FROZEN, human-curated set of past sessions we KNOW are
    authorized. Replays / diagnostics / tools may NEVER exceed this without an explicit owner
    edit — this is the anti-2020–2024-replay guard, and it stays frozen forever.
  * the **live active session** — passed in per call by the live workers from
    `get_active_session_info()`. `is_authorized_session(code, active_session=...)` treats the
    currently-active session as authorized so the workers don't halt on a rollover; the ban
    safety comes from the worker's one-time probe (see calendar_worker.session_follow_gate),
    NOT from trusting the code blindly.

Callers that pass ONLY `code` (every tool/replay) get the UNCHANGED frozen-set behavior.
`LIS_API_AUTHORIZED_SESSIONS` remains as a backward-compat alias of the historical set.
"""

# 5-digit MVC session codes. Regular sessions: "20" + YY + "1" (2025 -> 20251, 2026 -> 20261).
# FROZEN human-curated allowlist of KNOWN-authorized past sessions. Widen ONLY with an explicit owner edit
# (the anti-replay guard). The LIVE workers additionally auto-follow the active session via the probe gate;
# they do NOT edit this set. Historical sessions authorized off-portal would be added here by hand.
LIS_HISTORICAL_AUTHORIZED = frozenset({"20251", "20261"})

# Backward-compat alias: every existing importer (tools, replays, backend_worker) keeps frozen semantics.
LIS_API_AUTHORIZED_SESSIONS = LIS_HISTORICAL_AUTHORIZED


def normalize_session_code(session_code) -> str:
    """Best-effort 5-digit normalization so the check is robust to legacy 3-digit forms
    ("261" -> "20261"). Unknown shapes are returned stripped (and will fail the check)."""
    # `None`-safe WITHOUT `x or ""` boolean coercion (an odd falsy input must not silently blank; CodeRabbit).
    s = "" if session_code is None else str(session_code).strip()
    if len(s) == 3 and s.isdigit():   # legacy 3-digit -> MVC 5-digit
        return "20" + s
    return s


def is_historical_authorized(session_code) -> bool:
    """True iff the session is in the FROZEN historical allowlist (no auto-follow). This is the check the
    tools/replays want: they must never touch a session a human hasn't vetted."""
    return normalize_session_code(session_code) in LIS_HISTORICAL_AUTHORIZED


def is_authorized_session(session_code, active_session=None) -> bool:
    """True iff `session_code` may be queried.

    - Always True for a session in the frozen `LIS_HISTORICAL_AUTHORIZED` set.
    - Also True when `active_session` is supplied AND equals `session_code` — i.e. the live workers pass the
      Session-API-declared active session, and A-1 lets them follow it. Ban safety for a NEW active session
      comes from the worker's one-time probe (calendar_worker.session_follow_gate), not from this predicate.
    - Callers that omit `active_session` (all tools/replays) get the unchanged frozen-set behavior.
    """
    code = normalize_session_code(session_code)
    if code in LIS_HISTORICAL_AUTHORIZED:
        return True
    if active_session is None:
        return False
    active = normalize_session_code(active_session)
    # FAIL CLOSED: both sides must be non-empty, else two blank/None inputs would compare equal ("" == "")
    # and authorize a phantom session (CodeRabbit — ban-safety fail-open).
    return bool(code and active) and code == active


def assert_lis_authorized(session_code, active_session=None) -> str:
    """Raise unless the session is LIS-authorized. Call this BEFORE any lis.virginia.gov
    or lisfiles request. Returns the normalized 5-digit code on success. `active_session`
    is the A-1 live-follow escape hatch (see is_authorized_session); omit it for the frozen check."""
    s = normalize_session_code(session_code)
    if not is_authorized_session(s, active_session):
        raise PermissionError(
            f"LIS API authorization violation: session {s!r} is not authorized "
            f"(historical {sorted(LIS_HISTORICAL_AUTHORIZED)} = 2025/2026 only"
            f"{'' if active_session is None else f', active={normalize_session_code(active_session)!r}'}). "
            f"Pre-2025 data must use legacylis.virginia.gov CSV. Calling the new API for an unauthorized "
            f"session risks an API ban. If LIS authorized a new HISTORICAL session, add it to "
            f"LIS_HISTORICAL_AUTHORIZED (docs/knowledge/lis_api_authorization.md); the live workers "
            f"auto-follow the active session via the probe gate."
        )
    return s
