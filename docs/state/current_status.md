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

**✅ SECTION 9 = 10 — MEASURED on the FULL live Sheet1 (65,180 rows processed, 35,491 written) after #74 (ministerial rule) + #75 (window clamp), 2026-06-03. Trajectory: 1,072 peak → 210 → 25 (#71+#72) → 10 (#74). A 99.1% reduction.** Cache 100% hydrated; crossover `meeting_in_ledger` holds 9→0.

**Two things landed this block:**

1. **The ministerial event-type law (#74 / [[failures/assumptions_audit#67]])** — the answer to "can't gamble on an influx next session." The empty-status admin class was 412 timeless signings (404 on sine die), recurring/growing. Resolved dictionary-free: *a deliberative action leaves a vote OR a timestamp; a ministerial record leaves neither.* `compute_ministerial_eventcodes()` derives, from each session's own data, the EventCodes that never (≥20 occ) carry a vote or a real time → Ledger. 33-code set, self-calibrating, zero per-state config. Cleared the 15 signed/placed rows (590 admin rows moved meeting→Ledger, 0 genuine meetings swept).

2. **A silent-data-loss bug, found + fixed (#75 / [[failures/assumptions_audit#68]])** — the first verify run returned "Section 9 = 0" on a 277-row sheet that had **silently dropped crossover week**: `df_past`'s window came from the Session API's sparse 5-event summary, whose min-date intermittently jumps forward (65,180 vs 310 processed on identical inputs), and `df_past.empty` was False so no alert fired. Fixed by clamping the window to never shrink below the pinned investigation floor + hardening `safe_fetch_csv` (retries, 60s timeout, Content-Length completeness). The 65,180-row re-run confirms the sheet is whole again.

**The 10 residue (measured, full sheet, all named — none ballooning):** 3 governor date-drift (HISTORY-vs-LegEvent date mismatch), 2 LIS-published Time-TBA (upstream-empty), 1 rereferred (HB438, #71 conservative non-guess), 4 other (HB447 "Continued…Rule 22" = TBA; HB642 "Conferees appointed"; SJ209 "Reported from P&E" = confirmed NOT in DOCKET.CSV; +1). ~5-6 are upstream-limited (no time exists in any LIS source); ~3 governor are fixable via a date-reconciliation pass.

**Section 9 residue decomposition — BEFORE (210 pre-merge) → AFTER (25 measured):**

| Class | Before | After | Route/Origin | Status |
|---|---|---|---|---|
| **Governor** (`Governor's Recommendation`, `…received by Senate/House`) | 114 | **3** | now admin/admin_default | **FIXED → PR #72** (null-cell `"None"`). 111/114 now route admin → Ledger. The **3 residual** are a HISTORY-vs-LegEvent **date drift** (Sheet1 row dated 4/13–4/14 from HISTORY; the LegEvent is 4/11–4/12 "received" / 4/22 "concurred" → exact-date route match misses → blank → text reads "recommend**ation**" as meeting). Reconvene/veto-session edge; candidate micro-fix below. |
| **Rereferred to Y** (HISTORY secondary split of "Reported from X and rereferred to Y") | ~69 | **1** | meeting/journal_default | **FIXED → PR #71** (sibling-time inheritance). 68/69 cleared. The **1 residual** (HB438) had no unambiguous resolved sibling that day, so #71 correctly declined to guess (Standard #3). |
| **Empty-status admin** = `Signed by President/Speaker` (14) + `Placed on Calendar` (1 residual) | ~20 | **15** | meeting/floor_miss + journal_default | **IRREDUCIBLE without a dictionary** — see below. (Most "Placed on" cleared via route; 14 signed-by + 1 placed remain.) |
| **Genuine schedule-gap** = SJ209 `Reported from P&E (13-Y…)`, `Conferees appointed` (HB642), `Passed by for the day` (HB246) | ~4 | **3** | meeting/journal_default | Real meetings we failed to time. **SJ209 is a true DOCKET/schedule miss** — the one legitimately-fixable sliver (committee met, our DOCKET join missed it). |
| **LIS Time-TBA** = `Continued pursuant to Rule 22` (HB447), COMMITTEE_DRIFT | 3 | **3** | api_schedule | **Honest — LIS itself publishes `Time TBA`** (no concrete time exists upstream). Not a bug. |
| **TOTAL** | **210** | **25** | | |

**Candidate micro-fixes for the last ~8 (optional — diminishing returns, weigh against risk):**
1. **3 governor date-drift** → a date-tolerant route match for *unambiguous single-occurrence actor events* (a bill has exactly one Governor's Recommendation per session, so matching by (bill, ActorType=Governor) within ±2 days is structurally safe). Carries a small false-match risk — needs the "single distinct candidate" guard like #71. **OR** treat as a HISTORY-date-accuracy issue (the calendar may be placing the action 1–2 days off LIS's authoritative LegEvent date).
2. **1 rereferred (HB438)** → inherent #71 limitation; only closes if its sibling resolves.
3. **SJ209** → DOCKET coverage gap (Senate P&E meeting not joined). The genuinely-fixable schedule-gap.
The remaining **14 signed-by + 1 placed = 15** are the hard no-dictionary floor; **2 TBA** are upstream-empty. So the irreducible floor is ~15–17 and the rest (~8) are fixable with care.

**The ~20 "empty-status admin" rows are the proven structural floor (honest residue).** Full raw-LIS-event probe (2026-06-03): "Signed by" (`S5620`/`H5620`) and "Placed on Calendar" (`H5220`) are represented *identically* to genuine floor meeting actions on every field the lobbyist-path may use — empty `Status`, no `VoteTally`, `RefType=None`, chamber `ActorType`. The one structural separator is `EventCode`/`LegislationEventTypeID` (a per-state dictionary the owner explicitly rejected — won't scale to 50 states). **Time-presence on the event's own `EventDate` is NOT a clean separator either:** "Placed"/"Signed" are always midnight (0 real-time of 532/2601), but **755 genuine "Read third time" floor reads are also midnight** — so flipping the router's empty-status default to time-presence would clear the 20 admin rows at the cost of misclassifying 755 floor reads to admin (net worse). These 20 are non-actionable for a lobbyist (the minute a JR was signed at sine die; a clerk's calendar placement). **Decision: accept as honest upstream-limited residue.** Literal 0 requires re-admitting a text/EventCode exception → contradicts Standard #3 + #6. Revisit only if the owner accepts a narrow ceremonial exception, OR if LIS publishes an EventType→category reference that lets us derive it at runtime (Standard #5 — the one path that would close it structurally).

**ACHIEVED (measured, not projected):** 1,072 → **25** after #71 + #72 merged + one worker cycle. ~15–17 are the irreducible floor (14 signed-by + 1 placed empty-status admin + 2 LIS-TBA); the other ~8 (3 governor date-drift, 1 rereferred sibling-miss, SJ209 DOCKET-gap, etc.) are fixable with care but carry diminishing returns / Standard-#3 risk. **The architecture is sound: no probabilistic guesses, no dictionary, scales to 50 states unchanged. The remaining floor is upstream-limited (LIS structural ambiguity / LIS-published TBA / HISTORY-vs-LegEvent date drift), not an architecture defect.**

**Verification method (use this, not full_validate.py):** fetch live Sheet1 via gviz CSV, run both text-only and route-aware `classify_action` against it, cross-tab text-class × route-value on no-time rows. ⚠️ **Read the sheet with `gspread.get_all_values` semantics (raw strings), NOT `pandas.read_csv`** — pandas auto-NaN's the string `"None"` and silently heals the very corruption production chokes on (that masked the Governor bug for weeks; [[failures/assumptions_audit#66]]). The worker SYSTEM_METRICS line (`legevent_floor_recovered`, `legevent_route_admin/meeting/blank`) is the second corroborating source.

**Owner guardrails (locked):**
1. No LLM runtime dependency.
2. No OpenStates fallback (regex-on-text brittleness).
3. No hiding rows / no probabilistic guesses — lobbyist surface complete AND structurally correct (Standard #3 sharpened 2026-05-12).
4. Designed for dynamic environment (2027 session, new vocabulary, new clerks) — the structural router consumes LIS's own published vocabulary, so a never-seen value falls through to text + CRITICAL drift alert rather than silent break. Training-free by construction.

## Open PRs

| # | Branch | State | Notes |
|---|--------|-------|-------|
| 60 | `docs/forward-calendar-design` | **Open — forward-calendar design (docs)** | 2027 upcoming-meetings surface design. 4 Gemini findings folded in. Design only. **Awaiting bot re-review.** |
| 56 | `claude/legevent-backfill-burst` | **Open — `⏩ LegEvent Backfill Burst`** | Re-hydration tool. No longer needed for current backfill (cache is full); reserved for 2027 cold-start. `gh api` state-fetch fix pushed. Mergeable anytime. |

**Merged this session (Section 9: 1,072 → 25):** #57, #58 (router UI + floor recovery), #61 (cache capacity), #62 (cadence + quiet hours), #63 (legacy post-mortem), #67 (Tier-A starvation fix), #69 (forward-window foundation), #70 (route 0-overlap guard), **#71 (sibling-time inheritance — rereferred 69→1)**, **#72 (LegEvent null-cell normalization — governor 114→3)**. See [[log]].

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

## Known bug count (MEASURED against the FULL live Sheet1, 2026-06-03 post #74+#75 + worker cycle 26914210038)

- **X-Ray Section 9 — route-aware (current production):** **10** ✓ (down from 1,072 peak / 25 pre-ministerial — a **99.1% reduction**). Measured on the full sheet (65,180 rows processed, 35,491 written). Decomposed: 3 governor-date-drift + 2 LIS-TBA + 1 rereferred + 4 other (HB447 TBA, HB642 conferees, SJ209 not-in-DOCKET, +1).
- **Influx-proofed:** the dominant former class (empty-status signings/placings) is now handled by the **self-calibrating ministerial law** (#74), so next session's bulk signings are classified from their own data with zero maintenance — no longer a ballooning risk.
- **Remaining floor:** ~5-6 upstream-limited (no time exists in any LIS source — TBA / not-in-DOCKET / date-only); ~3 governor are fixable via a date-reconciliation pass; 1 rereferred is a #71 conservative non-guess.
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
