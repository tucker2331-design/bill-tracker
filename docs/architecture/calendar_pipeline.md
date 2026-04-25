# Calendar Worker Pipeline Architecture

## Data Flow

```
LIS Session API -> get_active_session_info() -> ACTIVE_SESSION code
                                              -> test_start_date / test_end_date

LIS Committee API -> build_committee_code_map() -> COMMITTEE_CODE_MAP (runtime)
                                                -> LOCAL_LEXICON (derived)
                                                -> PARENT_MAP (ParentCommitteeID)

Google Sheets API_Cache -> api_schedule_map (historical)
                        -> convene_times (historical)

LIS Schedule API -> build_time_graph() -> resolved_parent_map
                 -> api_schedule_map (live, merged with cache)
                 -> convene_times (live)
                 -> agenda URLs -> extract_rogue_agenda() -> bill lists

Azure Blob DOCKET.CSV -> docket_memory (date -> bill -> committees)
Azure Blob HISTORY.CSV -> Sequential Turing Machine:
                          - resolve_committee_from_refid() [Phase 1: structural]
                          - LOCAL_LEXICON matching [Phase 2: text fallback]
                          - bill_locations state machine
                          - find_api_schedule_match() [time resolution]
                          -> master_events

master_events -> noise filter -> journal collapse -> dedup -> viewport slice -> Sheet1
             -> new_cache_entries -> API_Cache
```

## Committee Resolution Priority
1. **History_refid** (structural primary key) - COMMITTEE_CODE_MAP lookup
2. **LOCAL_LEXICON** (text-based fallback) - alias matching against outcome text
3. **bill_locations** memory (state machine) - where the bill was last seen

