#!/usr/bin/env python3
"""Docket-drop histogram — WHEN does LIS post/alter committee schedules? (build-wave TASK 4a)

WHY: the product pitch includes "the 10 PM docket-drop anxiety-killer" (docs/ideas/lobbyist_jtbd_ideation §8,
feature A2). That "10 PM" was an ILLUSTRATION, never a measurement — flagged to be replaced with real data.
This tool measures it from `Schedule_Witness`, which stamps every ADDED/CHANGED schedule delta with the ET
time WE detected it (`seen_at_utc`) — a close proxy for when LIS published/changed the meeting, bounded by
our ~15-min in-session cadence. It buckets deltas by ET hour-of-day so the real drop-time distribution is
visible ("committee dockets for tomorrow's 7:30 AM subs land mostly between X and Y PM").

DATA REALITY (measured 2026-07-14): the witness has 90-day retention, so the 2026 session (Jan–Mar) is
already pruned, AND the tab has auto-sharded to VA·Ops (WITNESS_WORKBOOK=ops). This tool therefore:
  * reads the witness from wherever it lives (VA·Live default, VA·Ops when WITNESS_WORKBOOK=ops), via the
    service account — it is CI-run (needs GCP_CREDENTIALS), like the retention prune;
  * reports the distribution over whatever window is retained + prints the min/max seen_at so the caller
    knows the window;
  * is the instrument for the 2027 session — off-season interim meetings give a distribution, but the
    session-docket-drop signal only appears in-session.

Run in CI (workflow_dispatch): needs GCP_CREDENTIALS. Locally it prints how to run.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"   # VA · Live
OPS_WORKBOOK_ID = "1X7wa4brFROP9Bn81Esf4z3zjlxTZvpKeUdPWpyBkD3c"  # VA · Ops (witness lives here after auto-shard)
WITNESS_TAB = "Schedule_Witness"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# The witness stores seen_at_utc as an ISO UTC string. ET is UTC-5 (EST) / UTC-4 (EDT). VA session is
# Jan–Mar → EST. We convert with a fixed −5 for the histogram's purpose (the drop-hour buckets are coarse;
# a DST hour doesn't change the "evening vs morning" story, and using a fixed offset keeps this dependency-
# free). Off-season summer rows are EDT (−4); the CLI notes the offset so the reader isn't misled.
ET_OFFSET_HOURS = -5


def _load_witness_rows():
    creds = os.environ.get("GCP_CREDENTIALS")
    if not creds:
        print("This tool needs GCP_CREDENTIALS (the witness lives in an auth-walled workbook).")
        print("Run it via the workflow: gh workflow run witness_histogram.yml")
        return None, None
    import gspread
    from google.oauth2.service_account import Credentials
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds), scopes=SCOPES))
    book_id = OPS_WORKBOOK_ID if os.environ.get("WITNESS_WORKBOOK", "").strip().lower() == "ops" else SPREADSHEET_ID
    try:
        ws = gc.open_by_key(book_id).worksheet(WITNESS_TAB)
    except Exception as e:
        print(f"⚠️ could not open {WITNESS_TAB} in {book_id[:12]}… ({e}). "
              f"If it sharded, set WITNESS_WORKBOOK=ops.")
        return None, book_id
    return ws.get_all_values(), book_id


def _et_hour(iso_utc: str):
    try:
        dt = datetime.strptime(iso_utc[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None
    return (dt.hour + ET_OFFSET_HOURS) % 24, dt


def main() -> int:
    rows, book_id = _load_witness_rows()
    if rows is None:
        return 0
    if not rows or len(rows) < 2:
        print(f"{WITNESS_TAB} is empty (or header-only) in {str(book_id)[:12]}… — nothing to histogram.")
        return 0

    header = [h.strip().lower() for h in rows[0]]
    try:
        i_seen = header.index("seen_at_utc")
        i_type = header.index("event_type")
    except ValueError:
        print(f"⚠️ unexpected {WITNESS_TAB} header {rows[0]} — schema drift; aborting rather than mis-reading.")
        return 1

    by_hour = Counter()
    by_hour_added = Counter()
    seens = []
    counted = 0
    for r in rows[1:]:
        if len(r) <= max(i_seen, i_type) or not r[i_seen].strip():
            continue
        parsed = _et_hour(r[i_seen])
        if parsed is None:
            continue
        hour, dt = parsed
        seens.append(dt)
        by_hour[hour] += 1
        if r[i_type].strip().upper() == "ADDED":
            by_hour_added[hour] += 1
        counted += 1

    if not counted:
        print(f"{WITNESS_TAB}: no parseable seen_at_utc rows.")
        return 0

    lo, hi = min(seens), max(seens)
    span_days = (hi - lo).days
    print(f"📊 Docket-drop histogram — {counted:,} witness deltas over {span_days}d "
          f"({lo:%Y-%m-%d} → {hi:%Y-%m-%d} UTC; hours shown ET, fixed {ET_OFFSET_HOURS:+d}).")
    in_season = lo.month <= 3 or hi.month <= 3
    if not in_season:
        print("   ⚠️ window is OFF-SEASON only — the session docket-drop signal needs in-session data "
              "(re-run during the 2027 session; the 2026 session is past the 90-day witness retention).")
    peak = max(by_hour, key=by_hour.get)
    print(f"   busiest ET hour: {peak:02d}:00 ({by_hour[peak]} deltas).  Distribution (all deltas | ADDED):")
    mx = max(by_hour.values())
    for h in range(24):
        n, a = by_hour.get(h, 0), by_hour_added.get(h, 0)
        bar = "█" * round(40 * n / mx) if mx else ""
        print(f"   {h:02d}:00  {n:5d} | {a:5d}  {bar}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
