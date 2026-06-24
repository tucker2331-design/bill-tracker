---
tags: [ny, state, live]
updated: 2026-06-24
status: active
---

# New York Current Status

**Goal:** retune the Virginia bill-tracker engine for New York while keeping the
state-specific source contracts clearly separated in the brain and code.

## Active focus

First pass is the New York bill-record engine, not the UI:

- `ny_bill_tracker.py` is a new file and does not mutate the Virginia `bill_tracker.py` path.
- Output defaults to a separate `NY_Bill_Tracker` sheet tab.
- Source is New York OpenLegislation (`legislation.nysenate.gov/api/3`).
- Required runtime secret is `NY_OPENLEG_API_KEY`.
- Session defaults to `NY_OPENLEG_SESSION_YEAR=2025` (New York's 2025-2026 two-year session).

## What exists now

- Full bill-universe pagination through `/api/3/bills/{sessionYear}`.
- Record flattening into the same product columns used by Virginia's `Bill_Tracker` tab:
  Bill, Title, Status, Outcome, Patron, Chamber, Crossed Over, Last Committee,
  Referrals, Last Action, Latest Vote JSON, Upcoming JSON, History JSON,
  Data As Of, Source.
- Completeness JSON at `R1`, including action-history coverage, sponsor coverage,
  vote coverage, summary coverage, agenda-reference count, outcome-source counts,
  and a New York calendar-scope note.
- Manual-only GitHub Actions workflow: `New York Bill Tracker`
  (`check-config`, `dry-run`, `write`). No schedule yet.

## Important source caveat

The first NY engine deliberately does not claim full meeting/calendar coverage.
OpenLeg's public docs state that Assembly calendar data is not currently sent
to OpenLeg, and the committee docs say Assembly committee data is not currently
sent and `chamber` must be `senate`. So bill records are the first reliable
NY layer; full meeting parity needs a separate source-validation pass.

## Next steps

1. Run a dry fetch with a real `NY_OPENLEG_API_KEY`.
2. Inspect the first full-session completeness object before writing to a user-facing tab.
3. Decide where NY should live operationally: same workbook with `NY_*` tabs or a separate NY workbook.
4. Validate a meeting/calendar source for Assembly before building a NY calendar worker.
