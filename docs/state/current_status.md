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

**🎯 SECTION 9 PIPELINE NOW CLOSED.** Both end-of-session PRs merged 2026-06-02 — see [[log#2026-06-02 pr | PR #57 + #58 merged]] for the play-by-play.

- **PR #55 (merged 2026-06-02 morning)** — PR-C7.1b-1: structural router backend deployed. Worker writes `LegEventRoute` per Sheet1 row from LIS's own `ReferenceType` / `VoteTally` / `Status` (dictionary-free; 52-status drift check validates the grouping at startup). Full-scale validated against 1,049 flagged Section-9 rows: **943 admin (false positives — `H5601`/`S5601`/`G7210` substring matches) + 103 meeting (genuine residue) + 3 no_event (clerical) + 0 FAILED + 0 drift.**
- **PR #57 (merged 2026-06-02 at `486faa2`)** — X-Ray consumes `LegEventRoute`. `classify_action(outcome_text, legevent_route="")` reads route first, text patterns fall back; flagged-subset proof counter renders the 943-admin / 103-meeting / 3-blank distribution in Section 9. Codex + Gemini fold-in landed (NaN-safe `.fillna("")`, `apply(axis=1)` → `zip` list-comp ~100×, full-column drift scan). **Visible impact: Section 9 1,049 → ~106 once Streamlit reloads against main.**
- **PR #58 (merged 2026-06-02 at `07c4a17`)** — worker `floor_miss → LegEvent` time recovery via new `_find_legevent_time_in_cache` helper, gated `route == "meeting"`. Helper is cache-direct (bypasses `_resolve_via_legislation_event_api`'s `LegislationID` short-circuit), which also fixed a silent regression in the pre-existing journal_default LegEvent recovery — every fresh/terminal bill (most of them post-cold-start) had been failing recovery since PR-C7 because `_legislation_id_cache` is in-memory while `_legislation_event_cache` is persisted, and the seeding handler set `id = ""` for every non-rehydrated bill. `_floor_miss_dates` switched from `set` → `collections.Counter` to preserve multiplicity (Codex P2 + Gemini medium). **Visible impact (one cron cycle in, ~15 min): Section 9 ~106 → ~3 + the silent journal_default rows.**

**Verification (the next ~30 min):** at the next worker cron cycle, watch the SYSTEM_METRICS line for `legevent_floor_recovered=N` climbing toward ~103 and `legislation_event_recovered` increasing more than it had pre-merge (the previously-silent journal_default rows). The X-Ray reflects the new bug count on next page load.

**Why this closes the months-long objective:** the 1,049 number was always two populations — 90% misclassification + 10% missing-time + ~3 clerical. The structural router IS the architectural answer (no per-state pattern list to maintain; consumes LIS's published vocabulary; new sessions / new clerks survive the change). C7.1b-2 made the verdict visible; C7.1c gave the genuine residue its times. Final ~3 clerical no_event rows are below the noise floor — addressing them is overfitting to static data per owner mandate (designed-for-dynamic > overfit-to-2026).

**Owner guardrails (locked):**
1. No LLM runtime dependency.
2. No OpenStates fallback (regex-on-text brittleness).
3. No hiding rows / no probabilistic guesses — lobbyist surface complete AND structurally correct (Standard #3 sharpened 2026-05-12).
4. Designed for dynamic environment (2027 session, new vocabulary, new clerks) — the structural router consumes LIS's own published vocabulary, so a never-seen value falls through to text + CRITICAL drift alert rather than silent break. Training-free by construction.

## Open PRs

| # | Branch | State | Notes |
|---|--------|-------|-------|
| 56 | `claude/legevent-backfill-burst` | **Open — `⏩ LegEvent Backfill Burst` (parked, infrastructure)** | Workflow-only one-shot cold-start helper. NOT needed for the current backfill (handoff measured cold-start completed organically on the 15-min cron). Kept as infrastructure for 2027 session start / schema migrations. Bot review fold-in pushed: shared `calendar-worker` concurrency group (Codex P1) + state-aware re-enable preserving owner-disabled cron (Codex P2). Off the critical path to Section 9 = 0; merge whenever owner is ready. |

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

## Known bug count (today — PR #57 + #58 merged, pending Streamlit reload + next cron cycle)

- **X-Ray Section 9 expected steady state:** ~3 (clerical no_event residue; below noise floor, intentionally not addressed).
- **Post-PR-#57 / pre-PR-#58 cron cycle (Streamlit only):** ~106 (UI now reflects the router; the residue still needs PR #58's worker time-recovery to land in a cron run).
- **Real meeting-time bugs:** ~0 once both have propagated. The two-population framing PR-C7.1d nailed has been fully addressed structurally.
- **Worker UNKNOWN_ACTION counter:** 6 (untouched by this session's work; separate path).
- **Section 7 (Sheet vs LIS time parity):** 0 ✓ — perfect parity on resolvable cases.
- **Workbook capacity:** 29.2% of 10M cap (post PR-C6.2 trim) — comfortable headroom for LegEvent tabs.

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
