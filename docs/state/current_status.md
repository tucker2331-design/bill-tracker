---
tags: [state, live]
updated: 2026-04-24
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Feb 9-13, 2026 (crossover week).

## Active focus
**PR-C2 merged (PR#29, 2026-04-24) — gap detection + Schedule_Witness + reconciliation now live.** Three rounds of Gemini review folded in: round-1 inline at PR open; round-2 = Location-delta whitelist + prune→L3b + migration burst guard + size canary; round-3 = `col_values()` for the reconciliation witness-date index (avoids a scale cliff on the change-feed tab). First post-merge cycle produced the expected migration burst on `Schedule_Witness` — cached entries with `Location=""` populated to live values, and a subset where SortTime also drifted bypassed the `{Location}`-only burst guard and emitted `CHANGED` rows. That's first-cycle behavior; the next cycle is being monitored to confirm steady-state quiet. Three observability gaps surfaced from the post-merge sheet inspection, all flagged in [[ideas/future_improvements]]: (1) witness cache-carryover scope — diff iterates the full cache, so historical entries outside the scrape window emit noise on any tracked-field drift; (2) `API_Cache` historical-row `Location` is permanently empty after migration unless explicitly backfilled; (3) `Bug_Logs` tab is still empty for `calendar_worker` (no integration yet). Active work: **scaffolding PR-C2.1** — Playwright historical scraper triggered on `CONFIRMED BLIND-WINDOW LOSS` for time recovery (per Gemini round-2 concern #3: `wait_for_selector()` bound to the schedule-table DOM, ≥15s per-date timeout); also the natural backfill channel for historical `API_Cache` Location. See [[architecture/calendar_pipeline#Gap Detection + Witness Log + Reconciliation (PR-C2)]].

## Open PRs
*(none currently open — PR-C2.1 will appear here when branched.)*

## Recently closed
- **PR#29** `claude/pr-c2-gap-detection-witness-log` — merged 2026-04-24. PR-C2 landed: Y1 gap detection + 7 `gap_cause` classes (WARN @ >20m, CRITICAL @ >60m or stale-cursor); `Schedule_Witness` change-feed tab (13 cols, whitelist-iterated `WITNESS_DELTA_FIELDS = (Time, SortTime, Status, Location)`, migration burst guard, retention deferred to L3b); HISTORY-vs-witness reconciliation with 7-day cap + CRITICAL-over-cap alert. Three rounds of Gemini review folded in (round-2: Location delta + prune→L3b + canary; round-3: `col_values()` scale-cliff fix). Zero bug-count delta — observability + data-recovery infrastructure. New `source_miss_counts` counters: `gap_minutes`, `gap_cause`, `witness_rows`, `witness_location_backfills`, `reconciliation_blind_dates`, `reconciliation_checked_dates`.
- **PR#28** `claude/pr-c1-append-event-chokepoint` — merged 2026-04-21. PR-C1 landed: `_append_event()` chokepoint enforcing I1-I4, mass-violation circuit breaker (`Sheet1!X1`/`W1` durable visibility), state cell `Sheet1!Y1` for `last_successful_cycle_end_utc`, GitHub Actions `concurrency` block. Codex P1/P2 + Gemini denominator review fixes folded in. Zero bug-count delta — scaffolding for PR-C2+.
- **PR#27** `claude/crossover-audit` — merged 2026-04-20. Crossover-week full-universe audit confirmed the 9-bug count is real (no hidden meeting-misclass, phantom rows, or silent bill-drops). Bug class distribution: 4 × Class 1 (Schedule API gap at full committee), 5 × Class 2 (subcommittee attribution miss). Documented in [[testing/crossover_audit#findings]].
- **PR#26** `claude/pr-b-metrics-visibility-diagnostic` — merged 2026-04-17. PR-B landed: (1) `Origin in {system_alert, system_metrics}` exempt from viewport slice (denominator row now reaches Sheet1); (2) `DiagnosticHint` column populated on `journal_default` / `floor_miss` rows. Sheet1 schema: 10 → 11 columns. See [[failures/gemini_review_patterns]] #36-#37.
- **PR#25** `claude/worker-source-miss-visibility` — merged 2026-04-16. PR-A landed (all 5 source-miss visibility changes + Gemini review fixes #31-#35). Worker run confirmed counters wired (denominator = 63,081 mutually-exclusive buckets). Metrics row never reached Sheet1 due to viewport bug → fixed in PR-B.
- **PR#24** `claude/pr23-gemini-review-fixes` — merged 2026-04-16. Gemini review follow-ups for PR#23 (placeholder link, severity alignment, `<module>` consistency, log accuracy, section-anchor wikilink).
- **PR#23** `claude/docs-obsidian-brain` — merged 2026-04-16. Obsidian brain consolidation.
- **PR#22** `claude/pr22-offered-admin-override` — closed unmerged. Premise invalidated. See [[failures/assumptions_audit]] #41 and [[failures/pr22_post_mortem]].

## Next PR
PR-C2.1 first (still PR-C series infrastructure / data recovery), then per-class fix-passes:
- **PR-C2.1** *(active)* — Playwright historical scraper triggered on `CONFIRMED BLIND-WINDOW LOSS` for time recovery, plus historical `API_Cache` Location backfill (same scrape, second column). `wait_for_selector()` bound to the schedule-table DOM (NOT `networkidle`), ≥15s per-date timeout. See [[ideas/future_improvements#PR-C2.1 — Playwright historical scraper (deferred from PR-C2)]].
- **PR-C3** — LegislationEvent API as secondary time source (collapses Class 1: 4 bugs — HB111/505/972/609). Fallback chain documented in [[log]] 2026-04-20 entry and [[knowledge/lis_api_reference]].
- **PR-C4** — Subcommittee attribution resolver (collapses Class 2: 5 bugs — HB24/1266/1372, SB494/555).
- **PR-C5+** — Mop-up: address whichever category X-Ray Section 0 surfaces as largest residual (`unsourced_journal` / `unsourced_anchor` / `floor_anchor_miss` / `dropped_ephemeral`). Each PR must cite before/after counts from Section 0 to meet CLAUDE.md Standard #7.

## Known bug count (as of last measured X-Ray)
Crossover week, post-PR-B, **audit-verified 2026-04-19**:
- Meeting actions without times: **9** ✓ (confirmed via full-universe audit; no hidden bugs)
- Unclassified: **9** (same bucket; see breakdown in [[testing/crossover_week_baseline]])
- The 9-count is now the true bug count, not a symptom count. Full-universe audit in [[testing/crossover_audit]] ruled out hidden-meeting-misclass, phantom rows, and silent bill-drops.
- Bug class distribution: 4 × Class 1 (Schedule API gap at full committee), 5 × Class 2 (subcommittee attribution miss). See [[testing/crossover_audit#findings]].

## Active architecture
Two parallel Streamlit apps and two scheduled workers. Full description in [[architecture/calendar_pipeline]].
- `backend_worker.py` — main product worker ("Mastermind Ghost Worker")
- `calendar_worker.py` — calendar subsystem worker ("Mastermind Ghost Worker 2"), being perfected before merging into v2
- `pages/ray2.py` — X-Ray diagnostic (Streamlit-served)
- `calendar_xray.py` — diff-identical backup of `pages/ray2.py`

## What changes this page
Anything that changes the answer to "what is Tucker working on right now?" — opening/closing a PR, changing the active bug count, shifting the goal, pausing/resuming a thread. The LLM updates this page on every session conclusion.
