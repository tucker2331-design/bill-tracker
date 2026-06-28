---
tags: [ny, architecture, calendar, sources]
updated: 2026-06-25
status: active
---

# New York Calendar Source Options

Purpose: scope the safest way to rebuild the Virginia-style calendar for New
York without pretending that New York publishes the same source shape Virginia
does. This is a source-options and architecture page, not a production build
commitment.

The best path is a New York calendar spine with source tiers. Senate calendar
data starts with OpenLeg because it exposes structured agenda and Senate
calendar APIs. Assembly calendar data needs a separate official-source path
because OpenLeg documents that Assembly calendar and committee data are not
currently sent to OpenLeg.

## VA parity target

Virginia's iconic calendar is valuable because it is not just a list of dates.
It carries:

- source provenance per row
- exact time vs fallback time vs explicit no-time reason
- source-miss counters
- health rows and breaker behavior
- reconciliation against independent official artifacts
- visible diagnostic origins rather than silent blanks

New York should mirror those guarantees, not Virginia's exact source plumbing.

## Recommended source tiers

| Tier | Source | Use | Initial confidence |
|---|---|---|---|
| 1 | OpenLeg committee agenda APIs | Senate committee meetings, agenda/bill linkage, meeting time windows | High for Senate |
| 1 | OpenLeg Senate calendar APIs | Senate floor calendar, active lists, bill calendar references | High for Senate floor list; time needs a session/convene source |
| 2 | Assembly official committee agenda pages | Assembly agenda identity, committee, date, relative time labels, bill links | Medium-high after DOM probe |
| 2 | Assembly official floor calendar pages | Assembly calendar numbers, release/update timestamps, bill lists | Medium-high after DOM probe |
| 2 | Assembly official session calendar / iCal / PDF links | Session dates and session-layer events | Medium after probe |
| 3 | Senate public events calendar and iCal/PDF links | Corroboration, public hearings, session calendar witness | Witness first |
| 3 | Assembly hearing pages and hearing calendars | Public hearing layer and witness checks | Witness first |
| 3 | Assembly standing committee schedule PDF | Standing room/day/time anchor only | Low for exact agenda time |
| Reject by default | Unofficial feeds, social posts, generic search snippets, prose-only scraping | Do not use for durable production claims | Rejected |

## Official source notes

OpenLeg documentation says its public service delivers New York Senate and
Assembly legislative information through REST APIs, but the available content
types are not symmetric across chambers.

Key OpenLeg options:

- `GET /api/3/agendas/meetings/{fromDateTime}/{toDateTime}` returns committee
  meetings in a time range, ordered earliest first.
- `GET /api/3/agendas/{year}` lists agenda IDs.
- `GET /api/3/agendas/{year}/{agendaNo}` returns a committee agenda.
- `GET /api/3/agendas/{year}/{agendaNo}/{committeeName}` returns a committee
  inside an agenda.
- Agenda update endpoints can support later incremental refresh.
- Bill responses include `committeeAgendas` and Senate `calendars` references
  that can be joined back to calendar rows.
- Senate calendar responses include calendar date, floor calendar,
  supplemental calendars, active lists, release datetimes, and calendar entries.
- Committee docs include Senate committee `location`, `meetDay`, `meetTime`,
  and `meetAltWeek`, but state that Assembly committee data is not currently
  sent to OpenLeg.

Official Assembly pages found during scoping:

- Committee agenda index: lists current committee agendas and many relative
  timing labels such as `OFF THE FLOOR`.
- Committee agenda detail pages: include committee, chair, date/relative time,
  bill links, and descriptions.
- Floor calendar list: exposes Assembly calendar numbers, dates, release
  timestamps, and update timestamps.
- Floor calendar detail pages: expose calendar number/version, sections, and
  bill lists.
- Legislative session calendar page: exposes session-day calendar links,
  including add-to-calendar options.
- Public hearing pages: expose public hearing calendar and floor-calendar
  links.

Official Senate public pages found during scoping:

- Statewide Senate events calendar with event type filters for event, meeting,
  public hearing, and session.
- Session calendar PDF and add-to-calendar links.
- Public hearing schedule PDF.

## Time policy

Concrete clock times may only come from structured or structurally extracted
official fields.

Allowed concrete-time sources:

- OpenLeg agenda meeting time fields.
- Official calendar/iCal event fields after a probe confirms the feed structure.
- Official hearing calendar fields after parser validation.

Allowed non-clock values:

- `OFF_THE_FLOOR`
- `TBA`
- `NO_CLOCK_SOURCE`
- `SESSION_DATE_ONLY`
- `CALENDAR_RELEASE_ONLY`

Do not convert `OFF THE FLOOR` into a guessed clock time. It is a real
legislative timing state and must remain visible as relative timing. The row can
still sort with a deterministic sentinel, but its `Time` value must not claim an
exact clock.

Assembly standing committee schedule times can be stored as anchors only after
validation. They should not overwrite an agenda row's explicit relative time.
If used, mark the origin as a standing schedule anchor rather than an exact
agenda time.

## Proposed row contract

The NY calendar worker should mirror the VA calendar shape while adding
NY-specific chamber and confidence fields:

