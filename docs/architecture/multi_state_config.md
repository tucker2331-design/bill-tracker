---
tags: [architecture, multistate, standard-6, config]
updated: 2026-10-31
status: active
open_loop: The bill pipeline and the SPA are split; the calendar worker (calendar_worker.py, ~8.8k lines) still carries its VA assumptions inline, and the Timeline's two-lane drawing is crossover-shaped (a state with no crossover needs its own drawing before its screens ship).
---

# Multi-state config — every state assumption in one place (Standard #6)

**Built 2026-10-31.** The product's bill path (`bill_tracker.py` → `Bill_Tracker` tab → `web/`) no longer names
Virginia anywhere except its state config. Adding a state = one config module + one registry line on each side.

## The two halves

| | Python (backend) | TypeScript (SPA) |
|---|---|---|
| Contract | `states/base.py` `StateConfig` | `web/src/states/types.ts` `StateConfig` |
| Virginia | `states/va.py` `VA` | `web/src/states/va.ts` `VA` |
| Registry | `states.get_state(code)` — unknown code **raises** (fail closed) | `web/src/states/index.ts` `STATE` |
| Source machinery | `StateConfig.adapter` → `states/va_lis.py` (LIS session discovery, auth gate, guarded blob fetch, committee resolver — shared with the calendar worker) | n/a (the SPA reads the sheet) |

**What the config holds:** code, name, publisher name ("LIS"), timezone, chamber prefix map, the stage list
(VA includes a `crossover` *marker* stage), `session_years` (1 for VA, 2 for PA), the bill-page URL template,
source endpoints by role, the source's own status vocabulary (keyword-fallback outcome), floor-event phrases,
which bill prefixes pass both chambers, and the summary-type rank. SPA-only: product name, legislature name,
crossover dates per session, the bill-id pattern.

**What it deliberately does NOT hold:** anything the source can tell us at runtime — the session code, the
committee list, the members (Standard #5). The config names *where to ask*, never the answer.

**Selection:** backend `BILL_STATE` env (default `VA`); SPA `STATE` in `web/src/states/index.ts` (one line —
becomes a profile lookup when a deployment serves more than one state).

## Proof of no behaviour change (VA)

- `test_state_va_goldens.py` runs the REAL `build_bill_records` on the cached 2026 LIS blobs
  (`tools/historical_cache/va/20261/`: HISTORY, DOCKET, Sponsors — 3,645 bills) and compares a SHA-256 of every
  record + the completeness payload + every URL requested against `goldens/va_bill_records_20261.json`, captured
  from the code **before** the split. Universe + BILLS.CSV are not cached for 20261, so they are synthesized
  deterministically from the real HISTORY rows; the golden checks that OUTPUT did not move, not LIS facts.
- `web/src/states/__tests__/va.regression.mjs` (39 checks): every former SPA literal reproduced exactly; the
  chamber-of-a-bill rule matches each caller's old inline code on odd inputs (`""`, `X1`, lower case — the old
  callers disagreed on the default, and each keeps its own); the bill-id regex matches the old one.
- `test_states.py`: registry fails closed; the Python and TS configs agree on code, publisher, stage ids, link.

## Pennsylvania (added 2026-10-31)
`states/pa.py` (config: two-year session, no crossover, concurrence stage, adopted for resolutions),
`states/pa_adapter.py` (export + schedule RSS → the same bill contract + `stage`), `states/pa_fetch.py` (bulk feeds
only, hourly cap, honest UA, stop on 403). PA does NOT use `bill_tracker.py`'s LIS-shaped pipeline — its source
contract differs. Source facts: [[knowledge/pa_bill_history_xml]]. Scheduled job, sheet tab and screens come later.

## Not split yet (the open loop)

- **`calendar_worker.py`** — the calendar subsystem merges into the product only at 100% accuracy; its VA
  logic (refid shapes, Schedule API, agenda PDFs) is inline. Split it when the calendar↔product merge happens,
  with the same golden-first method (capture, move, prove identical).
- **The Timeline drawing** (`web/src/views/Timeline.tsx`) is two lanes that swap at crossover. A state with no
  crossover (PA) needs its own drawing; `STATE.stages` already says whether a crossover exists.
- **The `Bill_Tracker` column header "Status (LIS)"** is a sheet contract; renaming it is a coordinated
  backend+SPA migration, not part of a no-behaviour-change split.
- Found while building the goldens (not caused by the split): DOCKET.CSV's `Bill_no` column was never matched,
  so `upcoming` was always empty — FIXED right after the split ([[failures/assumptions_audit]] #152); the golden was
  re-captured then, and the only change is `upcoming` + four docket counters.

See also [[audits/fable_2026-07/50_state_scaling_architecture]], [[audits/fable_2026-07/multistate_ingestion_pa]].
