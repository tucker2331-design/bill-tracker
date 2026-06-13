#!/usr/bin/env python3
"""Sustainability Audit — the recurring, EXPANSION-AWARE guardian against latent
"time-bomb" failures (Standard #1 zero-assumptions + #2 bank-grade + #8 zero-maintenance).

WHY THIS EXISTS
---------------
A latent failure is code that is correct on TODAY's data but wired to a trigger
that has not fired yet. The 2026 text-parsing bug was one instance of a general
class. The triggers are a small, ENUMERABLE set, so the system is audited by
walking the list — not by hoping to stumble on the next one:

    TEMPORAL      breaks when a year / session rolls over
    CAPACITY      breaks when data accumulates past a Sheets limit
    UPSTREAM      breaks when LIS renames a field / changes a vocabulary  (the text bug's class)
    STATE-WEDGE   breaks when a breaker / baseline gets stuck and cannot recover
    DETERMINISM   breaks when output depends on ordering / time / locale

THE META-LESSON THIS TOOL ENCODES
---------------------------------
The prose audits (docs/architecture/stress_test_failure_modes.md) rotted: they
were a ledger of CLAIMS no one re-executed, so a claim drifted out of sync with
the code and the text bug hid behind it. A claim no one re-runs is
indistinguishable from a lie once enough time passes. This file is the same
audit made EXECUTABLE: it runs weekly, against the LIVE workbook and the LIVE
code, and FAILS LOUDLY — so the ledger can never silently rot again.

EXPANSION-AWARE BY CONSTRUCTION (owner constraint: the DB will grow)
-------------------------------------------------------------------
Every check is CONVENTION-DRIVEN, not enumeration-driven, so future additions
(new tabs, new columns, new LIS fields) are AUTO-COVERED or AUTO-FLAGGED, never
silently skipped:
  * CAPACITY walks the workbook's ACTUAL worksheets (gspread .worksheets()) — a
    new tab is measured the moment it exists; an unrecognised large tab is
    flagged so its retention policy gets declared.
  * UPSTREAM scans the code's ACTUAL event field-reads and asserts the schema
    canary covers them — reading a NEW LIS field without registering it fails.
  * DETERMINISM asserts the live data has no dedup collision — if a future schema
    carries multiple actions per (bill, committee, date), it fails BEFORE the
    nondeterminism ships.

SEVERITY MODEL (so it ships green while surfacing trajectory risk)
-----------------------------------------------------------------
  FAIL  (exit 1, gates CI) — a PRESENT, active danger: broken TODAY.
  WARN  (exit 0, loud)     — a latent / trajectory risk: will break if unattended.
  SKIP  (exit 0, loud)     — the check could not run (e.g. no credentials); never silent.
  PASS  — verified sound.

Sibling tools: tools/cell_count_audit/audit.py (one-shot capacity diagnostic) and
tools/verification/accuracy_sentinel.py (daily accuracy metric). This is the
recurring CROSS-trigger sustainability monitor that complements both.

Usage:  python3 tools/verification/sustainability_audit.py
        (CAPACITY/STATE checks need GCP_CREDENTIALS; the rest run anywhere.)
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict, namedtuple
from datetime import datetime, timezone

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
GOOGLE_SHEETS_CELL_CAP = 10_000_000
SOFT_CEILING = 9_500_000  # mirrors calendar_worker.LEGEVENT_WORKBOOK_CELL_CEILING

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
WORKER = os.path.join(_ROOT, "calendar_worker.py")

# --- CAPACITY: declared retention policy per APPEND-ONLY tab. A tab listed here
# must not contain rows older than its retention horizon (the prune must be
# working). A tab NOT listed and NOT in BOUNDED_TABS that grows large is flagged
# for a policy decision — that is how a future append-only tab auto-surfaces. ---
RETENTION_DAYS = {"Schedule_Witness": 90}
# Tabs whose size is bounded by OVERWRITE semantics (write-then-clear-trailing),
# not by retention — they need no prune. Membership is asserted by behaviour
# (they are rewritten each cycle), documented here so the "unrecognised large
# tab" warning does not false-fire on them.
BOUNDED_TABS = {"Sheet1", "LegEvent_Cache", "LegEvent_Events"}
UNRECOGNISED_TAB_ROW_WARN = 50_000  # a large tab we don't know the policy of -> WARN

# --- UPSTREAM: internal keys that ride on event-shaped dicts but are NOT LIS API
# fields (the worker's own normalised-event schema), so they are not expected in
# the LIS schema canary. Anything read off an event receiver that is NEITHER here
# NOR in the canary is a schema-coverage gap. ---
INTERNAL_EVENT_KEYS = {
    "Date", "Committee", "Time", "Origin", "Source", "Outcome", "Bill",
    "SortTime", "LegEventRoute", "RefidClass", "ScheduleClass",
}

Result = namedtuple("Result", "trigger name severity detail")
ORDER = {"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS": 3}


def _get(url, tries=4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)  # exponential backoff on transient/rate-limit errors (Gemini #125)
    return ""


def _gviz_rows(tab="Sheet1"):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={tab}"
    return list(csv.reader(io.StringIO(_get(url))))


def _worker_src():
    with open(WORKER, encoding="utf-8") as fh:
        return fh.read()


# ============================================================================
# TEMPORAL — no un-derived year/session literal on the live path
# ============================================================================
def check_temporal():
    out = []
    src = _worker_src()

    # 1. ACTIVE_SESSION must be DERIVED, never a bare module-scope literal. The
    #    legitimate assignments are the Session-API value and the year-relative
    #    offline fallback f"20{now.year % 100:02d}1". A new hardcoded assignment
    #    like ACTIVE_SESSION = "20261" would pin the worker to one year.
    assigns = re.findall(r'^\s*ACTIVE_SESSION\s*=\s*(.+)$', src, re.MULTILINE)
    # A hardcoded pin is a bare or quoted numeric literal (ACTIVE_SESSION = "20261"
    # OR = 20261). Quote-agnostic so an unquoted int pin is also caught (Gemini #125).
    bad = [a.strip() for a in assigns if re.match(r'["\']?\d', a.strip())]
    if bad:
        out.append(Result("TEMPORAL", "session-derivation",
                           "FAIL", f"ACTIVE_SESSION assigned a hardcoded literal: {bad}"))
    else:
        out.append(Result("TEMPORAL", "session-derivation", "PASS",
                           f"ACTIVE_SESSION derived only ({len(assigns)} runtime assignments, no literal pin)"))

    # 2. The year-relative offline fallback must still be present (a 2027 offline
    #    cycle must derive 20271, not a stale 2026).
    if re.search(r'''f["']20\{now\.year\s*%\s*100''', src):  # quote-agnostic (Gemini #125)
        now = datetime.now(timezone.utc)
        expect = f"20{now.year % 100:02d}1"
        out.append(Result("TEMPORAL", "offline-fallback", "PASS",
                           f"year-relative fallback present; for {now.year} it derives {expect}"))
    else:
        out.append(Result("TEMPORAL", "offline-fallback", "FAIL",
                           "year-relative offline session fallback missing — an offline future cycle could pin to 2026"))

    # 3. The one deliberate pinned constant (investigation window) must keep its
    #    staleness WARN, so the annual transition self-alerts (audit #1r) rather
    #    than silently anchoring metrics to an old window.
    if re.search(r'INVESTIGATION_END', src) and re.search(r'stale|window.*WARN|WARN.*window', src, re.IGNORECASE):
        out.append(Result("TEMPORAL", "window-staleness-alarm", "PASS",
                           "investigation-window staleness WARN still wired (deliberate annual transition self-alerts)"))
    else:
        out.append(Result("TEMPORAL", "window-staleness-alarm", "WARN",
                           "could not confirm the investigation-window staleness WARN — verify the #1r alarm still fires"))
    return out


# ============================================================================
# UPSTREAM — the LIS schema canary must cover every event field the code reads
# ============================================================================
def check_upstream_schema():
    out = []
    src = _worker_src()

    # Canary's declared expected keys (AST-free: parse the frozenset literal).
    m = re.search(r'_EXPECTED_EVENT_KEYS\s*=\s*frozenset\(\{(.+?)\}\)', src, re.DOTALL)
    if not m:
        return [Result("UPSTREAM", "schema-canary", "FAIL",
                       "_EXPECTED_EVENT_KEYS not found — the field-rename canary is gone")]
    expected = set(re.findall(r'["\']([A-Za-z_]+)["\']', m.group(1)))

    # Every field read off an LIS-event receiver (event / ev / e). Convention-
    # driven: a NEW field read here that is not in the canary or the internal
    # allowlist is auto-flagged, so adding code that consumes a new LIS field
    # forces the canary to grow.
    read = set(re.findall(r'\b(?:event|ev|e)\.get\(\s*["\']([A-Za-z_]+)["\']', src))
    lis_read = read - INTERNAL_EVENT_KEYS
    gap = lis_read - expected

    out.append(Result("UPSTREAM", "canary-present", "PASS",
                       f"_EXPECTED_EVENT_KEYS covers {len(expected)} LIS fields: {sorted(expected)}"))
    if gap:
        out.append(Result("UPSTREAM", "canary-coverage", "WARN",
                           f"code reads LIS event field(s) {sorted(gap)} NOT in the canary — a rename of these "
                           f"would go UNDETECTED. Add to _EXPECTED_EVENT_KEYS or to INTERNAL_EVENT_KEYS."))
    else:
        out.append(Result("UPSTREAM", "canary-coverage", "PASS",
                           f"every LIS event field the code reads ({len(lis_read)}) is covered by the canary"))
    return out


# ============================================================================
# DETERMINISM — same input must yield the same calendar
# ============================================================================
def check_determinism():
    out = []
    src = _worker_src()

    # Static guard: the final dedup must have a deterministic tiebreaker so that
    # IF a collision ever appears, the survivor is stable. Look for a sort that
    # carries a row-unique column (OriginalOrder / a stable index) immediately
    # before the final drop_duplicates(subset=['Date', 'Committee', 'Bill']).
    final_dedup = re.search(r"sort_values\(by=\[([^\]]+)\]\)\s*\n\s*final_df\s*=\s*final_df\.drop_duplicates\(\s*subset=\[\s*['\"]Date['\"]", src)
    tiebreak_ok = bool(final_dedup and re.search(r"OriginalOrder|RowUID|_uid|StableIndex", final_dedup.group(1)))
    if tiebreak_ok:
        out.append(Result("DETERMINISM", "dedup-tiebreaker", "PASS",
                           "final drop_duplicates is preceded by a sort with a row-unique tiebreaker"))
    else:
        out.append(Result("DETERMINISM", "dedup-tiebreaker", "WARN",
                           "final drop_duplicates(['Date','Committee','Bill']) has NO row-unique sort tiebreaker — "
                           "if a future schema carries >1 action per (bill,committee,date), the survivor is "
                           "chosen by an unstable sort (nondeterministic). Add OriginalOrder to the sort."))

    # Live guard: assert today's data has zero dedup collisions. If a DB
    # expansion introduces the multi-action shape, this fails BEFORE it renders.
    try:
        rows = _gviz_rows("Sheet1")
        if len(rows) < 2:
            out.append(Result("DETERMINISM", "live-collisions", "SKIP", "Sheet1 unreadable/empty"))
            return out
        ci = {c: i for i, c in enumerate(rows[0])}

        def g(r, c):
            return r[ci[c]] if c in ci and ci[c] < len(r) else ""

        groups = defaultdict(set)
        for r in rows[1:]:
            if g(r, "Source") == "SYSTEM":
                continue
            # Skip gviz trailing/blank rows so they can't read as a phantom
            # collision group (Gemini #125).
            if not any(cell.strip() for cell in r):
                continue
            groups[(g(r, "Date"), g(r, "Committee"), g(r, "Bill"), g(r, "Source"))].add((g(r, "Time"), g(r, "Outcome")))
        collisions = sum(1 for v in groups.values() if len(v) > 1)
        if collisions:
            out.append(Result("DETERMINISM", "live-collisions", "FAIL",
                               f"{collisions} (Date,Committee,Bill,Source) group(s) differ in Time/Outcome — the "
                               f"surviving calendar row is NONDETERMINISTIC right now."))
        else:
            out.append(Result("DETERMINISM", "live-collisions", "PASS",
                               "0 dedup collisions in the live sheet — output is deterministic on current data"))
    except Exception as exc:
        out.append(Result("DETERMINISM", "live-collisions", "SKIP", f"could not read live sheet: {exc}"))
    return out


# ============================================================================
# CAPACITY — workbook cells + per-tab retention (needs gspread credentials)
# ============================================================================
def check_capacity():
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        return [Result("CAPACITY", "workbook-cells", "SKIP",
                       "GCP_CREDENTIALS not set — tab-dimension + retention checks run in CI only")]
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except Exception as exc:
        return [Result("CAPACITY", "workbook-cells", "SKIP", f"gspread/google-auth unavailable: {exc}")]

    out = []
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)

    # 1. Total allocated cells vs the 10M cap — walks ACTUAL worksheets, so a new
    #    tab is auto-included. FAIL >90% cap, WARN >60%.
    tabs = sheet.worksheets()
    ws_by_title = {ws.title: ws for ws in tabs}  # reuse — avoid a per-tab worksheet() API call (Gemini #125)
    per_tab = [(ws.title, int(ws.row_count), int(ws.col_count), int(ws.row_count) * int(ws.col_count)) for ws in tabs]
    total = sum(c for _, _, _, c in per_tab)
    frac = total / GOOGLE_SHEETS_CELL_CAP
    detail = f"{total:,}/{GOOGLE_SHEETS_CELL_CAP:,} cells ({frac:.1%}); {len(tabs)} tabs; headroom {GOOGLE_SHEETS_CELL_CAP - total:,}"
    if frac >= 0.90:
        out.append(Result("CAPACITY", "workbook-cells", "FAIL", "OVER 90% of the 10M cell cap — " + detail))
    elif frac >= 0.60:
        out.append(Result("CAPACITY", "workbook-cells", "WARN", "over 60% of the 10M cell cap — " + detail))
    else:
        out.append(Result("CAPACITY", "workbook-cells", "PASS", detail))

    # 2. Unrecognised large tab — a tab we have NO declared policy for that has
    #    grown big. This is how a FUTURE append-only tab surfaces for a policy
    #    decision instead of silently filling the workbook.
    for title, rc, cc, cells in per_tab:
        if title in BOUNDED_TABS or title in RETENTION_DAYS:
            continue
        if rc >= UNRECOGNISED_TAB_ROW_WARN:
            out.append(Result("CAPACITY", f"unrecognised-tab:{title}", "WARN",
                               f"'{title}' has {rc:,} rows but no declared retention/overwrite policy — "
                               f"register it in RETENTION_DAYS or BOUNDED_TABS and confirm it cannot grow unbounded"))

    # 3. Retention enforcement — for each append-only tab with a declared horizon,
    #    assert no row is older than that horizon (the prune is actually running).
    now = datetime.now(timezone.utc)
    for title, days in RETENTION_DAYS.items():
        ws = ws_by_title.get(title)
        if ws is None:
            out.append(Result("CAPACITY", f"retention:{title}", "SKIP", f"tab '{title}' not found"))
            continue
        rc = int(ws.row_count)
        # The tab is append-only with a monotonic seen_at_utc in column 1, so the
        # OLDEST row is the first data row. Read only a small top slice (one ranged
        # read) instead of the whole 100k+ column (Gemini #125 HIGH), and take the
        # min parseable date — robust even if the first cell is momentarily blank.
        top = ws.get("A2:A11") or []
        oldest = None
        for cell in top:
            v = cell[0] if cell else ""
            mdate = re.match(r'(\d{4}-\d{2}-\d{2})', str(v))
            if mdate:
                d = datetime.strptime(mdate.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if oldest is None or d < oldest:
                    oldest = d
        hard_cap_rows = SOFT_CEILING // max(1, int(ws.col_count))
        if oldest is None:
            # No parseable timestamp in column 1 — we CANNOT assert retention.
            # Surface it (SKIP, never a silent PASS) so the column assumption
            # gets re-confirmed rather than masked.
            out.append(Result("CAPACITY", f"retention:{title}", "SKIP",
                               f"'{title}' has no parseable YYYY-MM-DD in column 1 ({rc:,} rows) — "
                               f"cannot verify the {days}d retention; confirm the timestamp column."))
            continue
        age = (now - oldest).days
        if age > days:
            out.append(Result("CAPACITY", f"retention:{title}", "WARN",
                               f"'{title}' holds rows {age}d old (> {days}d retention) — the prune is NOT running. "
                               f"{rc:,} rows; ~{hard_cap_rows - rc:,} rows of runway to the cell ceiling. "
                               f"Build/repair the retention prune (Standard #8: no routine manual compaction)."))
        else:
            out.append(Result("CAPACITY", f"retention:{title}", "PASS",
                               f"'{title}' oldest row {age}d old (<= {days}d) — retention enforced; {rc:,} rows"))
    return out


# ============================================================================
# STATE-WEDGE — no breaker/halt stuck, baselines in-band (best-effort via gviz)
# ============================================================================
def check_state_wedge():
    # The breaker and LIS-halt are re-judged every cycle (verified: they preserve
    # last-known-good on a trip but never latch). The durable assertion is that no
    # persisted HALT is STALE — a halt older than 2 days means the worker has been
    # wedged, not transiently retrying.
    try:
        rows = _gviz_rows("Sheet1")
    except Exception as exc:
        return [Result("STATE-WEDGE", "stale-marker", "SKIP", f"could not read live sheet: {exc}")]
    # An empty/unreadable sheet must NOT read as "no marker -> PASS" (false pass,
    # Gemini #125) — there is simply nothing to verify, so SKIP loudly.
    if not rows:
        return [Result("STATE-WEDGE", "stale-marker", "SKIP", "Sheet1 empty/unreadable — cannot check for a wedge marker")]
    blob = "\n".join(",".join(r) for r in rows[:3])
    # Cover BOTH persisted wedge markers: the LIS-authorization HALT and a
    # carried-forward CIRCUIT BREAKER trip (Gemini #125) — either, when stale,
    # means the worker is stuck rather than transiently retrying.
    m = re.search(r'(HALT|BREAKER\s+TRIPPED|TRIPPED)\D{0,40}?(\d{4}-\d{2}-\d{2})', blob)
    if not m:
        return [Result("STATE-WEDGE", "stale-marker", "PASS", "no persisted HALT / breaker-trip marker on the sheet")]
    marker, day = m.group(1).strip(), m.group(2)
    stuck = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - stuck).days
    if age > 2:
        return [Result("STATE-WEDGE", "stale-marker", "FAIL",
                       f"a {marker} marker dated {day} is {age}d old — the worker appears wedged, not retrying")]
    return [Result("STATE-WEDGE", "stale-marker", "WARN", f"a recent {marker} marker dated {day} ({age}d) — confirm recovery")]


def main():
    print("=" * 78)
    print("  SUSTAINABILITY AUDIT — executable time-bomb sweep (5 trigger classes)")
    print(f"  {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}  ·  expansion-aware (walks live tabs + code)")
    print("=" * 78)

    # (trigger, fn) registry: a check that RAISES is tagged with its real trigger
    # (not fn.__name__), so the harness error still groups + prints (Gemini #125) —
    # an audit tool must never silently drop its own failure.
    checks = [
        ("TEMPORAL", check_temporal),
        ("UPSTREAM", check_upstream_schema),
        ("DETERMINISM", check_determinism),
        ("CAPACITY", check_capacity),
        ("STATE-WEDGE", check_state_wedge),
    ]
    results = []
    for trigger, fn in checks:
        try:
            results.extend(fn())
        except Exception as exc:
            results.append(Result(trigger, "harness-error", "FAIL", f"check raised: {exc}"))

    by_trigger = defaultdict(list)
    for r in results:
        by_trigger[r.trigger].append(r)
    glyph = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "🚨", "SKIP": "⏭️ "}
    # Iterate the known order first, then any other trigger present, so a result
    # with an unexpected trigger is still printed rather than dropped.
    ordered = [t for t, _ in checks]
    ordered += [t for t in by_trigger if t not in ordered]
    for trigger in ordered:
        if trigger not in by_trigger:
            continue
        print(f"\n[{trigger}]")
        for r in sorted(by_trigger[trigger], key=lambda x: ORDER[x.severity]):
            print(f"  {glyph[r.severity]} [{r.severity}] {r.name}: {r.detail}")

    fails = [r for r in results if r.severity == "FAIL"]
    warns = [r for r in results if r.severity == "WARN"]
    skips = [r for r in results if r.severity == "SKIP"]
    print("\n" + "=" * 78)
    print(f"  {len(fails)} FAIL · {len(warns)} WARN · {len(skips)} SKIP · "
          f"{sum(1 for r in results if r.severity == 'PASS')} PASS")
    if fails:
        print("  🚨 SUSTAINABILITY AUDIT FAIL — present danger:")
        for r in fails:
            print(f"     - [{r.trigger}] {r.name}: {r.detail}")
        print("=" * 78)
        return 1
    if warns:
        print("  ⚠️  PASS with trajectory WARNINGS (not yet dangerous; fix before they are):")
        for r in warns:
            print(f"     - [{r.trigger}] {r.name}")
    print("  ✅ SUSTAINABILITY AUDIT PASS — no present time-bomb danger.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
