"""Polite fetcher for California's pubinfo bulk files (the PA rules, applied to CA).

  * BULK FILES ONLY: a URL must be a pubinfo file on downloads.leginfo.legislature.ca.gov. The interactive site
    (leginfo.legislature.ca.gov) is behind a bot challenge and is refused before any request is made.
  * NO MORE OFTEN THAN PUBLISHED: Legislative Counsel publishes once a day, so a URL fetched in the last
    `min_interval` seconds (default 20 h) is served from the on-disk cache.
  * STREAMED TO DISK: the session file is ~1.2 GB; it is never held in memory. Returns the cached file's path.
  * HONEST USER-AGENT naming the project and its public repo; a 401/403/429 STOPS the intake (no retry, no header
    change) — a human decides what happens next.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

from .pa_fetch import USER_AGENT, FeedRefused, NotABulkFeed

_ALLOWED = (
    re.compile(r"^https://downloads\.leginfo\.legislature\.ca\.gov/$"),
    re.compile(r"^https://downloads\.leginfo\.legislature\.ca\.gov/pubinfo_(\d{4}|daily_[A-Z][a-z]{2}|[A-Z][a-z]{2}|load)\.zip$"),
)
DEFAULT_MIN_INTERVAL = 20 * 3600


class BulkFetcher:
    def __init__(self, cache_dir: str, min_interval: float = DEFAULT_MIN_INTERVAL,
                 opener: Optional[Callable] = None, clock: Callable[[], float] = time.time):
        self.cache_dir, self.min_interval = cache_dir, min_interval
        self.opener = opener or (lambda req, t: urllib.request.urlopen(req, timeout=t))
        self.clock = clock
        self.requests_made = 0
        os.makedirs(cache_dir, exist_ok=True)

    def path(self, url: str) -> str:
        if not any(p.match(url) for p in _ALLOWED):
            raise NotABulkFeed(f"refusing to request {url!r}: only California's pubinfo bulk files are fetched")
        key = hashlib.sha256(url.encode()).hexdigest()[:24]
        body_p, meta_p = os.path.join(self.cache_dir, key + ".body"), os.path.join(self.cache_dir, key + ".meta.json")
        if os.path.exists(meta_p) and os.path.exists(body_p):
            with open(meta_p, encoding="utf-8") as f:
                meta = json.load(f)
            if self.clock() - meta["fetched_at"] < self.min_interval:
                return body_p
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        self.requests_made += 1
        tmp = body_p + ".part"
        try:
            with self.opener(req, 600) as resp, open(tmp, "wb") as out:
                shutil.copyfileobj(resp, out, length=1 << 20)
                status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429):
                raise FeedRefused(f"{url} answered HTTP {e.code}; intake stopped — no retry, no header change "
                                  f"(owner rule). A human decides what to do next.") from None
            raise
        os.replace(tmp, body_p)
        with open(meta_p, "w", encoding="utf-8") as f:
            json.dump({"url": url, "fetched_at": self.clock(), "status": status, "bytes": os.path.getsize(body_p)}, f)
        return body_p

    def get(self, url: str) -> bytes:
        with open(self.path(url), "rb") as f:
            return f.read()
