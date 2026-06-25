---
tags: [ny, ideas, data-inventory]
updated: 2026-06-25
status: active
---

# New York Data Inventory

## First-pass sources

| Need | OpenLeg source | Status |
|---|---|---|
| Bill universe | `/api/3/bills/{sessionYear}` | Built in `ny_bill_tracker.py` |
| Title | bill `title` | Built |
| Raw status | `status.statusDesc` / `status.statusType` | Built |
| Structural outcome | `signed`, `vetoMessages` | Partial; unresolved bills are `unknown_structural` and counted |
| Sponsor | `sponsor.member` | Built |
| Summary | `summary` | Counted in completeness; not yet written as its own UI column |
| History | `actions.items[]` | Built |
| Latest vote | `votes.items[]` | Built |
| Committee position | `status.committeeName` + `pastCommittees` | Built |
| Product chamber | `billType.chamber`, `actions.items[].chamber`, `pastCommittees[].chamber` | Built; Assembly maps to product House and NY-native values are preserved |
| Agenda references | `committeeAgendas` | Counted as provenance |
| Senate committee agenda meetings | `/api/3/agendas/meetings/{fromDateTime}/{toDateTime}` plus agenda details | Scoped as first calendar spine source; not built |
| Senate floor calendars | `/api/3/calendars/...` plus bill `calendars` refs | Scoped as floor-list source; time needs a session/convene source |
| Assembly committee agendas | Official Assembly agenda index/detail pages | Scoped for DOM-structured official-source probe; not built |
| Assembly floor calendars | Official Assembly floor calendar list/detail pages | Scoped for DOM-structured official-source probe; not built |
| Full meeting calendar | mixed source spine | Not built; see [[ny/architecture/calendar_source_options]] |
| Incremental updates | `/api/3/bills/updates/...`, `/api/3/updates/...` | Planned after full-universe validation |

Raw status is display/provenance text only. It must not be used to convert
`unknown_structural` into signed, dead, pending, governor, crossed-over, or
other product classifications.

## Calendar / meeting gap

The docs for `calendars` say Assembly calendar data is not currently sent to
OpenLeg. The docs for `committees` similarly say Assembly committee data is not
currently sent and the chamber must be Senate. This means New York's bill engine
can be useful before the calendar engine, but the calendar cannot simply copy
Virginia's source assumptions.

Current scoping result: build a NY-specific calendar spine. Senate should start
with OpenLeg agenda meeting and Senate calendar endpoints. Assembly should start
with official Assembly agenda/floor calendar pages using structural DOM/link
extraction, not prose parsing. Public hearing calendars, session calendar PDFs,
and standing committee schedule PDFs are witness or anchor sources until a
probe proves they are stable enough for production claims.

## Decisions to make

1. Workbook strategy: separate New York workbook for now, via `NY_SPREADSHEET_ID`.
2. Should summary be added to the shared product tab schema now, or wait until the UI is ready?
3. Which Assembly exact-time source, if any, survives the source probe?
4. Run cadence: once daily for now; revisit after frontend and incremental-update scoping.
