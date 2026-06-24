---
tags: [ny, workflow, scoping]
updated: 2026-06-24
status: active
---

# New York Source Scoping Protocol

This is the New York rule the owner asked for: scope, plan, and test before
committing to a long-term build route.

## Phase 0 - State the question

Write the exact claim before building:

- "OpenLeg can provide all NY bills for session 2025."
- "OpenLeg can provide both-chamber meeting times."
- "OpenLeg action history can replace Virginia HISTORY.CSV."

The narrower the claim, the easier it is to prove or reject.

## Phase 1 - Source contract

For each source, record:

- Official URL/doc page.
- Endpoint and required params.
- Auth and rate-limit assumptions.
- Fields used by the engine.
- Known source-side caveats.
- Whether the field is structural data or display text.

Write durable facts to [[knowledge/ny_openleg_api_reference]] and open gaps to
[[ny/ideas/data_inventory]].

## Phase 2 - Small probe

Before a full engine change:

- Fetch one or a few known records if credentials are available.
- Save only aggregated findings in the brain, not secrets or raw private keys.
- Build a fixture based on the observed shape.
- Add a counter for every optional/gap field.

## Phase 3 - Fixture test

Every parser/flattener gets fixture tests before live writing. The first NY
fixture suite is `test_ny_bill_tracker.py`.

## Phase 4 - Full dry run

Run the engine without writing:

`NY_OPENLEG_API_KEY=... NY_OPENLEG_SESSION_YEAR=2025 python3 ny_bill_tracker.py --dry-run`

Record:

- records written / bills seen
- action-history coverage
- sponsor coverage
- vote coverage
- summary coverage
- outcome-source distribution
- any missing/gap counters

## Phase 5 - Promote carefully

Only after the dry-run metrics are reviewed:

- Write to a confirmed `NY_SPREADSHEET_ID`.
- Keep the workflow manual at first.
- Schedule only after the first successful full write and a cadence decision.

## Phase 6 - Write back

Update [[ny/log]], [[ny/state/current_status]], and whichever source/architecture
page changed. If the source disproves the initial claim, say so plainly and
record the next candidate source.
