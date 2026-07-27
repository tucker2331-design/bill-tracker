#!/usr/bin/env python3
"""Open States request budget — the hard ceiling that keeps us a welcome API consumer (W6).

THE LIMITS WE WERE GIVEN (owner-reported from the account page, 2026-07-27, recorded in
docs/knowledge/legiscan_terms.md): **500 requests/day, paced at 1 request/second.** Their ToS reserves the
right to block anyone who *"attempted to exceed or circumvent these limits."*

WHY THIS FILE EXISTS RATHER THAN A `time.sleep()` AT THE CALL SITE
LIS-safety guardrail #4: the cap must be an ABSOLUTE runaway guard that lives OUTSIDE the calling logic, so a
bug in a loop can never spike us into a ban. A sleep sprinkled at one call site protects only that call site.

WE SIT DELIBERATELY BELOW THEIRS. 500/day → our 400 (80%); 1/s → our 1.2s spacing (20% slower). Headroom is
the point: a race, a retry, or a clock skew must not put us at their edge. Absence of enforcement is not
permission.

THE ARCHITECTURAL CONSEQUENCE, STATED PLAINLY: 500/day is ~0.35 req/min sustained. A single state's bill
texts would take MONTHS to pull through the API, so the API can never be the corpus path — **bulk downloads
are, and they cost zero API calls.** The API is for targeted lookups only (a specific bill, a spot-check).
This module exists to make that boundary enforceable rather than a note someone remembers.

Pure + offline-testable: the clock and the persistence layer are injected.
"""
from __future__ import annotations

import json
import os
import time

# Ours, not theirs — see the module docstring. Env-overridable DOWNWARD only (see `_ceiling`).
DAILY_CAP = int(os.environ.get("OPENSTATES_DAILY_CAP", "400"))
MIN_SPACING_S = float(os.environ.get("OPENSTATES_MIN_SPACING_S", "1.2"))
THEIR_DAILY_LIMIT = 500          # documented, for the guard below
THEIR_MIN_SPACING_S = 1.0

STATE_PATH = os.environ.get("OPENSTATES_BUDGET_STATE", ".openstates_budget.json")


class BudgetExceeded(BaseException):
    """A BaseException, deliberately: it must bypass broad `except Exception` handlers the way
    LisRequestCapExceeded does, so a runaway loop aborts the run instead of being swallowed and retried."""


def _ceiling():
    """Clamp our configured cap to something that can never exceed the provider's. An env var is a
    convenience for lowering the cap, never a way to raise it past what we were told we may use."""
    return min(DAILY_CAP, THEIR_DAILY_LIMIT), max(MIN_SPACING_S, THEIR_MIN_SPACING_S)


class RequestBudget:
    """Tracks spend for the current UTC day and enforces spacing.

    `now` and `sleep` are injected so the whole thing is testable without real time passing.
    """

    def __init__(self, state_path=STATE_PATH, now=time.time, sleep=time.sleep):
        self._path, self._now, self._sleep = state_path, now, sleep
        self._last_request_at = 0.0
        self._day, self._count = self._load()

    # ── persistence: the day's spend must survive process restarts, or a crash-loop resets the budget ──
    def _today(self):
        return time.strftime("%Y-%m-%d", time.gmtime(self._now()))

    def _load(self):
        """Resume today's spend. ABSENT and CORRUPT are different events and must not share a handler
        (our own Semgrep house rule caught this file swallowing both — Standard #4).

        * absent  → first run of the day. Expected; silent.
        * corrupt → the day's spend count was LOST, so this process starts from zero and could push us past
          the provider's daily limit without knowing. That is exactly the runaway the budget exists to
          prevent, so it is announced loudly rather than passed over.
        """
        try:
            with open(self._path, encoding="utf-8") as fh:
                d = json.load(fh)
        except FileNotFoundError:
            return self._today(), 0            # expected on the first call of a day
        except (OSError, ValueError) as e:
            print(f"⚠️ [openstates_budget] spend file unreadable ({type(e).__name__}: {e}) — today's count "
                  f"is LOST and restarts at 0. If a run already spent requests today, the provider's daily "
                  f"limit could be exceeded; verify before a large batch.")
            return self._today(), 0
        if isinstance(d, dict) and d.get("day") == self._today() and isinstance(d.get("count"), int):
            return d["day"], d["count"]
        if isinstance(d, dict) and d.get("day") not in (None, self._today()):
            return self._today(), 0            # yesterday's file: a normal rollover, not an anomaly
        print(f"⚠️ [openstates_budget] spend file has an unexpected shape — today's count restarts at 0.")
        return self._today(), 0

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump({"day": self._day, "count": self._count}, fh)
        except OSError as e:
            # Fail-OPEN on persistence, fail-CLOSED on the budget: we still enforce in-process. A lost file
            # can only make us MORE conservative next run (it resets to 0 spend... which is the one risk, so
            # it is surfaced loudly rather than swallowed).
            print(f"⚠️ [openstates_budget] could not persist spend ({e}) — a restart would under-count today.")

    # ── the guard ──────────────────────────────────────────────────────────────────────────────────────
    def remaining(self):
        cap, _ = _ceiling()
        if self._day != self._today():          # UTC rollover resets the day
            self._day, self._count = self._today(), 0
        return cap - self._count

    def spend(self, n=1):
        """Reserve `n` requests. Raises BudgetExceeded rather than letting the caller proceed."""
        cap, spacing = _ceiling()
        if self.remaining() < n:
            raise BudgetExceeded(
                f"Open States daily budget exhausted: {self._count}/{cap} used today "
                f"(their limit is {THEIR_DAILY_LIMIT}/day). Use bulk downloads for corpus work — "
                f"the API is for targeted lookups only.")
        # spacing is enforced BEFORE the count increments, so a caller that catches nothing still waits
        gap = self._now() - self._last_request_at
        if self._last_request_at and gap < spacing:
            self._sleep(spacing - gap)
        self._last_request_at = self._now()
        self._count += n
        self._save()
        return self._count

    def snapshot(self):
        cap, spacing = _ceiling()
        return {"day": self._day, "used": self._count, "cap": cap, "remaining": self.remaining(),
                "spacing_s": spacing, "provider_daily_limit": THEIR_DAILY_LIMIT}
