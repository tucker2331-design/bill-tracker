---
tags: [ny, log, meta]
updated: 2026-06-25
status: active
---

# New York Log

Append-only, reverse-chronological. Use the same prefix shape as the main log:
`## [YYYY-MM-DD] <kind> | <title>`.

## [2026-06-25] review | PR #173 bot fold-in

Folded in valid Gemini, Qodo, and CodeRabbit findings on the read-only calendar
probe branch. The probe now preserves falsy source values in labels, ignores
malformed OpenLeg `result` payloads safely, fails invalid
`NY_CALENDAR_PROBE_DETAIL_LIMIT` values with a controlled message, logs source
probe exceptions before storing typed audit errors, warns on per-source
zero-row gaps, surfaces unknown time buckets in totals, and makes denominator
drift reachable when a row lands outside the known bucket set.

## [2026-06-25] implementation | Read-only NY calendar probe scaffolded

Added `ny_calendar_probe.py` and `test_ny_calendar_probe.py` as the first
calendar-engine implementation step after [[ny/architecture/calendar_source_options]].
The probe parses OpenLeg Senate agenda-meeting JSON plus official Assembly
agenda/floor-calendar link structures into audit rows, explicit time buckets,
and health counters. It performs no Google Sheet writes and does not populate
`Upcoming JSON`.

Local validation passed by direct fixture invocation because `pytest` is not
installed locally: syntax compile with `PYTHONPYCACHEPREFIX=/private/tmp/pycache`,
`test_ny_calendar_probe` direct function calls, and
`ny_calendar_probe.py --check-config --sources assembly`.

Live Assembly validation also passed on 2026-06-25 with
`ny_calendar_probe.py --sources assembly --detail-limit 3`: 365 rows across
four audited source buckets, zero source errors, zero health findings, and zero
time-bucket denominator drift. The split was 17 agenda-index rows, 5
floor-index rows, 154 agenda-detail bill rows with `OFF_THE_FLOOR` relative
timing, and 189 floor-calendar bill rows marked `CALENDAR_RELEASE_ONLY`.
OpenLeg live agenda validation remains separate because it requires
`NY_OPENLEG_API_KEY`.

## [2026-06-25] scoping | New York calendar source options documented

Scoped the safest path for rebuilding the Virginia-style calendar in New York.
Added [[ny/architecture/calendar_source_options]] as the primary architecture
note: Senate begins with OpenLeg agenda meetings and Senate calendar APIs;
Assembly uses official Assembly agenda/floor calendar pages through
DOM/link-structured extraction after a probe; public hearings, session
calendars, and standing committee schedules start as witness or anchor sources.
The page records explicit time policy, row origins, health counters, rejected
shortcuts, and a read-only source-probe plan before production `Upcoming JSON`.

Bot fold-in on PR #172 accepted Qodo's frontmatter/root-index isolation and
endpoint-consistency findings plus Gemini's metrics-denominator cautions:
`docs/index.md` now has complete frontmatter and only links to NY strategy,
OpenLeg agenda-meetings placeholders use one canonical date-time spelling, and
calendar health metrics are documented as final audit/completeness outputs
rather than stale main-table rows. Timeless-by-design rows must occupy explicit
denominator buckets.

## [2026-06-24] audit | Daily schedule and quality audit scoped

Owner approved a once-daily schedule while frontend work is pending. Updated the
NY workflow to add a daily scheduled write while retaining manual
`check-config`, `dry-run`, and `write` modes. Added [[ny/testing/quality_audit]]
to record which fields are structurally supported, which fields are
display/provenance only, why `Upcoming` remains an explicit calendar-source gap,
and which health counters must stay visible.

Gemini review on PR #170 found that two quality-audit counter names did not
match the actual `R1` completeness JSON. Folded in the correction:
`committee_agenda_refs` and `skipped_malformed_bill`.

Qodo review on PR #170 found three operational review items. Folded in the
actionable ones: added [[ny/testing/quality_audit]] to the root [[index]],
restricted production NY writes to `refs/heads/main`, and split concurrency so
manual config/dry-run probes cannot queue ahead of scheduled writes.

PR #170 merged to `main` as squash commit `7cd08c8`. Post-merge GitHub Actions
run `28139043035` passed in `check-config` mode on `main`, confirming the merged
workflow is dispatchable and the non-write path skips production writes.

## [2026-06-24] validation | Read-back verifier merged and passed on main

PR #169 merged to `main` as squash commit `5cfd215`. Post-merge GitHub Actions
run `28137876638` passed in write mode on `main`: 25,314 bills built, 25,315
rows verified, 25,314 bills verified, `R1` health status `WARN`, and the
bounded tail range verified through row 25,365. Scheduling remains a separate
cadence decision; the artifact verifier is now live.

## [2026-06-24] review | PR #169 bot fold-in

Folded in valid Gemini, Qodo, and CodeRabbit findings on the NY read-back
verification branch: reused the already-fetched first sheet row for `R1`
completeness JSON instead of making a separate `acell` call, rejected non-object
`R1` JSON before `.get()` access, bounded tail verification to the documented
50-row sentinel range, and changed clean health status from non-standard `OK` to
standard `INFO`. Post-fold-in branch Actions run `28137572349` passed in write
mode on commit `bc9b691`: 25,314 bills built, 25,315 rows verified, and tail
verified through row 25,365.

## [2026-06-24] hardening | Automated sheet read-back verification live-tested

Owner confirmed the first live `NY_Bill_Tracker` sheet spot check loaded
correctly. Follow-up PR #169 adds production read-back verification of the
actual Google Sheet artifact after write mode: header contract, `R1`
completeness JSON, active bill column, and stale-tail cells below the payload.
Branch Actions run `28137147423` passed in write mode on commit `61636dc`:
25,314 bills built, 25,315 rows verified, and tail verified through row 25,365.
Scheduling remains blocked until this verifier passes bot review and merges.

## [2026-06-24] validation | First live write passed

Post-merge GitHub Actions live write passed for `New York Bill Tracker` mode
`write`, session year `2025`, against the explicitly configured New York sheet
target. Run `28136320411` completed in 2m 25s and built `NY_Bill_Tracker` with
25,314 bills, 25,268 bills with sponsor, and 25,314 bills with action history.
This confirms the engine can fetch the full 2025 OpenLeg bill session and write
the NY tab without touching Virginia workflow state. GitHub also emitted a
non-engine annotation that pinned official actions using Node.js 20 are being
run on Node.js 24 by GitHub.

## [2026-06-24] validation | Full-session dry run passed

Post-merge GitHub Actions validation passed for `New York Bill Tracker` mode
`dry-run`, session year `2025`, no `max_pages` cap. Run `28136128891` completed
in 1m 56s with 25,314 records written from 25,314 bills seen. Health status was
`WARN` only for the expected `UNKNOWN_STRUCTURAL_OUTCOME` source-contract bucket
(24,326 / 25,314); malformed bills, unknown chamber values, missing action text,
and missing source URLs were all zero.

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
