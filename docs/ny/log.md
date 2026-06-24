---
tags: [ny, log, meta]
updated: 2026-06-24
status: active
---

# New York Log

Append-only, reverse-chronological. Use the same prefix shape as the main log:
`## [YYYY-MM-DD] <kind> | <title>`.

## [2026-06-24] hardening | Structural-only outcome and health counters

Owner standard tightened: no text parsing for durable classifications. Removed
OpenLeg status-text outcome fallbacks from `ny_bill_tracker.py`; `outcome` now
uses structural `signed` and `vetoMessages` only, with all other bills marked
`unknown_structural`. Added health findings/counters for unknown structural
outcomes, unrecognized chamber values, malformed bill IDs, and missing source
URL sessions. Folded in CodeRabbit-valid durability feedback: bounded OpenLeg
HTTP retries, guarded public bill URLs, modern `gspread.service_account_from_dict`
write auth, and an explicit completeness-cell layout comment.

## [2026-06-24] review | Gemini fold-in on PR #168

Gemini reviewed PR #168 and flagged two actionable findings: `crossed_over`
used status/milestone text instead of structural action chamber, and
`_norm_chamber()` matched the ambiguous `ASS` prefix for Assembly. Folded both
in: crossed-over now derives from normalized `actions.items[].chamber`, tests
include an Assembly action fixture, and Assembly prefix matching uses `ASSEM`
instead of `ASS`. Added assumptions-register entry #2.

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
