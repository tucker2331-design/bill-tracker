---
tags: [state, live]
updated: 2026-04-21
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Feb 9-13, 2026 (crossover week).

## Active focus
**PR-C1 opened — write-time safety rails + state scaffolding.** First PR in the PR-C series. Lands four pieces of infrastructure that PR-C2+ (the actual bug fixes) depend on: (1) single write-time chokepoint `_append_event()` enforcing invariants I1 (schema completeness), I2 (Origin enum), I3 (Time/Origin parity for concrete sources), I4 (meeting-verb telemetry); (2) mass-violation circuit breaker that refuses the Sheet1 overwrite on >10% violation rate / ≥50 absolute violations / ≥50 meeting_unsourced, preserving last-known-good data; (3) state cell `Sheet1!Y1` holding `last_successful_cycle_end_utc` (read in C1, consumed by C2 for gap-backfill); (4) GitHub Actions `concurrency` block queuing overlapping cycles. Zero bug-count delta expected from C1 alone — this is the scaffolding that makes subsequent fix-passes auditable. The crossover-audit-confirmed 9-bug target (4×Class 1 Schedule API gaps + 5×Class 2 subcommittee attribution misses) is the scope for PR-C2+. See [[testing/crossover_audit]] and [[architecture/calendar_pipeline#Write-Time Safety Rails (PR-C1)]].

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| TBD | `claude/pr-c1-append-event-chokepoint` | **Open — PR-C1** | Write-time safety rails + state scaffolding. (1) `_append_event()` chokepoint in `run_calendar_update` enforcing I1-I4. (2) Mass-violation circuit breaker preserving last-known-good Sheet1 on threshold trip. (3) State cell `Sheet1!Y1` read/write for `last_successful_cycle_end_utc` cursor. (4) YAML `concurrency: { group: calendar-worker, cancel-in-progress: false }` on calendar_worker workflow. (5) Two new orthogonal counters in `source_miss_counts`: `invariant_violations`, `meeting_unsourced`. Scaffolding for PR-C2+; no bug-count change expected. See [[architecture/calendar_pipeline#Write-Time Safety Rails (PR-C1)]]. |
| TBD | `claude/pr-b-metrics-visibility-diagnostic` | **Open — PR-B** | (1) Exempt `Origin in {system_alert, system_metrics}` from viewport slice so denominator row reaches Sheet1. (2) Add `DiagnosticHint` column populated ONLY on source-miss rows (`journal_default` / `floor_miss`). Sheet1 schema: 10 → 11 columns. See [[failures/gemini_review_patterns]] #36-#37. |

## Recently closed
- **PR#22** `claude/pr22-offered-admin-override` — closed unmerged. Premise invalidated. See [[failures/assumptions_audit]] #41 and [[failures/pr22_post_mortem]].
- **PR#23** `claude/docs-obsidian-brain` — merged 2026-04-16. Obsidian brain consolidation.
- **PR#24** `claude/pr23-gemini-review-fixes` — merged 2026-04-16. Gemini review follow-ups for PR#23 (placeholder link, severity alignment, `<module>` consistency, log accuracy, section-anchor wikilink).
- **PR#25** `claude/worker-source-miss-visibility` — merged 2026-04-16. PR-A landed (all 5 source-miss visibility changes + Gemini review fixes #31-#35). Worker run confirmed counters wired (denominator = 63,081 mutually-exclusive buckets). Metrics row never reached Sheet1 due to viewport bug → PR-B.

## Next PR (after PR-C1 merges)
**PR-C2: gap-backfill using the `Y1` cursor.** PR-C1 lands the write side of the cursor (Y1 advance on successful overwrite, left alone on breaker trip). PR-C2 consumes it as the "since" cursor so a failed/skipped cycle's window is automatically re-processed on the next healthy run. After C2, the PR-C fix-passes (per-class) begin:
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
