---
tags: [log, meta]
updated: 2026-04-24
---

# Project Log

Append-only, reverse-chronological (newest at top). Each entry opens with `## [YYYY-MM-DD] <kind> | <title>` so `grep "^## \[" log.md | head -20` gives a parseable timeline.

**Kinds:** `ingest` (new source/doc processed), `pr` (PR opened/merged/closed), `decision` (architectural or workflow), `lint` (wiki health-check pass), `session` (notable multi-hour working block), `post-mortem` (failure analysis).

---

## [2026-04-24] pr | PR#29 merged — PR-C2 (gap detection + Schedule_Witness + reconciliation)

Merged into `main` at 17:17 UTC after three rounds of Gemini review (round-1 inline at PR open, round-2 Location/prune/canary patches, round-3 `col_values()` scale-cliff fix). Merge commit `fddfea6`. Final shipped scope: Y1 gap-detection with 7 `gap_cause` classes + WARN/CRITICAL thresholds; `Schedule_Witness` change-feed tab (13 cols, ADDED+CHANGED only, whitelist-iterated `WITNESS_DELTA_FIELDS = (Time, SortTime, Status, Location)`, migration burst guard, retention deferred to L3b Nightly Audit); HISTORY-vs-witness reconciliation with 7-day cap. Zero bug-count delta as expected — observability + data-recovery infrastructure. Counters added to `source_miss_counts`: `gap_minutes`, `gap_cause`, `witness_rows`, `witness_location_backfills`, `reconciliation_blind_dates`, `reconciliation_checked_dates`. Three follow-ups still flagged in [[ideas/future_improvements]]: L3b Nightly Audit (witness retention owner), PR-C2.1 Playwright historical scraper (data-recovery), Notification Routing for `y1_stale` / `gap_reconciliation_oversized` / `gap_critical` CRITICALs. Next: PR-C3 (LegislationEvent API as secondary time source) — first fix-pass that collapses Class 1 bugs.

## [2026-04-24] pr | PR-C2 round-3 patch — col_values() for reconciliation witness-date index

Single-point fix in response to Gemini round-3 HIGH review of PR #29. Part C reconciliation was reading the `Schedule_Witness` tab via `get_all_values()` to build the prior-cycle `witness_dates` index. Given the 90-day retention target and high cycle frequency, the change-feed can approach Sheets' 10M-cell ceiling, and pulling the entire sheet into memory every cycle is a latent scale cliff that eventually breaks the worker via timeout or memory pressure. Only `meeting_date` is needed for the index. Switched to `col_values(WITNESS_HEADER.index("meeting_date") + 1)` which fetches only that column. Header cell is sliced off via `[1:]`. The existing try/except fallback-to-deltas-only semantics is unchanged, so a col-read failure still degrades gracefully.

Adversarial audit: WITNESS_HEADER is the canonical schema we write at tab creation (inside `_ensure_witness_tab`), so index lookup against the constant is stable and matches what's on the tab. No schema drift risk unless someone hand-edits the tab header — and in that case the col fetch still returns the data, just potentially from a different column; the fallback semantics would give weaker reconciliation for one cycle until detected. Acceptable. No other `witness_tab.get_all_values/get_all_records` call sites in the worker (grep-verified). AST parse clean.

Docs updated: architecture/calendar_pipeline Part C bullet 2 now documents the `col_values()` path + the memory-cliff rationale.

---

## [2026-04-24] pr | PR-C2 round-2 patches — Location delta, prune moved to L3b, size canary

Pushed three patches on the open PR-C2 branch in response to Gemini round-2 review. Owner greenlit Concerns 1 + 2 for the current branch; Concern 3 (Playwright scraper) deferred to PR-C2.1.

**Concern 1 — Location/Room missing from witness (round-1 junk-delta whitelist + round-2 "Missing Room Update"):** `WITNESS_DELTA_FIELDS = ("Time", "SortTime", "Status", "Location")` constant introduced with DO-NOT-ADD-METADATA warning. Delta comparison rewritten to iterate the whitelist — never iterate `_wval.items()` or any future metadata key becomes a delta trigger. `_extract_meeting_location(meeting)` uses a `Location → Room → RoomDescription` fallback chain (the field is not documented in [[knowledge/lis_api_reference]]) and logs which key fired. Location threaded through `api_schedule_map`, `new_cache_entries`, API_Cache header + compaction. `WITNESS_HEADER` grew from 11 → 13 cols (`location`, `prev_location` appended to both the current-state and prev-state halves). **Migration burst guard:** on first cycle(s) after deploy, API_Cache-seeded entries have Location="" while live entries are populated — without suppression every meeting would emit a bogus CHANGED delta. Suppress ONLY when the delta is {"Location"} and it went empty→populated; count in `witness_location_backfills` so the one-time burst is visible but quiet. Real room moves (both sides non-empty) still emit. One-time header migration in the cache-read path writes `F1="Location"` if missing, so subsequent cycles can actually read the column back (without this, the burst guard would fire forever).

