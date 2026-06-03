---
tags: [state, live]
updated: 2026-06-03
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Full 2026 VA GA session (2026-01-14 → 2026-05-01). **VA GA is now ADJOURNED — HISTORY is static (no new actions until the 2027 session). Pre-launch: lobbyists are not using the product yet.**

## Active focus

**✅ CACHE FULLY HYDRATED (3,645/3,645 bills, ~65k event rows). Section 9 driven from 1,072 → 210 measured, with two open PRs projecting → ~28.** The cache-starvation era is over (PRs #61/#67 fixed truncation + Tier-A starvation; crossover audit confirmed `meeting_in_ledger 9→0` vs frozen LIS ground truth). Section 9 is now decomposed into named, structural residue classes — **no remaining "mystery" rows.**

**Section 9 residue decomposition (measured 2026-06-03, route-aware, live Sheet1 = 210):**

| Class | Count | Route/Origin | Status |
|---|---|---|---|
| **Governor** (`Governor's Recommendation`, `…received by Senate/House`) | **114** | blank/journal_default | **FIXED → PR #72** (null-cell `"None"` bug; now route admin → Ledger) |
| **Rereferred to Y** (HISTORY secondary split of "Reported from X and rereferred to Y") | **~69** | meeting/journal_default | **FIXED → PR #71** (sibling-time inheritance from the resolved "Reported from X" meeting) |
| **Empty-status admin** = `Signed by President/Speaker` (14) + `Placed on Calendar/Agenda` (6) | **~20** | meeting/floor_miss + meeting/journal_default | **IRREDUCIBLE without a dictionary** — see below |
| **Genuine schedule-gap** = `Reported from P&E (13-Y…)` (SJ209), `Conferees appointed`, `Passed by for the day` | **~4** | meeting/journal_default | Real meetings we failed to time; **#71 may rescue via sibling**; SJ209 is a true DOCKET/schedule miss worth a future look |
| **LIS Time-TBA** = `Continued pursuant to Rule 22`, 2× COMMITTEE_DRIFT | **3** | api_schedule | **Honest — LIS itself publishes `Time TBA`** (no concrete time exists upstream). Not a bug. |

**The ~20 "empty-status admin" rows are the proven structural floor (honest residue).** Full raw-LIS-event probe (2026-06-03): "Signed by" (`S5620`/`H5620`) and "Placed on Calendar" (`H5220`) are represented *identically* to genuine floor meeting actions on every field the lobbyist-path may use — empty `Status`, no `VoteTally`, `RefType=None`, chamber `ActorType`. The one structural separator is `EventCode`/`LegislationEventTypeID` (a per-state dictionary the owner explicitly rejected — won't scale to 50 states). **Time-presence on the event's own `EventDate` is NOT a clean separator either:** "Placed"/"Signed" are always midnight (0 real-time of 532/2601), but **755 genuine "Read third time" floor reads are also midnight** — so flipping the router's empty-status default to time-presence would clear the 20 admin rows at the cost of misclassifying 755 floor reads to admin (net worse). These 20 are non-actionable for a lobbyist (the minute a JR was signed at sine die; a clerk's calendar placement). **Decision: accept as honest upstream-limited residue.** Literal 0 requires re-admitting a text/EventCode exception → contradicts Standard #3 + #6. Revisit only if the owner accepts a narrow ceremonial exception, OR if LIS publishes an EventType→category reference that lets us derive it at runtime (Standard #5 — the one path that would close it structurally).

**Net projection once #71 + #72 merge + one worker cycle:** 210 → ~27, of which ~20 are the irreducible empty-status admin (signed/placed), 3 are honest LIS Time-TBA, and ~4 are genuine schedule-gaps (#71 may shrink further). **The "desired product" is effectively a ~97% structural reduction (1,072 → ~27) with EVERY remaining row named and explained — no probabilistic guesses, no dictionary, scales to 50 states unchanged. The remaining floor is upstream-limited (LIS structural ambiguity / LIS-published TBA), not an architecture defect.**

**Verification method (use this, not full_validate.py):** fetch live Sheet1 via gviz CSV, run both text-only and route-aware `classify_action` against it, cross-tab text-class × route-value on no-time rows. ⚠️ **Read the sheet with `gspread.get_all_values` semantics (raw strings), NOT `pandas.read_csv`** — pandas auto-NaN's the string `"None"` and silently heals the very corruption production chokes on (that masked the Governor bug for weeks; [[failures/assumptions_audit#66]]). The worker SYSTEM_METRICS line (`legevent_floor_recovered`, `legevent_route_admin/meeting/blank`) is the second corroborating source.

**Owner guardrails (locked):**
1. No LLM runtime dependency.
2. No OpenStates fallback (regex-on-text brittleness).
3. No hiding rows / no probabilistic guesses — lobbyist surface complete AND structurally correct (Standard #3 sharpened 2026-05-12).
4. Designed for dynamic environment (2027 session, new vocabulary, new clerks) — the structural router consumes LIS's own published vocabulary, so a never-seen value falls through to text + CRITICAL drift alert rather than silent break. Training-free by construction.

## Open PRs

| # | Branch | State | Notes |
|---|--------|-------|-------|
| **72** | `claude/pr-c7-1k-legevent-null-normalization` | **Open — Governor blank-route fix (the 114-row residue)** | `_clean_legevent_cell()` collapses JSON-null `"None"` → `""` on persist+load. Clears all 114 Governor rows (route admin → Ledger). Validated with raw-string repro. **Awaiting bot review.** [[failures/assumptions_audit#66]]. |
| **71** | `claude/pr-c7-1j-sibling-time-inheritance` | **Open — sibling-time inheritance (the ~69 rereferred rows)** | Timeless meeting-routed `journal_default`/`floor_miss` row inherits the resolved time of its same-`(Bill,Date)` committee/floor meeting, ONLY when unambiguous. Zero vocabulary. **Awaiting bot review.** [[failures/assumptions_audit#65]]. |
| 60 | `docs/forward-calendar-design` | **Open — forward-calendar design (docs)** | 2027 upcoming-meetings surface design. 4 Gemini findings folded in. Design only. **Awaiting bot re-review.** |
| 56 | `claude/legevent-backfill-burst` | **Open — `⏩ LegEvent Backfill Burst`** | Re-hydration tool. No longer needed for current backfill (cache is full); reserved for 2027 cold-start. `gh api` state-fetch fix pushed. Mergeable anytime. |

**Merge sequencing:** #71 and #72 touch DIFFERENT regions of `calendar_worker.py` (no code conflict) but both append to `assumptions_audit.md` (#65 vs #66) — expect a trivial append conflict on whichever merges second; resolve by keeping both in numeric order. After both merge, dispatch one worker cycle, then re-cross-tab Section 9 (expect ~28).

**Merged earlier this session:** #57, #58 (router UI + floor recovery), #61 (cache capacity), #62 (cadence + quiet hours), #63 (legacy post-mortem), #67 (Tier-A starvation fix), #69 (forward-window foundation), #70 (route 0-overlap guard). See [[log]].

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

## Known bug count (MEASURED against live Sheet1, 2026-06-03 post-hydration)

- **X-Ray Section 9 — route-aware (current production):** **210** (down from the 1,072 cache-starvation peak). Fully decomposed (see Active focus table): 114 Governor (→ #72) + ~69 rereferred (→ #71) + 14 ceremonial signed-by (irreducible) + ~13 misc tail.
- **Projected after #71 + #72 merge + one cycle:** **~28** (14 irreducible signed-by + ~13 unmapped misc + 1).
- **Crossover accuracy (frozen LIS ground truth, Feb 9-13):** `meeting_in_ledger` **9 → 0** ✓ at full hydration. The structural correctness check passes.
- **Worker UNKNOWN_ACTION counter:** 6 (separate path, untouched).
- **Section 7 (Sheet vs LIS time parity):** 0 ✓.
- **Cache coverage:** **3,645 / 3,645 bills hydrated (100%)** ✓; `LegEvent_Events` ~65k rows (tab capacity 120k post-#61). The 29% starvation is resolved.

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
