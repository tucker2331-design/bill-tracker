"""Coverage windows as DATA, not typed labels — queue item E4.

WHY THIS EXISTS: mockups v6–v8 render `(2025–2026)` under every statistic. Written as a literal, that string
is true on the day someone types it and silently wrong forever after — the moment a session is added, or a
stat is computed from a narrower slice than the caller assumes. It is the same class as the fabricated
`(2020–2026)` the owner caught: a claim about provenance that nothing verifies.

So a window is computed FROM the rows a figure was actually derived from, and travels WITH the figure.

Two rules the type enforces rather than documents:

1. **A window describes the data that produced the number, not the data we wish we had.** If a member's
   record only covers 20261 because they were seated in 2026, the label says 2026 — not 2025–2026 with a
   silent gap.

2. **Zero rows yields a window of None, never a plausible-looking span.** "No data" and "data covering
   2025–2026" must not render identically (Standard #4; the sentinel-collision trap, audit #53).

The authorised span is 2025–2026 ([[knowledge/lis_api_authorization]]). Nothing here may present a wider
one: `AUTHORIZED_SESSIONS` is the ceiling and `Coverage.exceeds_authorized()` is the check.
"""
from __future__ import annotations

from dataclasses import dataclass

# The authorised set is IMPORTED, never re-declared. `lis_authorization.py` calls itself the SINGLE SOURCE
# OF TRUTH for this rule, and a second copy here would be a compliance rule that can drift silently -- the
# worst possible thing to duplicate. (Caught by the code gate's Standard #6 check on first write.)
#
# ⚠ VIRGINIA-SPECIFIC, and knowingly so: these are LIS session codes. New York's authorised span is a
# different vocabulary entirely (docs/ny/). When state #2 lands, this becomes a per-state lookup rather
# than a module constant -- flagged here so the seam is visible before it is load-bearing.
try:
    from lis_authorization import LIS_HISTORICAL_AUTHORIZED as AUTHORIZED_SESSIONS
except ImportError:  # pragma: no cover - import path differs when run from tools/votes/
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from lis_authorization import LIS_HISTORICAL_AUTHORIZED as AUTHORIZED_SESSIONS


def session_year(session_code: str) -> int | None:
    """`20261` -> 2026. Returns None for anything that is not a 5-digit session code.

    Never guesses: an unparseable code must not silently become a year, because that year would then appear
    under a statistic as if it were sourced.
    """
    code = (session_code or "").strip()
    if len(code) != 5 or not code.isdigit():
        return None
    return int(code[:4])


@dataclass(frozen=True)
class Coverage:
    """The span a figure was actually computed over, plus the sessions that produced it."""

    sessions: tuple[str, ...]

    @property
    def years(self) -> tuple[int, ...]:
        ys = {y for s in self.sessions if (y := session_year(s)) is not None}
        return tuple(sorted(ys))

    @property
    def unparseable(self) -> tuple[str, ...]:
        """Session codes we could not read. Surfaced, never dropped (Standard #4)."""
        return tuple(s for s in self.sessions if session_year(s) is None)

    def label(self) -> str | None:
        """`(2026)` or `(2025–2026)`. **None when there is nothing to describe.**

        Returning None rather than a placeholder is the point: a caller must render absence as absence. An
        en-dash is used for the range because it is a span, not a subtraction.
        """
        ys = self.years
        if not ys:
            return None
        return f"({ys[0]})" if len(ys) == 1 else f"({ys[0]}–{ys[-1]})"

    def exceeds_authorized(self) -> tuple[str, ...]:
        """Sessions outside the authorised set. Non-empty means a figure is claiming data we may not use."""
        return tuple(s for s in self.sessions if s not in AUTHORIZED_SESSIONS)

    def is_complete_over(self, expected: frozenset[str]) -> bool:
        """True when this figure covers every session the caller expected.

        The honest use: a member's 'voted with us 1 of 6' may cover only one session while the committee
        stat beside it covers two. Adjacent numbers with different windows are not comparable, and this is
        how a caller detects that instead of assuming.
        """
        return expected.issubset(set(self.sessions))


def coverage_from(session_codes) -> Coverage:
    """Build a Coverage from whatever sessions actually contributed rows.

    Deduplicated and sorted so two figures over the same sessions compare equal regardless of input order.
    Blank entries are dropped here (they carry no claim); malformed non-blank ones are KEPT so
    `unparseable` can report them.
    """
    seen = {str(s).strip() for s in (session_codes or []) if str(s).strip()}
    return Coverage(sessions=tuple(sorted(seen)))


def coverage_of_votes(vote_history, member_number: str, session_code: str) -> Coverage:
    """Coverage for one member's record.

    `VoteHistory` holds ONE session per parse, so this reports that session only if the member actually
    voted in it. A member with no votes yields an EMPTY coverage — label() is then None, and the caller must
    show "no record", not "(2026)" over a zero.
    """
    votes = getattr(vote_history, "by_member", {}).get(member_number) or {}
    return coverage_from([session_code] if votes else [])
