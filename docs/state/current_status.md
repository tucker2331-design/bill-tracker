---
tags: [state, live]
updated: 2026-06-09
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Full 2026 VA GA session (2026-01-14 → 2026-05-01). **VA GA is now ADJOURNED — HISTORY is static (no new actions until the 2027 session). Pre-launch: lobbyists are not using the product yet.**

## Active focus

**🎯 PR-C8 — CLOSE THE 16% STRUCTURALLY (2026-06-09, NEXT UP).** The blank-route rows
(~16%) are still classified by hand-built text patterns — the last Standard-#3 violation on
the lobbyist path. Deep-reasoning session produced the full execution spec:
**[[architecture/pr_c8_structural_classification]] — the implementing model MUST follow it
verbatim (hard rules, gates, golden tests, stop-and-escalate protocol).** Foundation: the
`History_refid` typed-namespace discovery + VOTE.CSV roll-call join + the batch-notice law
(96.7% of blank journal rows proven structurally, 0 counterexamples) —
[[knowledge/history_refid_namespace]]. **C8.1 DONE (PR #111, shadow): RefidClass batch-notice law solves the journal_default 16% at 98.3%, 0 counterexamples, K=2; next C8.1b = ScheduleTypeID for 964 api_schedule-text rows, then C8.2 flip.** Three PRs: C8.1 shadow telemetry → C8.2 flip (text
patterns deleted from ray2/calendar_xray) → C8.3 guards (completeness tripwire + unconfirmed
budget). Also done this block: LIS API authorization rule captured + enforced in code
(PR #110, [[knowledge/lis_api_authorization]]); dynamic session window (PR #109) — no more
pinned INVESTIGATION window in the worker.


**🔒 SUSTAINABILITY AUDIT + VERIFICATION + FUTURE-PROOFING (2026-06-07).** Owner asked to confirm the Section-9=0 work checks off all standards, verify it independently, and proactively hunt edge cases ("who's to say that's all the bugs?"). Three phases, all done:
- **Phase A — standards audit** ([[architecture/scalability_audit]], PR #101): re-ran the 8 standards against the new architecture. Lobbyist-critical path sound. 4 gaps: **G2** (derived volume guard) + **G4** (derived denominator) FIXED (PR #104); **G1** (window drift counter) deferred (B1 closes the known class); **G3** (50-state isolation of derived_standing's VA/English specifics) logged as YAGNI until state #2.
- **Phase B — independent verification + reconciliation tripwire** ([[tools/reconciliation]], PR #103, Standard #2): a continuous diff of our committee reports vs the official **MinutesBook** (a source the pipeline never touches). **99.67% independently confirmed; 0.33% known residual (opening-day JRs + crossover) → PASS.** The durable answer to "unknown bugs." (Vote-tally diffing found unreliable — minutes' VoteTally often empty; tripwire verifies meeting/attribution existence ±2d.) Chrome visual spot-check still pending (extension offline).
- **Phase C — proactive multi-session replay** ([[testing/edge_case_registry]], PR #102): ran the pure functions against every session LIS serves. Found **B1** (real bug: `parse_24h_time` rejected `"8am"`/`"8:30AM"` → 23:59 sort → mis-ordered; same blind spot as #79) — FIXED (PR #104); the LIS rolling-window limit; and text-fallback coverage gaps (veto/rename) that `route_event` already handles structurally. 2027 cold-start dry-run (DR1) PASSED for the new features.

**✅✅ SECTION 9 = 0 — MEASURED IN PRODUCTION (2026-06-06). EVERY meeting action now has a time.** Trajectory: 1,072 → … → 6 (first REAL cold-start measurement) → 4 (#87) → 1 (#75/PR-C7.1v cache migration) → **0 (#76/PR-C7.1w standing-schedule derivation)**. The last holdout, SJ209's Senate P&E report, was NOT irreducible after all — its time is derivable from the committee's own published standing pattern. **1 time is `derived_standing` (SJ209 → 5:34 PM), flagged in the X-Ray as ASSUMED — never hidden, never presented as a hard fact.** 0 missing, 0 mis-timed, cache 100% migrated, crossover `meeting_in_ledger` 9→0.

**SJ209 closed (audit #76):** owner pushed past "irreducible" a third time. Exhaustive hunt across all 246 LIS endpoints found the committee MinutesBook (confirms the 3/10 P&E meeting officially, "Closed") and proved the concrete time is derivable: P&E's modal published pattern "15 minutes after the Senate adjourns" (6/6 regular-session meetings) + the published 3/10 "Senate adjourned 5:19 PM" = 5:34 PM. Implemented as a FLAGGED last-resort (`derived_standing`) that fires only after every real source — HB438 still keeps its real 8:00 AM. Owner-approved narrow relaxation of Standard #3 (flagged, not hidden).

**⚠️ Procedural lesson (audit #74): #72's "4 → 1" was a PROJECTION, never measured — the verifying backfill burst checked out the PR #84 commit an hour BEFORE #87 merged, so it ran the pre-recovery code. The first real cold-start measurement was 6. Always verify a metric delta on a run whose `headSha` provably contains the PR's commit — and READ the produced rows, not just the count.**

**How the residual 4 → 1 was actually closed (each MEASURED):**
- **#74 / PR-C7.1t — the 05:00 artifact (ministerial):** `structural_router._has_meeting_time`'s `{00:00,04:00}` blocklist missed `05:00`, so Rule-22 continuances (`H0840`) looked "timed" → dodged the ministerial law → routed meeting. Fixed by unifying the router + recovery on ONE `[07:00,23:00]` window (validated against 117 bills / 300 EventCodes). Swept the common clerical codes (Enrolled/Bill-text), but the per-bill residual was actually a cache bug ↓.
- **#75 / PR-C7.1v — the REAL blocker: 500 cached bills starved the recovery.** `_recover_time_via_legevent_committee` was proven CORRECT on fresh API data (HB438→8 AM, HB246→12 PM, HB447→10 AM all resolve) — but in production it reads the persisted cache, and **500 bills / 12,793 events still had `CommitteeName="?"`** (pre-column hydration). The recovery refuses `"?"`, and those bills were skipped as "fresh" (persist bumps `FetchedAtUTC` without re-fetching, so they never re-qualify). Fix: detect `"?"` directly and re-queue BEFORE the terminal/TTL skips. One migration cycle (`schema_backfill=500`) → cache fully migrated → HB438/HB246/HB447 all timed → Section 9 = 1.
- **SJ209** "Reported from P&E (13-Y…)" 3/10 — **the one genuinely irreducible row.** P&E voted but LIS published no 3/10 P&E meeting (`api_2026-03-10` = caucuses + Senate Convenes only). The time exists in no LIS source; the only candidate is the forbidden "15-min-after-adjournment" probabilistic guess (Standard #3). Honestly timeless.

**Latent follow-up (audit #75):** the cache "fresh" signal tracks last-PERSIST, not last-FETCH — it can mask a genuinely stale row. Orthogonal to the migration (now that all `"?"` are gone), flagged for a separate pass.

**The owner pushed past "upstream-limited": several timeless rows weren't missing a TIME, they were missing a JOIN.** The fix (#81, regression-fixed by #82 — [[failures/assumptions_audit#71]]) recovers a timeless meeting row from its matched LegEvent's OWN published structural fields: `CommitteeName` → that committee's scheduled meeting time (the committee it actually met in — e.g. HB438's rereferral → Senate Courts of Justice 8:00 AM); no committee + chamber `ActorType` → that chamber's convene time (HB642/HB246 floor actions → 12:00 PM). Dictionary-free, scales to 50 states. **HB642 already recovered; HB438/HB246 land their times once `CommitteeName` back-fills (6h TTL / a backfill burst).**

**Also this block:**
- **#79 (relative-time sort fix):** committees that meet "X min after adjournment" now sort to their real after-adjournment slot (Senate adjourned-time + offset), not convene+1min — ~168 committees re-ordered correctly. Display time stays LIS's published relative string (LIS-parity). [[failures/assumptions_audit#70]].
- **#80 (forward calendar Step 1b):** the producer — future Schedule meetings tagged `scheduled_future`. Verified no-op on the adjourned session; activates 2027.
- **The regression I caught (#82):** #81's first cut didn't persist `CommitteeName`, so it timed committee reports as floor actions (SJ209 → wrong 10:00 AM). Caught by verifying the ROW, not the count. Fixed with a 3-state sentinel (name / "" floor / "?" unknown-refuse).

**SJ209 is the one genuinely irreducible row:** P&E voted 13-Y on 3/10 but LIS published NO 3/10 P&E meeting — the time exists in no source (only the forbidden "15-min-after-adjournment" pattern guess). The remaining floor (~4) = SJ209 + HB447/HB919/SB834 (House committees with empty published schedule times).

**Three things landed this block (#74, #75, #77):**

0. **EventType-reference admin recovery (#77 / [[failures/assumptions_audit#69]])** — the last reducible class was 3 "Governor's Recommendation" rows blanked by HISTORY-vs-LegEvent **date drift** (1-9 days). Fixed dictionary-free: when the date-match is blank, recover the route from LIS's OWN published EventCode↔description reference (`GetLegislationEventTypeReferencesAsync`), routing admin only when every mapped code is admin. This is the standardization step — blank rows now route via LIS vocabulary, not hand text patterns (shrinking the Standard-#3 text dependency). Self-calibrating, zero maintenance.

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

## Known bug count (MEASURED against the FULL live Sheet1, 2026-06-05 post PR-C7.1t/u/v + migration cycle 26987774153)

- **X-Ray Section 9 — route-aware (current production):** **0** ✓✓ (down from 1,072 peak — a **100% reduction**). MEASURED via a faithful reproduction of ray2.py `bug_count = len(mt_without)` against the live Sheet, production raw-string read. Every meeting action has a time. **1 time is `derived_standing` (SJ209 → 5:34 PM), flagged ASSUMED in the X-Ray "DERIVED / ASSUMED times" block** — the committee's own published standing pattern + adjournment, a last-resort that fires only when no per-meeting entry exists (worker metric `derived_standing=1`). Cache 100% migrated (0 `"?"`); 0 mis-timed; durable.
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
