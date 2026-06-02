---
tags: [state, live]
updated: 2026-06-02
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Full 2026 VA GA session (2026-01-14 → 2026-05-01). **VA GA is now ADJOURNED — HISTORY is static (no new actions until the 2027 session). Pre-launch: lobbyists are not using the product yet.**

## Active focus

**⚠️ SECTION 9 NOT YET CLOSED — earlier "closed" claim was FALSE (corrected 2026-06-02 by live verification).** PR #57 + #58 merged, but a post-merge cross-tab against live Sheet1 showed the count went **UP** (1,010 → 1,072), not down. Root cause: the `LegEvent_Events` cache tab is undersized 3.4× and silently truncates — only 1,063 of 3,645 bills (HB1..HB577) have cached events; the rest route blank, so both PRs are no-ops on the flagged set (`legevent_floor_recovered=0`). Full measurement + framework lesson in [[failures/assumptions_audit#62]]. **The fix is PR #61 (PR-C7.1e) — in flight.** The architecture is sound; the cache just couldn't hold the data.

**What's actually deployed (correct, but starved by the cache bug):**
- **PR #55** — PR-C7.1b-1: structural router backend. Worker writes `LegEventRoute` from LIS's own `ReferenceType`/`VoteTally`/`Status` (dictionary-free; 52-status drift check). Validated *offline* by `full_validate.py` (fresh fetch) at 943-admin / 103-meeting / 3-no_event — but that tool never exercised the truncated production cache (the trap in #62).
- **PR #57** (`486faa2`) — X-Ray `classify_action(outcome_text, legevent_route="")` reads route first, text fallback. **Correct code, but blank routes (from the starved cache) make it fall through to text → no collapse in production yet.**
- **PR #58** (`07c4a17`) — worker floor_miss → LegEvent recovery via `_find_legevent_time_in_cache`, gated `route=="meeting"`. **Correct code, but the gate never fires because routes are blank → `legevent_floor_recovered=0`.** (Also fixed a real pre-existing journal_default regression — that fix stands.)

