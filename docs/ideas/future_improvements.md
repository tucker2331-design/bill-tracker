# Future Improvements

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
