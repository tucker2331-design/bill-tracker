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

- `violation_rate > 10%` (invariants / total_processed)
- OR `invariant_violations >= 50`
- OR `meeting_unsourced >= 50` (baseline today: ~9 for crossover week)

If any threshold trips, the worker **refuses the Sheet1 overwrite** and
leaves the previous cycle's data intact as last-known-good. A compact
banner lands in `Sheet1!X1`; a categorized `DATA_ANOMALY / CRITICAL` alert
goes to `alert_rows` (so the next healthy cycle surfaces it). The state
cell `Y1` (see below) is NOT advanced, so the next cycle's gap-backfill
window (PR-C2) naturally covers the skipped cycle.

Thresholds are intentionally generous — a safety net for REGRESSIONS, not
a gate on normal operation.

### State Cell `Sheet1!Y1` — `last_successful_cycle_end_utc`

Written at the end of every successful Sheet1 overwrite with the ISO UTC
timestamp of the cycle. Read at the top of the next cycle (logged only in
C1; PR-C2 will consume this as the "since" cursor so a failed cycle auto-
backfills in the next healthy cycle). Empty on first post-PR-C1 deploy —
that's expected and does not alert. A read or write API error emits a
categorized `API_FAILURE` alert.

### GitHub Actions Concurrency

`.github/workflows/calendar_worker.yml` declares
`concurrency: { group: calendar-worker, cancel-in-progress: false }`. If a
cycle's runtime slips past 15 min, the next cron firing queues rather than
running in parallel. No in-flight cycle is ever cancelled — half-written
Sheet1 is worse than a delayed cycle.

### Counter schema additions (for X-Ray Section 0)

`source_miss_counts` gains two orthogonal tag counters:
- `invariant_violations` — tally of rows that failed I1/I2/I3 at `_append_event` time
- `meeting_unsourced` — rows with meeting-verb outcome AND Origin in `{journal_default, floor_miss}` (the Section 9 bug shape)

Both overlap the existing denominator buckets by design, like
`unsourced_anchor` and `dropped_ephemeral`. See [[failures/gemini_review_patterns]] #31 for the orthogonal-vs-denominator pattern.
