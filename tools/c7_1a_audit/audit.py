"""
PR-C7.1a — Derived-classifier viability audit (the math-proof).

Owner mandate (2026-05-11):
  "I do not trust 'good ideas' without mathematical proof. ... Define
  a strict mathematical threshold for 'Trust'. ... Give me the exact
  percentage of historical rows that pass the Trust Threshold versus
  the percentage that fail and route to the DLQ. If the DLQ rate is
  too high, this architecture is not sustainable. Consider processing
  power and don't lose progress on hourly/weekly limits."

What this audit does
--------------------
1. Sample N bills deterministically from HISTORY.CSV.
2. Two-step LIS lookup per bill (LegislationVersion -> LegislationID,
   then LegislationEvent). Persists fetched events to a Sheets tab
   incrementally so a mid-process interruption loses at most one
   batch (PHASE 0 checkpoint).
3. Build training corpus of (description, EventCode) pairs from the
   fetched events.
4. Hold out 20% of sampled bills for validation. Train token stats
   on the remaining 80%.
5. Score the ENTIRE HISTORY.CSV corpus (all ~65,000 rows) against
   the trained classifier under the chosen trust thresholds.
6. Report PASS / DLQ split (exact percentages) AND validation
   accuracy (precision on held-out PASS rows).
7. Sweep over a small grid of (MIN_SUPPORT, MAX_ENTROPY) to expose
   the Pareto frontier of DLQ vs accuracy.
8. Write three result tabs:
     - C7_1a_TokenStats   (per-token signal table)
     - C7_1a_DLQ_Samples  (50 DLQ examples for manual inspection)
     - C7_1a_Summary      (headline numbers + the sweep grid)

What this audit does NOT do
---------------------------
- Touch Sheet1, the LegEvent_Bills cache, or the LegEvent_Events
  cache. It uses an isolated read-only path.
- Write to W1, X1, Y1, Y2 state cells (those are worker-owned).
- Modify the worker's schema. Schema migration to persist EventCode
  per event lives in PR-C7.0.6 if this audit passes.

Checkpointing strategy
----------------------
The slow phase is LIS fetches (~200 API calls for N=100 bills, ~5
minutes with retries). Every 10 bills, we APPEND fetched event rows
to C7_1a_RawCorpus tab. On re-run, we READ the tab first, build the
"already-fetched bills" set, and skip those. So an interrupted run
can be resumed cheaply.

The math phases (token stats, row scoring, validation) are pure
in-memory and run in <10 seconds even on the full HISTORY corpus.
Re-running them after a checkpoint just re-derives the same answer
from the (now-larger) raw corpus.

Pre-push audit walk
-------------------
1.  Verb forms: N/A — not editing pattern lists.
2.  Function scope: all defs at module level.
3.  Doc version sync: tracked in current_status / log writeback.
4.  Duplicate file check: doesn't touch pages/ray2.py or
    calendar_xray.py.
5.  Architecture conformance: this audit is the gate before PR-C7.1b
    commits to the architecture.
6.  Zero-trust data: every API failure path emits a categorized
    print + does NOT raise into mainline; failed fetches are
    explicitly skipped with the bill recorded in a `failed_bills`
    list that the summary surfaces.
7.  Cross-list validation: N/A — no classification lists in the
    audit; the math operates on derived stats.
8.  Import resolution from subpage: N/A — not touching pages/.
9.  Source-miss visibility: every skip/abort path logs WHY.
10. Function-scope shadow check: no local re-imports of module names.
11. Side-effect gating: result-tab writes happen after each phase
    completes; checkpoint tab is written incrementally; nothing
    gated on a check that can be permanently true.
12. Fallback liveness: no try/fallback patterns (the audit is
    single-source-of-truth from LIS).
13. Dead-path resurrection: no fallback removals.
14. Threshold calibration: MIN_SUPPORT / MAX_ENTROPY / etc. are
    audit-internal parameters with a published sweep grid. They are
    NOT production breaker thresholds.
15. Sentinel-value collision: DLQ reasons are explicit string
    constants from trust_math.py, not encoded by sentinel values.
"""
from __future__ import annotations

import io
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import gspread
import pandas as pd
import requests
from enum import Enum
from google.oauth2 import service_account
from gspread.exceptions import WorksheetNotFound

# Local import: pure math module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trust_math import (  # noqa: E402
    TokenStats,
    compute_token_stats,
    score_row,
    tokenize,
    validate_against_held_out,
    DLQ_NO_TRUSTED_TOKENS,
    DLQ_INSUFFICIENT_TRUSTED_TOKENS,
    DLQ_INSUFFICIENT_TOP_VOTES,
    DLQ_INSUFFICIENT_MARGIN,
)


# ---------------------------------------------------------------------------
# Constants (audit-internal — NOT production thresholds)
# ---------------------------------------------------------------------------

GSHEET_ID = "1msUW9wq6OavWmw_DwT4yTLuKzUtnpmKzAoflpijhAUE"  # Mastermind DB
GSHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

LIS_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"
LIS_HEADERS = {"WebAPIKey": LIS_API_KEY}
SESSION_CODE_5D = "20261"

