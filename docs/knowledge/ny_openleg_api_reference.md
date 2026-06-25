---
tags: [knowledge, ny, api, openleg]
updated: 2026-06-25
status: active
---

# New York OpenLegislation API Reference

New York brain home: [[ny/index]].

Source of truth: the official Open Legislation docs at
<https://legislation.nysenate.gov/static/docs/html/index.html>.

## API shape

- Base host: `legislation.nysenate.gov`
- API version used by docs: `/api/3`
- Auth: a free OpenLeg API key is required and is sent as the `key` query parameter.
- Session year: New York legislative sessions are two-year sessions named by the odd-numbered first year (for example, `2025` for the 2025-2026 session).

## Bill source

Primary endpoint for the New York bill engine:

`GET /api/3/bills/{sessionYear}?limit=1000&offset=1&full=true&key=...`

The bill response includes:

- `basePrintNo`, `printNo`, `session`, `billType`
- `title`, `summary`
- `sponsor.member`
- `status` (`statusType`, `statusDesc`, `actionDate`, `committeeName`, `billCalNo`)
- `milestones`
- `actions.items[]` (`date`, `chamber`, `sequenceNo`, `text`)
- `votes.items[]` (`voteType`, `voteDate`, `committee`, `memberVotes`)
- `pastCommittees`
- `committeeAgendas`
- `signed`, `vetoMessages`, `approvalMessage`

The first NY engine lives in `ny_bill_tracker.py` and writes the same product row shape as the Virginia `Bill_Tracker` tab, defaulting to a separate `NY_Bill_Tracker` tab.

## Calendar / agenda caveat

OpenLeg's docs state that Assembly calendar data is not currently sent to OpenLeg, and the committee docs likewise say Assembly committee data is not currently sent and `chamber` must be `senate`.

Available Senate-centered endpoints:

- `GET /api/3/calendars/{year}/{calendarNumber}`
- `GET /api/3/calendars/{year}`
- `GET /api/3/agendas/{year}/{agendaNo}`
- `GET /api/3/agendas/{year}`
- `GET /api/3/agendas/meetings/{fromDateTime}/{toDateTime}`
- `GET /api/3/committees/{session}/senate`

`fromDateTime` and `toDateTime` are date-time path parameters. Keep this
placeholder spelling in NY docs so future probe code has one canonical endpoint
shape to implement.

Implication: New York's first product backend must not claim full state meeting coverage from these sources alone. `ny_bill_tracker.py` keeps bill-level `committeeAgendas` as provenance, but leaves `upcoming` empty until a meeting-source pass can be validated.

## Update feeds

OpenLeg exposes bill-specific and aggregate update APIs:

- `GET /api/3/bills/updates/{fromDateTime}/{toDateTime}`
- `GET /api/3/bills/{sessionYear}/{printNo}/updates`
- `GET /api/3/updates/{fromDateTime}/{toDateTime}`

Use these for a future incremental NY engine. The first pass is a full bill-universe build because it establishes the schema and completeness counters.

## Engine contract

Environment:

- `NY_OPENLEG_API_KEY` required.
- `NY_OPENLEG_SESSION_YEAR` optional, default `2025`.
- `NY_OPENLEG_LIMIT` optional, default `1000`.
- `NY_OPENLEG_MAX_PAGES` optional local/testing cap.
- `NY_BILL_TRACKER_TAB` optional, default `NY_Bill_Tracker`.

Trust counters written to `R1`:

- `records_written` / `bills_seen`
- `has_actions` and `has_actions_rate`
- `patron_present` / `patron_missing`
- `summary_present`
- `committee_agenda_refs`
- `outcome_sources`
- `unknown_structural_outcome` and `unknown_structural_outcome_rate`
- `unknown_chamber_value`
- `missing_action_text`
- `source_url_missing_session`
- `health.status` and `health.findings`
- `calendar_scope_note`

Outcome mapping is structural-only in the first engine: `signed == true` maps to
`signed`, present `vetoMessages` maps to `vetoed`, and everything else remains
`unknown_structural` until another durable source field is validated. Status
description text is retained on rows but is not used as a classifier.

The shared product `Chamber` column emits `House` / `Senate`; OpenLeg's native
`Assembly` value is preserved in NY-only provenance fields so the existing
product parser and the state-native facts are both explicit.

## Open questions

- Confirm the most complete authoritative source for Assembly committee meeting times. OpenLeg's docs warn that Assembly committee/calendar data is not available through the Senate OpenLeg endpoints.
- Decide whether NY should run as a separate workbook/tab family or a multi-state tab schema once the UI is ready.
- Add an incremental path using OpenLeg update tokens after the full-universe output is validated.
