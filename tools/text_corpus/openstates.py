#!/usr/bin/env python3
"""Open States (Plural Open) client — targeted lookups ONLY, under a hard budget.

SCOPE, AND WHY IT IS NARROW (docs/knowledge/legiscan_terms.md): the account's limits are **500 requests/day
paced at 1/second**. That is ~0.35 req/min sustained, so the API can never be the corpus path — a single
state's bill texts would take months. **Bulk downloads are the corpus** (they cost zero API calls); this
client exists for targeted lookups, spot-checks, and the parity probe.

SAFETY POSTURE (mirrors knowledge/lis_api_safety.md, applied to a second upstream):
  * every request passes through `RequestBudget` — a hard cap OUTSIDE the calling logic (guardrail #4)
  * 1.2s spacing, 20% slower than required (guardrail #2/#5 — never sit on a provider's edge)
  * retries respect Retry-After and back off; a 429 is treated as a STOP, not a speed bump (guardrail #3)
  * the API key is read from the environment and NEVER logged, echoed, or included in an error message
  * read-only: this module has no write verbs and never will

TRUST CLASS (docs/design/information_display.md P24a/P25c): data from here is **sourced-at-one-remove** —
another state's official record, relayed by a provider whose ToS says "as-is" with "no warranty that the
Services will be error free". It must be labeled `via Open States` on any surface and must NEVER inherit the
verified treatment our LIS-checked Virginia data receives.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from budget import RequestBudget  # noqa: E402  (BudgetExceeded propagates from RequestBudget.spend)

BASE = "https://v3.openstates.org"
KEY_ENV = "OPENSTATES_API_KEY"
TIMEOUT_S = 30
ATTRIBUTION = "Bill text and cross-state data via Open States (openstates.org)."


class OpenStatesError(Exception):
    """A failure the caller should surface, never swallow. Carries no key material."""


class OpenStates:
    def __init__(self, api_key=None, budget=None, session=None):
        self._key = api_key or os.environ.get(KEY_ENV) or ""
        self._budget = budget or RequestBudget()
        self._session = session
        # Presence is tracked as a BOOLEAN, not by truthiness of the value elsewhere in the code
        # (pre-push #15: a sentinel must not be confusable with a legitimate runtime value).
        self.has_key = bool(self._key)

    def _http(self):
        if self._session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            s = requests.Session()
            # Respect Retry-After; do NOT retry 429 automatically — a rate-limit response means we were
            # already too fast, so hammering it is exactly the behaviour their ToS calls circumvention.
            s.mount("https://", HTTPAdapter(max_retries=Retry(
                total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504],
                respect_retry_after_header=True, allowed_methods=["GET"])))
            self._session = s
        return self._session

    def get(self, path, **params):
        """One budgeted GET. Raises BudgetExceeded (a BaseException) when the day's cap is spent."""
        if not self.has_key:
            raise OpenStatesError(
                f"{KEY_ENV} is not set — refusing to call the API. (Set it as a GitHub Actions "
                f"repository secret; corpus work should use bulk downloads, which need no key.)")
        self._budget.spend(1)                    # blocks for spacing, raises at the ceiling
        url = f"{BASE}{path}"
        try:
            r = self._http().get(url, headers={"X-API-KEY": self._key, "Accept": "application/json"},
                                 params=params, timeout=TIMEOUT_S)
        except Exception as e:                   # network-layer failure: report the TYPE, never the request
            raise OpenStatesError(f"request to {path} failed: {type(e).__name__}") from None
        if r.status_code == 429:
            raise OpenStatesError(
                f"429 rate-limited on {path} — we are pacing at {self._budget.snapshot()['spacing_s']}s and "
                f"have used {self._budget.snapshot()['used']} today. STOP and re-check the budget; do not retry.")
        if r.status_code in (401, 403):
            raise OpenStatesError(f"{r.status_code} on {path}: the key was rejected (key value NOT logged).")
        if r.status_code >= 400:
            raise OpenStatesError(f"HTTP {r.status_code} on {path}")
        try:
            return r.json()
        except ValueError:
            raise OpenStatesError(f"non-JSON response from {path} (HTTP {r.status_code})") from None

    # ── the few targeted lookups we actually need ──────────────────────────────────────────────────────
    def bill(self, state, session, bill_id, include=("sources", "versions")):
        """One bill. `include=versions` is what carries text links — the field the corpus design hangs on."""
        params = {}
        for i, inc in enumerate(include):
            params[f"include{i}"] = inc
        # the v3 route is /bills/{jurisdiction}/{session}/{bill_id}
        return self.get(f"/bills/{state}/{session}/{bill_id}", **params)

    def budget_snapshot(self):
        return self._budget.snapshot()


def redact(text, key=None):
    """Belt-and-braces: strip a key from anything about to be printed. The client never logs the key, but a
    caller printing a raw exception from some other library must not be able to leak it either."""
    k = key or os.environ.get(KEY_ENV) or ""
    return text.replace(k, "***REDACTED***") if k else text
