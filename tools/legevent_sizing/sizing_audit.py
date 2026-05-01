"""
PR-C6.4: LIS-WAF sizing audit for PR-C7's structural pivot.

Context
-------
PR-C7 will drop the MEETING_VERB_TOKENS gate at calendar_worker.py:2593
and let every `journal_default` row attempt LegislationEvent recovery,
gated only by a cross-cycle persistent cache. This is the
direction documented under "Structural classifier as source of truth"
in docs/ideas/future_improvements.md.

The PR-C3 incident (assumptions_audit #42) hung the worker on N+1
LegEvent fetches against the LIS WAF when the gate was naively
removed. PR-C3.1 added a per-cycle response cache that solved the
within-cycle fetch storm; PR-C7's cross-cycle persistence solves the
between-cycles cost. But before shipping PR-C7, we need to size the
worst case:

  - How many unique bills appear in journal_default rows across
    the full session window?
  - How does that compare to today's verb-gated subset (which the
    worker already pays for)?
  - On a cold-start cycle (empty cross-cycle cache), how many LegEvent
    fetches fire? Does that fit within the 15-min Actions cron budget
    given the LIS WAF rate-limiter's documented behavior?
  - On a warm cycle (cache hot from prior runs), how many incremental
    fetches fire?

This script answers those questions from live Sheet1 data. Read-only.

Method
------
Reads Sheet1 via get_all_values() (same defense against duplicate
header keys as PR-C6.3.1). Finds rows where Origin == "journal_default"
in the active investigation window. Groups by Bill, then by Outcome
verb match, and emits four sections:

  1. Universe sizing — total journal_default rows, unique bills,
     average rows per bill.
  2. Verb-gate split — N_verb_gated vs N_no_verb_match, the today
     baseline against which PR-C7's expansion is measured.
  3. Top 20 bills by journal_default row count — diagnostic on which
     bills drive the volume (helps reason about cache hit rates).
  4. Cold-start vs warm-cycle fetch projections, with a phased-
     rollout recommendation if the cold-start N exceeds a safe
     per-cycle budget.

Read-only by construction
-------------------------
spreadsheets.readonly OAuth scope. No write APIs anywhere in this
script. Output is stdout only.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
TARGET_SHEET = "Sheet1"
JOURNAL_DEFAULT_ORIGIN = "journal_default"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
TOP_BILLS_N = 20

# Conservative LIS WAF safe rate. PR-C3 hung at uncapped concurrent
# fetches against the WAF; the original urllib3.Retry config used
# total=4, backoff_factor=2 which compounded to 40s+ stalls on 429s.
# Assume 1 req/sec is comfortably under the rate-limiter and gives
# headroom for retries. The 15-min Actions cron budget allows ~14
# minutes of useful work after setup, so safe per-cycle cap is
# 14*60 = 840 fetches (back-of-envelope; tighten with telemetry).
LIS_SAFE_REQ_PER_SEC = 1.0
ACTIONS_CYCLE_USEFUL_SECONDS = 14 * 60
SAFE_FETCHES_PER_CYCLE = int(LIS_SAFE_REQ_PER_SEC * ACTIONS_CYCLE_USEFUL_SECONDS)

# Investigation window — single source of truth at the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from investigation_config import INVESTIGATION_START, INVESTIGATION_END  # noqa: E402

INVESTIGATION_START_DATE = datetime.strptime(INVESTIGATION_START, "%Y-%m-%d").date()
INVESTIGATION_END_DATE = datetime.strptime(INVESTIGATION_END, "%Y-%m-%d").date()

# === MEETING_VERB_TOKENS duplicated from calendar_worker.py:362 ===
# Source as of 2026-05-01. DRIFT RISK: see
# docs/ideas/future_improvements.md "Per-state lexicon extraction".
# Kept inline so this script runs without importing the worker module
# (which has heavy LIS API + Google Sheets side effects at import time).
MEETING_VERB_TOKENS = [
    "reported from",
    "recommends reporting",
    "recommends continuing",
    "recommends passing",
    "recommends laying",
    "recommends defeating",
    "recommends striking",
    "committee amendment offered",
    "committee substitute offered",
    "subcommittee substitute offered",
    "subcommittee amendment offered",
    "committee offered",
    "subcommittee offered",
    "continued to next session",
    "continued to 2027",
    "passed by for the day",
    "passed by indefinitely",
    "engrossed",
    "read first time",
    "read second time",
    "read third time",
    "constitutional reading dispensed",
    "taken up",
    "laid on the table",
    "stricken from docket",
    "block vote",
    "voice vote",
    "rules suspended",
]


def in_window(date_str: str) -> bool:
    s = str(date_str or "").strip()
    if not s:
        return False
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return False
    return INVESTIGATION_START_DATE <= d <= INVESTIGATION_END_DATE


def matches_meeting_verb_gate(outcome: str) -> bool:
    """Replicates calendar_worker.py:2593 gate predicate.

    `if origin == "journal_default" and any(v in outcome_lower for v in MEETING_VERB_TOKENS):`
    """
    lower = str(outcome or "").lower()
    return any(token in lower for token in MEETING_VERB_TOKENS)


def main() -> int:
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        print("ERROR: GCP_CREDENTIALS env var not set.", file=sys.stderr)
        return 1

    gc = gspread.authorize(
        Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    )
    sheet = gc.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(TARGET_SHEET)

    print(f"Workbook:        {sheet.title}")
    print(f"Spreadsheet ID:  {SPREADSHEET_ID}")
    print(f"Target sheet:    {TARGET_SHEET}")
    print(f"Window:          {INVESTIGATION_START} → {INVESTIGATION_END}")
    print(f"Filter:          Origin == {JOURNAL_DEFAULT_ORIGIN!r}")
    print()

    # PR-C6.3.1 lesson: Sheet1 has duplicate-empty header cells in cols
    # 13-26, so get_all_records() throws GSpreadException. Use
    # get_all_values() + manual column-index lookup.
    all_values = ws.get_all_values()
    if not all_values:
        print("ERROR: Sheet1 is empty.", file=sys.stderr)
        return 1
    header = all_values[0]
    required_cols = ["Date", "Bill", "Outcome", "Origin"]
    col_idx: dict[str, int] = {}
    for col in required_cols:
        if col not in header:
            print(
                f"ERROR: required column {col!r} not found in Sheet1 header. "
                f"Available cols: {[h for h in header if h]}",
                file=sys.stderr,
            )
            return 1
        col_idx[col] = header.index(col)

    idx_date = col_idx["Date"]
    idx_bill = col_idx["Bill"]
    idx_outcome = col_idx["Outcome"]
    idx_origin = col_idx["Origin"]

    data_rows = all_values[1:]
    print(f"Loaded {len(data_rows):,} data rows from {TARGET_SHEET}.")
    print()

    in_window_count = 0
    journal_default_count = 0
    bills_all: Counter[str] = Counter()
    bills_verb_gated: Counter[str] = Counter()
    rows_verb_gated = 0
    for r in data_rows:
        row_len = len(r)
        val_date = r[idx_date] if idx_date < row_len else ""
        if not in_window(val_date):
            continue
        in_window_count += 1
        val_origin = (r[idx_origin] if idx_origin < row_len else "").strip()
        if val_origin != JOURNAL_DEFAULT_ORIGIN:
            continue
        journal_default_count += 1
        val_bill = (r[idx_bill] if idx_bill < row_len else "").strip()
        if not val_bill:
            continue
        bills_all[val_bill] += 1
        val_outcome = r[idx_outcome] if idx_outcome < row_len else ""
        if matches_meeting_verb_gate(val_outcome):
            bills_verb_gated[val_bill] += 1
            rows_verb_gated += 1

    n_unique_bills_all = len(bills_all)
    n_unique_bills_gated = len(bills_verb_gated)
    n_total_journal_rows = sum(bills_all.values())

    # === Section 1: universe sizing ===
    print("=== Section 1: universe sizing (journal_default rows in window) ===")
    print()
    print(f"  In-window rows:                        {in_window_count:,}")
    print(f"  Origin == {JOURNAL_DEFAULT_ORIGIN!r}:           {journal_default_count:,}")
    print(f"    ... with non-empty Bill:             {n_total_journal_rows:,}")
    print(f"  Unique bills (PR-C7 cold-start surface): {n_unique_bills_all:,}")
    avg_rows_per_bill = (n_total_journal_rows / n_unique_bills_all) if n_unique_bills_all else 0
    print(f"  Avg rows per bill:                     {avg_rows_per_bill:.1f}")
    print()

    # === Section 2: today's gate baseline ===
    print("=== Section 2: today's MEETING_VERB_TOKENS gate baseline ===")
    print()
    print(f"  Rows where verb gate fires today:      {rows_verb_gated:,}")
    print(f"  Unique bills under today's gate:       {n_unique_bills_gated:,}")
    if n_unique_bills_all:
        coverage_pct = 100.0 * n_unique_bills_gated / n_unique_bills_all
        print(f"  Coverage:                              {coverage_pct:.1f}% of journal_default bills")
    pr_c7_expansion_factor = (
        n_unique_bills_all / n_unique_bills_gated if n_unique_bills_gated else float("inf")
    )
    print(f"  PR-C7 expansion factor (cold-start):   {pr_c7_expansion_factor:.1f}×")
    print()

    # === Section 3: top bills by journal_default row count ===
    print(f"=== Section 3: top {TOP_BILLS_N} bills by journal_default row count ===")
    print()
    print("Diagnostic on volume distribution. If a few bills dominate, the")
    print("cross-cycle cache buys disproportionate value (one fetch covers")
    print("many rows). If volume is flat across many bills, the cache still")
    print("helps but the cold-start cost is closer to the worst case.")
    print()
    print(f"  {'rows':>5}  bill")
    print(f"  {'─' * 5}  {'─' * 20}")
    for bill, n in bills_all.most_common(TOP_BILLS_N):
        print(f"  {n:>5}  {bill}")
    print()

    # === Section 4: fetch projections + safety ===
    print("=== Section 4: PR-C7 fetch projections + safety ===")
    print()
    print(f"  Per-cycle safe budget (assumed):       {SAFE_FETCHES_PER_CYCLE:,} fetches")
    print(f"    = {LIS_SAFE_REQ_PER_SEC} req/sec × {ACTIONS_CYCLE_USEFUL_SECONDS}s useful runtime")
    print()
    print(f"  Cold-start cycle (empty cache):")
    print(f"    PR-C7 fetches: {n_unique_bills_all:,}")
    cold_safe = n_unique_bills_all <= SAFE_FETCHES_PER_CYCLE
    print(f"    Fits in single cycle:                  {'YES' if cold_safe else 'NO'}")
    if not cold_safe:
        cycles_needed = -(-n_unique_bills_all // SAFE_FETCHES_PER_CYCLE)  # ceil div
        cycles_minutes = cycles_needed * 15
        print(f"    Phased rollout: {cycles_needed} cycles ({cycles_minutes} min wall-clock)")
    print()
    print(f"  Steady-state warm cycle (empirical estimate):")
    # Warm cycle = new bills since last cycle. Without telemetry we
    # can only model. Three scenarios for the reader to triangulate:
    for label, growth_pct in [("conservative", 0.10), ("typical", 0.05), ("optimistic", 0.02)]:
        new_bills = int(n_unique_bills_all * growth_pct)
        safe = new_bills <= SAFE_FETCHES_PER_CYCLE
        print(
            f"    {label:>14} ({growth_pct*100:>4.0f}% new bills/cycle): "
            f"{new_bills:,} fetches — {'OK' if safe else 'OVER BUDGET'}"
        )
    print()

    # === Recommendation ===
    print("=== Recommendation for PR-C7 ===")
    print()
    if cold_safe:
        print(
            f"  Cold-start fits in a single cycle ({n_unique_bills_all:,} ≤ "
            f"{SAFE_FETCHES_PER_CYCLE:,}). PR-C7 can ship with one-shot cache"
        )
        print(f"  hydration on first run after merge. No phasing needed.")
    else:
        cycles_needed = -(-n_unique_bills_all // SAFE_FETCHES_PER_CYCLE)
        print(
            f"  Cold-start ({n_unique_bills_all:,} bills) exceeds safe budget "
            f"({SAFE_FETCHES_PER_CYCLE:,}/cycle). PR-C7 MUST phase the hydration:"
        )
        print(f"    - Cache hydration cap per cycle: ~{SAFE_FETCHES_PER_CYCLE:,} fetches")
        print(f"    - Cycles needed for full hydration: {cycles_needed}")
        print(f"    - Wall-clock to steady state: ~{cycles_needed * 15} min ({cycles_needed * 15 / 60:.1f} hr)")
        print()
        print(
            f"  During phased hydration, rows whose bill isn't yet cached "
            f"fall through to the existing journal_default path (visible per "
            f"PR-A source-miss conventions; not a regression)."
        )
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
