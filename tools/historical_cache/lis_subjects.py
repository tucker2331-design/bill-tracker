#!/usr/bin/env python3
"""One-time backfill of the LIS bill<->subject index for the AUTHORIZED sessions (2025, 2026).

WHY THIS EXISTS
---------------
`CiBillSubjects.csv` is published only for 2023/2024 (legacy CSV route). For 2025/2026 there is NO subject
blob — measured, clean 404 on both casings ([[knowledge/legacylis_csv_route]]). The linkage exists only
through the search API. Without it, the subject classifier learns LIS's filing conventions from two seed
sessions, and 88% of its unlabelled bills have a catalogue head that never appears in those two sessions
with a subject. More seed sessions is the ONLY lever that moves that number ([[testing/subject_labels]]).

THE COST, MEASURED NOT ESTIMATED (probe 2026-08-04)
---------------------------------------------------
The index is keyed **by subject, not by bill** — so this is not ~4,700 per-bill calls:

    505 subjects x 2 authorized sessions = 1,010 requests, +1 session list, +2 dictionaries

At the delay below that is ~35 minutes of wall clock, ONCE. For scale, the two live workers already make
several hundred LIS API GETs on a busy in-session day, so the whole backfill is roughly a day and a half of
normal traffic. ToS §4 forbids an "unreasonable or disproportionately large load"; this is not that.

WHY THIS PACE, AND WHY NOT SPREAD OVER WEEKS
---------------------------------------------
[[knowledge/lis_api_safety]] is explicit that the number is not the risk: *"the cadence number is downstream
of the guardrails — the number is never the risk; the PATTERN (predictable metronome) and UNCONDITIONAL
re-downloads are."* A single bounded run that finishes and never repeats is the OPPOSITE of a metronome. A
daily trickle for a fortnight would look more like one, not less, and would keep the exposure open longer.

So: one contiguous, resumable, jittered run at ~2s/request (4x more conservative than the 0.5s this repo
already uses against legacylis), during a period when the GA is ADJOURNED and competing load is near zero.
`--limit` exists for fault tolerance and owner control, not because spreading is safer.

GUARDRAILS (the five from the charter, all five apply)
-------------------------------------------------------
1. CONDITIONAL — the manifest records every (session, subject) already fetched; a re-run costs 0 requests.
   These sessions are closed, so the data is static and re-fetching is pure waste.
2. JITTER — the delay is randomised, never a fixed tick.
3. BACKOFF — 429/503 honour `Retry-After`, then exponential; repeated failure ABORTS rather than hammers.
4. HARD CEILING — `--cap` bounds requests per invocation independently of the loop logic, so a bug cannot
   spike us into a ban.
5. ACTIVITY-CORRELATED — n/a by nature: this is a one-time historical backfill, not a recurring poll. It is
   therefore held to the stricter test of being bounded, announced in the log, and never repeated.

AUTHORIZATION
-------------
Every session code passes `assert_lis_authorized` before any request. 2025/2026 are the frozen authorized
set; pre-2025 is legacylis-only and this tool must never be pointed there.

Usage:
    python3 tools/historical_cache/lis_subjects.py --plan     # counts only, ZERO index requests
    python3 tools/historical_cache/lis_subjects.py --run [--limit N] [--cap N]
    python3 tools/historical_cache/lis_subjects.py --status
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from lis_authorization import (                                          # noqa: E402
    LIS_PUBLIC_API_KEY, assert_lis_authorized, LIS_HISTORICAL_AUTHORIZED)

BASE = "https://lis.virginia.gov"
DICT_URL = BASE + "/LegislationSubject/api/GetSubjectReferencesAsync?sessionID={sid}"
INDEX_URL = BASE + "/AdvancedLegislationSearch/api/GetLegislationListAsync"
SESSIONS_URL = BASE + "/Session/api/GetSessionListAsync"

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "va_subjects")
MANIFEST = os.path.join(CACHE_DIR, "manifest.json")

DELAY_S = 2.0             # 4x more conservative than the 0.5s used against legacylis in fetch.py
JITTER_S = 0.7            # guardrail #2 — never a fixed tick
PAGE_SIZE = 2000          # ONE request per subject — no pagination at all. The largest subject measured is
                          # 808 bills, and at this size the server returns TotalPages=1 and every distinct
                          # bill. Do NOT lower it: at 500 the same subject reported TotalCount=657 while
                          # actually holding 808, so the count field is page-size dependent and cannot be
                          # trusted to detect a short read.
DEFAULT_CAP = 1200        # guardrail #4 — a runaway guard, not the plan (the plan is ~1,010)
MAX_CONSECUTIVE_FAILS = 5
MAX_PAGES = 20            # absolute page ceiling per subject. The largest real subject is 657 bills = 2
                          # pages at PAGE_SIZE; 20 is far above anything legitimate and exists solely so a
                          # lying HasNext can never loop forever again (measured, subject 66).


class Aborted(RuntimeError):
    """Raised to stop the run. Never caught inside the loop — a struggling source is not retried blindly."""


def _headers(page=None):
    h = {"WebAPIKey": LIS_PUBLIC_API_KEY, "Accept": "application/json",
         "Content-Type": "application/json; charset=utf-8"}
    if page:
        h["X-Pagination"] = json.dumps(page)
    return h


def _request(url, body=None, page=None, timeout=25):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(page),
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _sleep():
    time.sleep(DELAY_S + random.uniform(0, JITTER_S))


def _backoff(attempt, headers):
    """Guardrail #3. Honour Retry-After when the server states one; otherwise exponential."""
    ra = headers.get("Retry-After")
    if ra:
        try:
            return min(float(ra), 120.0)
        except ValueError:
            pass
    return min(2.0 ** attempt, 60.0)