**The actual path to closing Section 9:**
1. **Merge PR #61 (PR-C7.1e cache capacity fix)** — events tab 25k→120k + dynamic grow-or-alert. Unblocks everything.
2. **Re-hydrate the cache** — dispatch the worker ~6 cycles, or run the Backfill Burst (PR #56) once, so all 3,645 bills get cached events persisted.
3. **Re-verify against live Sheet1** (the cross-tab in this session's method, NOT a sidecar tool). Only then is the drop real. Expected: ~1,010 → ~106 (router collapse) → ~3 (floor recovery), but **measure, don't assume** — that's exactly the mistake #62 documents.

**Verification method (use this, not full_validate.py):** fetch live Sheet1 via gviz CSV, run both text-only and route-aware `classify_action` against it, cross-tab text-class × route-value on no-time rows. This exercises the real production artifact (`LegEventRoute` column written by the worker). The worker SYSTEM_METRICS line (`legevent_floor_recovered`, `legevent_route_admin/meeting/blank`) is the second corroborating source.

**Owner guardrails (locked):**
1. No LLM runtime dependency.
2. No OpenStates fallback (regex-on-text brittleness).
3. No hiding rows / no probabilistic guesses — lobbyist surface complete AND structurally correct (Standard #3 sharpened 2026-05-12).
4. Designed for dynamic environment (2027 session, new vocabulary, new clerks) — the structural router consumes LIS's own published vocabulary, so a never-seen value falls through to text + CRITICAL drift alert rather than silent break. Training-free by construction.

## Open PRs

| # | Branch | State | Notes |
|---|--------|-------|-------|
| 61 | `claude/pr-c7-1e-legevent-cache-capacity` | **Open — PR-C7.1e: LegEvent_Events cache capacity fix (THE blocker)** | The reason #57/#58 are no-ops. Events tab 25k→120k rows + `_ensure_row_capacity` (grow-before-write, workbook-cell-budget-guarded, CRITICAL alert on overflow) + one-step lift of the existing 25k tab. 3-branch unit test passing. **Merge → re-hydrate → re-verify = the real Section 9 drop.** See [[failures/assumptions_audit#62]]. |
| 60 | `docs/forward-calendar-design` | **Open — forward-calendar design entry (docs)** | Detailed design for the 2027 upcoming-meetings surface. 4 Gemini findings folded in (datetime/date TypeError, pinned-investigation reproducibility guard, dedup key granularity, viewport-slice disconnect) + corrected the stale "Section 9 closed" premise. Design only; no code. |
| 56 | `claude/legevent-backfill-burst` | **Open — `⏩ LegEvent Backfill Burst` (now USEFUL for PR #61 re-hydration)** | Workflow-only N-cycle burst. Originally parked, but post-#61 it's the fastest way to re-hydrate the cache (run once → all 3,645 bills cached in one dispatch instead of ~6 cron cycles). Bot fold-in pushed: shared `calendar-worker` concurrency group (Codex P1) + state-aware re-enable (Codex P2). |

## Next up (after this session's merges)

1. **Admin-route gating on journal_default fallback resolver** (deferred from PR #58 scope) — when `route == "admin"` on a journal_default row, skip the resolver too (currently it recovers admin rows with 4 AM document times). Small follow-up.
2. **Chronological-replay simulation** — dynamic-readiness validation. Feed HISTORY day-by-day to test incremental arrival / evolving bill state on the frozen 2026 corpus. The one dynamic test possible on static data. See [[ideas/future_improvements]].
3. **Forward-calendar block** — the real dynamic frontier (upcoming meetings before they happen; Schedule API future-window + reconciliation against actual outcomes). Owner-flagged hardest future challenge.
4. **`backend_worker.py` / `v2_shadow_test` rework** to absorb the calendar subsystem's advanced material before subsystem merger.

## Recently closed (highlights — full chronology in [[log]])

- **PR #55** (2026-06-02): PR-C7.1b-1 re-land after #40 recurrence — structural router backend, drift check, additive `LegEventRoute` column. Worker + structural router promoted to repo root.
- **PR #54** (2026-06-01): PR-C7.1b realignment — abandoned EventCode→category dictionary; routed on LIS's own structural fields ([[failures/assumptions_audit#57]] + [[failures/assumptions_audit#58]]).
- **PR #52, #51** (2026-05-31): PR-C7.1d floor-gate diagnosis + structural audit — 1,049 flagged = ~942 false positives + ~100 genuine meetings + 3 no_event ([[failures/assumptions_audit#55]]).
- **PR #50** (2026-05-12): Standard #8 (Zero Routine Human Maintenance) codified in CLAUDE.md ([[workflow/zero_routine_maintenance]], [[failures/assumptions_audit#54]]).
- **PR #46** (2026-05-11): 15-point pre-push audit codified (Points 10-15 added).
- **PR #45** (2026-05-09): PR-C7.0.4 breaker recalibration — `meeting_unsourced_delta` (rolling Y2 baseline) replaces absolute threshold ([[failures/assumptions_audit#53]]).
- **PR #41-44** (2026-05-05 → 2026-05-06): PR-C7 structural pivot + cold-start hotfixes ([[failures/assumptions_audit#50]], [[failures/assumptions_audit#51]], [[failures/assumptions_audit#52]]).

## Known bug count (MEASURED against live Sheet1, 2026-06-02 post-#57/#58)

- **X-Ray Section 9 — route-aware (current production):** **1,072** ❌ (went UP from text-only 1,010 — the cache-starvation regression, not a real increase). This is the honest number until PR #61 lands + cache re-hydrates.
- **X-Ray Section 9 — text-only (pre-#57 baseline):** 1,010.
- **Why up not down:** 1,008/1,010 flagged rows route `blank` (cache has events for only 1,063/3,645 bills); 0 collapsed to admin; the router *added* 62 false-positives (admin rows like "Placed on X Agenda" routing to meeting). Full cross-tab in [[failures/assumptions_audit#62]].
- **Expected after PR #61 + re-hydration:** ~106 (collapse) then ~3 (floor recovery) — **to be re-measured, not assumed.**
- **Worker UNKNOWN_ACTION counter:** 6 (separate path, untouched).
- **Section 7 (Sheet vs LIS time parity):** 0 ✓.
- **Cache coverage (the bug):** 1,063 / 3,645 bills have cached events (29%); `LegEvent_Events` at 24,999/25,000 rows (full). PR #61 fixes the allocation.

## Active architecture

Two parallel Streamlit apps and two scheduled workers. Full description in [[architecture/calendar_pipeline]].

- `backend_worker.py` — main product worker ("Mastermind Ghost Worker") — front-end bill page; needs rework to match calendar_worker's advanced material before any subsystem merger.
- `calendar_worker.py` — calendar subsystem worker ("Mastermind Ghost Worker 2"). PR-C7 cross-cycle persistent LegEvent cache deployed. PR-C7.1b-1 writes `LegEventRoute` + persists 4 structural fields per event. PR #58 (in flight) adds floor_miss → LegEvent time recovery.
- `pages/ray2.py` — X-Ray diagnostic (Streamlit-served). PR #57 (in flight) wires `classify_action()` to consume `LegEventRoute`.
- `calendar_xray.py` — diff-identical backup of `pages/ray2.py`.
- `structural_router.py` — repo root (PR-C7.1b-1). Single source of truth; imported by worker AND validation tools.

## Active diagnostic tooling (read-only, `workflow_dispatch` only)

| Workflow | Purpose | Result |
|---|---|---|
| 🔍 Cell Count Audit (Mastermind DB) | Per-worksheet cell distribution + 10M-cap headroom | API_Cache 92% pre-trim → 29.2% post-trim |
| ✂️ Trim API_Cache Columns | One-shot 26→6 col trim with three-layer safety | One-shot complete (PR-C6.2 cycle) |
| 🩺 Dump Unrecovered Meeting Outcomes | Pre/post-PR-C7 verification | Pre-PR-C7 baseline captured 2026-05-01 |
| 📐 LegEvent Sizing Audit | Cold-start fetch sizing vs LIS WAF budget | 2,002 bills → 4 cycles at 500/cycle (actual: 3,645 / ~8 cycles) |
| ⏩ LegEvent Backfill Burst | One-shot N-cycle cold-start (PR #56, parked) | Not needed for current backfill; reserved for 2027 cold-start |

## Watch items

- **Gemini Code Assist GitHub bot sunset** — VERIFIED on Google's deprecation page: consumer install blocked 2026-06-18, all review activity ceases 2026-07-17. This affects the free `gemini-code-assist[bot]` PR reviewer only. **Codex (`chatgpt-codex-connector`) is unaffected.** Replacement candidates in [[ideas/future_improvements]]: CodeRabbit free OSS tier, Qodo PR-Agent, GitHub Copilot PR review. Decide before mid-July.

## What changes this page

Anything that changes the answer to "what is Tucker working on right now?" — opening/closing a PR, changing the active bug count, shifting the goal, pausing/resuming a thread. The LLM updates this page on every session conclusion. Historical narrative belongs in [[log]] (append-only); active state belongs here (live, pruned).