## Time Resolution Priority
1. **Exact match** in api_schedule_map (date + normalized committee name) → `Origin=api_schedule`
2. **Parent fallback** (subcommittee inherits parent time via ParentCommitteeID) → `Origin=api_schedule`
3. **Hint matching** (derive_room_hints from outcome text like "placed on X agenda") → `Origin=api_schedule`
4. **Substring matching** (partial name overlap) → `Origin=api_schedule`
5. **Convene time** (Floor actions inherit chamber convene time) → `Origin=convene_anchor`
6. **No match** → `Time="⏱️ [NO_SCHEDULE_MATCH]"`, `Origin=journal_default` (or `"⏱️ [NO_CONVENE_ANCHOR]"` / `Origin=floor_miss` for Floor actions that couldn't resolve via convene).

Every `master_events` row carries an `Origin` column (added in PR-A). This is the provenance field that survives the Journal→Ledger rename so downstream (X-Ray Section 0) can distinguish silent defaults from concrete sources. See [[workflow/source_miss_visibility]].

## Sheet1 Schema (worker output)
11 columns: `Date | Time | SortTime | Status | Committee | Bill | Outcome | AgendaOrder | Source | Origin | DiagnosticHint`.

The `Origin` column was added in PR-A. Enumerated values: `api_schedule`, `convene_anchor`, `journal_default`, `floor_miss`, `system_alert`, `system_metrics`. One `SYSTEM_METRICS` row per run carries a JSON-encoded snapshot of the source-miss counters (`total_processed`, `sourced_api`, `sourced_convene`, `unsourced_journal`, `unsourced_anchor`, `dropped_ephemeral`, `dropped_noise`, `floor_anchor_miss`). X-Ray Section 0 parses this row to render the denominator.

The `DiagnosticHint` column was added in PR-B. Populated ONLY for rows where `Origin in {journal_default, floor_miss}`; empty string otherwise. Value format: `loc='<bill_locations[bill]>'; api_<date>=[<committee>@<time>; ...]` (nearest-3 same-chamber Schedule API candidates for that date, or `<none>`). Pure measurement — no classification impact. See [[workflow/source_miss_visibility]] and [[failures/gemini_review_patterns]] #37.

## Key Design Decisions
- Calendar subsystem is separate from v2_shadow_test to allow independent perfection
- API_Cache provides resilience when LIS API is offline
- Mismatch detection catches state machine errors without stopping processing
- Noise filtering happens AFTER state machine updates (so memory stays correct)
- Ledger-Updates collapse happens BEFORE dedup (so phantom committees merge properly) and gates off the `Origin` column, not the Time string, so provenance survives the rename (PR-A)
- Viewport slice exempts `Origin in {system_alert, system_metrics}` from the `scrape_start..scrape_end` window so meta rows (stamped with the run timestamp, not investigation dates) actually reach Sheet1 (PR-B, see [[failures/gemini_review_patterns]] #36)

## Write-Time Safety Rails (PR-C1)

All bill-row writes into `master_events` pass through a single closure,
`_append_event()`, defined inside `run_calendar_update()`. The chokepoint
enforces four invariants:

| # | Invariant | Failure mode |
|---|-----------|--------------|
| I1 | Schema completeness — all 11 columns present | fill missing with `""`, push `DATA_ANOMALY / CRITICAL` alert |
| I2 | `Origin` in `{api_schedule, convene_anchor, journal_default, floor_miss, system_alert, system_metrics}` | push `DATA_ANOMALY / CRITICAL` alert (row is not rewritten — downstream must handle visibly) |
| I3 | Concrete-source Origins (`api_schedule` / `convene_anchor`) cannot carry a `⏱️ [NO_*]` Time | push `DATA_ANOMALY / CRITICAL` alert |
| I4 | Telemetry counter `meeting_unsourced` (no invariant) — outcome contains a meeting verb AND Origin is unsourced | increment counter; fed to the circuit breaker |

Rows are NEVER dropped by the chokepoint. Visibility beats silence; the
mass-violation circuit breaker downstream watches the rate. Violations and
the meeting-verb counter both surface through the existing `SYSTEM_METRICS`
row (X-Ray Section 0 renders them alongside the prior counters).

### Mass-Violation Circuit Breaker

Just before `worksheet.clear() + worksheet.update()`, the worker evaluates:

- `violation_rate > 10%` (invariants / **`rows_appended`** — see Counter schema below; review-fix from Gemini)
- OR `invariant_violations >= 50`
- OR `meeting_unsourced >= 50` (baseline today: ~9 for crossover week)

If any threshold trips, the worker **refuses the Sheet1 overwrite** and
leaves the previous cycle's data intact as last-known-good. Three
durable visibility writes happen on trip (review-fix from Codex —
`alert_rows` is in-memory and dies with the process, so the original
design would have lost SYSTEM_ALERT visibility of the trip):

- `Sheet1!X1` — compact human-readable banner (truncated to 4500 chars)
- `Sheet1!W1` — machine-readable JSON trip record (`trip_utc`,
  `invariant_violations`, `meeting_unsourced`, `rows_appended`,
  `total_processed`, `violation_rate`, `thresholds`). Read at the TOP
  of the next cycle as a carry-forward; that cycle emits a proper
  `DATA_ANOMALY / CRITICAL` SYSTEM_ALERT row describing the prior
  trip, so Bug_Logs / SYSTEM_ALERT monitors see the trip one cycle
  delayed. W1 is cleared on the next successful overwrite so the
  carry-forward doesn't double-report.
- In-memory `alert_rows` entry — surfaces THIS cycle's stdout /
  GitHub Actions log, but is expected to die with the process on the
  breaker branch. The durable W1 + next-cycle carry-forward is the
  real monitoring path.

The state cell `Y1` is NOT advanced, so the next cycle's gap-backfill
window (PR-C2) naturally covers the skipped cycle.

Thresholds are intentionally generous — a safety net for REGRESSIONS, not
a gate on normal operation.

### State Cell `Sheet1!Y1` — `last_successful_cycle_end_utc`

Written at the end of every successful Sheet1 overwrite with the ISO UTC
timestamp of the cycle (**real UTC via `datetime.now(timezone.utc)`** —
review-fix from Codex. The `now` variable used throughout the cycle is
`datetime.now(America/New_York).replace(tzinfo=None)` i.e. naive ET;
using it for the Y1 "UTC" write would shift the cursor by 4–5 hours
across DST). Read at the top of the next cycle (logged only in C1;
PR-C2 will consume this as the "since" cursor so a failed cycle auto-
backfills in the next healthy cycle). Empty on first post-PR-C1 deploy —
that's expected and does not alert. A read or write API error emits a
categorized `API_FAILURE` alert.

### State Cell `Sheet1!W1` — durable breaker trip record (PR-C1 review-fix)

JSON-encoded record written on circuit-breaker trip so the trip survives
the process exit when the normal `worksheet.update(...)` path is skipped.
Read at the top of the next cycle and surfaced as a carry-forward
`DATA_ANOMALY / CRITICAL` SYSTEM_ALERT. Cleared (`""`) on every
successful Sheet1 overwrite.

Format:
```json
{
  "trip_utc": "2026-04-21T14:30:00Z",
  "invariant_violations": 52,
  "meeting_unsourced": 9,
  "rows_appended": 4500,
  "total_processed": 63081,
  "violation_rate": 0.0116,
  "thresholds": {"rate": 0.10, "violations_abs": 50, "meeting_unsourced_abs": 50}
}
```

Non-JSON content in W1 triggers a `WARN` SYSTEM_ALERT (possible manual
edit or partial write). Read errors emit `API_FAILURE / INFO`.

### GitHub Actions Concurrency

`.github/workflows/calendar_worker.yml` declares
`concurrency: { group: calendar-worker, cancel-in-progress: false }`. If a
cycle's runtime slips past 15 min, the next cron firing queues rather than
running in parallel. No in-flight cycle is ever cancelled — half-written
Sheet1 is worse than a delayed cycle.

### Counter schema additions (for X-Ray Section 0)

`source_miss_counts` gains three orthogonal tag counters:
- `invariant_violations` — tally of rows that failed I1/I2/I3 at `_append_event` time
- `meeting_unsourced` — rows with meeting-verb outcome AND Origin in `{journal_default, floor_miss}` (the Section 9 bug shape)
- `rows_appended` (PR-C1 review-fix, Gemini) — the true denominator for
  the circuit breaker's violation-rate threshold. Counts rows that
  actually reached `_append_event` (i.e. where an invariant COULD have
  fired). `total_processed` is NOT used for the rate because it also
  counts rows that died before append (noise drops, etc.), which would
  dilute the rate and make the threshold less sensitive.

All three overlap the existing denominator buckets by design, like
`unsourced_anchor` and `dropped_ephemeral`. See [[failures/gemini_review_patterns]] #31 for the orthogonal-vs-denominator pattern.

## Gap Detection + Witness Log + Reconciliation (PR-C2)

PR-C2 closes the loop from PR-C1 scaffolding. Three cooperating pieces, each
doing one thing:

### Part A — Y1 gap detection

At the top of every cycle, the worker now parses `Sheet1!Y1`
(`last_successful_cycle_end_utc`), computes `gap_minutes` against
`datetime.now(timezone.utc)`, and classifies the cause. `gap_cause` is one of:

| Value | Meaning | Alert |
|-------|---------|-------|
| `first_run` | Y1 empty — fresh deploy / cleared | (none) |
| `future_cursor` | Y1 > now (clock skew / manual edit) | WARN `DATA_ANOMALY` |
| `stale_cursor` | Y1 > 30 days old | CRITICAL `DATA_ANOMALY` |
| `malformed_cursor` | Y1 parse failed | WARN `DATA_ANOMALY` |
| `breaker_carryforward` | W1 populated — previous cycle tripped breaker | (carry-forward alert from W1 block) |
| `outage` | valid cursor, gap past threshold | WARN @ >20 min, CRITICAL @ >60 min (`API_FAILURE`) |
| `normal` | gap within 20 min | (none) |

Thresholds in code: `GAP_WARN_MINUTES=20`, `GAP_CRITICAL_MINUTES=60`,
`GAP_STALE_DAYS=30`, `GAP_RECONCILIATION_MAX_DAYS=7`.

`source_miss_counts` gains two new keys for SYSTEM_METRICS: `gap_minutes`
(float, or `-1` sentinel when N/A) and `gap_cause` (string). Both are
orthogonal to the denominator buckets.

`_gap_window_start_utc` is the usable bound for Part C — set ONLY when Y1
parses cleanly and is neither future nor stale.

### Part B — `Schedule_Witness` change-feed tab

Append-only log of **ADDED + CHANGED** LIS Schedule API deltas, one row per
delta. Schema (13 cols):

```
seen_at_utc | run_id | event_type | meeting_date | committee | time |
sort_time | status | location | prev_time | prev_sort_time | prev_status |
prev_location
```

Delta computation:
1. **Before** the live Schedule API loop: deep-copy `api_schedule_map` →
   `_pre_live_schedule_snapshot`.
2. Live loop runs unchanged, mutating `api_schedule_map`. Each meeting's
   `Location` is extracted via `_extract_meeting_location()` — a fallback
   chain over `Location` → `Room` → `RoomDescription` because the field
   is not explicitly documented (see [[knowledge/lis_api_reference]]).
3. **After** the live loop (but before the `best_times` post-pass, so we
   capture raw LIS signal): iterate `api_schedule_map` and diff each entry
   against the snapshot using the strict whitelist `WITNESS_DELTA_FIELDS =
   ("Time", "SortTime", "Status", "Location")`. ADDED = key not in
   snapshot. CHANGED = any whitelisted field differs.

**Whitelist rule (Gemini round-1 concern #1, round-2 concern #1):** fields
outside `WITNESS_DELTA_FIELDS` are invisible to delta logic. Volatile LIS
metadata (last_modified, ETags, opaque IDs) MUST NOT be added here or the
change-feed explodes into junk. Room moves are a real-world schedule
delta a legislative tracker cares about, so Location is in; purely
cosmetic server-side metadata is out.

**Migration burst guard:** API_Cache did not store Location before this
PR, so the first cycle post-deploy has `prev.Location = ""` for every
cached entry. Without suppression, every meeting would emit a bogus
CHANGED delta. We suppress the delta when the ONLY changed field is
Location going empty → populated, and count suppressions in
`witness_location_backfills` so the one-time burst is visible but quiet.
Real room moves (prev and cur both non-empty but different) pass through
normally.

**REMOVED** is intentionally NOT emitted — absence from a poll cannot be
reliably distinguished from cross-session cache staleness or filtering.
Data-loss detection for those cases is handled by Part C reconciliation.

- **Tab auto-created** on first delta (via `gspread.exceptions.WorksheetNotFound`
  → `sheet.add_worksheet(...)` + header write).
- **API_Cache schema migration:** on every cycle, if `row_values(1)` lacks
  `"Location"`, cell F1 is repaired so future `get_all_records()` reads
  pick up the Location column. Idempotent. Failure surfaces an INFO alert
  (`cache_header_migration_fail`) — migration-burst guard keeps delta
  stream clean even if repair stalls.
- **Retention ownership moved to L3b Nightly Audit** (Gemini round-1
  concern #2). The original design pruned inside the 15-min cycle with
  `append_rows` + `col_values(1)` + `delete_rows` on the same tab; that
  is a documented eventual-consistency race in the Sheets API and has
  been removed. Retention is now a TODO owned by
  [[ideas/future_improvements]].
- **Size canary** replaces the prune: a cheap `len(col_values(1))` read
  exposes the row count in `source_miss_counts["witness_rows"]` and
  emits a WARN (`witness_canary_over_threshold`) if rows exceed
  `WITNESS_CANARY_ROW_THRESHOLD = 500_000`. The canary's purpose is to
  make L3b-audit lag visible, not to enforce retention.
- **Write is NOT gated by the circuit breaker** — witness rows survive
  even when Sheet1 overwrite is suppressed. This is the whole point:
  reconciliation on the next healthy cycle needs the record of what LIS
  told us even during a trip.
- **Volume math:** steady-state deltas/cycle is small (cache warms
  quickly). Worst case 100 deltas × 96 cycles × 90 days × 13 cols ≈ 11M
  cells — trims close to the 10M limit, which is why the canary
  threshold is set to trigger well before that ceiling and why L3b
  ownership is required.

### Part C — Gap-triggered reconciliation (HISTORY-vs-witness)

Runs ONLY when `gap_cause in {outage, breaker_carryforward}` AND
`gap_minutes >= GAP_CRITICAL_MINUTES (60)` AND `_gap_window_start_utc` is
set.

Hard cap: `GAP_RECONCILIATION_MAX_DAYS = 7`. Gaps larger than the cap emit
a CRITICAL `DATA_ANOMALY` (`dedup_key=gap_reconciliation_oversized::<date>`)
and skip the check — manual review required.

Within the cap, the worker:
1. Builds the gap date range in ET (dates from `_gap_window_start_utc`
   through current cycle, inclusive).
2. Builds a **witness date index** = `{meeting_date}` from THIS cycle's
   deltas + all prior rows in `Schedule_Witness`. The prior-rows read
   fetches **only the `meeting_date` column** via `col_values()` (not
   `get_all_values()`) — the witness tab is a change-feed that can
   approach Sheets' 10M-cell ceiling and a full-sheet pull is a memory
   cliff at scale (Gemini round-3 HIGH). Column index comes from
   `WITNESS_HEADER.index("meeting_date") + 1` (1-indexed Sheets API).
3. Filters `df_past` (HISTORY.CSV) to rows whose `ParsedDate` is in the gap
   window AND whose description contains any `MEETING_VERB_TOKENS` entry.
4. Groups candidates by date. For each gap-window date with HISTORY
   meeting-verb rows but **no** witness evidence → emits WARN
   `DATA_ANOMALY` (`dedup_key=blind_window_loss::<date>::<gap_cause>`)
   labeled "CONFIRMED BLIND-WINDOW LOSS".

Counters added to `source_miss_counts`: `reconciliation_blind_dates`,
`reconciliation_checked_dates`.

**Why date-granularity, not committee-granularity:** HISTORY rows don't
carry committee names directly — committee is resolved by the Sequential
Turing Machine later in the cycle. Running reconciliation BEFORE the
state machine keeps the check cheap and independent of STM correctness.
A date with zero witness events is unambiguous blind-window loss
regardless of which committee met.

### Future-consideration flag

The CRITICAL alerts emitted by PR-C2 (`y1_stale`, `gap_reconciliation_oversized`,
`gap_critical`) are routed through the existing `push_system_alert` path
(appear as `SYSTEM_ALERT` rows in Sheet1 / Bug_Logs). Owner may later want
to re-route these through a dedicated dashboard or push channel. See
[[ideas/future_improvements#Notification Routing (flagged 2026-04-24, PR-C2)]].

## Recovery Scraper (PR-C2.1)

When PR-C2 Part C emits `CONFIRMED BLIND-WINDOW LOSS` for a historical
date, PR-C2.1's `lis_historical_scraper.py` is invoked to fetch the LIS
Meeting Schedule web page (a React SPA) and recover times + locations
for that date. The Schedule API only returns current-window meetings;
the web page exposes historical schedules via a date-keyed URL.

### Scope split

This is landing in two commits to keep review surface area tight:

1. **Scaffolding commit (current)** — adds the scraper module + workflow
   wiring without touching `calendar_worker.py`. The worker still emits
   `CONFIRMED BLIND-WINDOW LOSS` exactly as in PR-C2; nothing consumes it
   yet.
   - `lis_historical_scraper.py` — Playwright scraper. Public API:
     `scrape_historical_schedule(date_str, selector_timeout_ms=15_000)`
     returns `{date, url, meetings: [...], errors: [...]}` and **never**
     raises into the caller; all failures are categorized strings in
     `errors`.
   - `.github/workflows/calendar_worker.yml` — installs Playwright +
     Chromium, cached across runs (`actions/cache` keyed on
     `playwright-chromium-v1`) so per-cycle install cost is one-time.
2. **Integration commit (next)** — modifies Part C to track
   `_blind_window_loss_dates` as a list (currently only counted as
   `reconciliation_blind_dates`), iterate it after reconciliation,
   invoke the scraper, and write recovered rows to:
   - `Schedule_Witness` as `event_type="RECOVERED"` (so the audit trail
     captures what was recovered and from when), and
   - `API_Cache` so the next cycle's `api_schedule_map` picks up the
     recovered times for downstream resolution.
   - New `source_miss_counts` keys: `recovery_attempted`,
     `recovery_succeeded`, `recovery_meetings_added`, `recovery_failed`.

### Design constraints (Gemini round-2 concerns #2 and #3)

1. **`wait_for_selector()` bound to the schedule-table DOM** — never
   `wait_for_load_state("networkidle")`. Bloated government sites rarely
   reach true network idle (broken background trackers / analytics);
   networkidle hangs indefinitely. The scraper tries a list of candidate
   container selectors and surfaces `container_selector_drift` if all
   miss within the timeout.
2. **Per-date timeout ≥ 15s** — the earlier 5s budget produced
   false-positive timeouts on slow LIS historical-database queries
   during peak session. Enforced as a `ValueError` in
   `scrape_historical_schedule(...)` so the constraint is unbypassable.

### LIS DOM contract (must be verified pre-prod)

Constants at the top of `lis_historical_scraper.py` encode three
heuristics that need first-run verification against the live LIS site:
- `SCHEDULE_URL_TEMPLATE = "https://lis.virginia.gov/Schedule?date={date}"` —
  inferred from the API endpoint at the same path; date passed via
  query string for SPA date-picker mount.
- `SCHEDULE_CONTAINER_SELECTORS` — multiple candidates tried in order;
  first match wins. Drift surfaces as `container_selector_drift`.
- `ROW_SELECTORS`, `*_FIELD_SELECTORS` — same multi-candidate pattern
  per-row. `all_rows_unparseable` fires if rows are present but no
  field selector returns text.

CLAUDE.md Standard #1 (Zero Assumptions) compliance: every static
heuristic above has a runtime validation path that emits a categorized
error string for the caller to route via `push_system_alert`.

### Cost model

Triggered ONLY when (PR-C2 Part C emits `CONFIRMED BLIND-WINDOW LOSS`)
which itself requires `gap_cause in {outage, breaker_carryforward}` AND
`gap_minutes >= 60` AND HISTORY shows meeting-verb actions on a date
with no witness evidence. Hard-capped at 7 dates by
`GAP_RECONCILIATION_MAX_DAYS`, so worst-case added latency is
`7 dates × (20s navigate + 15s selector wait) ≈ 245s` on a recovery
cycle. Acceptable: the alternative is silent data loss.

### Why a separate module

`calendar_worker.py` is already large; isolating the Playwright surface
keeps the worker's hot-path imports lean (Playwright is loaded only when
the recovery path actually fires) and lets the scraper be unit-tested
against fixture HTML without spinning up the full worker.
