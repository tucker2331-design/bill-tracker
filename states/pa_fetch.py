"""Polite fetcher for Pennsylvania's bulk feeds (owner rules, 2026-10-31).

  * BULK FEEDS ONLY. A URL must match one of PA's feed templates (the Bill History export, the committee-schedule
    RSS, the data index). Anything else — above all a per-bill page under /legislation/bills/, which robots.txt
    protects from crawling — is refused before any request is made.
  * NO MORE OFTEN THAN THE FEEDS UPDATE. The export is hourly and the RSS is per publication; none of them send an
    ETag or Last-Modified (measured 2026-10-31), so conditional GET is impossible and the cap is time-based: a URL
    fetched in the last `min_interval` seconds (default 3600) is served from the on-disk cache, no request at all.
  * ONE REQUEST AT A TIME. A process-wide lock; callers fetch sequentially.
  * AN HONEST USER-AGENT naming the project and its public repo as the contact. Never altered, never a browser string.
  * A 403 (or 401/429) STOPS the intake: `FeedRefused` is raised, nothing is retried, no header is changed. A human
    decides what happens next (owner rule).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

USER_AGENT = "bill-tracker-intake/0.1 (+https://github.com/tucker2331-design/bill-tracker)"   # contact = the repo (owner 2026-11-01)
DEFAULT_MIN_INTERVAL = 3600

# The only URLs this fetcher will request (anchored; www.palegis.us only).
_ALLOWED = (
    re.compile(r"^https://www\.palegis\.us/data$"),
    re.compile(r"^https://www\.palegis\.us/data/file\?documentType=BillHistoryData&session=\d{4}_\d$"),
    re.compile(r"^https://www\.palegis\.us/(house|senate)/rss/[a-z/-]+(\?[A-Za-z]+=[a-z-]+)?$"),
)
_LOCK = threading.Lock()


class FeedRefused(RuntimeError):
    """The host refused us (401/403/429). The intake stops; nothing is retried or disguised."""


class NotABulkFeed(ValueError):
    """The URL is not one of PA's bulk feeds — never requested."""


def _default_opener(req: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(req, timeout=timeout)


class PoliteFetcher:
    def __init__(self, cache_dir: str, min_interval: float = DEFAULT_MIN_INTERVAL,
                 opener: Optional[Callable] = None, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep, spacing: float = 2.0):
        self.cache_dir, self.min_interval = cache_dir, min_interval
        self.opener, self.clock, self.sleep, self.spacing = opener or _default_opener, clock, sleep, spacing
        self.requests_made = 0          # counted, so a run can prove how much it asked for
        self._last_request_at: Optional[float] = None
        os.makedirs(cache_dir, exist_ok=True)

    def _paths(self, url: str):
        key = hashlib.sha256(url.encode()).hexdigest()[:24]
        return os.path.join(self.cache_dir, key + ".body"), os.path.join(self.cache_dir, key + ".meta.json")

    def get(self, url: str) -> bytes:
        if not any(p.match(url) for p in _ALLOWED):
            raise NotABulkFeed(f"refusing to request {url!r}: only PA's bulk feeds are fetched")
        body_p, meta_p = self._paths(url)
        with _LOCK:
            meta = None
            if os.path.exists(meta_p) and os.path.exists(body_p):
                with open(meta_p, encoding="utf-8") as f:
                    meta = json.load(f)
                if self.clock() - meta["fetched_at"] < self.min_interval:
                    with open(body_p, "rb") as f:
                        return f.read()       # fresh enough: no request
            if self._last_request_at is not None:   # space consecutive requests
                wait = self.spacing - (self.clock() - self._last_request_at)
                if wait > 0:
                    self.sleep(wait)
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            self._last_request_at = self.clock()
            self.requests_made += 1
            try:
                with self.opener(req, 60) as resp:
                    body = resp.read()
                    status = getattr(resp, "status", 200)
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 429):
                    raise FeedRefused(f"{url} answered HTTP {e.code}; intake stopped — no retry, no header change "
                                      f"(owner rule). A human decides what to do next.") from None
                raise
            with open(body_p, "wb") as f:
                f.write(body)
            with open(meta_p, "w", encoding="utf-8") as f:
                json.dump({"url": url, "fetched_at": self.clock(), "status": status, "bytes": len(body)}, f)
            return body
