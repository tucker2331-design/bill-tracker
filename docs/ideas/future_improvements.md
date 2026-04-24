# Future Improvements

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
