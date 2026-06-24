---
tags: [ny, meta, start-here]
updated: 2026-06-24
status: active
---

# New York Brain - Start Here

This is the primary entry point for New York work. Read this before changing
New York code or making claims about New York sources.

The New York system is a sibling to Virginia, not a blind clone. It should reuse
the product discipline, testing discipline, and source-honesty standards from
Virginia while keeping New York facts, source contracts, assumptions, and logs
separate until we intentionally generalize them.

## Read order for NY work

1. [[ny/README]] - this page.
2. [[ny/project_standards]] - New York-specific operating standards.
3. [[ny/index]] - catalog of the NY brain.
4. [[ny/state/current_status]] - active NY build state.
5. The relevant task page:
   - API/source work: [[knowledge/ny_openleg_api_reference]] and [[ny/ideas/data_inventory]]
   - Architecture work: [[ny/architecture/bill_pipeline]]
   - Planning/scoping: [[ny/workflow/source_scoping_protocol]]
   - Testing/validation: [[ny/testing/validation_plan]]
   - Failures/lessons: [[ny/failures/assumptions_register]]
   - Owner inputs: [[ny/workflow/owner_setup]]

## Current boundary

The first New York implementation is a bill-record engine:

- Code: `ny_bill_tracker.py`
- Tests: `test_ny_bill_tracker.py`
- Output tab default: `NY_Bill_Tracker`
- Required source key: `NY_OPENLEG_API_KEY`
- Required write target: `NY_SPREADSHEET_ID`

It does not yet claim complete meeting/calendar parity. That is a scoped next
phase, not a hidden TODO.

## Write-back rule

Every NY finding lands in the NY branch of the brain first:

| Artifact | NY location |
|---|---|
| API quirk/source fact | [[knowledge/ny_openleg_api_reference]] |
| Architecture decision | [[ny/architecture/bill_pipeline]] |
| Source uncertainty or data gap | [[ny/ideas/data_inventory]] |
| Test result/validation metric | [[ny/testing/validation_plan]] |
| Broken assumption/fix lesson | [[ny/failures/assumptions_register]] |
| Session event/decision | [[ny/log]] |
| Active focus change | [[ny/state/current_status]] |

If a lesson is clearly multi-state, link it back into the main VA/general docs
after recording the NY-local fact.