HISTORY_CSV_URL = (
    "https://lis.blob.core.windows.net/lisfiles/20261/HISTORY.CSV"
)
LEGISLATION_VERSION_URL = (
    "https://lis.virginia.gov/LegislationVersion/"
    "api/GetLegislationVersionbyBillNumberAsync"
)
LEGISLATION_EVENT_URL = (
    "https://lis.virginia.gov/LegislationEvent/"
    "api/GetPublicLegislationEventHistoryListAsync"
)

# Sample size for the LIS fetch phase.
#
# Owner correction (2026-05-11): the original SAMPLE_BILLS=100 was a
# grave mistake. At MIN_SUPPORT=10 (a token must appear >=10 times to
# be TRUSTED), 100 bills × ~30 events = ~3,000 events isn't enough to
# cover the EventCode alphabet. Many real codes get filtered out as
# "rare" and the math doesn't actually prove anything.
#
# Cardinality of the universe: the cold-start drain (2026-05-08) had
# loaded=3,645 bills in the persistent cache. Setting SAMPLE_BILLS to
# a number >= that bound means we sample every distinct bill in
# HISTORY.CSV. The Phase-0 checkpoint handles the resulting
# 7,000-API-call workload across multiple workflow runs if needed.
#
# Cost analysis:
#   ~3,600 bills × 2 API calls = ~7,200 LIS requests
#   At ~1-2 calls/sec with backoff = 60-120 min wall clock for a
#   from-scratch run. Checkpointing every 25 bills keeps the
#   resume-loss bounded to one batch.
SAMPLE_BILLS = 10_000               # effectively "all" — the sample is bounded by the distinct-bill universe
HELDOUT_FRACTION = 0.2
RANDOM_SEED = 20260511              # deterministic so re-runs hit the same sample
CHECKPOINT_BATCH = 25               # bills per checkpoint flush (was 10; raised for higher volume)

# Checkpoint tab: appended incrementally during PHASE 0.
RAW_CORPUS_TAB = "C7_1a_RawCorpus"
RAW_CORPUS_HEADER = [
    "Bill", "LegislationEventID", "EventDate", "EventCode",
    "ChamberCode", "Description",
]
# Codex P1 review fix (2026-05-11): distinguish three fetch outcomes
# so transient API failures are NOT checkpointed as "confirmed empty"
# (which would silently bias the corpus + skip permanently on rerun).
#
# Confirmed-empty bills (LIS returned no LegislationID OR an empty
# events list) are checkpointed with a single sentinel row where
# EventCode = `_CONFIRMED_EMPTY_` and other event columns are blank;
# this is distinguishable from "fetched with events" (real EventCode)
# AND from "not yet fetched" (no row at all).
#
# Failed bills are NOT checkpointed; they remain in to_fetch on
# resume so transient failures retry naturally.
CONFIRMED_EMPTY_SENTINEL = "_CONFIRMED_EMPTY_"

# Output tabs (rewritten on each completion).
TOKEN_STATS_TAB = "C7_1a_TokenStats"
TOKEN_STATS_HEADER = [
    "Token", "Support", "Entropy_bits",
    "Top_EventCode", "Top_Probability", "Trusted",
]
DLQ_SAMPLES_TAB = "C7_1a_DLQ_Samples"
DLQ_SAMPLES_HEADER = [
    "Bill", "History_Date", "Outcome", "DLQ_Reason",
    "Trusted_Token_Count", "Top_Votes", "Second_Votes", "Margin",
]
SUMMARY_TAB = "C7_1a_Summary"
SUMMARY_HEADER = [
    "Key", "Value",
]

# Headline trust thresholds. The sweep grid below explores the
# neighborhood; this is the point we report as "the chosen
# configuration." All four parameters are tunable; the sweep tells
# us if a different point would be materially better.
HEADLINE_MIN_SUPPORT = 10
HEADLINE_MAX_ENTROPY = 1.0
HEADLINE_MIN_TRUSTED_TOKENS = 2
HEADLINE_MIN_TOP_VOTES = 2
HEADLINE_MIN_MARGIN = 1

SWEEP_MIN_SUPPORT = [5, 10, 20, 50]
SWEEP_MAX_ENTROPY = [0.5, 1.0, 1.5, 2.0]

# Networking budgets
LIS_TIMEOUT_S = 15
LIS_RETRY_MAX = 3
LIS_RETRY_BACKOFF_S = 2.0


# ---------------------------------------------------------------------------
# Authentication + sheet handle
# ---------------------------------------------------------------------------

def authenticate_sheets() -> gspread.Spreadsheet:
    """Returns the Mastermind DB spreadsheet handle."""
    raw = os.environ.get("GCP_CREDENTIALS")
    if not raw:
        raise RuntimeError(
            "GCP_CREDENTIALS env var is empty. The workflow must inject it."
        )
    creds_dict = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=GSHEET_SCOPES,
    )
    client = gspread.authorize(creds)
    return client.open_by_key(GSHEET_ID)


