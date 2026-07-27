#!/usr/bin/env python3
"""Virginia bill-text ingest — the first NATIVE state scanner (W2).

WHY NATIVE FIRST: the standing per-state rule (docs/knowledge/legiscan_terms.md) is that every state we
onboard gets its own text scanner, and each one retires that state's aggregator slice. Virginia is the proof
of the pattern — and unlike the aggregator path, **LIS returns full text INLINE** (probe-confirmed
2026-07-17: `DraftText`, ~19 KB for a sample bill), so there is no document-fetch second hop at all.

AUTHORIZATION: hard-gated through `lis_authorization` exactly like every other LIS caller. The API toolset is
authorized for 2025/2026 session data only; pre-2025 must come from legacylis, never this path
(docs/knowledge/lis_api_authorization.md).

SAFETY: obeys the LIS charter (docs/knowledge/lis_api_safety.md) — conditional fetch via a content hash so
unchanged text is never re-downloaded (guardrail #1), a hard per-run request cap (guardrail #4), and no
metronome (this is a per-session backfill, not a per-cycle poll; guardrail #5).

SEPARATION: fetching lives here; comparison lives in `normalize.py`. That keeps the similarity core pure and
offline-testable, and it is what lets a second state swap the FETCHER without touching the math (Standard #6).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)

VERSION_LIST_URL = "https://lis.virginia.gov/LegislationVersion/api/GetLegislationVersionbyBillNumberAsync"
TEXT_BY_ID_URL = "https://lis.virginia.gov/LegislationText/api/GetLegislationTextByIDAsync"

CORPUS_DIR = os.environ.get("VA_TEXT_CORPUS_DIR", ".va_text_corpus")
# Runaway guard, independent of the loop's own logic (guardrail #4). A full session backfill is ~3,600 bills
# × ~3 versions; this cap is a per-RUN ceiling so a bug cannot turn a backfill into a hammering.
REQUEST_CAP = int(os.environ.get("VA_TEXT_REQUEST_CAP", "9000"))


class TextRequestCapExceeded(BaseException):
    """BaseException so a broad `except Exception` in a caller cannot swallow a runaway (same choice as
    LisRequestCapExceeded and the Open States budget)."""


def text_digest(text):
    """Content hash — the conditional-fetch key. Hashing the TEXT (not a header) means we detect a real
    change even if the upstream doesn't send validators."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def corpus_path(session_code, bill, version_id):
    return os.path.join(CORPUS_DIR, str(session_code), f"{bill}__v{version_id}.json")


def load_cached(session_code, bill, version_id):
    """Cached record or None. A corrupt cache entry returns None (re-fetch) rather than raising — but it is
    reported, never silently swallowed (Standard #9)."""
    path = corpus_path(session_code, bill, version_id)
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        if isinstance(rec, dict) and "text" in rec:
            return rec
        print(f"⚠️ [va_text] cache entry has no text, re-fetching: {path}")
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        print(f"⚠️ [va_text] unreadable cache entry ({type(e).__name__}), re-fetching: {path}")
    return None


def save_cached(session_code, bill, version_id, record):
    path = corpus_path(session_code, bill, version_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False)
    os.replace(tmp, path)          # atomic: a crash mid-write can never leave a half-written entry
    return path


def _extract_versions(payload):
    """LIS wraps the list; tolerate the wrapper moving without inventing data. Returns [] on an unexpected
    shape rather than guessing, and the caller counts that as a source miss."""
    if not isinstance(payload, dict):
        return []
    for key in ("LegislationsVersion", "LegislationVersions", "Versions"):
        v = payload.get(key)
        if isinstance(v, list):
            return v
    for v in payload.values():     # last resort: the single list in the wrapper
        if isinstance(v, list) and v and isinstance(v[0], dict) and "LegislationTextID" in v[0]:
            return v
    return []


def _extract_text(payload):
    """Pull `DraftText` out of the text payload. Returns "" when absent — never a partial guess."""
    if not isinstance(payload, dict):
        return ""
    lst = payload.get("TextsList")
    if isinstance(lst, list):
        for item in lst:
            if isinstance(item, dict) and item.get("DraftText"):
                return item["DraftText"]
    for v in payload.values():
        if isinstance(v, str) and len(v) > 500:
            return v
    return ""


class VaTextFetcher:
    """Session/HTTP is injected so every path is testable offline with a fake."""

    def __init__(self, session_code, http_get, headers=None, sleep=time.sleep):
        # Authorization is asserted ONCE, up front, before any request can be issued.
        from lis_authorization import assert_lis_authorized
        assert_lis_authorized(str(session_code))
        self.session_code = str(session_code)
        self._get = http_get
        self._headers = headers or {}
        self._sleep = sleep
        self.requests_made = 0
        self.stats = {"versions_seen": 0, "fetched": 0, "cache_hits": 0,
                      "empty_text": 0, "version_list_miss": 0}

    def _request(self, url, params):
        if self.requests_made >= REQUEST_CAP:
            raise TextRequestCapExceeded(
                f"va_text hit its per-run request cap ({REQUEST_CAP}); aborting rather than hammering LIS.")
        self.requests_made += 1
        return self._get(url, params=params, headers=self._headers, timeout=20)

    def versions_for(self, bill):
        r = self._request(VERSION_LIST_URL, {"billNumber": bill, "sessionCode": self.session_code})
        if getattr(r, "status_code", 0) != 200:
            self.stats["version_list_miss"] += 1
            return []
        versions = _extract_versions(r.json())
        if not versions:
            # An empty list is a SOURCE MISS worth counting, not a silent zero (Standard #9).
            self.stats["version_list_miss"] += 1
        self.stats["versions_seen"] += len(versions)
        return versions

    def text_for(self, bill, version):
        """Return the cached-or-fetched record for one version. Conditional: a cache hit costs no request."""
        vid = version.get("LegislationTextID")
        if vid is None:
            self.stats["empty_text"] += 1
            return None
        cached = load_cached(self.session_code, bill, vid)
        if cached is not None:
            self.stats["cache_hits"] += 1
            return cached
        r = self._request(TEXT_BY_ID_URL, {"legislationTextID": vid, "sessionCode": self.session_code})
        if getattr(r, "status_code", 0) != 200:
            self.stats["empty_text"] += 1
            return None
        text = _extract_text(r.json())
        if not text:
            self.stats["empty_text"] += 1
            return None
        record = {
            "bill": bill, "session_code": self.session_code, "version_id": vid,
            "version_label": version.get("Version") or version.get("Description") or "",
            "draft_date": version.get("DraftDate") or "",
            "text": text, "digest": text_digest(text), "chars": len(text),
            "source": "lis_api", "fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        save_cached(self.session_code, bill, vid, record)
        self.stats["fetched"] += 1
        return record

    def ingest_bill(self, bill):
        """All versions of one bill, newest LIS order preserved. Returns the records actually obtained."""
        out = []
        for v in self.versions_for(bill):
            rec = self.text_for(bill, v)
            if rec:
                out.append(rec)
        return out
