# Future Improvements

## ⚠️ Workbook capacity — API_Cache row retention + stale-tab cleanup (LIVE finding, sustainability_audit 2026-06-14, OWNER DECISION NEEDED)

**The finding (surfaced by `sustainability_audit` CAPACITY on its first live run):** the Mastermind DB workbook is at **79.7% of Google Sheets' 10M-cell cap** (7,969,640 / 10,000,000; ~2M headroom, 17 tabs). At the cap, the worker's Sheet1 write fails (`gspread.APIError [400] … above the limit of 10000000 cells` — the exact crash in `tools/cell_count_audit/audit.py`). The cell-ceiling guard (`LEGEVENT_WORKBOOK_CELL_CEILING=9.5M`) protects the LegEvent-cache writes but NOT Sheet1/API_Cache appends. Two contributors need a decision:

1. **`API_Cache` — 353,811 append-only rows, no row-retention (the structural risk).** The worker appends new `(Date,Committee,…)` schedule-cache entries every cycle (the `cache_sheet.append_rows` call in `calendar_worker.py`) and never prunes rows; it grows every session. The existing `trim_api_cache_cols.py` trims *padding columns* (26→6), not rows. **Options:** (a) session-scoped prune on rollover — drop prior-session rows (mirrors the LegEvent cache S1 fix / [[architecture/stress_test_failure_modes]] S1); (b) age-based retention; (c) dedup on `(Date,Committee,Location)`. **(a) is the cleanest and matches an existing pattern.** *Destructive (deletes cache rows — re-fetchable from LIS), needs careful design so time-recovery lookups aren't broken; needs owner go-ahead.*
2. **`C7_1a_RawCorpus` — 65,447 rows of DEAD data.** A one-shot corpus from the PR-C7.1a audit (`tools/c7_1a_audit/audit.py`), referenced by nothing in production. Deleting the tab (+ siblings `C7_1a_TokenStats`/`C7_1a_DLQ_Samples`/`C7_1a_Summary`) reclaims the cells immediately. *Whole-tab delete = irreversible; regenerable by re-running the audit; needs owner go-ahead.*

**Tracking:** `sustainability_audit` keeps both as `unrecognised-tab` WARNs until a policy is declared (register in `RETENTION_DAYS` or `BOUNDED_TABS`). Cross-ref [[architecture/stress_test_failure_modes]] Y5 + standing-open #1.

## Forward-calendar block — upcoming meetings before they happen (flagged 2026-06-02 post-PR-#57/#58, real-work-prep priority)