def get_or_create_tab(
    sheet: gspread.Spreadsheet, name: str, header: list[str], rows: int = 1000,
) -> gspread.Worksheet:
    """Idempotent: open if exists, else create with header."""
    try:
        ws = sheet.worksheet(name)
        return ws
    except WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows=rows, cols=len(header))
        ws.update(values=[header], range_name="A1")
        print(f"📝 Created {name} ({rows} rows x {len(header)} cols).")
        return ws


# ---------------------------------------------------------------------------
# PHASE 0: LIS corpus fetch (with checkpoint)
# ---------------------------------------------------------------------------

def fetch_history_csv() -> pd.DataFrame:
    """Pull HISTORY.CSV from the canonical Azure blob URL.

    Mirrors calendar_worker.py:2574. ISO-8859-1 encoding per the brain.
    Returns a DataFrame with at least Bill_id, History_date,
    History_description.
    """
    print(f"📡 Downloading HISTORY.CSV from {HISTORY_CSV_URL} ...")
    response = requests.get(HISTORY_CSV_URL, timeout=30)
    response.raise_for_status()
    df = pd.read_csv(io.BytesIO(response.content), encoding="iso-8859-1")
    # Gemini medium review fix: strip whitespace from column names so
    # downstream substring matches don't trip on " BillNumber" etc.
    # Mirrors calendar_worker.py:1340.
    df.columns = df.columns.str.strip()
    print(f"✅ HISTORY.CSV: {len(df):,} rows, columns: {list(df.columns)}")
    return df


def _find_bill_column(history_df: pd.DataFrame) -> str:
    """Locate the bill-number column robustly.

    Gemini HIGH review fix: production HISTORY.CSV often uses
    `BillNumber` (or `Bill_id` for older snapshots). Match by
    substring `bill` in column name (same pattern as
    calendar_worker.py:2669), with explicit failure if absent.
    """
    candidates = [c for c in history_df.columns if "bill" in c.lower()]
    if not candidates:
        raise RuntimeError(
            f"HISTORY.CSV has no bill column; saw {list(history_df.columns)}"
        )
    # Prefer an exact match if present, else the first substring hit.
    for preferred in ("Bill_id", "BillNumber", "Bill"):
        for c in candidates:
            if c == preferred:
                return c
    return candidates[0]


def sample_bills(history_df: pd.DataFrame, n: int, seed: int) -> list[str]:
    """Deterministic random sample of distinct bills from HISTORY.

    Sorted before sampling so the choice is reproducible across runs
    (set-iteration order is not stable). If n exceeds the universe
    size, returns the full universe (the post-correction default).
    """
    bill_col = _find_bill_column(history_df)
    distinct = sorted({str(b).strip() for b in history_df[bill_col] if str(b).strip()})
    if n is None or n <= 0 or n >= len(distinct):
        return distinct
    rng = random.Random(seed)
    return rng.sample(distinct, k=n)


def read_checkpoint(corpus_ws: gspread.Worksheet) -> tuple[set[str], list[dict]]:
    """Read existing rows from C7_1a_RawCorpus.

    Returns (already_fetched_bills_set, prior_events_list_of_dicts).
    A run that completed PHASE 0 partially produced rows for some
    bills; those are loaded so PHASE 0 only fetches the rest.
    """
    values = corpus_ws.get_all_values()
    if not values or len(values) <= 1:
        return set(), []
    header = values[0]
    # Header column index map. Verifies the persisted schema matches
    # the current header (otherwise a schema drift would silently
    # mis-read values).
    try:
        col_idx = {col: header.index(col) for col in RAW_CORPUS_HEADER}
    except ValueError:
        print(
            f"⚠️ {RAW_CORPUS_TAB} header mismatch: got {header!r}; expected "
            f"{RAW_CORPUS_HEADER!r}. Discarding checkpoint."
        )
        return set(), []
    fetched: set[str] = set()
    events: list[dict] = []
    for row in values[1:]:
        if not row or len(row) <= col_idx["Bill"]:
            continue
        bill = row[col_idx["Bill"]].strip()
        if not bill:
            continue
        fetched.add(bill)
        events.append({
            "Bill": bill,
            "LegislationEventID": row[col_idx["LegislationEventID"]] if col_idx["LegislationEventID"] < len(row) else "",
            "EventDate": row[col_idx["EventDate"]] if col_idx["EventDate"] < len(row) else "",
            "EventCode": row[col_idx["EventCode"]] if col_idx["EventCode"] < len(row) else "",
            "ChamberCode": row[col_idx["ChamberCode"]] if col_idx["ChamberCode"] < len(row) else "",
            "Description": row[col_idx["Description"]] if col_idx["Description"] < len(row) else "",
        })
    return fetched, events


def append_checkpoint(corpus_ws: gspread.Worksheet, new_event_rows: list[list]) -> None:
    """Append a batch of fetched event rows to the checkpoint tab."""
    if not new_event_rows:
        return
    corpus_ws.append_rows(new_event_rows, value_input_option="RAW")


