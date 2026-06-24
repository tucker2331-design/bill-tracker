---
tags: [ny, log, meta]
updated: 2026-06-24
status: active
---

# New York Log

Append-only, reverse-chronological. Use the same prefix shape as the main log:
`## [YYYY-MM-DD] <kind> | <title>`.

## [2026-06-24] session | New York brain and first bill engine scaffolded

Created the NY brain branch inside `docs/ny/` with a separate start page,
standards, state, architecture, data inventory, source-scoping protocol,
validation plan, assumptions register, owner setup checklist, and NY-local log. Added
`ny_bill_tracker.py`, a separate New York OpenLegislation bill-record engine
that writes the Virginia product tab shape to `NY_Bill_Tracker` while keeping
calendar/meeting coverage explicitly unclaimed until source validation.
Fixture tests pass by direct invocation; `pytest` is not installed locally.
Live dry-run is blocked on owner-provided `NY_OPENLEG_API_KEY`; live write is
blocked on `NY_SPREADSHEET_ID` and workbook strategy confirmation.