**Strategic context:** Section 9's structural fix is *in flight* — PR #57 + #58 merged 2026-06-02, but live verification showed they're no-ops until the cache-capacity bug lands (PR #61 / PR-C7.1e) and the cache re-hydrates; see [[failures/assumptions_audit#62]]. (An earlier draft of this block said "structurally closed" — the same premature-victory mistake #62 documents. Corrected.) Once that's done, the next dynamic frontier for the 2027 session is showing lobbyists *upcoming* meetings — not just past actions. The product today is HISTORY.CSV-backed and shows "what happened in committee at time T." The real lobbyist surface is "what's on the schedule for the next 7-14 days?"

**Why this is the right next move for real-work readiness:** the structural router + LegEvent recovery handle past-action accuracy. The forward calendar is functionally NEW capability — a different signal source (Schedule API future-window) writing different row shapes (SCHEDULED-not-yet-happened). VA GA is currently adjourned, so we can ship the code with synthetic test fixtures and have it ready before 2027-01.

**Architecture (extends existing patterns, not a rewrite):**
1. **Data source — Schedule API future window.** `getschedulelistasync` returns the FULL session's schedule including future-dated meetings. The worker already calls this endpoint (line 2460); today it filters to `test_start_date ≤ meeting_date ≤ test_end_date` and the viewport slice further filters to `[scrape_start, scrape_end]`. Extend the viewport on the upper end. **⚠️ Both the fetch filter AND the final viewport slice must use the new `effective_scrape_end` upper bound (Gemini PR-#60 finding):** the worker fetches against one bound but the viewport slice (`final_df = final_df[... Date <= scrape_end]`) re-filters before Sheet1 write. If the slice still uses the old `scrape_end`, every future-dated row we just fetched gets silently dropped before write. Thread `effective_scrape_end` through to the slice, not just the fetch.
2. **Effective viewport upper bound.** New constant `FORWARD_WINDOW = timedelta(days=14)` (configurable). `effective_scrape_end = min(test_end_date, max(scrape_end, today + FORWARD_WINDOW))`. Keeps the upper bound within-session (no spurious 2028 entries) and capped at +14 days (no mile-long calendar when a session has months of scheduled meetings). **Two type/semantics traps (Gemini PR-#60 findings):**
   - **`today` must be a tz-naive `datetime`, not `date.today()` (TypeError risk).** `test_end_date` / `scrape_end` are tz-naive `datetime` objects in the worker; `min()`/`max()` between a `date` and a `datetime` raises `TypeError`. Build `today` from the existing ET `now` helper (`datetime.now(pytz.timezone('America/New_York')).replace(tzinfo=None)`, normalized to midnight) so all operands are the same type. `FORWARD_WINDOW` is a `timedelta` so `today + FORWARD_WINDOW` is a `datetime`.
   - **Only extend forward in a LIVE/in-session run, not a pinned investigation (reproducibility).** When `scrape_end` is pinned to a historical date via `investigation_config.py`, real-world `today` is far later, so `max(scrape_end, today + FORWARD_WINDOW)` collapses to `today + FORWARD_WINDOW` → capped at `test_end_date` → the worker scrapes the WHOLE session, silently ignoring the pinned `INVESTIGATION_END`. Guard: only apply the forward extension when the run is live (e.g. `scrape_end >= today - small_epsilon`, or an explicit `IS_LIVE_RUN` flag), so pinned investigations stay reproducible at their configured window.
3. **Row shape — distinctive Origin.** Schedule API future-dated entries get `Origin = "scheduled_future"` (new enum value). HISTORY-backed (past) entries keep their existing Origins. The chokepoint's I2 validator (`_VALID_ORIGINS`) gets the new value added.
4. **Reconciliation — natural transition as future becomes past.** Each cycle re-fetches the Schedule API. As "today" advances, a previously-future meeting either:
   - Has HISTORY rows now → the HISTORY-backed row supersedes the future entry (existing logic; structural router classifies the action).
   - Has no HISTORY rows → the meeting is "in progress today" or "happened but no bills moved" → stays as `scheduled_future` until it's clearly in the past, then either gets a HAPPENED marker (if HISTORY shows up later) or stays in the calendar as "no bills moved."
5. **X-Ray section — `Section X: Upcoming meetings (next 14 days)`.** Filters Sheet1 rows where `Origin == "scheduled_future" AND meeting_date > today`. Renders as a calendar widget grouped by date.
6. **Cancellation handling.** Schedule API already exposes `IsCancelled` (line 2472). Cancelled future meetings render with strikethrough + `Status="CANCELLED"`. No code change needed beyond the section's display.

**Dynamic-safety considerations:**
- Schedule API may return MORE fields in 2027 than today (LIS adds metadata). The worker already does defensive `.get()` reads; verify no `dict[key]` accesses on the Schedule API response path.
- A meeting that's scheduled today + has bills move TODAY → both `scheduled_future` row and HISTORY-backed rows would exist on the same meeting until `meeting_date < today`. Dedup: if a HISTORY row exists for the meeting, suppress the `scheduled_future` placeholder (HISTORY is the source of truth). **⚠️ Dedup key must NOT be just `(date, committee)` (Gemini PR-#60 finding) — too coarse.** A committee can meet twice in one day (morning + afternoon), and subcommittees normalize to the same parent name, so a single HISTORY row would wrongly suppress an unrelated `scheduled_future` placeholder for the *other* meeting that day. Use a finer key — `(date, committee, time)` (distinguishes morning/afternoon sittings) or `(date, committee, bill)` (suppress the placeholder only for meetings whose bills actually moved). Prefer `(date, committee, time)` since the Schedule API carries the meeting time and that's the natural identity of a sitting; fall back to bill-level suppression only if time granularity proves insufficient.
- Sheet1 capacity (currently 29.2% of 10M-cell cap) easily absorbs +14 days × 50 meetings/day = ~700 cells/cycle. No headroom concern.
- The structural router (`_route_for_row`) currently returns `""` for rows without cached LegEvent (true for scheduled_future rows by definition — no LegEvent until the meeting happens). The X-Ray's full-column drift scan (PR #57 fold-in) treats `""` as `"blank"` → no false drift alerts on the new rows.

**Testing approach (since VA GA is adjourned and no real future data exists today):**
- Synthetic Schedule API fixture: inject mock future-dated entries via `pages/v2_shadow_test.py` "Manual upload" mode (the existing manual-upload pattern is the test seam).
- A pytest-style unit test that calls the worker's row-processing on synthetic data and asserts the resulting Sheet1-shape includes `scheduled_future` rows.
- A workflow_dispatch tool that POSTS synthetic Schedule API rows into a test spreadsheet and runs the worker against it. Smoke-tests the full pipeline.

**Sequencing:**
1. **Step 1a (DONE — PR-FC1, 2026-06-03):** the date-window FOUNDATION shipped — `FORWARD_WINDOW = timedelta(days=14)` + the pure, unit-tested `compute_effective_scrape_end(scrape_end, test_end_date, today)` (both Gemini #1 tz-safety + #2 pinned-reproducibility findings baked in: pinned/historical runs return scrape_end unchanged, live runs extend +14d capped at session end), wired into the viewport slice (Gemini #4), and `scheduled_future` registered in `_VALID_ORIGINS`. **Verified no-op on the current adjourned session** (scrape_end pinned in the past). NO producer yet.
   - **Step 1b (next):** the row-GENERATION — turn Schedule-API meetings with `meeting_date > today` into `scheduled_future` master_events rows (the risky part; touches the Schedule-API→rows path). Worker writes future rows. Still no X-Ray change.
2. **Step 2 (small):** X-Ray Section X — read `Origin = "scheduled_future"` rows, render as upcoming-meetings widget.
3. **Step 3 (med):** dedup + reconciliation — when HISTORY catches up to a previously-future meeting, suppress the duplicate. Test the boundary handoff.
4. **Step 4 (synthetic-test):** ship the workflow_dispatch tool with synthetic-injection capability so we can validate the 2027 flow without waiting for January.

**Owner guardrails:** same as today — Standard #1 / #4 / #6 / #8. The forward-calendar adds NEW dynamic surface but doesn't change the existing safety story (text-parsing forbidden, source-miss visibility maintained, etc.).

## ~~New-Verb Canary — drift detection at cycle 1~~ (REJECTED 2026-04-28)
- ❌ **REJECTED by owner 2026-04-28** as a band-aid that creates
  perpetual manual engineering debt. The end state still required a
  developer to hardcode each new verb into a lexicon file — unscalable
  to 50 states and to vocabulary drift within VA. A canary that fires
  visibility events at cycle 1 only shortens the time-to-detection;
  it does not change the response shape, which remains "human reads
  alert, human writes code." Replaced by the structural-classifier
  direction below. Audit trail preserved here so the rationale is
  not lost on next read.

## Structural classifier as source of truth — LegislationEvent over text patterns (flagged 2026-04-28, IMPLEMENTED 2026-05-03 in PR-C7)
- ✅ **IMPLEMENTED 2026-05-03 — PR #41 (in flight, awaiting bot re-review on commit `45c72b5`).** Time-recovery side of the pivot ships as PR-C7. Classification side deferred to PR-C7.1 (Sheet1 `LegEventType` column + X-Ray reads it). See [[log#2026-05-03-pr--pr-c7-opened-pr-41--drop-verb-gate--cross-cycle-persistent-legevent-cache]] and [[state/current_status]] for current state.
- [ ] **The architectural pivot.** Replace the text-pattern verb gate
  with structural data from the LIS LegislationEvent API as the
  classifier of record. The text-pattern architecture
  (`KNOWN_NOISE_PATTERNS`, `KNOWN_EVENT_PATTERNS`, `MEETING_VERB_TOKENS`,
  `MEETING_ACTION_PATTERNS`, `ADMINISTRATIVE_PATTERNS`,
  `ADMIN_OVERRIDE_PATTERNS`) doesn't scale: each new verb, each new
  session, each new state requires a hand-edit to a hardcoded list.
  The PR-C6 full-session stress test surfaced 997 meeting bugs
  precisely because new vocabulary entered HISTORY.CSV between the
  Feb 9-13 crossover sample and the rest of the session.
  **Why structural wins:** every state's bill-tracking system exposes
  SOME structured event API (VA's LegislationEvent, Congress.gov bulk
  data, NCSL state-legislatures aggregator). The structural API tells
  us WHAT happened — vote, report, reading, referral — without us
  parsing free-form text. Use it as the classifier of record; text
  patterns become a last-resort fallback for rows the structural data
  doesn't cover.
  **Concrete code move for VA (PR-C6.3 alternative direction):**
    1. Remove the `MEETING_VERB_TOKENS` gate from the LegislationEvent
       fallback at `calendar_worker.py:2522`. Today, a row only attempts
       LegEvent recovery if its outcome contains a verb in the allowlist
       — that is the verb-list dependency we are escaping.
    2. Add a persistent cross-cycle LegEvent cache (keyed by
       `(bill, session)`, persisted between worker runs in a sibling
       sheet or a small SQLite blob). The endpoint returns the bill's
       whole event history in one call, so a cache hit is a free
       in-memory lookup. Cost stays bounded as the cache fills.
    3. With #1 and #2 in place, ANY `journal_default` row attempts
       LegEvent recovery; matching events backfill time/committee.
       The 994 meeting bugs from the PR-C6 stress test should collapse
       without adding a single line to `MEETING_VERB_TOKENS`.
    4. The remaining tail (LegEvent has no matching event for the row)
       lands in a residual `unsourced_no_legevent` bucket — visible,
       counted, far smaller surface than the current verb-list
       maintenance burden.
  **Risk to manage:** PR-C3 (PR #30) hung the worker on N+1 LegEvent
  fetches against the LIS WAF — the original sin that drove the
  per-cycle cache in PR-C3.1 ([[failures/assumptions_audit]] #42).
  Going from "verb-gated" to "all journal_default rows fire LegEvent"
  enlarges the candidate set by ~15× per cycle. The per-cycle cache
  alone may not be enough; the cross-cycle cache (item #2 above) is
  what makes the move safe. Pre-merge audit MUST size
  `unique_bills_in_journal_default × expected_calls_per_bill` against
  the LIS WAF rate-limiter before shipping.
  **For 50 states:** each new state plugs in ONE structural-event
  adapter that normalizes its API response into a shared internal
  schema `(bill, date, chamber, action_type)`. The text pattern lists
  get archived as the VA-only fallback they already are. No more
  per-clerk verb maintenance.
  **Connects to:** [[failures/assumptions_audit]] #6 (Noise Words
  Negative Filter — names this risk class); CLAUDE.md Standard #6
  (50-state isolation); CLAUDE.md Standard #3 (data-driven, not
  text-driven — structural identifiers over text parsing).

## Per-state lexicon extraction — `lexicons/va.py` (flagged 2026-04-28, PR-C6 stress test)
- [ ] Extract every VA-specific pattern list from `calendar_worker.py`
  and `pages/ray2.py` into a single `lexicons/va.py` module. The
  pattern lists in scope (currently duplicated across files):
  `KNOWN_NOISE_PATTERNS`, `KNOWN_EVENT_PATTERNS`, `MEETING_VERB_TOKENS`,
  `MEETING_ACTION_PATTERNS`, `ADMINISTRATIVE_PATTERNS`,
  `ADMIN_OVERRIDE_PATTERNS`. The X-Ray and worker today carry partly
  overlapping copies — drift is silent and only caught by manual diff.
  **Why now:** PR-C6.3 will add verbs to the worker's
  `MEETING_VERB_TOKENS` to recover 994 lost meeting times. The X-Ray's
  `MEETING_ACTION_PATTERNS` has its own list; both need the same edit
  to stay aligned. A single source of truth eliminates the drift class.
  **50-state vector:** CLAUDE.md Standard #6 ("every VA-specific pattern
  must be isolated and swappable") names this — adding state #2 should
  be `lexicons/<state>.py` plus a config flag, NOT a code fork. Keeping
  this on the deferred list because it's a refactor with non-trivial
  blast radius and PR-C6.3/C6.4/C6.5 should land first to stabilize the
  current verb set before extracting it.
  **Tagged in:** CLAUDE.md Standard #6.

## ✅ DONE — L3b Nightly Audit — Schedule_Witness retention owner (flagged 2026-04-24; SHIPPED #126, 2026-06-14)
- [x] **SHIPPED in PR #126** as `tools/witness_retention/prune.py` + `.github/workflows/witness_retention.yml`. Deletes the contiguous leading prefix of `Schedule_Witness` rows whose `seen_at_utc < now − 90d`; aborts on schema drift; no-op when nothing expired. The workflow **joins the worker's `calendar-worker` concurrency group** (`cancel-in-progress: false`) → exclusive tab access, no append/delete race, zero worker-workflow change. Caught by `sustainability_audit` CAPACITY (asserts no Witness row older than the horizon). *(Note: surfaced by the sustainability audit, which found this had been a `TODO` the whole time despite stress-test Y5 claiming "retention prune exists.")* Original design notes below for history:
  **Context:** PR-C2's original design pruned the witness tab inside the
  15-min cycle (`append_rows` + `col_values(1)` + `delete_rows` on the same
  tab). Gemini round-1 concern #2 flagged this as a documented
  eventual-consistency race in the Sheets API — under load the prune can
  silently delete rows we just appended, or skew the retention boundary.
  The in-cycle prune was removed in the PR-C2 round-2 patches. Retention
  is now enforced by an L3b Nightly Audit which runs outside the 15-min
  hot path, reads the witness tab under exclusive use, and deletes rows
  whose `seen_at_utc` < `now_utc - 90d`.
  **Canary in place:** the 15-min cycle still reads `col_values(1)` and
  surfaces `witness_rows` in `source_miss_counts` + `witness_canary_over_threshold`
  WARN when rows > 500_000 — so L3b-audit lag is visible.
  **Tagged in:** [[architecture/calendar_pipeline#Part B — `Schedule_Witness` change-feed tab]]
  and in code comments at the canary site.

## Witness cache-carryover scope filtering (flagged 2026-04-24, PR-C2 post-merge)
- [ ] Filter `api_schedule_map` keys to a bounded date window before the
  `Schedule_Witness` delta diff so historical cache entries outside the
  active scrape window stop emitting `CHANGED` rows on every cycle.
  **Context:** First post-merge cycle showed `CHANGED` deltas for cached
  meetings dated Nov 2025 - Jan 2026 — well outside the Feb 9-13 scrape
  window. Mechanism: `api_schedule_map` is seeded from ALL `API_Cache`
  rows at `calendar_worker.py:1221` with no date filter. The live-loop
  date filter at `:1332` scopes only the *write* side; the delta diff at
  `:1472` then iterates the FULL map. The `{Location}`-only burst guard
  correctly suppresses Location-only changes, but any historical entry
  where SortTime/Status also drifts still emits a `CHANGED` row — noise
  for meetings the witness isn't responsible for tracking.
  **Fix:** Filter `api_schedule_map.items()` to keys whose
  `meeting_date >= scrape_start - <buffer>` immediately before the diff
  loop. Preserves Part C reconciliation's full witness index (it reads
  the tab via `col_values()`, independent of this filter).
  **Tagged in:** [[architecture/calendar_pipeline#Part B — `Schedule_Witness` change-feed tab]]

## PR-C2.1 — Playwright historical scraper (deferred from PR-C2)
- [ ] When Part C emits `CONFIRMED BLIND-WINDOW LOSS` for a date, launch a
  Playwright scrape of the LIS Meeting Schedule web page for that
  historical date so missing times can be filled in. Gemini correction
  (2026-04-24): the LIS Meeting Schedule page has a date-picker that
  exposes historical schedules, so the scraper CAN act as a time machine
  — Part C elevates from "detect blind-window loss" to "recover missing
  times where possible".
  **Must-have (Gemini round-2 concerns #2 and #3):**
  - Use `wait_for_selector()` bound to the actual schedule-table DOM
    element. Do NOT use `wait_for_load_state("networkidle")` — bloated
    government sites rarely reach true network idle (broken background
    trackers), causing indefinite hangs.
  - Per-date timeout ≥ 15 seconds. The prior plan's 5s budget is too
    tight for LIS during peak session and produces false-positive
    timeouts on slow historical-database queries.

## API_Cache historical Location backfill (flagged 2026-04-24, PR-C2 post-merge)
- [ ] Backfill `Location` on `API_Cache` rows that predate the PR-C2
  schema migration. The migration only writes `F1="Location"` in the
  header; pre-existing rows stay rectangular via `""` padding from
  `get_all_records()` and never receive a real Location value.
  **Context:** Post-merge inspection showed `API_Cache` rows for
  Nov 2025 - Dec 2025 with `Location=""` while the live LIS API returns
  real values (Senate Room A, House Chamber, Virtual Meeting, etc.). The
  witness `{Location}`-only burst guard correctly suppresses the
  first-cycle backfill noise on the witness, but the cache itself stays
  empty — every historical row is permanently degraded for downstream
  consumers (X-Ray, Sheet1 location resolution, future analytics).
  **Channel:** PR-C2.1's Playwright scraper is the natural backfill path
  — it already revisits historical schedules for `CONFIRMED BLIND-WINDOW
  LOSS` time recovery, and Location lives one DOM tier from time on the
  same page. Folding Location backfill into the same scrape avoids a
  second pass through LIS for the same dates.
  **Tagged in:** [[ideas/future_improvements#PR-C2.1 — Playwright historical scraper (deferred from PR-C2)]]

## Notification Routing (flagged 2026-04-24, PR-C2)
- [ ] Re-route PR-C2 CRITICAL alerts to a dedicated monitoring channel.
  **Context:** PR-C2 emits two CRITICAL classes via `push_system_alert` (so
  they surface as `SYSTEM_ALERT` rows in Sheet1/Bug_Logs):
  1. `y1_stale::*` — cursor older than 30 days (worker offline > 30d).
  2. `gap_reconciliation_oversized::*` — gap > 7 days, reconciliation cap
     hit, manual review required.
  3. Any `gap_critical::*` (gap > 60 min) — 4+ missed 15-min cycles.
  Owner (Tucker) flagged during PR-C2 scoping that these may eventually
  want a dedicated dashboard or push channel (e.g. email, pager, separate
  Streamlit alert panel) rather than routing through generic `SYSTEM_ALERT`
  rows. The 7-day cap alert in particular signals the scenario where
  blind-window losses cannot be confirmed programmatically and require
  human judgement — exactly the kind of signal that should not get buried
  in Bug_Logs if alert volume grows. Tagged in
  [[architecture/calendar_pipeline#Part C — Gap-Triggered Reconciliation (PR-C2)]]
  and in code comments on the two alert sites.

## Bug_Logs routing for calendar_worker (flagged 2026-04-24, PR-C2 post-merge)
- [ ] Wire `calendar_worker.py` to write categorized alerts to the
  `Bug_Logs` tab (PR-A's `source_miss_counts` denominator buckets,
  PR-C1's circuit-breaker trips, PR-C2's gap/witness/reconciliation
  alerts) rather than only routing them through `SYSTEM_ALERT` rows on
  `Sheet1`.
  **Context:** Post-merge inspection confirmed the `Bug_Logs` tab is
  empty for `calendar_worker`. Today, `push_system_alert()` appends to
  the in-memory `alert_rows` list, which lands as `SYSTEM_ALERT` rows in
  the cycle's `Sheet1` overwrite. `Sheet1` is rewritten on every cycle —
  alerts disappear once a healthy cycle ships. `Bug_Logs` exists in the
  workbook (only `backend_worker.py` writes there).
  **Why it matters now:** PR-C2's CRITICAL alerts (`y1_stale`,
  `gap_reconciliation_oversized`, `gap_critical`) deserve durable
  history per the [[ideas/future_improvements#Notification Routing (flagged 2026-04-24, PR-C2)]]
  entry above. Bug_Logs routing is a precondition for any future
  dashboard or push channel consuming those rows, since `Sheet1` is
  ephemeral while `Bug_Logs` is append-only. Already partially captured
  under "High Priority (Before v2 Merge)" below; this entry is the
  concrete post-PR-C2 confirmation that the gap exists and matters.
  **Tagged in:** [[architecture/calendar_pipeline]]

## High Priority (Before v2 Merge)
- [ ] Nightly session/committee discovery bot (Session API + Committee API)
- [ ] Bug_Logs integration in calendar_worker (currently only in backend_worker.py)
- [ ] Mismatch categorization with severity levels instead of suppression
- [ ] Runtime optimization (currently ~4-5min, target <3min)

## Medium Priority (Post-Merge)
- [ ] Reconciliation job: nightly diff of Sheet1 vs LIS Schedule API
- [ ] Circuit breaker: if zero events on a weekday during session, halt and alert
- [ ] Historical trend dashboard (committee activity patterns over sessions)
- [ ] Stale data detection: alert if API_Cache hasn't been updated in >24hrs during session

## Low Priority (Multi-State Expansion)
- [ ] Abstract Virginia-specific patterns into swappable config
- [ ] State adapter interface (committee codes, API endpoints, data formats)
- [ ] National committee name normalization
- [ ] Cross-state legislative intelligence (similar bills in different states)

## Performance Ideas
- [ ] Profile HISTORY.CSV iteration — possible vectorization with pandas ops
- [ ] Batch Google Sheets writes instead of clear+update
- [ ] Lazy agenda PDF extraction (only fetch if bill list is empty from docket)
- [ ] Cache Committee API response (changes only at session start)

## Dynamic-environment readiness (added 2026-06-02, owner mandate)
We validate against a FROZEN, complete session; the product's real job is the LIVE session. These design for that — see [[state/current_status#Why the remaining work is DESIGN-FOR-DYNAMIC, not static cleanup]] and [[log#2026-06-02 decision]].
- [ ] **Chronological-replay simulation** — feed HISTORY.CSV day-by-day in date order and confirm the worker/router/cache handle incremental arrival, a bill's state evolving across days, and late-breaking actions. The ONE dynamic test runnable on static data, pre-launch. Validates the structural router + cache stay correct as data accrues, not just on the complete snapshot.
- [ ] **Forward calendar (upcoming meetings before they happen)** — the real dynamic frontier and owner-flagged hardest future challenge. All work to date is HISTORY-backed (past actions). Requires the Schedule API future-window as the signal source + reconciliation against actual outcomes as days pass (predicted meeting → did it happen / reschedule / cancel). Different success metric ("did the predicted meeting occur as scheduled?"). Scope after C7.1b closes.
- [ ] **Bot-reviewer continuity** — Gemini Code Assist GitHub bot sunsets (consumer install blocked 2026-06-18, reviews cease 2026-07-17; per Google's deprecation page the for-individuals IDE extension + Gemini CLI stop 2026-06-18 too, migration target "Antigravity"). This is the free `gemini-code-assist[bot]` PR reviewer only — distinct from any consumer Gemini chatbot subscription, which is unaffected. **Codex (`chatgpt-codex-connector`) is unaffected and stays as reviewer #1.** Replacement candidates for the second pair of eyes (all free for public repos):
    - **CodeRabbit** — free Pro tier for public/OSS repos; closest drop-in to the Gemini bot's inline-PR-comment UX.
    - **Qodo PR-Agent** (formerly CodiumAI, open-source, ~8.5k★) — self-host via GitHub Action with our own LLM key; works with any model incl. local. Most control, no vendor lock-in.
    - **GitHub Copilot code review** — included if we ever hold a Copilot seat; native to the PR surface.
    - Fallback with zero new vendor: **Codex alone + the tightened 15-point self-audit** (already covers the bug classes the bots historically caught). Decide before mid-July; parked until C7.1b closes.

## ~~Structural migration of the Part C reconciliation verb pre-filter~~ — DONE (Part C, 2026-06-13)

DONE: the Part C gap-recovery check now uses a recorded-vote `RefidClass` signal
(`VOTE_COMMITTEE`/`VOTE_FLOOR`) instead of `MEETING_VERB_TOKENS` — cache-independent (it runs
before LegEvent hydration, so `route_event` was unavailable; computed from `History_refid` + the
VOTE.CSV id set). Measured MORE precise (drops non-session Sunday false-positives). The worker's
`MEETING_VERB_TOKENS` constant was removed — **the worker is now fully text-free on the meeting
path.** The only remaining verb lists are in OFFLINE standalone tools (their own copies, not
imports): `tools/crossover_audit/diff_sheet1.py` and `tools/meeting_bug_triage/`. Migrating those
is optional (offline, not the lobbyist/worker path).
