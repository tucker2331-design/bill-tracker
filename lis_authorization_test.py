"""Unit tests for lis_authorization.py — the ban-safety predicate (A-1 self-extending authorization).

    python3 lis_authorization_test.py   # -> "ALL N lis_authorization tests passed" or raises

Pure, no I/O, no deps. The worker-side probe (calendar_worker.session_follow_gate) is what actually verifies
a new session against LIS; THIS covers the predicate that gate + every tool relies on.
"""
import lis_authorization as a

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


# ── frozen historical set: unchanged, always authorized regardless of active_session ──
ok(a.is_authorized_session("20251"), "20251 historical -> authorized")
ok(a.is_authorized_session("20261"), "20261 historical -> authorized")
ok(a.is_historical_authorized("20251") and a.is_historical_authorized("20261"), "historical predicate")
ok(not a.is_historical_authorized("20271"), "20271 is NOT historical (must be probe-followed, not frozen)")

# ── backward compatibility: tools import LIS_API_AUTHORIZED_SESSIONS and expect the frozen set ──
ok(a.LIS_API_AUTHORIZED_SESSIONS == a.LIS_HISTORICAL_AUTHORIZED == frozenset({"20251", "20261"}),
   "LIS_API_AUTHORIZED_SESSIONS stays a frozen alias of the historical set")

# ── frozen behavior for callers that DON'T pass active_session (every tool/replay) ──
ok(not a.is_authorized_session("20271"), "20271 without active_session -> NOT authorized (frozen behavior)")
ok(not a.is_authorized_session("20241"), "20241 (pre-2025) -> never authorized via this API")

# ── A-1 live-follow: the active session LIS declares is authorized for the workers that pass it ──
ok(a.is_authorized_session("20271", active_session="20271"), "20271 == active -> authorized (A-1 follow)")
ok(not a.is_authorized_session("20271", active_session="20261"),
   "20271 while active is 20261 -> NOT authorized (only the CURRENT active session follows)")
ok(a.is_authorized_session("20251", active_session="20271"),
   "a historical session stays authorized even when a different session is active")

# ── normalization: legacy 3-digit forms normalize on both sides of the active-session compare ──
ok(a.is_authorized_session("271", active_session="20271"), "'271' normalizes to 20271 == active")
ok(a.is_authorized_session("20271", active_session="271"), "active '271' normalizes to 20271")

# ── assert_lis_authorized mirrors the predicate ──
ok(a.assert_lis_authorized("20261") == "20261", "assert returns normalized code on success")
ok(a.assert_lis_authorized("271", active_session="20271") == "20271", "assert follows the active session")
raised = False
try:
    a.assert_lis_authorized("20271")            # no active_session -> frozen -> must raise
except PermissionError:
    raised = True
ok(raised, "assert_lis_authorized('20271') without active_session must raise (ban guard)")
raised = False
try:
    a.assert_lis_authorized("20241", active_session="20271")   # 2024 is neither historical nor active
except PermissionError:
    raised = True
ok(raised, "assert_lis_authorized for a non-historical, non-active session must raise")

print(f"ALL {_checks} lis_authorization tests passed")
