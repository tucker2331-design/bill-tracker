#!/usr/bin/env python3
"""Reconciliation tripwire (Standard #2) — diff our calendar output against an
INDEPENDENT LIS source the pipeline never touches: the official committee
MinutesBook. The continuous answer to "who's to say that's all the bugs" — it
catches UNKNOWN output drift in production, not just bugs we can enumerate.

WHAT IT RECONCILES (and what it deliberately does NOT):
The official minutes reliably record that a committee MET on a date and ACTED on
a bill, but their structured `VoteTally` field is frequently EMPTY (the tally
lives in the LegislationEvent — our own source — so a vote-to-minutes diff is
both unreliable AND partly circular; measured 2026-06-07). So the tripwire
verifies the durable, independent signal — **every committee report we publish
corresponds to a real official meeting of that committee that acted on that
bill** — which catches mis-attribution, fabricated meetings, and gross date
errors. Per row:
  MATCH_SAMEDAY    bill in that committee's official minutes on the same date
  MATCH_NEARBY     bill in that committee's minutes within ±DATE_TOL days (date drift — informational)
  MISATTRIB        committee HAS minutes near the date but the bill is ABSENT (DRIFT — alert)
  NO_BOOK          no official book for that committee near the date (coverage gap: thin House minutes / subcommittee / unpublished — NOT our error)

DRIFT = MISATTRIB / (committee meetings we could check). Exit non-zero if it
exceeds --max-drift. Designed to run one-shot AND on a schedule (manual until
proven). Usage: python3 tools/reconciliation/reconcile_votes.py [--max-drift 0.5] [--limit N]
"""
import sys, io, csv, re, json, time, argparse, urllib.request, os
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lis_authorization import (assert_lis_authorized,  # LIS API 2025/2026-only gate (ban-safe)
    LIS_API_KEY as API_KEY, LIS_PUBLIC_API_KEY as PUB_KEY)  # S-1: single env-first key source (no literal here)

SHEET = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"

def _get(url, headers=None, timeout=60, retries=3):
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            if a == retries - 1:
                raise
            time.sleep(2 ** a)

def committee_core(name):
    s = re.sub(r'\s+', ' ', str(name or '')).lower()
    s = re.sub(r'\b(senate|house|committee|the)\b', '', s)
    s = s.split(' - ')[0].split('subcommittee')[0].split('-')[0]
    return re.sub(r'[^a-z]', '', s)

