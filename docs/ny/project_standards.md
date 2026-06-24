---
tags: [ny, standards]
updated: 2026-06-24
status: active
---

# New York Project Standards

This mirrors the role of root `CLAUDE.md` for New York-specific work. It does
not replace the repo-wide standards; it narrows them for the NY retune.

## Owner goal

Build a New York legislative intelligence engine by reusing the Virginia
product discipline while independently validating New York sources. Do not let
Virginia assumptions harden into New York architecture without proof.

## Non-negotiables

1. **Scope before structure.** Before a long-term worker, tab schema, source
   adapter, or workflow is introduced, write down the source contract, known
   gaps, validation path, and rollback/gating plan.
2. **Source honesty over completeness theater.** A field may be empty if the
   source is not validated. Empty fields must be counted or explained in
   completeness metadata; never silently imply coverage.
3. **Separate until proven common.** Keep NY code and NY brain files separate
   from VA until both state contracts are understood well enough to extract a
   shared abstraction safely.
4. **Runtime inputs are explicit.** NY writes require `NY_SPREADSHEET_ID`; do
   not default into the Virginia workbook by accident. NY source calls require
   `NY_OPENLEG_API_KEY`.
5. **Raw status stays visible but does not classify.** Derived fields such as
   `outcome` and `crossed_over` must come from structural fields. OpenLeg status
   text is kept for display/provenance only. If a structural mapping is not
   proven, write an explicit unresolved value and count it in health metrics.
6. **Exact structural code maps only.** Source-code normalizers must use
   explicit accepted values, not prefix/prose matching. Unknown codes stay
   unknown, preserve raw provenance where useful, and increment health counters.
7. **No meeting-calendar claims without both-chamber validation.** OpenLeg's
   Senate agenda/calendar endpoints are useful, but Assembly coverage must be
   independently sourced or validated before the UI claims full NY calendar
   parity.
8. **Tests before promotion.** Fixture tests are acceptable for source-shape
   logic. A live dry run with denominators is required before scheduling or
   writing to a production tab.

## Current implementation standard

`ny_bill_tracker.py` is allowed to be a separate, simple engine while the
source contract is young. Do not prematurely abstract it into `bill_tracker.py`.
The first shared abstraction should be extracted only after a full NY dry run
shows which fields truly map cleanly across states.

## Required user inputs before a live write

- `NY_OPENLEG_API_KEY` from New York OpenLegislation.
- `NY_SPREADSHEET_ID` for the New York output workbook.
- Confirmation whether NY should live in a separate workbook or in a clearly
  prefixed tab family in the existing workbook.

## Pre-build checklist

Before adding a new NY data path:

- Which official source is being used?
- Which fields are structural and which are display text?
- Which classifications are structural-only, and which are still unresolved?
- What is the denominator for the completeness claim?
- What happens when the source is missing, partial, or rate-limited?
- Which fixture test proves the flattener?
- Which live dry-run metric proves the source at session scale?
