---
tags: [ny, state, live]
updated: 2026-06-25
status: active
---

# New York Current Status

**Goal:** retune the Virginia bill-tracker engine for New York while keeping the
state-specific source contracts clearly separated in the brain and code.

## Active focus

First pass is the New York bill-record engine plus a read-only calendar source
probe, not the UI. The bill engine has now
passed full-session dry-run, first live-write validation, branch-level
production read-back verification, bot review, merge, and post-merge main
validation. The once-daily workflow schedule is live on `main` as of PR #170
(`7cd08c8`):

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
- Read-only calendar probe scaffold: `ny_calendar_probe.py` parses OpenLeg
  Senate agenda-meeting JSON and official Assembly agenda/floor-calendar link
  structures into audit rows and health counters without writing sheets.
- Live Assembly probe validation passed on 2026-06-25: 365 rows across agenda
  index, floor index, agenda-detail sample, and floor-detail sample sources;
  zero source errors; zero health findings; zero time-bucket denominator drift.

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

Calendar scoping has a dedicated architecture page:
[[ny/architecture/calendar_source_options]]. The recommended path is Senate
OpenLeg agenda/calendar APIs first, Assembly official agenda/floor calendar
DOM probes second, and public hearing/session/standing-schedule documents as
witness or anchor sources until validated.

## Next steps

1. Run the read-only NY calendar source probe live against OpenLeg with `NY_OPENLEG_API_KEY`, then record Senate agenda coverage metrics.
2. Design the first NY calendar worker from the validated probe contract before promoting any non-empty `Upcoming JSON`.
3. Scope durable terminal-outcome parity for bills currently counted as `unknown_structural`, without status-text inference.
4. Build a session-rollover plan before the next New York legislative session.
5. Revisit cadence after frontend and incremental-update scoping.