def _norm(s):
    # Normalize BOTH sides identically before substring-matching: lowercase,
    # drop every non-alphanumeric. "13-Y 0-N 1-A" -> "13y0n1a"; "SJ 209" ->
    # "sj209". (The first cut normalized only the vote and compared against the
    # raw blob — a self-inflicted 100%-"drift" false positive; a tripwire must be
    # validated against known-good data before its signal is trusted.)
    return re.sub(r'[^a-z0-9]', '', str(s).lower())  # "(13-Y 0-N 1-A)" -> "13y0n1a"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-drift", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=0, help="0 = all committee-report rows")
    ap.add_argument("--session", default="20261")
    args = ap.parse_args()
    assert_lis_authorized(args.session)  # ban-safe: refuse to reconcile against an unauthorized session
    H = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    HP = {"WebAPIKey": PUB_KEY, "Accept": "*/*"}

    # 1) independent index: official minutes books (chamber, committee-core) ->
    # {date: bookId}. We match a Sheet1 row to a book within ±DATE_TOL days, so
    # the known HISTORY-vs-LegEvent date drift (a row dated 1-2 days off the
    # actual meeting) does NOT masquerade as vote drift. The tripwire's job is to
    # catch a WRONG VOTE, not a slightly-off DATE (tracked separately).
    from datetime import datetime as _dt, timedelta as _td
    DATE_TOL = 2
    # EXTERNAL-SOURCE DEPENDENCY (Gemini review): this tripwire relies on the LIS
    # MinutesBook JSON API (NOT HTML/PDF scraping — more stable, but still external
    # and versionable). It is the SECOND, independent source; if it FAILS or returns
    # suspiciously FEW books, we must NOT silently report PASS — an empty/broken
    # independent source verifies nothing (0 drift would be a false PASS, the same
    # "homework-grading" trap). Raise a distinct EXTERNAL SOURCE CHANGE failure
    # (exit 2) so it is never confused with a real drift breach (exit 1).
    MIN_EXPECTED_BOOKS = 50   # a real session publishes hundreds; <50 == source broke/empty
    print("Fetching official MinutesBook index (independent source)…")
    book_idx = {}
    nbooks = 0
    try:
        for cc in ("S", "H"):
            j = json.loads(_get(f"https://lis.virginia.gov/MinutesBook/api/getpublishedminutesbooklistasync?sessionCode={args.session}&chamberCode={cc}", H).decode())
            for m in j.get("Minutes") or []:
                if m.get("CommitteeName") and m.get("MinutesDate"):
                    book_idx.setdefault((cc, committee_core(m["CommitteeName"])), {})[m["MinutesDate"][:10]] = m["MinutesBookID"]
                    nbooks += 1
    except Exception as e:
        print(f"🚨 EXTERNAL SOURCE CHANGE — MinutesBook API fetch/parse failed ({type(e).__name__}: {e}). "
              f"Cannot reconcile against the independent source; NOT reporting PASS.")
        return 2
    print(f"  {nbooks} official committee-meeting books")
    if nbooks < MIN_EXPECTED_BOOKS:
        print(f"🚨 EXTERNAL SOURCE CHANGE — only {nbooks} minutes books (< {MIN_EXPECTED_BOOKS}); the "
              f"MinutesBook API likely changed shape or returned empty. An empty independent source "
              f"can't verify drift — NOT reporting PASS (this is NOT '0 drift').")
        return 2

    def books_near(cc, core, date):
        """(abs_offset, bookId) for this committee within ±DATE_TOL days, nearest first."""
        out = []
        try:
            d0 = _dt.strptime(date, "%Y-%m-%d")
        except Exception:
            return out
        bydate = book_idx.get((cc, core), {})
        for off in range(-DATE_TOL, DATE_TOL + 1):
            bid = bydate.get((d0 + _td(days=off)).strftime("%Y-%m-%d"))
            if bid:
                out.append((abs(off), bid))
        return sorted(out)

    # 2) our output: Sheet1 committee-report rows with a recorded vote
    rows = list(csv.reader(io.StringIO(_get(f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet=Sheet1", timeout=120).decode())))
    ci = {c: i for i, c in enumerate(rows[0])}
    g = lambda r, c: (r[ci[c]] if c in ci and ci[c] < len(r) else "")
    targets = []
    for r in rows[1:]:
        cm = g(r, "Committee").lower(); o = g(r, "Outcome")
        if (cm.startswith("senate ") or cm.startswith("house ")) and "reported from" in o.lower() and re.search(r'\(\d+-Y', o):
            cc = "S" if cm.startswith("senate") else "H"
            vote = re.search(r'\((\d+-Y[^)]*)\)', o).group(1)
            targets.append((cc, committee_core(g(r, "Committee")), g(r, "Date"), g(r, "Bill"), vote))
    if args.limit:
        targets = targets[:args.limit]
    print(f"  {len(targets)} Sheet1 committee-report rows with a recorded vote\n")

    # 3) reconcile (cache book content per bookId)
    cache = {}
    cats = Counter(); drift_examples = []
    for i, (cc, core, date, bill, vote) in enumerate(targets):
        near = books_near(cc, core, date)
        if not near:
            cats["NO_BOOK"] += 1; continue
        nbill = _norm(bill)
        hit_off = None
        for off, bid in near:
            if bid not in cache:
                try:
                    cache[bid] = _norm(_get(f"https://lis.virginia.gov/MinutesBook/api/getminutesbookasync?minutesBookId={bid}&sessionCode={args.session}", HP).decode())
                except Exception:
                    cache[bid] = ""
            if nbill in cache[bid]:
                hit_off = off; break
        if hit_off == 0:
            cats["MATCH_SAMEDAY"] += 1
        elif hit_off is not None:
            cats["MATCH_NEARBY"] += 1  # found within ±DATE_TOL — date-placement drift, informational
        else:
            # committee HAS minutes near the date but the bill is absent -> our
            # report may be mis-attributed to the wrong committee. True drift.
            cats["MISATTRIB"] += 1
            if len(drift_examples) < 25: drift_examples.append((bill, date, core))
        if (i + 1) % 500 == 0:
            print(f"  …{i+1}/{len(targets)}")

    checkable = cats["MATCH_SAMEDAY"] + cats["MATCH_NEARBY"] + cats["MISATTRIB"]  # committee had minutes to check against
    drift = cats["MISATTRIB"]
    drift_pct = (100.0 * drift / checkable) if checkable else 0.0
    print("\n=== RECONCILIATION RESULT (Sheet1 committee reports vs independent official minutes) ===")
    for k in ("MATCH_SAMEDAY", "MATCH_NEARBY", "MISATTRIB", "NO_BOOK"):
        print(f"  {k:14s} {cats.get(k, 0)}")
    print(f"\n  checkable (committee had minutes near the date): {checkable}")
    print(f"  date-drift (found ±{DATE_TOL}d, not same-day):       {cats.get('MATCH_NEARBY',0)} (informational)")
    print(f"  coverage gap (no book near date):                {cats.get('NO_BOOK',0)} (thin House minutes / subcommittee / unpublished)")
    print(f"  DRIFT (mis-attribution): {drift}  ({drift_pct:.2f}%)   threshold {args.max_drift:.2f}%")
    if drift_examples:
        print("\n  mis-attribution examples (bill, our-date, our-committee-core):")
        for bill, date, core in drift_examples:
            print(f"    {bill:8s} {date:11s} {core}")
    ok = drift_pct <= args.max_drift
    print(f"\n  {'PASS' if ok else 'FAIL — DRIFT EXCEEDS THRESHOLD'}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
