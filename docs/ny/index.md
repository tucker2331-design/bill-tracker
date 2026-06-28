---
tags: [ny, index, meta]
updated: 2026-06-25
status: active
---

# New York Brain - Index

This is the New York section of the same project brain. It is intentionally
separate from the Virginia pages for clarity while the NY engine is being
retuned. The files here may duplicate the Virginia structure on purpose; merge
or generalize only after both systems are stable enough to compare cleanly.

## State

- [[ny/state/current_status]] - active New York build status and immediate next steps

## Standards / Start

- [[ny/README]] - read this first for New York work
- [[ny/project_standards]] - New York-specific standards mirroring the role of root `CLAUDE.md`

## Architecture

- [[ny/architecture/bill_pipeline]] - OpenLeg bill engine data flow and output contract
- [[ny/architecture/calendar_source_options]] - source options and recommended phased architecture for a New York calendar spine

## Workflow

- [[ny/workflow/source_scoping_protocol]] - scope, plan, test, then promote
- [[ny/workflow/owner_setup]] - owner setup checklist for API key, sheet, and secrets

## Testing / Failures

- [[ny/testing/validation_plan]] - fixture, dry-run, live-write validation gates
- [[ny/testing/quality_audit]] - structural indicators, time coverage, health counters, and open quality items
- [[ny/failures/assumptions_register]] - NY-local assumption and failure ledger
- [[ny/log]] - NY-local chronological log

## Ideas / Inventory

- [[ny/ideas/data_inventory]] - New York source inventory and known gaps

## Knowledge

- [[knowledge/ny_openleg_api_reference]] - raw OpenLeg endpoint map and engine env contract

## Current implementation

- `ny_bill_tracker.py` - first New York bill engine, separate from `bill_tracker.py`
- `test_ny_bill_tracker.py` - fixture-based unit smoke tests for the New York flattener
- `ny_calendar_probe.py` - read-only calendar source probe; no sheet writes and no `Upcoming JSON` promotion
- `test_ny_calendar_probe.py` - fixture-based tests for NY calendar source parsing and audit counters
