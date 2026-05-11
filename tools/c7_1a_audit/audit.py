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

# Sample size for the LIS fetch phase. 100 bills × ~30 events average
# = ~3,000 labeled training pairs. Well within rate-limit budget
# (~200 API calls total at 2 per bill).
SAMPLE_BILLS = 100
HELDOUT_FRACTION = 0.2
RANDOM_SEED = 20260511  # deterministic so re-runs hit the same sample

# Checkpoint tab: appended incrementally during PHASE 0.
RAW_CORPUS_TAB = "C7_1a_RawCorpus"
RAW_CORPUS_HEADER = [
    "Bill", "LegislationEventID", "EventDate", "EventCode",
    "ChamberCode", "Description",
]
RAW_CORPUS_CHECKPOINT_BATCH = 10

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
    print(f"✅ HISTORY.CSV: {len(df):,} rows, columns: {list(df.columns)}")
    return df


def sample_bills(history_df: pd.DataFrame, n: int, seed: int) -> list[str]:
    """Deterministic random sample of distinct Bill_id values from HISTORY.

    Sorted before sampling so the choice is reproducible across runs
    (set-iteration order is not stable).
    """
    bill_col = next(c for c in history_df.columns if c.lower() == "bill_id")
    distinct = sorted({str(b).strip() for b in history_df[bill_col] if str(b).strip()})
    rng = random.Random(seed)
    return rng.sample(distinct, k=min(n, len(distinct)))


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


def lis_fetch_with_retry(url: str, params: dict, kind: str) -> dict | None:
    """GET with exponential backoff. Returns parsed JSON dict or None.

    Caller is responsible for downstream None handling. We never raise
    so a single bad bill doesn't crash the whole audit; the failed
    bill is logged and the audit continues with the rest.
    """
    last_err = None
    for attempt in range(LIS_RETRY_MAX):
        try:
            r = requests.get(
                url, headers=LIS_HEADERS, params=params, timeout=LIS_TIMEOUT_S,
            )
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(LIS_RETRY_BACKOFF_S * (attempt + 1))
            continue
        if r.status_code != 200:
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            # 4xx is non-retryable except 429 (rate limit)
            if r.status_code != 429 and 400 <= r.status_code < 500:
                break
            time.sleep(LIS_RETRY_BACKOFF_S * (attempt + 1))
            continue
        try:
            return r.json()
        except Exception as e:
            last_err = f"JSON parse: {type(e).__name__}: {e}"
            break
    print(f"⚠️ {kind} fetch gave up after {LIS_RETRY_MAX} attempts: {last_err}")
    return None


def fetch_legislation_events_for_bill(bill_num: str) -> list[dict]:
    """Two-step LIS lookup. Returns list of event dicts (possibly empty)."""
    version = lis_fetch_with_retry(
        LEGISLATION_VERSION_URL,
        {"billNumber": bill_num, "sessionCode": SESSION_CODE_5D},
        kind=f"LegislationVersion[{bill_num}]",
    )
    if not isinstance(version, dict):
        return []
    versions_list = version.get("LegislationsVersion") or []
    if not versions_list:
        return []
    legislation_id = versions_list[0].get("LegislationID")
    if not legislation_id:
        return []
    events_payload = lis_fetch_with_retry(
        LEGISLATION_EVENT_URL,
        {"legislationID": legislation_id, "sessionCode": SESSION_CODE_5D},
        kind=f"LegislationEvent[{bill_num}/{legislation_id}]",
    )
    if not isinstance(events_payload, dict):
        return []
    events = events_payload.get("LegislationEvents") or []
    return events if isinstance(events, list) else []


def phase_0_fetch_corpus(
    sheet: gspread.Spreadsheet, target_bills: list[str],
) -> list[dict]:
    """Fetch LegEvent events for target_bills, checkpointing every N bills.

    Returns a list of event dicts. Each event dict carries:
      Bill, LegislationEventID, EventDate, EventCode, ChamberCode,
      Description.
    """
    corpus_ws = get_or_create_tab(
        sheet, RAW_CORPUS_TAB, RAW_CORPUS_HEADER, rows=5000,
    )
    already_fetched, prior_events = read_checkpoint(corpus_ws)
    print(
        f"📚 PHASE 0 checkpoint: {len(already_fetched)} bills already fetched, "
        f"{len(prior_events)} events on tab."
    )

    to_fetch = [b for b in target_bills if b not in already_fetched]
    print(
        f"📡 PHASE 0: fetching events for {len(to_fetch)} of {len(target_bills)} "
        f"target bills ..."
    )
    pending_rows: list[list] = []
    new_events: list[dict] = []
    fail_count = 0
    for i, bill in enumerate(to_fetch, start=1):
        events = fetch_legislation_events_for_bill(bill)
        if not events:
            fail_count += 1
            # We DO record the bill as "fetched (empty)" so we don't
            # retry it on resume. The corpus tab's row count for this
            # bill will be zero — by design, not by failure.
            pending_rows.append([bill, "", "", "", "", ""])
            already_fetched.add(bill)
        else:
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
        # Checkpoint every N bills
        if i % RAW_CORPUS_CHECKPOINT_BATCH == 0:
            append_checkpoint(corpus_ws, pending_rows)
            print(
                f"  💾 checkpoint at {i}/{len(to_fetch)} bills "
                f"(wrote {len(pending_rows)} new rows, {fail_count} no-event so far)"
            )
            pending_rows = []
    # Final flush
    if pending_rows:
        append_checkpoint(corpus_ws, pending_rows)
        print(
            f"  💾 final checkpoint flush: {len(pending_rows)} new rows."
        )
    all_events = prior_events + new_events
    print(
        f"✅ PHASE 0 complete: {len(all_events)} total events from "
        f"{len(already_fetched)} bills ({fail_count} new fetches returned empty)."
    )
    return all_events


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
    desc_col = next(
        (c for c in history_df.columns if c.lower() in {"history_description", "description"}),
        None,
    )
    bill_col = next(c for c in history_df.columns if c.lower() == "bill_id")
    date_col = next(
        (c for c in history_df.columns if c.lower() in {"history_date", "historydate", "date"}),
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
        (c for c in history_df.columns if c.lower() in {"history_description", "description"}),
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
    events = phase_0_fetch_corpus(sheet, target_bills)

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
        "sample_bills_target": SAMPLE_BILLS,
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
