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

## Pennsylvania site (built 2026-11-01) — a separate site, same code
- **Build-time state:** `VITE_STATE=PA` (`npm run build:pa` → `dist-pa/`); unset = Virginia. No switcher; a screen is
  shown or hidden only by `STATE.features` (PA: Search, bill card, Today's What's new + Tracking, intake Health,
  War Room without predictions and Calendar (2026-11-01); Timeline hidden). PA's Health (`views/HealthIntake.tsx`) shows only PA's own intake checks.
- **Its own Worker:** `wrangler.pa.toml` — name `bill-tracker-pa`, its own D1 (`bill-tracker-pa-db`), its own secrets,
  its own `SPREADSHEET_ID`. Same `worker/index.js`.
- **Its own job:** `pa_bill_tracker.yml` (hourly, weekdays) runs `pa_bill_tracker.py` on the existing fetch rules and
  writes PA's own sheet (`PA_SPREADSHEET_ID`) in Virginia's Bill_Tracker layout (`bill_rows.py`, shared), so the site
  reads PA exactly as it reads VA. It is NOT on Virginia's trust surface (`trust_surface_guard.OTHER_STATE_JOBS`).
- **Proof:** `test_pa_bill_tracker.py` (real sample → fake sheet: same header, widths, AA1 payload, heartbeat),
  `pa.regression.mjs`, `test_states.py` (Python↔SPA agree for PA), CI builds both sites. Virginia: the record golden
  is unchanged and VA's config values are pinned; the VA *bundle bytes* do change (new code ships in it), but each
  build bakes its own state in at compile time (checked: `m="VA"` vs `m="PA"`).
- **Owner steps** (passwords/accounts): see the PR and [[log]] 2026-11-01 — create the PA sheet + share it with the
  service account; `PA_SPREADSHEET_ID` repo secret; `wrangler d1 create`, paste the id into `wrangler.pa.toml`, apply
  migrations; `wrangler secret put` TEAM_EMAILS / GCP_SA_JSON for `bill-tracker-pa`; deploy; add the PA site's
  address to the Google OAuth client's authorised origins.

## PA War Room (built 2026-11-01) — the VA War Room with PA data, no vote predictions
- `features.predictions` (VA on, PA off): the War Room list hides the member bar, its key and the call-based order
  (every group is bill-number order; calls are never fetched); the bill page hides the member calls.
- `features.committeeRoster` (PA on, VA off): the bill page shows the current committee (`lastCommittee`) and its
  members — name, party, district, the source's role — from the `Committee_Roster` tab that `pa_bill_tracker.py` writes
  from PA's committee-assignments + members RSS (`states/pa_roster.py`; join rule in [[knowledge/pa_bill_history_xml]]).
  A broken roster feed never holds back the bills (`roster_status` published, old tab kept); a 403 still stops the run.
- Position and contact log: the same components, PA's own D1 (`bill-tracker-pa-db`), rows keyed `state = 'PA'`.
- A state with no summaries and no per-bill link hides the bill page's "More" box instead of leaving it empty.
- Goldens: `test_pa_roster.py` (real feeds), `roster.regression.mjs`, `pa.regression.mjs`, `test_pa_bill_tracker.py`.

## PA Calendar (built 2026-11-01) — the VA Calendar screen, fed by a small PA job
- `states/pa_calendar.py`, called by `pa_bill_tracker.py` (no split of `calendar_worker.py`), writes PA's `Sheet1` in the
  calendar subsystem's own 17-column layout + the freshness stamp at AA1, so `web/src/data/calendar.ts` reads it unchanged.
- **Committee meetings** from the schedule RSS (the intake's parse is reused — no new request). Bills come only from the
  `Bills` field; a meeting with none is written once with `DiagnosticHint=no_bills_listed`, and the card says
  "<source> lists no bills for this meeting (yet)" — on both sites (owner rule: never an unexplained empty card).
  Committee names via the roster key (exact); agencies keep their own names. Agency meetings listed in both feeds: once.
- **Session days (past only)** from the export: a (chamber, date) with floor business (`FLOOR_CLASSES`), written as
  "<Chamber> Convened" (the screen's floor marker) with each bill's own `<fullAction>`. Rule 71 / Senate Rule 9 automatic
  tablings are excluded — measured: 13 House "days" had nothing else, one a Sunday. Sample: 214 days (House 119,
  Senate 95). No future session day is invented (none is published; `calendarNote` says so under the Calendar).
- Goldens: `test_pa_calendar.py` (real sample), `agenda.regression.mjs` (now in CI), `pa.regression.mjs`,
  `test_pa_bill_tracker.py`.

## What's new — one line per bill, both sites (built 2026-11-01)
- Form (owner): `SB509 (In the House) Referred to Transportation` — the bill's latest action that day, where it happened,
  sentence case, no date. Full history stays on the bill card.
- **Data: a separate, additive `Action_Where` tab** (`action_where.py`; Bill | Where | Short), one code per history row
  (H / S / G / `-`). Chosen over a new Bill_Tracker field: Virginia's Bill_Tracker stays byte-identical (golden passes
  with the side output on), and the site reads one small tab.
- **Virginia: structural only, so partial.** A code exists only where the row's OWN committee refid names a committee —
  10,011 of 65,414 rows (2026), each agreeing with LIS's own leading chamber letter (10,011/10,011). Carrying the
  committee position forward was measured and REJECTED: wrong on 12,454 of 61,248 rows (enrolment/signing in the
  House after a Senate committee). So most VA lines show no bracket. **Owner decision pending:** LIS prefixes every
  description with a one-letter chamber code ("H "/"S "); if that fixed-position code counts as a field (like the
  "display a field verbatim" ruling in [[log]] 2026-06), VA gets full coverage at 100% agreement.
- **Pennsylvania:** `@actionChamber` (0 unknown) + a short line from verb + committee (roster name) + tally; verbs whose
  number sits in the prose ("Act No.", "Journal Page", "Prior Printer's No.") keep the source line (1,672 rows).
- Display: VA's "H "/"S " code column is removed for display only (`StateConfig.actionCodePrefix`), never read for where.
- Goldens: `test_action_where.py`, `action_where.regression.mjs`.

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
