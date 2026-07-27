#!/usr/bin/env python3
"""Goldens for the VA text fetcher (W2). Offline: a fake HTTP layer, a temp corpus dir, no network."""
import json
import os
import shutil
import sys
import tempfile

CORPUS = tempfile.mkdtemp(prefix="va_text_test_")
os.environ["VA_TEXT_CORPUS_DIR"] = CORPUS
sys.path.insert(0, "tools/text_corpus")
import va_text as V  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"  {'✓' if ok else '✗'} {label}")
    if not ok:
        print(f"      got: {got!r}  want: {want!r}")
        FAILURES.append(label)


class Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p


VERSIONS = {"LegislationsVersion": [
    {"LegislationTextID": 258097, "Version": "Introduced", "DraftDate": "2026-01-06T20:02:00"},
    {"LegislationTextID": 258098, "Version": "Engrossed", "DraftDate": "2026-02-01T10:00:00"},
]}
TEXT = {"TextsList": [{"DraftText": "<p>A BILL to amend the Code. " + ("word " * 200) + "</p>"}]}


class FakeHTTP:
    def __init__(self, version_payload=VERSIONS, text_payload=TEXT, status=200):
        self.calls = []
        self._v, self._t, self._status = version_payload, text_payload, status

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if "LegislationVersion" in url:
            return Resp(self._v, self._status)
        return Resp(self._t, self._status)


print("— authorization is asserted BEFORE any request —")
try:
    V.VaTextFetcher("20241", FakeHTTP())      # pre-2025 must never reach the API path
    blocked = False
except Exception:
    blocked = True
check("an unauthorized session is refused at construction", blocked, True)
check("an authorized session constructs fine", bool(V.VaTextFetcher("20261", FakeHTTP())), True)

print("\n— ingest —")
http = FakeHTTP()
f = V.VaTextFetcher("20261", http)
recs = f.ingest_bill("HB176")
check("both versions ingested", len(recs), 2)
check("text is captured", recs[0]["chars"] > 500, True)
check("a content digest is stored (the conditional-fetch key)", len(recs[0]["digest"]), 64)
check("provenance is stamped", recs[0]["source"], "lis_api")
check("the session code travels with the record", recs[0]["session_code"], "20261")
check("requests = 1 version list + 2 texts", http.calls and len(http.calls), 3)
check("every request carried the session code",
      all(c[1].get("sessionCode") == "20261" for c in http.calls), True)

print("\n— conditional fetch: a second run costs NO requests —")
http2 = FakeHTTP()
f2 = V.VaTextFetcher("20261", http2)
recs2 = f2.ingest_bill("HB176")
check("same records returned from cache", len(recs2), 2)
check("cache hits counted", f2.stats["cache_hits"], 2)
check("only the version list was re-requested (texts came from disk)", len(http2.calls), 1)

print("\n— honest failure modes —")
f3 = V.VaTextFetcher("20261", FakeHTTP(version_payload={"LegislationsVersion": []}))
f3.ingest_bill("HB999")
check("an empty version list counts as a SOURCE MISS, not a silent zero",
      f3.stats["version_list_miss"], 1)

f4 = V.VaTextFetcher("20261", FakeHTTP(text_payload={"TextsList": [{"DraftText": ""}]}))
got4 = f4.ingest_bill("HB176b")
check("missing text yields NO record rather than an empty one", got4, [])
check("...and is counted", f4.stats["empty_text"], 2)

f5 = V.VaTextFetcher("20261", FakeHTTP(status=500))
check("an upstream error yields no records", f5.ingest_bill("HB500"), [])

print("\n— cache robustness —")
bad = V.corpus_path("20261", "HBBAD", 1)
os.makedirs(os.path.dirname(bad), exist_ok=True)
with open(bad, "w", encoding="utf-8") as fh:
    fh.write("{not json")
check("a corrupt cache entry re-fetches instead of raising", V.load_cached("20261", "HBBAD", 1), None)

print("\n— the runaway guard —")
saved = V.REQUEST_CAP
V.REQUEST_CAP = 1
try:
    f6 = V.VaTextFetcher("20261", FakeHTTP())
    try:
        f6.ingest_bill("HB176c")
        raised = False
    except V.TextRequestCapExceeded:
        raised = True
    check("exceeding the per-run cap RAISES", raised, True)
    check("it is a BaseException, so a broad `except Exception` cannot swallow a runaway",
          issubclass(V.TextRequestCapExceeded, BaseException)
          and not issubclass(V.TextRequestCapExceeded, Exception), True)
finally:
    V.REQUEST_CAP = saved

print("\n— the corpus feeds the comparer —")
import normalize as N  # noqa: E402
a = N.shingles(N.normalize(recs[0]["text"]), k=8)
check("stored text normalizes into usable shingles", len(a) > 0, True)

shutil.rmtree(CORPUS, ignore_errors=True)
print()
if FAILURES:
    print(f"❌ {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("✅ all VA text-fetch goldens pass")