class FetchResult(Enum):
    """Codex P1 review fix: distinguish failure modes so the checkpoint
    doesn't conflate transient errors with confirmed-empty bills.

      OK      — got events; check the returned list
      EMPTY   — confirmed empty (no LegislationID or empty events list).
                Bill is structurally absent from LIS LegislationEvent;
                that's a stable fact, safe to checkpoint as known-empty.
      FAILED  — transient failure (retries exhausted, JSON parse, HTTP
                5xx, network timeout). Bill is NOT checkpointed; will
                be retried on the next workflow run.
    """
    OK = "OK"
    EMPTY = "EMPTY"
    FAILED = "FAILED"


def lis_fetch_with_retry(
    url: str, params: dict, kind: str,
) -> tuple[FetchResult, dict | None]:
    """GET with exponential backoff.

    Returns (status, parsed_json). status is FAILED for any transient
    error, OK for successful 200+JSON, EMPTY is never returned here
    (only the caller can interpret an empty response payload).

    Gemini medium review fix: true exponential backoff (2**attempt)
    instead of the prior linear (attempt + 1).
    """
    last_err = None
    for attempt in range(LIS_RETRY_MAX):
        try:
            r = requests.get(
                url, headers=LIS_HEADERS, params=params, timeout=LIS_TIMEOUT_S,
            )
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(LIS_RETRY_BACKOFF_S * (2 ** attempt))
            continue
        if r.status_code != 200:
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            # 4xx is non-retryable except 429 (rate limit)
            if r.status_code != 429 and 400 <= r.status_code < 500:
                break
            time.sleep(LIS_RETRY_BACKOFF_S * (2 ** attempt))
            continue
        try:
            return FetchResult.OK, r.json()
        except Exception as e:
            last_err = f"JSON parse: {type(e).__name__}: {e}"
            break
    print(f"⚠️ {kind} fetch FAILED after {LIS_RETRY_MAX} attempts: {last_err}")
    return FetchResult.FAILED, None


def fetch_legislation_events_for_bill(
    bill_num: str,
) -> tuple[FetchResult, list[dict]]:
    """Two-step LIS lookup with explicit failure distinction.

    Returns:
      (OK, [event, event, ...])      — fetched, has events
      (EMPTY, [])                    — fetched, confirmed no events
                                       (no LegislationID OR empty list)
      (FAILED, [])                   — transient failure; do not
                                       checkpoint; caller should retry
                                       on next workflow run

    Empty vs failed is determined by whether we got a clean HTTP 200
    + valid JSON back at every step. A 5xx, timeout, or JSON parse
    error is FAILED. A 200 with an empty response payload is EMPTY.
    """
    v_status, version_json = lis_fetch_with_retry(
        LEGISLATION_VERSION_URL,
        {"billNumber": bill_num, "sessionCode": SESSION_CODE_5D},
        kind=f"LegislationVersion[{bill_num}]",
    )
    if v_status == FetchResult.FAILED:
        return FetchResult.FAILED, []
    if not isinstance(version_json, dict):
        # OK status but unparsable structure — treat as FAILED so we
        # retry rather than checkpoint as empty.
        return FetchResult.FAILED, []
    versions_list = version_json.get("LegislationsVersion") or []
    if not versions_list:
        # 200 with no versions — the bill genuinely has no LegislationID.
        return FetchResult.EMPTY, []
    first = versions_list[0]
    if not isinstance(first, dict):
        return FetchResult.FAILED, []
    legislation_id = first.get("LegislationID")
    if not legislation_id:
        return FetchResult.EMPTY, []
    e_status, events_payload = lis_fetch_with_retry(
        LEGISLATION_EVENT_URL,
        {"legislationID": legislation_id, "sessionCode": SESSION_CODE_5D},
        kind=f"LegislationEvent[{bill_num}/{legislation_id}]",
    )
    if e_status == FetchResult.FAILED:
        return FetchResult.FAILED, []
    if not isinstance(events_payload, dict):
        return FetchResult.FAILED, []
    events = events_payload.get("LegislationEvents") or []
    if not isinstance(events, list):
        return FetchResult.FAILED, []
    if len(events) == 0:
        return FetchResult.EMPTY, []
    return FetchResult.OK, events


