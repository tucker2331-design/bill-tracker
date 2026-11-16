"""Google Sheets read/write limit: wait and retry instead of losing the write.

WHY (2026-11-01 22:24 UTC, measured): the bill job and the calendar job started in the same minute and share one
service account. Google's per-minute read quota answered HTTP 429, and the bill job lost its Action_Where and
Bill_Summaries writes AND its own heartbeat (Metrics_History) -- so Health could not even see that the cycle had
failed. The quota is per MINUTE, so waiting it out is the correct response, not giving up.

WHAT: an HTTP client for gspread (`authorize(creds)` -> `gspread.authorize(creds, http_client=client_class())`) that retries ONLY a
429 (rate limit), with waits of 5, 10, 20 and 40 s (75 s in all: past one full quota minute). Anything else -- and a
429 that survives every retry -- raises exactly as before, into each caller's existing alert path.

NOT gspread's own BackOffHTTPClient: it is marked "not production ready", retries 5xx and 408 too, keeps its backoff
counter on the CLASS (never reset between requests), and retries silently.

VISIBLE (Standard #4, no silent fallback): every retry is printed, and `retries()` / `exhausted()` give the cycle's
counts so each worker raises an INFO alert ("hit the limit N times, recovered") or the failure's own WARN.
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Callable, List

# gspread is imported LAZILY (inside client_class / authorize): calendar_worker and bill_tracker import this module at
# load time, and their tests replace gspread with a stub that has no submodules (test_pr_c3_helper_v2.py). A 429 is
# recognised by the error's own HTTP status, not by its class, so the retry needs no gspread import at all.

WAITS_S: List[int] = [5, 10, 20, 40]
_counts = {"retries": 0, "exhausted": 0}


def retries() -> int:
    return _counts["retries"]


def exhausted() -> int:
    return _counts["exhausted"]


def _status(err: BaseException) -> int:
    try:
        return int(err.response.status_code)
    except (AttributeError, TypeError, ValueError):
        return 0   # unknown status: not a rate limit we can prove -> never retried


def call_with_retry(fn: Callable[[], Any], sleep: Callable[[float], None] = time.sleep, label: str = "") -> Any:
    """Run fn(); on a 429 wait and retry per WAITS_S. Pure apart from `sleep` (injected for tests)."""
    for attempt in range(len(WAITS_S) + 1):
        try:
            return fn()
        except Exception as err:   # anything but a provable 429 re-raises untouched, into the caller's own alert path
            if _status(err) != 429:
                raise
            if attempt == len(WAITS_S):
                _counts["exhausted"] += 1
                print(f"⚠️ Sheets rate limit (429) persisted after {len(WAITS_S)} retries{label} — giving up on this call")
                raise
            _counts["retries"] += 1
            print(f"⏳ Sheets rate limit (429){label}: waiting {WAITS_S[attempt]}s, retry {attempt + 1} of {len(WAITS_S)}")
            sleep(WAITS_S[attempt])
    raise AssertionError("unreachable")


@lru_cache(maxsize=1)
def client_class():
    """The retrying gspread HTTP client CLASS. gspread.authorize takes a class and builds it itself
    (gspread 6: Client.__init__ does `self.http_client = http_client(auth, session)`)."""
    from gspread.http_client import HTTPClient

    class RetryingHTTPClient(HTTPClient):
        def request(self, *args: Any, **kwargs: Any):
            method = kwargs.get("method", args[0] if args else "")
            return call_with_retry(lambda: super(RetryingHTTPClient, self).request(*args, **kwargs), label=f" on {method}")

    return RetryingHTTPClient


def authorize(credentials):
    """gspread.authorize with the retrying client -- the one way the workers open Sheets."""
    import gspread
    return gspread.authorize(credentials, http_client=client_class())
