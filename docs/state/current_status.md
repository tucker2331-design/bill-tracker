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
**PR-C2 opened — gap detection + witness log + reconciliation.** Second PR in the PR-C series; closes the loop from PR-C1 scaffolding. Three-part scope: (A) Y1 gap detection at cycle top, classifying `gap_cause` (first_run / future / stale / malformed / breaker_carryforward / outage / normal) and emitting WARN @ >20 min, CRITICAL @ >60 min; (B) `Schedule_Witness` append-only change-feed tab capturing ADDED + CHANGED LIS Schedule API deltas with 90-day rolling prune, auto-created on first delta, NOT gated by the circuit breaker; (C) gap-triggered HISTORY-vs-witness reconciliation (capped at 7 days) that flags "confirmed blind-window loss" for dates where HISTORY has meeting-verb rows but Schedule_Witness has zero evidence. Zero bug-count delta expected from C2 alone — it's observability + data-recovery infrastructure. CRITICAL alerts (`y1_stale`, `gap_reconciliation_oversized`, `gap_critical`) are flagged for future re-routing to a dedicated dashboard; see [[ideas/future_improvements#Notification Routing (flagged 2026-04-24, PR-C2)]]. See [[architecture/calendar_pipeline#Gap Detection + Witness Log + Reconciliation (PR-C2)]].

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| TBD | `claude/pr-c2-gap-detection-witness-log` | **Open — PR-C2** | Gap detection + witness log + reconciliation. (A) Y1 gap computation + 7 `gap_cause` classes + WARN/CRITICAL thresholds. (B) `Schedule_Witness` change-feed tab (11 cols, ADDED+CHANGED only, 90-day prune). (C) HISTORY-vs-witness reconciliation with 7-day cap + CRITICAL-over-cap alert. New counters in `source_miss_counts`: `gap_minutes`, `gap_cause`, `reconciliation_blind_dates`, `reconciliation_checked_dates`. See [[architecture/calendar_pipeline#Gap Detection + Witness Log + Reconciliation (PR-C2)]]. |
| TBD | `claude/pr-b-metrics-visibility-diagnostic` | **Open — PR-B** | (1) Exempt `Origin in {system_alert, system_metrics}` from viewport slice so denominator row reaches Sheet1. (2) Add `DiagnosticHint` column populated ONLY on source-miss rows (`journal_default` / `floor_miss`). Sheet1 schema: 10 → 11 columns. See [[failures/gemini_review_patterns]] #36-#37. |

## Recently closed
- **PR#22** `claude/pr22-offered-admin-override` — closed unmerged. Premise invalidated. See [[failures/assumptions_audit]] #41 and [[failures/pr22_post_mortem]].
- **PR#23** `claude/docs-obsidian-brain` — merged 2026-04-16. Obsidian brain consolidation.
- **PR#24** `claude/pr23-gemini-review-fixes` — merged 2026-04-16. Gemini review follow-ups for PR#23 (placeholder link, severity alignment, `<module>` consistency, log accuracy, section-anchor wikilink).
- **PR#25** `claude/worker-source-miss-visibility` — merged 2026-04-16. PR-A landed (all 5 source-miss visibility changes + Gemini review fixes #31-#35). Worker run confirmed counters wired (denominator = 63,081 mutually-exclusive buckets). Metrics row never reached Sheet1 due to viewport bug → PR-B.
- **PR#28** `claude/pr-c1-append-event-chokepoint` — merged 2026-04-21. PR-C1 landed: `_append_event()` chokepoint enforcing I1-I4, mass-violation circuit breaker (`Sheet1!X1`/`W1` durable visibility), state cell `Sheet1!Y1` for `last_successful_cycle_end_utc`, GitHub Actions `concurrency` block. Codex P1/P2 + Gemini denominator review fixes folded in. Zero bug-count delta — scaffolding for PR-C2+.

## Next PR (after PR-C2 merges)
After C2, the PR-C fix-passes (per-class) begin:
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