**Concern 2 — Pruning race (round-1 "Pruning Race Condition"):** removed the in-cycle `append_rows` + `col_values(1)` + `delete_rows` block entirely. Same-cycle append-then-delete on a Google Sheets tab is a documented eventual-consistency race that can silently delete rows we just wrote. Retention is now owned by an L3b Nightly Audit (TODO, see [[ideas/future_improvements#L3b Nightly Audit — Schedule_Witness retention owner (flagged 2026-04-24, PR-C2 round-2)]]) running outside the 15-min hot path. Cycle still does a cheap `col_values(1)` read as a size canary: exposes `witness_rows` in `source_miss_counts` and fires `witness_canary_over_threshold` WARN at > 500,000 rows so L3b lag is visible.

**Concern 3 — Playwright scraper deferred to PR-C2.1.** Will use `wait_for_selector()` tied to the actual schedule-table DOM element (NOT `wait_for_load_state("networkidle")` which hangs on bloated gov sites) and ≥ 15s per-date timeout (5s was too aggressive for LIS at peak session). Flagged in [[ideas/future_improvements#PR-C2.1 — Playwright historical scraper (deferred from PR-C2)]].

**Adversarial audit (embedded at commit time):** Caught a NameError bug during audit — `WITNESS_DELTA_FIELDS` was originally defined after the live loop but referenced inside it; hoisted the constants block above the pre-live snapshot so closure order matches execution order. API_Cache schema migration is idempotent; compaction + rollback blocks both padded to 6 cols so writes stay rectangular. No new silent fallbacks: every new except path has a categorized alert with a unique dedup_key. Whitelist iteration means we cannot accidentally add a new field without explicitly opting in. AST parse clean.

---

## [2026-04-24] pr | PR-C2 opened — gap detection + witness log + reconciliation

Second PR in the PR-C series, on branch `claude/pr-c2-gap-detection-witness-log`. Three-part scope, all landing together so data-recovery infrastructure is cohesive:

**Part A — Y1 gap detection.** Parses `Sheet1!Y1` (written by PR-C1), computes `gap_minutes = now_utc − Y1`, classifies `gap_cause` as one of `first_run`, `future_cursor`, `stale_cursor` (>30 d), `malformed_cursor`, `breaker_carryforward` (W1 populated), `outage`, `normal`. Emits WARN at >20 min gap, CRITICAL at >60 min, CRITICAL on stale_cursor. `gap_cause` and `gap_minutes` land in `source_miss_counts` for SYSTEM_METRICS. `_gap_window_start_utc` becomes the usable bound for Part C — set ONLY when Y1 parses cleanly and is neither future nor stale. All comparisons use `datetime.now(timezone.utc)` (PR-C1 Codex P1 fix already made the UTC import available).

**Part B — `Schedule_Witness` change-feed tab.** Append-only log of ADDED + CHANGED LIS Schedule API deltas, one row per delta (11 cols: `seen_at_utc | run_id | event_type | meeting_date | committee | time | sort_time | status | prev_time | prev_sort_time | prev_status`). Pre-live deep-copy snapshot of `api_schedule_map` is diffed against post-live state BEFORE the `best_times` post-pass so the witness captures raw LIS signal. REMOVED deferred — can't reliably distinguish "LIS dropped it" from "LIS did not return it this poll" given cross-session cache staleness. Data-loss detection for that case is Part C's job. Tab auto-created on first delta. 90-day rolling prune via lexical sort of ISO timestamps + single `delete_rows(2, N)`. Write NOT gated by the circuit breaker — witness rows have to survive breaker trips, since the entire point is reconciliation on the next healthy cycle. Volume math: steady-state well under 10M-cell Sheets limit (change-feed, not snapshot); cold-start ~3.3k ADDED burst then normalizes.

**Part C — HISTORY-vs-witness reconciliation.** Runs ONLY when `gap_cause in {outage, breaker_carryforward}` AND `gap_minutes >= 60`. Hard cap `GAP_RECONCILIATION_MAX_DAYS = 7`: over cap, CRITICAL `DATA_ANOMALY` alert + skip (manual review required). Within cap, builds gap date range in ET, builds witness date index (this cycle's deltas + all prior Schedule_Witness rows), filters `df_past` (HISTORY.CSV) to meeting-verb rows in gap window, and for each date with HISTORY meeting-verb rows but zero witness evidence emits a WARN `DATA_ANOMALY` labeled "CONFIRMED BLIND-WINDOW LOSS". Date-granularity (not committee-granularity) because HISTORY doesn't carry committee directly — resolving committee would force reconciliation to run AFTER the Sequential Turing Machine, which defeats the "cheap and independent" goal. `reconciliation_blind_dates` / `reconciliation_checked_dates` added to `source_miss_counts`.

**Future-consideration flag.** Owner flagged during scoping that the CRITICAL alerts here (`y1_stale`, `gap_reconciliation_oversized`, `gap_critical`) may eventually want a dedicated dashboard or push channel rather than routing through `SYSTEM_ALERT` rows. Tagged in code comments on both alert sites, in [[architecture/calendar_pipeline#Future-consideration flag]], and in a new section in [[ideas/future_improvements#Notification Routing (flagged 2026-04-24, PR-C2)]].

Adversarial audit (because Codex/Gemini don't re-review mid-stream): 9-point pre-push checklist clean; boundary conditions verified — Y1 parse handles None + ValueError + future + stale + malformed; delta computation survives api_is_online=False (empty deltas, no write); prune handles all-old / all-new / empty-tab / single-row / multi-row cases; breaker interaction confirmed (trip leaves Y1 untouched → next cycle detects as `breaker_carryforward`); source_miss_counts mixed int/string values serialize cleanly via `json.dumps`; no new silent fallbacks (every except has a categorized alert).

Zero bug-count delta expected. This is observability + data-recovery infrastructure; PR-C3 (LegislationEvent API) is the first fix-pass that collapses Class 1 bugs.

---

## [2026-04-21] pr | PR-C1 review fixes — Codex P1/P2 + Gemini denominator

Three review findings on PR #28 addressed in one follow-up commit on `claude/pr-c1-append-event-chokepoint`. All three are real issues; all three surface anti-patterns worth extracting so future PRs don't repeat them. New entries #38, #39, #40 in [[failures/gemini_review_patterns]].

**Codex P1 — Y1 stored as ET mislabeled UTC:** `now = datetime.now(America/New_York).replace(tzinfo=None)` at L722. My Y1 write used `now.strftime("%Y-%m-%dT%H:%M:%SZ")` — the `Z` suffix is a lie, it's actually local ET wall-clock time. A PR-C2 consumer treating Y1 as UTC would shift the gap-backfill window by 4–5 hours across DST, either missing or double-processing intervals. Fix: added `timezone` to the datetime import, compute `_cycle_end_utc = datetime.now(timezone.utc)` at breaker evaluation time, use `_cycle_end_utc.strftime(...)` for Y1 and the breaker message. All other uses of `now` (alert rows' human-readable timestamp, date keys) stay ET because those are ET-facing fields. Anti-pattern #38.

**Codex P2 — breaker alert not durable:** `push_system_alert` appends to `alert_rows`, which is a function-local list persisted to Sheet1 ONLY as part of the main `worksheet.update(...)` call. The breaker path deliberately skips that update — so the alert died with the process. My architecture doc's claim "goes to `alert_rows` (so the next healthy cycle surfaces it)" was flat wrong — `alert_rows` resets each cycle. Fix: added a durable JSON trip record at `Sheet1!W1` (compact banner stays at X1), plus a carry-forward READ at the top of the next cycle that converts the W1 record into a proper `DATA_ANOMALY / CRITICAL` SYSTEM_ALERT row. W1 is cleared on successful overwrite so the carry-forward doesn't double-report. SYSTEM_ALERT monitors now see breaker trips one cycle delayed instead of never. Anti-pattern #39.

**Gemini high — denominator semantics:** `_violation_rate = invariant_violations / total_processed` used a denominator that counted pipeline entries including rows dropped before `_append_event` (noise filter, state-machine drops). Numerator can only fire INSIDE `_append_event`. Rate was silently diluted. Gemini's suggestion was to move `total_processed` increment into `_append_event` — I took a variation that preserves existing denominator-bucket math: added a new orthogonal counter `rows_appended` inside `_append_event`, used as the breaker's rate denominator. `total_processed` stays as the mutually-exclusive-bucket sum it's always been (Section 0 denominator). Anti-pattern #40.

**Also updated:** [[architecture/calendar_pipeline]] breaker section corrected re: in-memory alert durability; added W1 subsection; flagged real-UTC requirement on Y1.

**Phase-2 re-audit after fixes:** AST parse pass, `_append_event` still defined exactly once, diff visibility grep still empty. Ready to push.

## [2026-04-21] pr | PR-C1 opened — write-time chokepoint + circuit breaker + state cell + concurrency

First PR in the PR-C series. Pure scaffolding — lands the infrastructure that PR-C2+ (the actual bug fixes) depend on. Zero bug-count delta expected from C1 alone; this is a prerequisite for auditable fix-passes. Branch: `claude/pr-c1-append-event-chokepoint`.

**Five pieces shipped (diff: +265 / -9 across 2 files + 3 doc files):**

1. **Write-time chokepoint `_append_event()`** — nested closure inside `run_calendar_update()`, defined once, used at all 5 bill-row append sites (API chamber event, DOCKET row, API_Skeleton DLQ row, API_Skeleton agenda row, main CSV loop row). Enforces four invariants:
   - **I1** — schema completeness (all 11 columns). Missing keys fill with `""`, push `DATA_ANOMALY / CRITICAL` alert.
   - **I2** — `Origin` in the enumerated set `{api_schedule, convene_anchor, journal_default, floor_miss, system_alert, system_metrics}`. Out-of-enum pushes alert; row is NOT dropped (visibility beats silence).
   - **I3** — concrete-source Origins (`api_schedule` / `convene_anchor`) cannot carry a `⏱️ [NO_*]` Time string. Parity violation pushes alert.
   - **I4** — telemetry counter (no invariant): meeting-verb outcome AND Origin in `{journal_default, floor_miss}` increments `meeting_unsourced`. Feeds the circuit breaker.

2. **Mass-violation circuit breaker** — just before `worksheet.clear() + worksheet.update()`, evaluates three thresholds:
   - `violation_rate > 10%` (invariant_violations / total_processed)
   - OR `invariant_violations >= 50` absolute
   - OR `meeting_unsourced >= 50` (baseline today for crossover week: ~9)

   On trip, the worker REFUSES the Sheet1 overwrite — leaves the previous cycle's data intact as last-known-good. Banner written to `Sheet1!X1`, `DATA_ANOMALY / CRITICAL` alert pushed. Y1 is NOT advanced, so PR-C2's gap-backfill naturally covers the skipped cycle. Thresholds are intentionally generous — a safety net for regressions, not a gate on normal operation.

3. **State cell `Sheet1!Y1`** — `last_successful_cycle_end_utc`. Written with the ISO UTC timestamp after every successful overwrite. Read at cycle top (logged only in C1; C2 will consume it as the "since" cursor). Empty on first post-C1 deploy is expected and does not alert. Read/write errors emit categorized `API_FAILURE` alerts.

4. **GitHub Actions `concurrency`** on `calendar_worker.yml`: `{ group: calendar-worker, cancel-in-progress: false }`. If cycle N's runtime slips past 15 min, cycle N+1 queues rather than running in parallel. Never cancels mid-flight — half-written Sheet1 is worse than a delayed cycle.

5. **Counter schema additions** in `source_miss_counts`: `invariant_violations` (rows that failed I1/I2/I3 at append time) and `meeting_unsourced` (meeting-verb outcome + unsourced Origin). Both overlap the existing denominator buckets by design — orthogonal-tag pattern, same as `unsourced_anchor` and `dropped_ephemeral` (see [[failures/gemini_review_patterns]] #31).

**Module-level constant added:** `MEETING_VERB_TOKENS` (high-recall list mirroring `tools/crossover_audit/diff_sheet1.py` MEETING_VERBS — the two lists should stay in sync). False positives only elevate the telemetry counter, never drop or reclassify rows.

**Self-audit against 9-point pre-push checklist:** pass.
- (1) Verb forms — MEETING_VERB_TOKENS covers base/past/present as the crossover-audit pair does; no new conjugation lists.
- (2) Function scope — `_append_event` defined once, nested in `run_calendar_update`, before all call sites.
- (3) Doc version sync — architecture doc updated in same PR.
- (4) Duplicate file check — no `pages/ray2.py` / `calendar_xray.py` drift (PR doesn't touch X-Ray).
- (5) Architecture conformance — [[architecture/calendar_pipeline]] now has "Write-Time Safety Rails (PR-C1)" section.
- (6) Zero-trust data — all four invariants emit categorized alerts; no silent paths introduced.
- (7) Cross-list validation — MEETING_VERB_TOKENS overlaps with ABSOLUTE_FLOOR_VERBS, DYNAMIC_VERBS, KNOWN_EVENT_PATTERNS by design (orthogonal tagging, not classification).
- (8) Import resolution — no new top-level imports touched.
- (9) Source-miss visibility — grep on diff is empty; no new `continue` / `except: pass` / `"Time TBA"` sites.

**Writing back to:** [[architecture/calendar_pipeline]] (Write-Time Safety Rails section), [[state/current_status]] (PR-C1 added to Open PRs, Active focus updated), this entry.

**After Gemini review:** merge → PR-C2 (gap-backfill consuming Y1) → PR-C3 (LegislationEvent secondary time source, collapses Class 1) → PR-C4 (subcommittee attribution, collapses Class 2).

## [2026-04-20] pr | PR #27 review fixes — encoding, portability, phantom_row coverage

Six review comments from Gemini + Codex on the crossover-audit tooling addressed in one commit on branch `claude/crossover-audit`.

**Medium (Gemini):**
- `build_universe.py`, `diff_sheet1.py`: open HISTORY.CSV as `iso-8859-1` (per [[knowledge/lis_api_reference]]). Defensive — current snapshot happens to be pure ASCII, but that won't hold forever.
- `extract_truth.py`: `html.unescape()` added to `strip_tags` so LIS-emitted `&amp;` / `&nbsp;` / numeric refs don't desync downstream string compares against API-sourced text.
- `fetch_bills.sh`: `CHROME` path via env-var override with executable-bit check, so the script runs on Linux/CI without editing.

**Codex:**
- `fetch_bills.sh` (P2): capture Chrome exit status; report `FAIL` distinctly from `UNDERSIZED`. Previous version masked non-zero rc by redirecting stderr.
- `diff_sheet1.py` (P1): iterate `universe | sheet_bills` (union, not intersection) so phantom-row checks also cover the 19 bills in Sheet1 with no Feb 9-13 HISTORY activity. Re-ran: `phantom_row: 0` still holds — all 19 are correctly-classified `Outcome: Scheduled` placeholders (non-action).

**Extra fix caught during verification:**
- `diff_sheet1.py`: `sorted(all_dates)` before iteration so `crossover_audit_findings.json` is deterministic across runs. Python set iteration is hash-randomized; findings.json was churning on every re-run and cluttering diffs.

**Findings summary unchanged:** `meeting_in_ledger: 9`, `phantom_row: 0`, `subcommittee_miss: 0`. See [[testing/crossover_audit]].

**PR-C direction (decided this session, not yet coded):** LegislationEvent API (`GET /LegislationEvent/api/GetLegislationEventByLegislationIDAsync?legislationID=<int>`) is the bank-grade source. Per-bill event dump carries ISO `EventDate`, `CommitteeName`, `ParentCommitteeName`, `EventCode`, `VoteTally`. Requires a pre-built bill→integer-ID map (AdvLegSearch + sequential sweep covers all 3,634 session 20261 bills; the published `GetLegislationIdsListAsync` returns only 2,831). Coverage on the 9 known bugs: 6 fully rescued; 3 are LIS-side data holes (HB24 has no meeting-verb event; SB494 Feb 12 and SB555 Feb 12 × 2 carry `00:00` midnight-stub timestamps). New quirk logged to [[knowledge/lis_api_reference]] as follow-up.

**Fallback chain order** (to be implemented in PR-C):
1. `LegislationEvent` API, join-by-(bill, date) so fields merge across multiple events on the same day
2. `Schedule` API by (committee, date) for bills where LegislationEvent is committee-only or blank
3. `HISTORY.CSV` refid parsing (H18001 → parent H18) as last-resort committee attribution
4. `SOURCE_GAP` alert — never silent-fallback to `Time TBA` or `12:00`

## [2026-04-19] session | Crossover Week full-universe audit completed — X-Ray Section 9 bug count confirmed at 9

Ran tier-A ground-truth audit: 1,544 bills × 6,885 LIS actions vs 4,473 Sheet1 rows, Feb 9-13 2026 window. Pipeline: `tools/crossover_audit/{build_universe.py, fetch_bills.sh, extract_truth.py, diff_sheet1.py}`. Raw DOM via headless Chrome (see [[knowledge/lis_dom_scraping]]).

**Headline:** the X-Ray Section 9 bug count of **9 is the actual, full-window crossover-week bug count.** Confirmed zero hidden meeting-misrouted rows, zero phantom rows, zero silent bill-drops. The 51 bills in HISTORY-but-not-in-Sheet1 are all Fiscal-Impact-Statement-only entries correctly filtered as noise. See [[testing/crossover_audit]] for full findings table, 9-bug exemplars with LIS committee attributions, and class distribution.

**Class distribution:**
- **Class 1 (Schedule API gap at full committee):** 4 bugs — HB111/HB505/HB972 (Feb 12 H-P&E meeting), HB609 (Feb 12 H-Finance). Two upstream API gaps = 4 of 9 bugs. Fixing the secondary time source collapses Class 1 entirely.
- **Class 2 (Subcommittee attribution miss):** 5 bugs — HB24, HB1266, HB1372, SB494, SB555. State-machine / attribution bugs in worker's subcommittee resolution path.

**Instrumentation observation (not a bug, but worth noting):** 423 admin-verb rows are tagged `⏱️ [NO_SCHEDULE_MATCH]` because the worker runs the schedule lookup on every row regardless of verb class. Consider narrowing the tag to rows whose verb class implied a meeting was expected. Logged to [[state/open_anti_patterns]] as item #8.

**Artifacts checked in:**
- `docs/testing/crossover_lis_truth.json` — 1.3 MB, 6,885 actions structured per-bill
- `docs/testing/crossover_audit_findings.json` — 180 KB, categorized discrepancies
- `tools/crossover_audit/` — reproducible pipeline

**Lesson learned (scraping):** LIS bill-details DOM uses nested `<span>` tags in descriptions. A naive regex over the history-event-row block over-captures across row boundaries. The fix (row-split BEFORE parsing) is now documented in [[knowledge/lis_dom_scraping]] so the next scraping task doesn't repeat the mistake. Caught during audit dry-run by noticing empty LIS truth on bills that clearly had HISTORY activity — investigating revealed the regex bug rather than accepting "LIS is missing rows."

Next: PR-C scoping. Two-track fix — secondary time source for Class 1 (4 bugs) + subcommittee resolution fix for Class 2 (5 bugs). No code written until audit is reviewed.

## [2026-04-16] pr | PR-B opened — metrics visibility + source-miss diagnostic hint

Branch: `claude/pr-b-metrics-visibility-diagnostic` from `origin/main` post-PR#25-merge. Two focused fixes cashing in on real-world behavior of PR-A:

1. **Viewport slice was filtering out the `SYSTEM_METRICS` row.** PR-A stamped the metrics row with `Date=today` (run timestamp) so it'd write on every cycle. The end-of-pipeline viewport slice then filtered `final_df` to `scrape_start <= Date <= scrape_end` (= Feb 9-13, 2026), silently dropping the `Date=2026-04-16` metrics row before Sheet1. X-Ray Section 0 rendered blank even though upstream counters were correct. Fix: exempt `Origin in {system_alert, system_metrics}` from the window mask (`final_df = final_df[in_window | is_system]`). Logged as [[failures/gemini_review_patterns]] #36.
2. **NO_SCHEDULE_MATCH rows now carry a `DiagnosticHint` column.** New pre-loop dict `api_schedule_by_date` indexes `api_schedule_map` by date. `_build_diagnostic_hint()` produces `loc='<bill_locations[bill]>'; api_<date>=[<committee>@<time>; ...]` (nearest-3 same-chamber candidates). Populated in both `journal_default` and `floor_miss` branches; empty string for sourced rows. Added to all 9 `master_events.append` sites (4 API-sourced = `""`, 1 CSV branch = populated, plus push_system_alert / SYSTEM_METRICS / cache_alert meta sites). X-Ray Sections 4d, 9 sample rows, and the Ledger Health Check "meeting actions in Ledger" expander now surface the column when present. Sheet1 schema: 10 → 11 columns. Logged as [[failures/gemini_review_patterns]] #37.

Also re-synced `calendar_xray.py` with `pages/ray2.py` and updated [[architecture/calendar_pipeline]] schema section.

## [2026-04-16] pr | PR#25 merged — worker source-miss visibility instrumentation (PR-A)

Merged into `main` after Gemini review follow-up commits. Worker ran successfully with the new counters (mutual-exclusive denominator = 63,081). The `SYSTEM_METRICS` row never reached Sheet1 because of the viewport-slice bug documented in PR-B's entry above.

## [2026-04-16] pr | PR#25 updated — Gemini review follow-up for PR-A

Five issues from Gemini review of PR#25, logged as [[failures/gemini_review_patterns]] #31-#35:

1. **#31 Counter double-counting.** `source_miss_counts` split into mutually-exclusive denominator buckets (`sourced_api`, `sourced_convene`, `unsourced_journal`, `floor_anchor_miss`, `dropped_noise` — sum to `total_processed`) and orthogonal tag counters (`unsourced_anchor`, `dropped_ephemeral` — overlap intentional). `unsourced_anchor` now fires on every Memory-Anchor row regardless of time resolution.
2. **#32 Origin/metric parity.** Floor transitions from `api_schedule` to `convene_anchor` now decrement `sourced_api` and increment `sourced_convene`, so row Origin matches the counter.
3. **#33 Dedup-key scope.** `no_match` alert key now includes `bill_num` per [[workflow/source_miss_visibility]].
4. **#34 Redundant import.** Removed local `import json as _json`; use module-level `json`.
5. **#35 Origin field parity.** Added `Origin="api_schedule"` to 4 `master_events.append` sites in the Schedule API branch.

X-Ray Section 0 rewritten to visually separate denominator buckets (with sum-check warning on drift) from orthogonal tag counters.

## [2026-04-16] pr | PR-A opened — worker source-miss visibility instrumentation

Branch: `claude/worker-source-miss-visibility`. Instrumentation-only PR that cashes in all five items from [[state/open_anti_patterns]]:

1. `calendar_worker.py` L756 — `except: print` cache fallback now also calls `push_system_alert(..., category="API_FAILURE", severity="WARN")`.
2. L~1201 Memory Anchor path now tags both admin and dynamic verbs (`📝 [Memory Anchor: admin]` vs `⚙️ [Memory Anchor]`).
3. L~1181 silent `"Journal Entry"` default replaced with `"⏱️ [NO_SCHEDULE_MATCH]"` tag + deduped `push_system_alert` (category `TIMING_LAG`, severity `WARN`).
4. L~1340 ephemeral-filter silent `continue` replaced with counter + deduped alert (category `DATA_ANOMALY`, severity `INFO`).
5. Ledger-Updates rename (L~1363) now gates off a new `Origin` column (`journal_default` / `floor_miss` / `api_schedule` / `convene_anchor` / `system_alert`) instead of the renamed Time string, so provenance survives.

Also: `push_system_alert` extended to accept `category`, `severity`, and `dedup_key`; a JSON-encoded `SYSTEM_METRICS` row is written to Sheet1 per run. X-Ray `pages/ray2.py` gains Section 0 rendering the denominator (total / sourced / unsourced / dropped). `calendar_xray.py` re-synced.

Expected effect: bug count goes *up* short-term because previously-silent rows now surface with visible tags. That is the point — per [[failures/pr22_post_mortem]], the old metric was rewarding silencing.

## [2026-04-16] pr | PR#24 opened — Gemini review follow-up for the brain PR

Four doc fixes flagged by Gemini on PR#23: (1) removed placeholder `[LLM-Wiki](https://github.com/)` link in `docs/README.md`; (2) aligned severity labels in `docs/state/open_anti_patterns.md` to CLAUDE.md Standard #4 (`INFO`/`WARN`/`CRITICAL`); (3) `<mod>` → `<module>` in CLAUDE.md pre-push audit point 8 for consistency with [[workflow/three_phase_protocol]]; (4) corrected the log entry below to cite the actual migrated files (`feedback_always_push.md`, `project_tba_discovery.md`) instead of just the `MEMORY.md` index. Also untangled stale "PR#23" references in [[state/current_status]] and [[state/open_anti_patterns]] that referred to the instrumentation PR before PR#23 was assigned to the brain PR.

## [2026-04-16] pr | PR#23 merged — Obsidian brain consolidation

Vault is live on `main`. Primary checkout now carries `docs/` as the project brain. Follow-up fixes in PR#24 address Gemini review.

## [2026-04-16] decision | Consolidated brain into Obsidian-compatible wiki

Restructured `docs/` as an Obsidian vault. Created `index.md`, `log.md`, `state/`, and `workflow/` subtrees. Migrated the two entries from global `~/.claude/.../memory/` (`feedback_always_push.md` and `project_tba_discovery.md`, both indexed by `MEMORY.md`) into `[[workflow/push_and_pr]]` and `[[knowledge/tba_times]]`. Updated [[README]] as the vault entry point. CLAUDE.md now routes all persistent memory writes here, not to global memory.

Trigger: user reported scattered knowledge between `docs/` and hidden `~/.claude/` memory folder; adopting the LLM-Wiki pattern with Obsidian as visual interface.

## [2026-04-16] post-mortem | PR#22 framework failure — "only measuring the bugs we wanted"

See [[failures/pr22_post_mortem]] and [[state/open_anti_patterns]]. User invalidated PR#22's reclassification premise (members really do offer amendments in committee). Audit of `calendar_worker.py` found the anti-pattern PR#22 inherited is still live in four places: line ~1181 (silent "Journal Entry" default), lines ~1248-1261 (ephemeral `continue`), lines ~1158-1167 (selective Memory Anchor tag), lines ~1269-1275 (Journal → Ledger rename without provenance). Section 9 bug metric was measuring symptoms, not source-miss rate.

New workflow rule created: [[workflow/source_miss_visibility]]. PR#22 to be closed unmerged by user.

## [2026-04-15] pr | PR#22 opened — `[chamber] (sub)committee offered` as admin override

Reclassified 8 crossover-week "offered" rows as administrative via `ADMIN_OVERRIDE_PATTERNS`. Premise later invalidated by user pushback. Logged as [[failures/assumptions_audit]] entry #41. To be closed.

## [2026-04-14] pr | PR#21 merged — `_REPO_ROOT` file-probe replaces dir-name check

Gemini PR#20 review flagged brittle `_HERE.name == "pages"` check. Replaced with `(_HERE / "investigation_config.py").exists()` probe. Logged as [[failures/gemini_review_patterns]] pattern #30.

## [2026-04-13] pr | PR#20 merged — sys.path prelude fix for `pages/ray2.py`

Streamlit subpage threw `ModuleNotFoundError: investigation_config` on deploy after PR#19. Added sys.path prelude. Logged as [[failures/assumptions_audit]] #39.

## [2026-04-12] pr | PR#19 merged — window alignment via `investigation_config.py`

Rolling `scrape_end = now + timedelta(days=7)` was expanding the bug count mechanically every run. PR#14-18 metrics were polluted. Pinned to `INVESTIGATION_START/END = Feb 9-13` in a single module, imported by worker + X-Ray. Logged as [[failures/assumptions_audit]] #38.

## [2026-04-11] pr | PR#18 merged — "prefiled and ordered printed" → admin override

2,042 prefiled rows were misclassifying as meetings due to substring "offered". Added to `ADMIN_OVERRIDE_PATTERNS`. Logged as [[failures/assumptions_audit]] #37. (Note: #37's call about bare "committee offered" being a meeting was later invalidated by #41.)

## [2026-04-10] pr | PR#17 merged — subcommittee vote refid regex fix

`resolve_committee_from_refid()` regex missed H14003V... format (parent + 3-digit subcommittee + V + vote ID). 1,637 subcommittee refids were unlocked. Logged as [[failures/assumptions_audit]] #36.

## [2026-04-09] pr | PR#16 merged — sub-panel schedule matching + overwrite protection

Added Strategy B in `find_api_schedule_match` for hyphen-suffixed sub-panels (HCJ-Civil, etc.) that aren't in Committee API. Added map overwrite protection so "Time TBA" can't clobber concrete times. Logged as [[failures/assumptions_audit]] #34, #35.

## [2026-04-08] pr | PR#15 merged — whitespace normalization + session marker fallback

Session marker fallback now overwrites non-concrete placeholder times. `_is_non_concrete_time` hoisted to module level. Logged as [[failures/assumptions_audit]] #32, #33.

## Earlier entries

Pre-2026-04-08 PR history is captured in the [[testing/crossover_week_baseline]] progress tracker table and in numbered entries in [[failures/assumptions_audit]]. This log was backfilled starting 2026-04-16 and is append-only from that date forward.