def phase_0_fetch_corpus(
    sheet: gspread.Spreadsheet, target_bills: list[str],
) -> tuple[list[dict], list[str]]:
    """Fetch LegEvent events for target_bills, checkpointing every N bills.

    Codex P1 review fix: distinguish three outcomes per bill.
      - OK     -> checkpoint event rows; add to already_fetched
      - EMPTY  -> checkpoint a single sentinel row with EventCode =
                  CONFIRMED_EMPTY_SENTINEL; add to already_fetched
      - FAILED -> DO NOT checkpoint; bill remains in to_fetch on
                  next workflow run for natural retry

    Returns (all_events, failed_bills). all_events covers prior +
    new OK fetches. failed_bills is reported in the summary so
    transient failures are visible.
    """
    corpus_ws = get_or_create_tab(
        sheet, RAW_CORPUS_TAB, RAW_CORPUS_HEADER, rows=50_000,
    )
    already_fetched, prior_events = read_checkpoint(corpus_ws)
    print(
        f"📚 PHASE 0 checkpoint: {len(already_fetched)} bills already fetched "
        f"({len(prior_events)} event rows on tab — sentinels for confirmed-empty "
        f"are counted as fetched but contribute no events to the corpus)."
    )

    # Filter prior_events down to actual events (drop confirmed-empty sentinels)
    prior_real_events = [
        e for e in prior_events
        if e.get("EventCode") and e.get("EventCode") != CONFIRMED_EMPTY_SENTINEL
    ]
    if len(prior_real_events) != len(prior_events):
        print(
            f"   ({len(prior_events) - len(prior_real_events)} sentinel rows "
            f"filtered out of the training corpus.)"
        )

    to_fetch = [b for b in target_bills if b not in already_fetched]
    print(
        f"📡 PHASE 0: fetching events for {len(to_fetch)} of {len(target_bills)} "
        f"target bills ..."
    )
    pending_rows: list[list] = []
    new_events: list[dict] = []
    confirmed_empty_count = 0
    failed_bills: list[str] = []
    for i, bill in enumerate(to_fetch, start=1):
        status, events = fetch_legislation_events_for_bill(bill)
        if status == FetchResult.FAILED:
            # DO NOT checkpoint. Bill stays in to_fetch on resume.
            failed_bills.append(bill)
        elif status == FetchResult.EMPTY:
            # Checkpoint a sentinel row so we don't refetch on resume.
            pending_rows.append([bill, "", "", CONFIRMED_EMPTY_SENTINEL, "", ""])
            already_fetched.add(bill)
            confirmed_empty_count += 1
        else:  # OK
            for e in events:
                pending_rows.append([
                    bill,
                    str(e.get("LegislationEventID", "")),
                    str(e.get("EventDate", ""))[:25],
                    str(e.get("EventCode", "")),
                    str(e.get("ChamberCode", "")),
                    str(e.get("Description", ""))[:1000],
                ])
                new_events.append({
                    "Bill": bill,
                    "LegislationEventID": e.get("LegislationEventID", ""),
                    "EventDate": e.get("EventDate", ""),
                    "EventCode": e.get("EventCode", ""),
                    "ChamberCode": e.get("ChamberCode", ""),
                    "Description": e.get("Description", ""),
                })
            already_fetched.add(bill)
        # Checkpoint every N bills (whichever finishes first: i counter
        # or the pending_rows buffer hitting a threshold).
        if i % CHECKPOINT_BATCH == 0 and pending_rows:
            append_checkpoint(corpus_ws, pending_rows)
            print(
                f"  💾 checkpoint at {i}/{len(to_fetch)} bills "
                f"(wrote {len(pending_rows)} rows, "
                f"confirmed-empty={confirmed_empty_count}, "
                f"failed={len(failed_bills)})"
            )
            pending_rows = []
    # Final flush
    if pending_rows:
        append_checkpoint(corpus_ws, pending_rows)
        print(
            f"  💾 final checkpoint flush: {len(pending_rows)} new rows."
        )
    all_events = prior_real_events + new_events
    print(
        f"✅ PHASE 0 complete: {len(all_events)} total events from corpus "
        f"({len(already_fetched)} bills marked fetched, "
        f"{confirmed_empty_count} new confirmed-empty, "
        f"{len(failed_bills)} FAILED — will retry on next workflow run)."
    )
    if failed_bills:
        print(
            f"⚠️ FAILED bills (sample of up to 20): "
            f"{', '.join(failed_bills[:20])}"
            + (f" ... +{len(failed_bills) - 20} more" if len(failed_bills) > 20 else "")
        )
    return all_events, failed_bills


# ---------------------------------------------------------------------------
# PHASE 1: Build token stats from training corpus
# ---------------------------------------------------------------------------

