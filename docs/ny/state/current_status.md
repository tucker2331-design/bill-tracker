---
tags: [ny, state, live]
updated: 2026-06-24
status: active
---

# New York Current Status

**Goal:** retune the Virginia bill-tracker engine for New York while keeping the
state-specific source contracts clearly separated in the brain and code.

## Active focus

First pass is the New York bill-record engine, not the UI. The engine has now
passed full-session dry-run, first live-write validation, branch-level
production read-back verification, bot review, merge, and post-merge main
validation:

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
- The shared `Chamber` column emits product-compatible `House` / `Senate`; NY
  native `Assembly` / `Senate` chamber values are preserved in NY-only JSON
  provenance fields.
- Completeness JSON at `R1`, including action-history coverage, sponsor coverage,
  vote coverage, summary coverage, agenda-reference count, outcome-source counts,
  unknown structural outcome rate, unrecognized chamber counters, missing source
  URL counters, a run-level `health` object, and a New York calendar-scope note.
- Post-write read-back verification is live on `main` so the workflow checks the
  actual Google Sheet artifact after writing, not only the in-memory payload.
- GitHub Actions workflow: `New York Bill Tracker` with manual
  `check-config`, `dry-run`, and `write` modes plus a once-daily production
  write schedule.

## Important source caveat

The first NY engine deliberately does not claim full meeting/calendar coverage.
OpenLeg's public docs state that Assembly calendar data is not currently sent
to OpenLeg, and the committee docs say Assembly committee data is not currently
sent and `chamber` must be `senate`. So bill records are the first reliable
NY layer; full meeting parity needs a separate source-validation pass.

Terminal outcome classification is also intentionally source-honest. The engine
uses structural `signed` and `vetoMessages` fields; bills without a proven
structural terminal marker are labeled `unknown_structural` and counted in
health metrics instead of being inferred from status text.

## Next steps

1. Merge the once-daily workflow schedule after review.
2. Scope durable terminal-outcome parity for bills currently counted as `unknown_structural`, without status-text inference.
3. Validate a meeting/calendar source for Assembly before building a NY calendar worker.
4. Build a session-rollover plan before the next New York legislative session.
