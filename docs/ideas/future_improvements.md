# Future Improvements

## New-Verb Canary — drift detection at cycle 1 (flagged 2026-04-28, PR-C6 stress test)
- [ ] Add a startup canary in `calendar_worker.py` that scans HISTORY.CSV
  outcome strings for verbs not matched by ANY classifier list
  (`KNOWN_NOISE_PATTERNS`, `KNOWN_EVENT_PATTERNS`, `MEETING_VERB_TOKENS`,
  `ADMINISTRATIVE_PATTERNS`, `MEETING_ACTION_PATTERNS`,
  `ADMIN_OVERRIDE_PATTERNS`). For each unknown verb, emit one
  categorized `push_system_alert(category="DATA_ANOMALY", severity="WARN",
  dedup_key=f"new_verb::{verb_normalized}")`. Same dedup-by-verb pattern
  as the PR-C5.1 SB584 malformed-row alert — flooding-safe across cycles.
  **Why:** the PR-C6 full-session stress test surfaced 997 meeting-bug
  rows (vs 0 in crossover week) because verbs that appear post-Feb-13
  (`Reported with amendments`, `Conference report agreed`, etc. — exact
  list TBD by PR-C6.3 dump) are not in `MEETING_VERB_TOKENS` and so the
  PR-C3.1 LegislationEvent fallback gate never fires for them. We
  caught the drift only by running the X-Ray on a wider window — i.e.,
  when a human happened to look at Section 9. With a canary, the FIRST
  cycle that processes a new verb emits a visible alert; the next
  session, or any out-of-distribution edge case in the current session,
  is caught at cycle 1, not month 1. Cost is negligible (set
  difference over ~64k strings per cycle, computed once at startup).
  **Connects to:** [[failures/source_miss_visibility]] — same architecture
  (every silent fallback emits a categorized counted signal), extended
  to the verb-list dimension.
  **Tagged in:** [[failures/assumptions_audit]] #6 (the existing
  "noise words negative filter" entry already names this risk class).

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

## L3b Nightly Audit — Schedule_Witness retention owner (flagged 2026-04-24, PR-C2 round-2)
- [ ] Implement L3b nightly audit that owns `Schedule_Witness` retention.
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