def split_training_validation(
    events_by_bill: dict[str, list[dict]],
    holdout_fraction: float,
    seed: int,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Bill-level split: 80% of bills' events train; 20% validate.

    Bill-level (not event-level) split prevents leakage where the same
    bill's events appear in both train and test.
    """
    bills = sorted(events_by_bill.keys())
    rng = random.Random(seed)
    rng.shuffle(bills)
    n_holdout = int(len(bills) * holdout_fraction)
    holdout_bills = set(bills[:n_holdout])
    train_pairs: list[tuple[str, str]] = []
    held_pairs: list[tuple[str, str]] = []
    for bill, events in events_by_bill.items():
        for e in events:
            d = str(e.get("Description", "") or "")
            c = str(e.get("EventCode", "") or "")
            if not d or not c:
                continue
            if bill in holdout_bills:
                held_pairs.append((d, c))
            else:
                train_pairs.append((d, c))
    return train_pairs, held_pairs


def write_token_stats_tab(
    sheet: gspread.Spreadsheet,
    stats: dict[str, TokenStats],
) -> None:
    ws = get_or_create_tab(
        sheet, TOKEN_STATS_TAB, TOKEN_STATS_HEADER,
        rows=max(2000, len(stats) + 100),
    )
    rows = [TOKEN_STATS_HEADER]
    for ts in sorted(stats.values(), key=lambda x: (-x.support, x.token)):
        rows.append([
            ts.token,
            ts.support,
            round(ts.entropy, 4),
            ts.top_event_code,
            round(ts.top_probability, 4),
            "TRUE" if ts.trusted else "FALSE",
        ])
    ws.update(values=rows, range_name="A1")
    # Clear trailing rows (write-then-clear-trailing pattern from
    # PR-C7 Gemini review).
    allocated = ws.row_count
    if allocated > len(rows):
        ws.batch_clear([f"A{len(rows) + 1}:F{allocated}"])
    print(f"📝 Wrote {len(stats):,} tokens to {TOKEN_STATS_TAB}.")


# ---------------------------------------------------------------------------
# PHASE 2: Score the FULL HISTORY corpus
# ---------------------------------------------------------------------------

def score_full_history(
    history_df: pd.DataFrame,
    token_stats: dict[str, TokenStats],
    *,
    min_trusted_tokens: int,
    min_top_votes: int,
    min_margin: int,
) -> tuple[Counter, list[dict]]:
    """Apply trust math to every HISTORY row.

    Returns:
      - reason_counter: Counter of {"PASS", DLQ_reason_1, ...}
      - dlq_samples: up to 50 DLQ rows (with full context) for manual inspection
    """
    # Gemini HIGH review fix: substring-match column lookups so
    # this works on both BillNumber and Bill_id schemas.
    desc_col = next(
        (c for c in history_df.columns if "desc" in c.lower() or "action" in c.lower()),
        None,
    )
    bill_col = _find_bill_column(history_df)
    date_col = next(
        (c for c in history_df.columns if "date" in c.lower()),
        None,
    )
    if not desc_col:
        raise RuntimeError(
            f"HISTORY.CSV has no description column; saw {list(history_df.columns)}"
        )
    counter: Counter = Counter()
    samples: list[dict] = []
    SAMPLE_CAP = 50
    for _, row in history_df.iterrows():
        outcome = str(row[desc_col]) if pd.notna(row[desc_col]) else ""
        verdict = score_row(
            outcome,
            token_stats,
            min_trusted_tokens=min_trusted_tokens,
            min_top_votes=min_top_votes,
            min_margin=min_margin,
        )
        if verdict.verdict == "PASS":
            counter["PASS"] += 1
        else:
            counter[verdict.reason] += 1
            if len(samples) < SAMPLE_CAP and verdict.reason != DLQ_NO_TRUSTED_TOKENS:
                # Skip the most-common reason (no trusted tokens at all)
                # in the sample so the inspection cap covers the more
                # informative failures. The counter still has the totals.
                samples.append({
                    "bill": str(row[bill_col]) if bill_col else "",
                    "date": str(row[date_col]) if date_col else "",
                    "outcome": outcome[:300],
                    "reason": verdict.reason,
                    "trusted_tokens": verdict.trusted_tokens_used,
                    "top_votes": verdict.top_votes,
                    "second_votes": verdict.second_votes,
                    "margin": verdict.margin,
                })
            elif len(samples) < SAMPLE_CAP and verdict.reason == DLQ_NO_TRUSTED_TOKENS and counter[DLQ_NO_TRUSTED_TOKENS] < 5:
                # Keep a few NO_TRUSTED_TOKENS examples too, just enough
                # to confirm they're genuinely token-poor.
                samples.append({
                    "bill": str(row[bill_col]) if bill_col else "",
                    "date": str(row[date_col]) if date_col else "",
                    "outcome": outcome[:300],
                    "reason": verdict.reason,
                    "trusted_tokens": 0,
                    "top_votes": 0,
                    "second_votes": 0,
                    "margin": 0,
                })
    return counter, samples


def write_dlq_samples(sheet: gspread.Spreadsheet, samples: list[dict]) -> None:
    ws = get_or_create_tab(
        sheet, DLQ_SAMPLES_TAB, DLQ_SAMPLES_HEADER,
        rows=max(200, len(samples) + 50),
    )
    rows = [DLQ_SAMPLES_HEADER]
    for s in samples:
        rows.append([
            s["bill"], s["date"], s["outcome"], s["reason"],
            s["trusted_tokens"], s["top_votes"], s["second_votes"], s["margin"],
        ])
    ws.update(values=rows, range_name="A1")
    allocated = ws.row_count
    if allocated > len(rows):
        ws.batch_clear([f"A{len(rows) + 1}:H{allocated}"])
    print(f"📝 Wrote {len(samples)} DLQ samples to {DLQ_SAMPLES_TAB}.")


# ---------------------------------------------------------------------------
# PHASE 3: Sweep + summary
# ---------------------------------------------------------------------------

def run_sweep(
    history_df: pd.DataFrame,
    training_pairs: list[tuple[str, str]],
    held_out_pairs: list[tuple[str, str]],
) -> list[dict]:
    """Cartesian sweep over (MIN_SUPPORT, MAX_ENTROPY).

    Holds MIN_TRUSTED_TOKENS / MIN_TOP_VOTES / MIN_MARGIN at headline
    defaults — those govern row-level rigor (independent of token-level
    rigor) and don't interact with the sweep dimensions.
    """
    sweep_results: list[dict] = []
    desc_col = next(
        (c for c in history_df.columns if "desc" in c.lower() or "action" in c.lower()),
        None,
    )
    if not desc_col:
        return sweep_results
    descriptions = [
        str(d) if pd.notna(d) else ""
        for d in history_df[desc_col]
    ]
    for min_support in SWEEP_MIN_SUPPORT:
        for max_entropy in SWEEP_MAX_ENTROPY:
            stats = compute_token_stats(
                training_pairs,
                min_support=min_support,
                max_entropy=max_entropy,
            )
            n_trusted = sum(1 for ts in stats.values() if ts.trusted)
            # Score the full HISTORY
            counter: Counter = Counter()
            for outcome in descriptions:
                v = score_row(
                    outcome, stats,
                    min_trusted_tokens=HEADLINE_MIN_TRUSTED_TOKENS,
                    min_top_votes=HEADLINE_MIN_TOP_VOTES,
                    min_margin=HEADLINE_MIN_MARGIN,
                )
                counter["PASS" if v.verdict == "PASS" else "DLQ"] += 1
            total = sum(counter.values()) or 1
            pass_rate = counter["PASS"] / total
            # Validation accuracy on held-out
            v_result = validate_against_held_out(
                held_out_pairs, stats,
                min_trusted_tokens=HEADLINE_MIN_TRUSTED_TOKENS,
                min_top_votes=HEADLINE_MIN_TOP_VOTES,
                min_margin=HEADLINE_MIN_MARGIN,
            )
            sweep_results.append({
                "min_support": min_support,
                "max_entropy": max_entropy,
                "n_trusted_tokens": n_trusted,
                "pass_rate": pass_rate,
                "dlq_rate": 1 - pass_rate,
                "n_history_rows": total,
                "n_passed": counter["PASS"],
                "n_dlq": counter["DLQ"],
                "heldout_n_passed": v_result["n_passed"],
                "heldout_n_correct_among_passed": v_result["n_correct_among_passed"],
                "heldout_precision_on_passed": v_result["precision_on_passed"],
                "heldout_n_total": v_result["n_held_out"],
            })
    return sweep_results


def write_summary(
    sheet: gspread.Spreadsheet,
    summary: dict,
) -> None:
    """Single-row-per-key summary table (Key, Value).

    Easier to consume than wide schema; lets us add new fields without
    a schema migration.
    """
    ws = get_or_create_tab(sheet, SUMMARY_TAB, SUMMARY_HEADER, rows=200)
    rows = [SUMMARY_HEADER]
    for k, v in summary.items():
        rows.append([k, str(v) if not isinstance(v, str) else v])
    ws.update(values=rows, range_name="A1")
    allocated = ws.row_count
    if allocated > len(rows):
        ws.batch_clear([f"A{len(rows) + 1}:B{allocated}"])
    print(f"📝 Wrote {len(summary)} summary keys to {SUMMARY_TAB}.")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main() -> int:
    start_utc = datetime.now(timezone.utc)
    print(f"🚀 PR-C7.1a audit start {start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(
        f"   sample_bills={SAMPLE_BILLS}, holdout_fraction={HELDOUT_FRACTION}, "
        f"seed={RANDOM_SEED}"
    )
    print(
        f"   headline thresholds: min_support>={HEADLINE_MIN_SUPPORT}, "
        f"max_entropy<={HEADLINE_MAX_ENTROPY} bits, "
        f"min_trusted_tokens>={HEADLINE_MIN_TRUSTED_TOKENS}, "
        f"min_top_votes>={HEADLINE_MIN_TOP_VOTES}, "
        f"min_margin>={HEADLINE_MIN_MARGIN}"
    )
    sheet = authenticate_sheets()

    # PHASE 0a: HISTORY.CSV
    history_df = fetch_history_csv()

    # PHASE 0b: target bills + LIS fetch with checkpointing
    target_bills = sample_bills(history_df, SAMPLE_BILLS, RANDOM_SEED)
    print(
        f"📊 Target bills: {len(target_bills)} (sample cap was {SAMPLE_BILLS}; "
        f"distinct bills in HISTORY.CSV is the binding constraint when "
        f"SAMPLE_BILLS exceeds the universe)."
    )
    events, failed_bills = phase_0_fetch_corpus(sheet, target_bills)

    # Group events by bill for the split
    events_by_bill: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        b = str(e.get("Bill", "")).strip()
        if b:
            events_by_bill[b].append(e)
    n_bills_with_events = sum(1 for v in events_by_bill.values() if any(e.get("EventCode") for e in v))
    print(
        f"📊 Corpus shape: {len(events_by_bill)} bills, "
        f"{n_bills_with_events} with at least one EventCode, "
        f"{sum(len(v) for v in events_by_bill.values())} total events."
    )

    # PHASE 1: training/validation split + token stats
    train_pairs, held_pairs = split_training_validation(
        events_by_bill, HELDOUT_FRACTION, RANDOM_SEED,
    )
    print(
        f"📊 Split: {len(train_pairs)} training pairs, "
        f"{len(held_pairs)} held-out pairs."
    )
    if not train_pairs:
        print(
            "❌ No training pairs after split — corpus has no (description, "
            "EventCode) data. Aborting math phases."
        )
        return 1
    headline_stats = compute_token_stats(
        train_pairs,
        min_support=HEADLINE_MIN_SUPPORT,
        max_entropy=HEADLINE_MAX_ENTROPY,
    )
    n_trusted = sum(1 for ts in headline_stats.values() if ts.trusted)
    print(
        f"📊 Token stats: {len(headline_stats):,} distinct tokens; "
        f"{n_trusted:,} trusted at headline thresholds."
    )
    write_token_stats_tab(sheet, headline_stats)

    # PHASE 2: full-HISTORY score under headline thresholds
    counter, dlq_samples = score_full_history(
        history_df, headline_stats,
        min_trusted_tokens=HEADLINE_MIN_TRUSTED_TOKENS,
        min_top_votes=HEADLINE_MIN_TOP_VOTES,
        min_margin=HEADLINE_MIN_MARGIN,
    )
    total_rows = sum(counter.values()) or 1
    pass_rows = counter["PASS"]
    dlq_rows = total_rows - pass_rows
    pass_rate = pass_rows / total_rows
    print(
        f"📊 PHASE 2 (headline): {pass_rows:,}/{total_rows:,} PASS "
        f"({pass_rate:.2%}), {dlq_rows:,} DLQ ({1 - pass_rate:.2%})."
    )
    print(f"📊 DLQ reason breakdown:")
    for reason, n in counter.most_common():
        print(f"     {reason}: {n:,} ({n / total_rows:.2%})")
    write_dlq_samples(sheet, dlq_samples)

    # PHASE 2b: validation accuracy on held-out
    validation = validate_against_held_out(
        held_pairs, headline_stats,
        min_trusted_tokens=HEADLINE_MIN_TRUSTED_TOKENS,
        min_top_votes=HEADLINE_MIN_TOP_VOTES,
        min_margin=HEADLINE_MIN_MARGIN,
    )
    print(
        f"📊 Validation: {validation['n_passed']}/{validation['n_held_out']} "
        f"held-out events scored as PASS ("
        f"{validation['n_passed'] / max(1, validation['n_held_out']):.2%}), "
        f"{validation['n_correct_among_passed']} correct "
        f"({validation['precision_on_passed']:.2%} precision on passed)."
    )

    # PHASE 3: sweep
    print(f"📊 PHASE 3: sweeping (MIN_SUPPORT, MAX_ENTROPY)...")
    sweep_results = run_sweep(history_df, train_pairs, held_pairs)
    print(f"  {'min_sup':<8} {'max_ent':<8} {'n_trust':<9} {'pass_rate':<10} {'val_prec':<10}")
    for r in sweep_results:
        print(
            f"  {r['min_support']:<8} {r['max_entropy']:<8.2f} "
            f"{r['n_trusted_tokens']:<9,} {r['pass_rate']:<10.2%} "
            f"{r['heldout_precision_on_passed']:<10.2%}"
        )

    # Write the summary tab
    end_utc = datetime.now(timezone.utc)
    elapsed = (end_utc - start_utc).total_seconds()
    summary: dict = {
        "run_utc_start": start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_utc_end": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_seconds": round(elapsed, 1),
        "sample_bills_cap": SAMPLE_BILLS,
        "target_bills": len(target_bills),
        "bills_failed_this_run": len(failed_bills),
        "sample_bills_with_events": n_bills_with_events,
        "training_pairs": len(train_pairs),
        "heldout_pairs": len(held_pairs),
        "distinct_tokens": len(headline_stats),
        "trusted_tokens_headline": n_trusted,
        "headline_min_support": HEADLINE_MIN_SUPPORT,
        "headline_max_entropy": HEADLINE_MAX_ENTROPY,
        "headline_min_trusted_tokens": HEADLINE_MIN_TRUSTED_TOKENS,
        "headline_min_top_votes": HEADLINE_MIN_TOP_VOTES,
        "headline_min_margin": HEADLINE_MIN_MARGIN,
        "history_total_rows": total_rows,
        "history_pass_rows": pass_rows,
        "history_dlq_rows": dlq_rows,
        "history_pass_rate": f"{pass_rate:.4f}",
        "history_dlq_rate": f"{1 - pass_rate:.4f}",
        "dlq_no_trusted_tokens": counter.get(DLQ_NO_TRUSTED_TOKENS, 0),
        "dlq_insufficient_trusted_tokens": counter.get(DLQ_INSUFFICIENT_TRUSTED_TOKENS, 0),
        "dlq_insufficient_top_votes": counter.get(DLQ_INSUFFICIENT_TOP_VOTES, 0),
        "dlq_insufficient_margin": counter.get(DLQ_INSUFFICIENT_MARGIN, 0),
        "validation_n_heldout": validation["n_held_out"],
        "validation_n_passed": validation["n_passed"],
        "validation_n_correct": validation["n_correct_among_passed"],
        "validation_precision_on_passed": f"{validation['precision_on_passed']:.4f}",
        "sweep_results_json": json.dumps(sweep_results),
    }
    write_summary(sheet, summary)
    print(
        f"✅ PR-C7.1a complete in {elapsed:.1f}s. "
        f"Headline PASS rate: {pass_rate:.2%} on {total_rows:,} HISTORY rows. "
        f"Validation precision on passed: {validation['precision_on_passed']:.2%}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
