---
tags: [ideas, organization, multi-state, structure, refactor, plan]
updated: 2026-06-25
status: plan
---

# Multi-State Organization & Structure — clean-up plan (before 50 states)

Owner ask (2026-06-25): *"as we move to multiple states we need clean organization — consistent sheet
namings, folders, github cleaning — so when we have 50 states we know exactly where to find everything."*
Right call, and the right time (2 states in). This is the plan. **Sequencing: do the low-risk cleanup
anytime; do the code restructure as a dedicated PR AFTER the VA front end is finished, BEFORE heavy NY.**

## Where we are now (the audit)
- **Root code is flat + mixed:** active VA (`bill_tracker.py`, `calendar_worker.py`, `structural_router.py`,
  `calendar_xray.py`, `test_auto_calender.py`), **dead VA legacy** (`app.py` 46 KB, `shadow_v2.py` 54 KB,
  `backend_worker.py`, `backend_worker_3col_backup.py`, `xray.py`, `Test_api_2.py` — documented dead in
  [[failures/legacy_calendar_versions]]), NY (`ny_bill_tracker.py`, `ny_calendar_probe.py`), and ~12
  `test_*.py` — all at repo root.
- **Workflows flat (25+):** NY uses an `ny_*` prefix; VA workflows have **no `va_*` prefix** (inconsistent).
- **Sheets:** ✅ NY is properly **isolated in a separate workbook** (`NY_SPREADSHEET_ID`, refuses to write
  without it). ⚠️ but **tab names are inconsistent**: VA's bill tab is `Bill_Tracker`, NY's is
  `NY_Bill_Tracker`. Since each state has its own workbook, the per-state prefix on the TAB is redundant and
  forces the front end to special-case names.
- **Branches:** ~40 stale `claude/*` branches (mostly merged VA PRs) + the active `codex/ny-*`. Clutter.
- **Brain:** ✅ good split already — `docs/` (shared + VA) and `docs/ny/` (full parallel NY brain). But
  `docs/` mixes *shared-engine* knowledge with *VA-specific* knowledge with no marker.

## The target structure
### 1. Code — shared `core/` + per-state `states/<code>/`
```
core/        # state-AGNOSTIC engine: structural_router, the reconciliation framework, the calendar
             # time-resolution machinery, the trust/completeness primitives, shared GViz/Sheets IO
states/
  va/        # calendar_worker.py, bill_tracker.py, calendar_xray.py, investigation_config.py, va tests
  ny/        # ny_bill_tracker.py, ny_calendar_probe.py, ny tests
web/         # the front end (multi-state aware; per-state config — see §6)
legacy/      # app.py, shadow_v2.py, backend_worker*.py, xray.py, Test_api_2.py (or DELETE — they're dead)
tools/       # (already organized) verification, reconciliation, session_archive, …
```
The reusable VA engine (refid-namespace, meeting/admin router, convene-time graph) lifts into `core/`; each
state's `states/<code>/` declares its **source manifest** (see [[ideas/multi_state_data_strategy]] §4-A) and
calls `core`. **This is the big refactor** — touches imports + the Streamlit serving paths (`pages/`, the
`pages/ray2.py` ≡ `calendar_xray.py` diff-identical pair) + every workflow's entrypoint. Do it as ONE
focused PR with the full test suite green, AFTER VA is finished. Until then, the `ny_*` prefix is the interim.

### 2. Google Sheets — one convention, per state
- **One workbook per state** (already true for NY): `"<State> Mastermind DB"` + `"<State> Mastermind Archive"`.
- **Identical TAB names across states** so the front end only needs the per-state *workbook ID*, never
  different tab names: calendar = `Sheet1` (or rename to `Calendar` everywhere), bills = `Bill_Tracker`,
  metrics rows, `API_Cache`, etc. **→ rename NY's `NY_Bill_Tracker` tab → `Bill_Tracker`** (in its own
  workbook) for consistency. (Low effort; do before the front end goes multi-state.)
- A documented **registry**: state code → workbook ID → tab names, in one place the front end + workers read.

### 3. Workflows — `<state>_<job>.yml`
Adopt `va_calendar_worker.yml`, `va_bill_tracker.yml`, `ny_bill_tracker.yml`, … Shared/ops workflows
(sentinels, audits) stay unprefixed or `ops_*`. (Renaming VA workflows is churn — schedules live on the
default branch — so do it in the restructure PR, not piecemeal.)

### 4. Branches — prune + convention
- **Delete merged branches** (~40 `claude/pr-c*` etc. are long-merged). One-time cleanup.
- Convention going forward: `<state>/<feature>` (or keep the agent prefix: `claude/<state>-<feature>`,
  `codex/<state>-<feature>`) so it's obvious which state + who.

### 5. Brain — mark shared vs per-state
- Keep `docs/` as the shared + VA origin brain; `docs/<state>/` per state (the NY pattern is the template).
- Tag each `docs/` page **`scope: shared`** (engine/standards/workflow that ports to every state) vs
  **`scope: va`** (VA-specific). When state #3 arrives, the `shared` pages are the reuse manifest. (Cheap:
  a frontmatter tag, no file moves yet.) The cross-state strategy ([[ideas/multi_state_data_strategy]]) and
  this page are `shared`.

### 6. Front end — per-state config + a state switch
`web/src/config.ts` becomes a **per-state registry** (state → spreadsheet ID + tab names + crossover date +
session code). A state selector (or subdomain per state) picks the active config. Everything downstream
(gviz URLs, the calendar/health loaders) reads from the active state's config. Plan this when the front end
goes multi-state (after VA finishes).

## Sequencing (owner: finish VA first)
1. **Finish VA front end** (merge #166 + #167; the deferred VA items). ← we are here.
2. **Low-risk cleanup anytime:** delete/`legacy/` the dead files; prune merged branches; add `scope:` tags;
   rename the NY tab → `Bill_Tracker`.
3. **The code restructure PR** (`core/` + `states/`): after #1, before heavy NY. Full test suite green.
4. **Front-end multi-state config** (§6) alongside or just after the restructure.
5. **Then NY expansion** is "relatively easy" (owner) — it's mostly a new `states/ny/` manifest + a workbook,
   on the proven engine.

See also [[ideas/multi_state_data_strategy]], [[failures/legacy_calendar_versions]] (the dead files),
[[architecture/session_archive]] (the archive-workbook pattern), `docs/ny/` (the NY state-brain template).