| Field | Purpose |
|---|---|
| `Date` | Calendar date from the event source |
| `Time` | Exact clock, relative timing label, or explicit no-time state |
| `SortTime` | Deterministic sorting key, including sentinel values for relative states |
| `Status` | Scheduled, released, updated, held, canceled, or source-gap state |
| `Chamber` | Senate, Assembly, Joint, or Unknown |
| `Committee` | Committee name where applicable |
| `Bill` | Bill print number when linked |
| `Outcome` | Event/outcome label when structurally provided |
| `AgendaOrder` | Position from agenda/calendar source when available |
| `Source` | Official URL or API resource |
| `Origin` | Machine-readable source path |
| `DiagnosticHint` | Short reason for fallback, conflict, or limitation |
| `Confidence` | `canonical`, `official_dom`, `witness`, `anchor`, or `gap` |

Candidate origins:

- `ny_openleg_senate_agenda`
- `ny_openleg_senate_calendar`
- `ny_assembly_agenda_dom`
- `ny_assembly_floor_calendar_dom`
- `ny_assembly_session_calendar`
- `ny_assembly_standing_schedule_anchor`
- `ny_senate_events_witness`
- `ny_public_hearing_calendar`
- `ny_no_clock_relative`
- `ny_calendar_scope_gap`

Metrics are not a row origin. Do not serialize final health metrics into an
early-constructed `system_metrics` row in the main calendar table; that pattern
can go stale as later pipeline steps add, drop, or reconcile rows. Keep run
metrics in the final completeness/health object or a dedicated audit artifact
that is computed after row assembly is complete.

## Health counters

The calendar worker should not ship without a visible health surface at least
as strong as the current NY bill engine.

Required counters:

- source fetch count and source fetch failure count by source
- rows produced by source and chamber
- exact-clock rows
- relative-time rows
- no-time rows with explicit reason
- terminal or timeless-by-design rows with explicit origin bucket
- rows with source URL
- agenda/calendar bill-link count
- bill-link join misses against the bill universe
- unknown chamber values
- unknown committee names
- duplicate event collision count
- conflicting time count
- stale source age
- source update timestamp coverage
- Assembly OpenLeg scope gap count
- public witness mismatch count
- breaker status and reason

The completeness object should distinguish "calendar source not claimed" from
"no events found." A blank or empty result set is not safe unless the source
coverage denominator was known and the fetch/parser health passed.

Denominator rule: every produced row must land in exactly one time bucket:
`exact_clock`, `relative_time`, `no_clock_source`, `terminal_or_timeless`, or
`source_gap`. Administrative, executive, session-date-only, and other
timeless-by-design rows are not denominator leftovers; they need explicit
origin buckets so health math does not produce false drift warnings.

## Source-probe plan

Before production code, run a source probe over at least one active legislative
week and one quiet week.

Probe questions:

1. Does OpenLeg agenda meeting range return Senate meeting times with stable
   agenda IDs and committee names?
2. Do OpenLeg agenda details join cleanly to existing bill `committeeAgendas`
   references?
3. Do OpenLeg Senate calendars join cleanly to existing bill `calendars`
   references?
4. Do Assembly agenda index/detail pages expose stable links, query params, and
   bill links that can be parsed through DOM structure?
5. Do Assembly floor calendar list/detail pages expose stable calendar numbers,
   versions, sections, and bill lists?
6. Are Assembly session calendar add-to-calendar links durable enough to parse
   structurally?
7. Can public hearing pages/PDFs serve as witness sources without becoming the
   main bill-calendar truth?
8. Where exact times are missing, is the reason structural (`OFF THE FLOOR`,
   `TBA`, session date only) or a source failure?

Probe output should be a JSON artifact or `NY_Calendar_Source_Audit` tab with
counts and examples. It should not write product `Upcoming JSON` until the
health counters prove source coverage.

## Build sequence

1. Build `ny_calendar_probe.py` as read-only source audit tooling.
2. Promote Senate OpenLeg agenda meetings and Senate calendars into a
   high-confidence calendar layer.
3. Add Assembly agenda and floor calendar official-DOM extraction after the
   probe proves stable structure.
4. Add session calendar and public hearing witness sources.
5. Add reconciliation between bill references, agenda/calendar rows, and witness
   sources.
6. Only then write non-empty `Upcoming JSON` values in `NY_Bill_Tracker`.

## Rejected shortcuts

- Do not use OpenLeg alone for a both-chamber calendar claim.
- Do not infer times from bill action text or status text.
- Do not scrape prose with regex and call it durable.
- Do not treat `OFF THE FLOOR` as missing data.
- Do not suppress Assembly calendar gaps behind empty arrays.
- Do not ship a UI calendar before the source health surface is visible.

## Source links

- OpenLeg docs: https://legislation.nysenate.gov/static/docs/html/index.html
- OpenLeg agendas: https://legislation.nysenate.gov/static/docs/html/agendas.html
- OpenLeg calendars: https://legislation.nysenate.gov/static/docs/html/calendars.html
- OpenLeg bills: https://legislation.nysenate.gov/static/docs/html/bills.html
- OpenLeg committees: https://legislation.nysenate.gov/static/docs/html/committees.html
- Assembly committee agendas: https://nyassembly.gov/leg/?sh=agen
- Assembly floor calendars: https://nyassembly.gov/leg/?sh=sked
- Assembly legislative calendar: https://nyassembly.gov/leg/calendar/
- Assembly public hearings: https://nyassembly.gov/av/hearings/
- Senate events calendar: https://www.nysenate.gov/events
