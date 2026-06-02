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

**⚠️ SECTION 9 NOT YET CLOSED — cache fix MERGED, awaiting re-hydration + re-verification.** PR #57 + #58 merged but were no-ops in production: a live cross-tab showed the count went **UP** (1,010 → 1,072) because the `LegEvent_Events` cache tab was undersized 3.4× and silently truncated — only 1,063 of 3,645 bills (HB1..HB577) had cached events, the rest routed blank. **PR #61 (PR-C7.1e) — the fix — is now MERGED at `b837d17`.** But merging the fix ≠ the drop: the cache must still re-hydrate (the worker grows the tab + persists all bills' events over several cycles, or one Backfill Burst), and **then** a fresh live cross-tab confirms the real numbers. Full measurement + framework lesson in [[failures/assumptions_audit#62]]. The architecture is sound; it just needs the cache full before the routes populate.

**What's deployed now (all merged; correct code, waiting on a full cache):**
- **PR #55** — structural router backend (`LegEventRoute` from LIS's `ReferenceType`/`VoteTally`/`Status`).
- **PR #57** — X-Ray `classify_action` consumes the route (text fallback when blank).
- **PR #58** — worker floor_miss → LegEvent recovery, gated `route=="meeting"` (+ a real journal_default regression fix that stands).
- **PR #61** — cache capacity fix (events tab 25k→120k + dynamic grow-or-alert). **This unblocks the three above** once the cache re-hydrates.
- **PR #62** — cadence 3h + overnight quiet hours (API-ban + runtime); gap thresholds recalibrated for the new cadence.

**The remaining path to closing Section 9:**
1. ✅ ~~Merge PR #61~~ — done (`b837d17`).
2. **Re-hydrate the cache** (owner triggers — involves LIS calls): dispatch the worker several cycles, or run the ⏩ Backfill Burst (PR #56) once (bypasses quiet hours; ~4k LIS calls, paced by the 500/cycle cap → all 3,645 bills cached in one ~30-min run). Watch the worker log: `📈 Grew LegEvent_Events grid …` then `legevent_route_blank` should fall and `legevent_floor_recovered` climb over cycles.
3. **Re-verify against live Sheet1** (this session's cross-tab method, NOT a sidecar tool). Only then is the drop real. Expected ~1,010 → ~106 (router collapse) → ~3 (floor recovery) — **measure, don't assume** (the #62 trap).

**Verification method (use this, not full_validate.py):** fetch live Sheet1 via gviz CSV, run both text-only and route-aware `classify_action` against it, cross-tab text-class × route-value on no-time rows. This exercises the real production artifact (`LegEventRoute` column written by the worker). The worker SYSTEM_METRICS line (`legevent_floor_recovered`, `legevent_route_admin/meeting/blank`) is the second corroborating source.

**Owner guardrails (locked):**
1. No LLM runtime dependency.
2. No OpenStates fallback (regex-on-text brittleness).
3. No hiding rows / no probabilistic guesses — lobbyist surface complete AND structurally correct (Standard #3 sharpened 2026-05-12).
4. Designed for dynamic environment (2027 session, new vocabulary, new clerks) — the structural router consumes LIS's own published vocabulary, so a never-seen value falls through to text + CRITICAL drift alert rather than silent break. Training-free by construction.

## Open PRs

| # | Branch | State | Notes |
|---|--------|-------|-------|
| 60 | `docs/forward-calendar-design` | **Open — forward-calendar design entry (docs)** | Detailed design for the 2027 upcoming-meetings surface. 4 Gemini findings folded in (datetime/date TypeError, pinned-investigation reproducibility guard, dedup key granularity, viewport-slice disconnect) + corrected the stale "Section 9 closed" premise. Design only; no code. **Awaiting bot re-review of the fold-in commit before merge.** |
| 56 | `claude/legevent-backfill-burst` | **Open — `⏩ LegEvent Backfill Burst` (the re-hydration tool for PR #61)** | Workflow-only N-cycle burst. Post-#61 it's the fastest way to re-hydrate the cache (run once → all 3,645 bills cached in one dispatch, bypasses quiet hours). Bot fold-in pushed: shared `calendar-worker` concurrency group (Codex P1) + state-aware re-enable (Codex P2). Ready to merge + dispatch when owner is ready to spend the ~4k LIS calls. |

**Merged this session:** #57, #58 (router UI + floor recovery), #61 (cache capacity — the real fix), #62 (cadence + quiet hours), #63 (legacy post-mortem). See [[log]].

## Next up (after this session's merges)

1. ✅ ~~Admin-route gating on journal_default fallback resolver~~ — **done in PR-C7.1g** (`route == "admin"` journal_default rows now skip the resolver instead of getting a wrong 4 AM document time; new `legevent_admin_skipped` counter). Shipped before re-hydration so the freshly-filled cache produces correct output. Re-hydration-safe (blank routes still recover).
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
