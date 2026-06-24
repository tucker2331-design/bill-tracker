---
tags: [ny, ideas, data-inventory]
updated: 2026-06-24
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
| Agenda references | `committeeAgendas` | Counted as provenance |
| Full meeting calendar | agendas/calendars/committees | Not built; source coverage needs validation |
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

## Decisions to make

1. Should New York write to the same workbook with `NY_*` tabs, or to a separate workbook?
2. Should summary be added to the shared product tab schema now, or wait until the UI is ready?
3. What source should be used for Assembly meeting times?
4. What run cadence is acceptable under the OpenLeg API key terms once a full-session fetch is measured?