def load_manifest():
    if not os.path.exists(MANIFEST):
        return {"jurisdiction": "VA", "source": BASE, "fetched": {}, "sessions": {}}
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def save_manifest(m):
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, MANIFEST)          # atomic: an interrupted run never leaves a half-written manifest


def _as_list(payload):
    """LIS wraps its arrays under a per-endpoint key (`SubjectsReference`, `Legislations`, ...).
    Take the first list-valued field rather than hardcoding a name that varies by endpoint."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list):
                return v
    return []


def session_ids():
    """Map authorized SessionCode -> numeric SessionID. Derived at runtime, never hardcoded (Standard #1)."""
    status, _h, body = _request(SESSIONS_URL)
    if status != 200 or not body:
        raise Aborted(f"session list returned HTTP {status} — cannot resolve SessionID, refusing to guess.")
    out = {}
    for x in _as_list(json.loads(body)):
        code = str(x.get("SessionCode") or "")
        if code in LIS_HISTORICAL_AUTHORIZED and x.get("SessionID") is not None:
            out[code] = x["SessionID"]
    missing = set(LIS_HISTORICAL_AUTHORIZED) - set(out)
    if missing:
        # FAIL CLOSED: a session we cannot resolve is skipped loudly, never silently treated as empty.
        print(f"  WARN: no SessionID for authorized session(s) {sorted(missing)} — they will be skipped.")
    return out


def subject_dictionary(sid):
    status, _h, body = _request(DICT_URL.format(sid=sid))
    if status != 200 or not body:
        raise Aborted(f"subject dictionary for session {sid} returned HTTP {status}.")
    return _as_list(json.loads(body))


def fetch_subject(session_id, subject_id, counters, budget=None):
    """One (session, subject) query, following pages. Returns (bill_numbers, requests_used).

    HTTP 204 with an empty body is a LEGITIMATE EMPTY SET, not an error and not a missing subject — a
    documented LIS quirk ([[knowledge/lis_api_reference]]). Conflating it with failure would mark real
    zero-bill subjects as unfetched and re-request them on every run, forever.

    ⚠ `HasNext` IS NOT A TERMINATION CONDITION. Measured 2026-08-04 on subject 66 ("Commendations and
    Commemorations", TotalCount=657, TotalPages=2): the server returns `HasNext: true` on EVERY page and
    keeps serving 500 rows for page 3, page 4, ... forever. Trusting it produced an infinite request loop
    that ran ~800 requests before it was caught — and it went unnoticed because a loop that is sleeping
    politely between requests looks exactly like a stalled process from the outside.

    Pagination is therefore bounded by `TotalPages`/`TotalCount`, which are self-consistent, AND by an
    absolute page ceiling, AND by the caller's remaining request budget. Three independent bounds because
    the one bound the API advertises turned out to be a lie."""
    bills, seen, used, page_no = [], set(), 0, 1
    max_pages = MAX_PAGES
    while True:
        if page_no > max_pages:
            counters["page_capped"] += 1
            print(f"    page ceiling {max_pages} hit for subject {subject_id} — stopping this subject.",
                  flush=True)
            return bills, used
        if budget is not None and used >= budget:
            counters["budget_capped"] += 1
            return bills, used
        attempt = 0
        while True:
            status, headers, body = _request(
                INDEX_URL, body={"SessionID": session_id, "SubjectIndexID": subject_id},
                page={"PageNumber": page_no, "PageSize": PAGE_SIZE})
            used += 1
            if status in (429, 500, 502, 503, 504) and attempt < 4:
                wait = _backoff(attempt, headers)
                counters["retried"] += 1
                print(f"    HTTP {status} — backing off {wait:.0f}s", flush=True)
                time.sleep(wait)
                attempt += 1
                continue
            break
        if status == 204 or not body:
            counters["empty"] += 1
            return bills, used
        if status != 200:
            counters["failed"] += 1
            raise urllib.error.HTTPError(INDEX_URL, status, f"HTTP {status}", headers, None)
        for row in _as_list(json.loads(body)):
            num = row.get("LegislationNumber") or row.get("BillNumber")
            if num:
                num = str(num).strip()
                if num not in seen:          # page 2 re-served page 1 verbatim; dedupe, never trust order
                    seen.add(num)
                    bills.append(num)
        pg = json.loads(headers.get("X-Pagination") or "{}")
        # TotalPages/TotalCount are self-consistent; HasNext is not (see the docstring). Stop on either
        # the declared page count or on having collected the declared total — never on HasNext.
        total_pages = pg.get("TotalPages") or 0
        total_count = pg.get("TotalCount") or 0
        if page_no >= total_pages or len(bills) >= total_count or not total_pages:
            return bills, used
        page_no += 1
        _sleep()


def run(limit=None, cap=DEFAULT_CAP, plan_only=False):
    for code in sorted(LIS_HISTORICAL_AUTHORIZED):
        assert_lis_authorized(code)            # every code, before any request (never trust the loop bound)

    man = load_manifest()
    ids = session_ids()
    man["sessions"] = {c: ids[c] for c in sorted(ids)}
    used = 1
    counters = collections.Counter()

    plan = []
    for code in sorted(ids):
        sid = ids[code]
        _sleep()
        subs = subject_dictionary(sid)
        used += 1
        for s in subs:
            key = f"{code}|{s['SubjectIndexID']}"
            if key not in man["fetched"]:
                plan.append((code, sid, s["SubjectIndexID"], s.get("Subject", "")))
    print(f"authorized sessions: {dict(man['sessions'])}")
    print(f"already cached: {len(man['fetched']):,}   still to fetch: {len(plan):,} "
          f"(1 request each, +pages for the largest)")
    if plan_only:
        mins = len(plan) * (DELAY_S + JITTER_S / 2) / 60
        print(f"estimated: {len(plan):,} requests, ~{mins:.0f} min at {DELAY_S}s+jitter. No index calls made.")
        save_manifest(man)
        return 0

    todo = plan[:limit] if limit else plan
    fails = 0
    for i, (code, sid, subj_id, name) in enumerate(todo, 1):
        if used >= cap:
            print(f"\nHARD CAP {cap} reached — stopping cleanly. Re-run to continue.")
            break
        _sleep()
        try:
            bills, n = fetch_subject(sid, subj_id, counters, budget=max(0, cap - used))
            used += n
            fails = 0
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            fails += 1
            counters["failed"] += 1
            print(f"  FAIL {code}/{subj_id} {name[:28]}: {exc}", flush=True)
            if fails >= MAX_CONSECUTIVE_FAILS:
                save_manifest(man)
                raise Aborted(f"{fails} consecutive failures — stopping rather than hammering a "
                              f"struggling source (guardrail #3). Progress is saved; re-run to resume.")
            continue
        man["fetched"][f"{code}|{subj_id}"] = {
            "subject": name, "bills": bills, "n": len(bills),
            "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        counters["ok"] += 1
        if i % 10 == 0 or i == len(todo):
            save_manifest(man)
            print(f"  {i:>4}/{len(todo)}  requests used {used:,}  "
                  f"ok {counters['ok']} empty {counters['empty']} retried {counters['retried']} "
                  f"failed {counters['failed']}", flush=True)
    save_manifest(man)
    _write_index(man)
    print(f"\nrequests used this run: {used:,} (cap {cap})")
    print(f"ok {counters['ok']}  empty {counters['empty']}  retried {counters['retried']}  "
          f"failed {counters['failed']}")
    return 1 if counters["failed"] else 0


def _write_index(man):
    """Invert to bill -> [subjects], gzipped, alongside the manifest."""
    inv = collections.defaultdict(set)
    for key, rec in man["fetched"].items():
        code = key.split("|", 1)[0]
        for b in rec["bills"]:
            inv[f"{code}|{b}"].add(rec["subject"])
    path = os.path.join(CACHE_DIR, "bill_subjects.json.gz")
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump({k: sorted(v) for k, v in sorted(inv.items())}, fh, sort_keys=True)
    print(f"wrote {len(inv):,} bill->subject rows -> {path}")


def status():
    man = load_manifest()
    if not man["fetched"]:
        print("nothing cached yet.")
        return 1
    per = collections.Counter(k.split("|", 1)[0] for k in man["fetched"])
    bills = collections.defaultdict(set)
    for key, rec in man["fetched"].items():
        code = key.split("|", 1)[0]
        bills[code].update(rec["bills"])
    print(f"{'session':>9}{'subjects':>10}{'bills w/ >=1 subject':>23}")
    for code in sorted(per):
        print(f"{code:>9}{per[code]:>10,}{len(bills[code]):>23,}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="counts only; makes NO index requests")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="max subjects this invocation")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP, help="hard request ceiling (guardrail #4)")
    a = ap.parse_args()
    if a.status:
        return status()
    if a.plan:
        return run(plan_only=True)
    if a.run:
        return run(limit=a.limit, cap=a.cap)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
