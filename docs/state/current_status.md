---
tags: [state, live]
updated: 2026-04-25
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Feb 9-13, 2026 (crossover week).

## Active focus
**PR-C3 in flight — LegislationEvent API as secondary time source for Class-1 bugs.** The originally-planned PR-C2.1 (Playwright historical scraper) was reverted on 2026-04-25 after headless verification proved the premise wrong: no public web source has 2026 historical schedules the LIS Schedule API doesn't already expose. Deeper investigation surfaced the actual fix path — the LIS **LegislationEvent API** publishes minute-precision `EventDate` for every bill action, including the 4 Class-1 bug actions (HB111/505/972/609 on 2026-02-12) where the Schedule API has zero entries for the parent committee. Verification confirmed all four recoverable: HB111 → 9:02 PM, HB505 → 9:02 PM, HB972 → 9:03 PM, HB609 → 9:24 AM. Current commit on branch `claude/pr-c3-legislation-event-fallback` ships the surgical helper (`_resolve_via_legislation_event_api`) as fallback step 6 in the time-resolution chain, two new public-facing constants (`LIS_PUBLIC_API_KEY`, `LEGISLATION_EVENT_HEADERS`), 5-digit session-code normalization, per-cycle LegislationID cache, 3 new counters (`sourced_legislation_event` denominator + `legislation_event_attempted/recovered` orthogonal). 9-of-9 standalone unit-test cases pass (4 happy path + 5 negative). Bug-count delta target: **9 → 5** on the next worker run (the 4 Class-1 bugs collapse; 5 Class-2 subcommittee-attribution bugs remain for PR-C4). Two infrastructure gotchas captured in code + brain: (a) two distinct public WebAPIKeys (legacy worker key vs SPA public key), (b) 3-digit vs 5-digit session-code formats. See [[architecture/calendar_pipeline#Secondary Time Source via LegislationEvent (PR-C3)]] and [[knowledge/lis_api_reference]].

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| TBD | `claude/pr-c3-legislation-event-fallback` | **In flight — PR-C3** | Helper `_resolve_via_legislation_event_api()` as fallback step 6 in the Time Resolution chain (after API_Schedule / convene_anchor, before journal_default). Two-step LIS lookup (LegislationVersion → LegislationEvent). Targets the 4 Class-1 bugs on Feb 12. Standalone unit tests pass against all 4 verified bug cases. Awaiting worker run to confirm 9 → 5 bug-count delta. |

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
PR-C3 in flight (above); after merge:
- **PR-C4** — Subcommittee attribution resolver for Class 2 (5 bugs: HB24/1266/1372/SB494/SB555). LegislationEvent API (the PR-C3 hookup) gives TIME but `CommitteeNumber/CommitteeName` are `None` on vote-style events, so it doesn't help Class 2 directly. Likely needs `CommitteeLegislationReferral` API or `bill_locations` walking the SUBCOMMITTEE that received the action rather than the parent.
- **PR-C2.1 (deferred — invalidated)** — original Playwright historical scraper plan reverted on 2026-04-25 after headless verification. No public web source has 2026 historical schedules the API doesn't already expose.
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
