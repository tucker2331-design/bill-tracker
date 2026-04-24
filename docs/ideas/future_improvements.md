# Future Improvements

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
