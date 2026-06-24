---
tags: [ny, failures, assumptions]
updated: 2026-06-24
status: active
---

# New York Assumptions Register

Append-only ledger for New York assumptions, surprises, and fixes. This mirrors
the role of [[failures/assumptions_audit]] but stays NY-local while the state
adapter is young.

## 1. OpenLeg bill data is strong; meeting/calendar parity is not yet proven

**Assumption:** because OpenLeg bill records contain `committeeAgendas`,
`calendars`, and committee fields, the Virginia calendar engine can be source-
swapped directly.

**Reality:** official docs identify Senate calendar/agenda/committee APIs, and
the calendar/committee docs explicitly warn that Assembly calendar/committee
data is not currently sent to OpenLeg.

**Decision:** build the bill-record engine first. Keep `upcoming` empty and
surface a `calendar_scope_note` until both-chamber meeting coverage is validated.

**Guard:** [[ny/workflow/source_scoping_protocol]] requires a source contract and
dry-run proof before a long-term NY calendar worker is built.
