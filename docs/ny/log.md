---
tags: [ny, log, meta]
updated: 2026-06-24
status: active
---

# New York Log

Append-only, reverse-chronological. Use the same prefix shape as the main log:
`## [YYYY-MM-DD] <kind> | <title>`.

## [2026-06-24] review | CodeRabbit committee chamber health fold-in

Folded in CodeRabbit's health-surface finding after `8a14ad1`: unknown
`pastCommittees[].chamber` values now flow into row counters, run completeness,
and the `UNKNOWN_CHAMBER_VALUE` health finding instead of only preserving raw
referral provenance.

## [2026-06-24] review | CodeRabbit raw committee chamber fold-in

Folded in CodeRabbit's final referral de-dupe finding after `5c792d5`: unknown
OpenLeg committee chamber codes now remain distinct in the referral key by
falling back to raw chamber provenance when exact normalization fails. Added a
fixture so same-named referrals from different unknown chamber codes cannot
silently collapse.

## [2026-06-24] hardening | Exact chamber code normalization

Owner standard tightened again: structural source codes must be normalized by
explicit accepted values, not prefix matching. `ny_bill_tracker.py` now maps
known OpenLeg chamber codes exactly and treats unknown values as unresolved raw
provenance with health counters. Added regression coverage so future unrelated
codes like `SENIOR` or `ASSEMBLYMAN` cannot silently classify as Senate or
Assembly.

## [2026-06-24] review | CodeRabbit sheet stale-cell fold-in

Folded in CodeRabbit's active-row stale-cell finding after `d352834`: the
Google Sheets update payload now blanks column Q for all active rows and clears
column R below the `R1` completeness cell, while still avoiding pre-write
`ws.clear()`.

## [2026-06-24] review | CodeRabbit pagination/referral fold-in

Folded in two valid CodeRabbit findings after `7f148b0`: referral distinctness
now keys on `(NY chamber, committee name)` so same-named Senate/Assembly
committees do not collapse, and OpenLeg pagination now requires `total` and
`offsetEnd` metadata before deciding a fetch is complete.

## [2026-06-24] review | CodeRabbit second-pass safety fold-in

Folded in valid CodeRabbit findings after `e1b7f8f`: action records with blank
OpenLeg `text` are now preserved in history with `action_missing=true` and
counted in completeness health; OpenLeg request retries store sanitized
exception class/status only so `NY_OPENLEG_API_KEY` cannot leak through raised
request URLs; Google Sheets writes no longer call `ws.clear()` before replacement
data is written, preserving last-known-good rows on transient write failure.

## [2026-06-24] review | CodeRabbit and Qodo fold-in on PR #168

Folded in valid open review items after `dfbf989`: pinned the NY workflow's
GitHub actions to official tag SHAs, moved NY workflow dependencies to pinned
`requirements-ny.txt`, changed Slack-alert fallback category to `UNKNOWN`,
made OpenLeg pagination fail on empty pages before the declared end, and aligned
the shared product `Chamber` column with the VA contract (`House` / `Senate`)
while preserving NY-native `Assembly` / `Senate` in NY-only provenance fields.

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
