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

## 2. Crossed-over must use action chamber, not status text

**Assumption:** controlled OpenLeg status and milestone strings could safely
indicate whether a bill had crossed chambers.

**Reality:** even controlled status strings are still text for this purpose.
Gemini review on PR #168 correctly flagged that `crossed_over` should use the
structural `chamber` field from action history instead.

**Fix:** `_derive_position()` now receives normalized action history and sets
`crossed_over` from whether any action chamber differs from the bill's origin
chamber.

**Guard:** `test_bill_to_record_flattens_openleg_shape` now includes an Assembly
action in the fixture so the structural crossed-over path is tested.

## 3. Outcome must not be inferred from status text

**Assumption:** controlled OpenLeg `statusType` / `statusDesc` strings could be
used as a temporary terminal outcome fallback.

**Reality:** even controlled status strings are display/provenance text for this
engine. Using them to infer signed, dead, governor, or veto outcomes would hide
source-contract gaps and invite long-term drift.

**Fix:** `_derive_outcome()` now uses only structural `signed` and
`vetoMessages`. Anything else becomes `unknown_structural`.

**Guard:** completeness JSON includes `unknown_structural_outcome`,
`unknown_structural_outcome_rate`, and a `health` warning until terminal outcome
coverage is structurally validated.
