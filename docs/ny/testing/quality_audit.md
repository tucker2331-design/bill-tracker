---
tags: [ny, testing, audit, quality]
updated: 2026-06-25
status: active
---

# New York Quality Audit

Purpose: keep the New York engine honest at the same standard as Virginia.
This page records what the engine can prove structurally, what it only carries
as display/provenance, what it intentionally leaves unclaimed, and which health
counters make those limits visible.

## Current audit result

Status: pass with explicit source-contract gaps.

The current NY bill engine is suitable for once-daily bill-record refreshes.
It is not yet suitable for full meeting/calendar claims or final terminal
outcome parity in product UI without visible unresolved states.

## Structural indicators

| Claim | Current basis | Audit result |
|---|---|---|
| Bill universe completeness | `/api/3/bills/{sessionYear}` pagination with required `total` and `offsetEnd` metadata | Pass |
| Bill identity | `basePrintNo` / `printNo` plus malformed-ID health counter | Pass |
| Chamber and crossed-over | exact `Senate` / `Assembly` code map from `billType.chamber`, `actions.items[].chamber`, and `pastCommittees[].chamber` | Pass |
| Committee referrals | ordered `pastCommittees`, deduped by normalized or raw chamber plus committee name | Pass |
| Last committee | `status.committeeName`, fallback latest `pastCommittees` | Pass as position/provenance, not calendar timing |
| Latest vote | latest `votes.items[]` by `voteDate`, summarized from vote buckets | Pass as structural tally |
| History | `actions.items[]` sorted by date and sequence number | Pass |
| Source URL | session year and bill print number, with missing-session health counter | Pass |
| Terminal outcome | `signed == true` and present `vetoMessages` only | Partial |
| Upcoming meetings | no validated both-chamber source yet | Explicit gap |

## Display and provenance fields

These fields are useful and retained, but they must not drive durable
classifications:

- `status.statusDesc` / `status.statusType`: display/provenance only.
- `title`: display field.
- `summary`: counted in completeness; not yet a product output column.
- `committeeAgendas`: counted as agenda references only, not promoted into
  meeting rows or `Upcoming` times.

## Time coverage

The current bill sheet does not output a meeting time field. `Upcoming JSON` is
intentionally `[]` for every row until a validated New York meeting source
exists.

Fields that currently carry dates:

- `Last Action`: latest structural action date from OpenLeg action history.
- `History JSON`: action date and sequence provenance.
- `Latest Vote JSON`: latest vote date when OpenLeg provides one.
- `Data As Of`: run timestamp in UTC.
- `R1.checked_at_utc`: run timestamp in the completeness object.

Fields that do not currently carry times, by design:

- `Upcoming JSON`: empty because both-chamber meeting coverage is not validated.
- `committeeAgendas`: kept as references/provenance only. They do not prove a
  scheduled meeting time for the product.
- Administrative or status-position facts such as current committee, raw status,
  sponsor, summary, and outcome do not inherently need a clock time. They need
  source provenance and freshness, which are supplied by `Data As Of` and `R1`.

Audit rule: an empty `Upcoming JSON` value means "calendar source not claimed,"
not "there are no upcoming events." Any future UI must preserve that distinction
until the calendar worker has its own source contract and live validation.

## Health coverage

Current run-level health and completeness include:

- `records_written` and `bills_seen`
- `has_actions_rate`
- `has_votes_rate`
- `patron_present_rate`
- `summary_present_rate`
- `committee_agenda_refs`
- `outcome_sources`
- `unknown_structural_outcome`
- `unknown_structural_outcome_rate`
- `unknown_chamber_value`
- `skipped_malformed_bill`
- `missing_action_text`
- `source_url_missing_session`
- `calendar_scope_note`
- `health.status`
- `health.findings`

Current production health status is `WARN` because many bills remain
`unknown_structural` for terminal outcome. That warning is expected and useful;
it should not be suppressed until a structural terminal-outcome mapping is
validated or the product accepts an explicit unresolved terminal-state model.

## Artifact integrity

Write mode now verifies the actual Google Sheet after writing:

- header row matches the writer contract
- `R1` completeness JSON parses and matches the run
- `R1.health.status` matches the run
- active bill IDs in column A match the built payload
- the bounded tail below the active payload has no stale cells

This protects against partial writes, stale rows, and completeness metadata
that does not match the visible sheet.

Workflow-level production guardrails:

- scheduled and manual production writes are restricted to `refs/heads/main`
- manual `check-config` and `dry-run` modes can run from branches without
  acquiring the production write concurrency group
- scheduled writes and manual writes serialize with each other so two
  production writes cannot race the same tab

## Open audit items

1. Terminal outcome parity: find a durable structural OpenLeg field or keep the
   unresolved product state explicit.
2. Calendar/time parity: validate the staged source plan in
   [[ny/architecture/calendar_source_options]] before writing any NY calendar
   worker or non-empty `Upcoming` values.
3. Session rollover: the daily workflow currently defaults to session year
   `2025`. Build an explicit rollover strategy before the next NY session.
4. Cadence/rate limits: daily full-session refresh is acceptable based on
   observed run time and owner approval; revisit OpenLeg rate expectations
   before increasing frequency.
5. Official action maintenance: GitHub has warned that the pinned official
   actions are being run on a newer Node runtime. Track separately from engine
   correctness and update pinned SHAs under review.
