---
tags: [state, live]
updated: 2026-04-26
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Feb 9-13, 2026 (crossover week).

## Active focus
**🎯 First half of "done" criterion HIT — meeting actions without times = 0.** PR-C3.1 (PR #31) replaces the reverted PR-C3 (PR #30) and lands the LegislationEvent fallback safely. Worker run on the merged code shows X-Ray Section 9 = `0 meeting actions without times` (was 9 — all 4 Class-1 + all 5 Class-2 bugs collapsed in a single PR). LegEvent attempted = 185, recovered = 182 (98.4% hit rate). Worker completes a normal cycle (~2 min) — no recurrence of the Apr 25 hang. PR-C4 is provisionally **retired** (see [Class-2 collapse note](#class-2-collapse-via-legislationevent-pr-c31-side-effect) below). Remaining work to hit full "done": **unclassified = 157** (Section 9 REVIEW bucket, mostly meta/agenda rows the worker is treating as actions). PR-C5 will triage these into NOISE / ADMIN pattern lists.

### Class-2 collapse via LegislationEvent (PR-C3.1 side-effect)
Original plan: PR-C3 fixes 4 × Class-1, PR-C4 (subcommittee attribution resolver) fixes 5 × Class-2. Observed: PR-C3.1 fixed *all 9*. Mechanism (verified by reading `MEETING_VERB_TOKENS` at `calendar_worker.py:362`): the canonical allowlist contains both `"subcommittee offered"` (line 375 — matches HB24/1266/SB494/SB555 outcomes) and `"recommends continuing"` (line 365 — matches HB1372). All 5 Class-2 outcomes pass the PR-C3.1 gate. The LegislationEvent endpoint is keyed by **bill + date + chamber**, NOT by committee — so subcommittee-vs-parent attribution doesn't gate the time recovery. Time accuracy ✓; committee-name accuracy in the Sheet1 `Committee` column may still show parent or "Memory Anchor" for these rows, but that is *not* the project's bug-count metric (CLAUDE.md §"Current Goal": "every action that happened in a meeting must show the time of that meeting"). PR-C4 retired unless a separate committee-attribution accuracy goal is opened.

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| 31 | `claude/pr-c3.1-legislation-event-cached` | **Open — PR-C3.1, MERGEABLE** | Re-introduces PR-C3 LegislationEvent fallback with two surgical fixes: (a) `_legislation_event_cache` per-cycle keyed by (bill, session) — eliminates N+1 fetch storm against LIS WAF; (b) gate tightened from `if origin == "journal_default":` to also require `MEETING_VERB_TOKENS` match — collapses candidate set from thousands of admin rows to actual meeting verbs. Codex P1 outcome_text matcher + Codex P2 denominator + Gemini type-safety + session-code limitation from PR-C3 round-2 preserved unchanged. 13/13 tests passing (`test_pr_c3_helper_v2.py`). Worker run delivered the meeting-bug=0 milestone. Branch ancestry includes a `-s ours` merge of main (commit `a2bb618`) to clear the revert-of-merge three-way conflict without force-push — see [[failures/assumptions_audit]] #43. |

## Recently closed
- **PR#30** `claude/pr-c3-legislation-event-fallback` — **MERGED 2026-04-25, REVERTED 2026-04-26** (revert commit `246cba5` on main). Original PR-C3 implementation hung the GitHub Actions worker for 11+ min (vs normal ~2 min) on the first post-merge cycle. Two compounding regressions, both surgical-fixed in PR-C3.1: N+1 LegislationEvent fetch (no per-cycle response cache) cascading on urllib3 Retry/backoff against the LIS WAF, and over-broad `journal_default` gate firing across the full session window for thousands of admin rows. See [[failures/assumptions_audit]] #41 and #42.
- **PR#29** `claude/pr-c2-gap-detection-witness-log` — merged 2026-04-24. PR-C2 landed: Y1 gap detection + 7 `gap_cause` classes (WARN @ >20m, CRITICAL @ >60m or stale-cursor); `Schedule_Witness` change-feed tab (13 cols, whitelist-iterated `WITNESS_DELTA_FIELDS = (Time, SortTime, Status, Location)`, migration burst guard, retention deferred to L3b); HISTORY-vs-witness reconciliation with 7-day cap + CRITICAL-over-cap alert. Three rounds of Gemini review folded in (round-2: Location delta + prune→L3b + canary; round-3: `col_values()` scale-cliff fix). Zero bug-count delta — observability + data-recovery infrastructure. New `source_miss_counts` counters: `gap_minutes`, `gap_cause`, `witness_rows`, `witness_location_backfills`, `reconciliation_blind_dates`, `reconciliation_checked_dates`.
- **PR#28** `claude/pr-c1-append-event-chokepoint` — merged 2026-04-21. PR-C1 landed: `_append_event()` chokepoint enforcing I1-I4, mass-violation circuit breaker (`Sheet1!X1`/`W1` durable visibility), state cell `Sheet1!Y1` for `last_successful_cycle_end_utc`, GitHub Actions `concurrency` block. Codex P1/P2 + Gemini denominator review fixes folded in. Zero bug-count delta — scaffolding for PR-C2+.
- **PR#27** `claude/crossover-audit` — merged 2026-04-20. Crossover-week full-universe audit confirmed the 9-bug count is real (no hidden meeting-misclass, phantom rows, or silent bill-drops). Bug class distribution: 4 × Class 1 (Schedule API gap at full committee), 5 × Class 2 (subcommittee attribution miss). Documented in [[testing/crossover_audit#findings]].
- **PR#26** `claude/pr-b-metrics-visibility-diagnostic` — merged 2026-04-17. PR-B landed: (1) `Origin in {system_alert, system_metrics}` exempt from viewport slice (denominator row now reaches Sheet1); (2) `DiagnosticHint` column populated on `journal_default` / `floor_miss` rows. Sheet1 schema: 10 → 11 columns. See [[failures/gemini_review_patterns]] #36-#37.
- **PR#25** `claude/worker-source-miss-visibility` — merged 2026-04-16. PR-A landed (all 5 source-miss visibility changes + Gemini review fixes #31-#35). Worker run confirmed counters wired (denominator = 63,081 mutually-exclusive buckets). Metrics row never reached Sheet1 due to viewport bug → fixed in PR-B.
- **PR#24** `claude/pr23-gemini-review-fixes` — merged 2026-04-16. Gemini review follow-ups for PR#23 (placeholder link, severity alignment, `<module>` consistency, log accuracy, section-anchor wikilink).
- **PR#23** `claude/docs-obsidian-brain` — merged 2026-04-16. Obsidian brain consolidation.
- **PR#22** `claude/pr22-offered-admin-override` — closed unmerged. Premise invalidated. See [[failures/assumptions_audit]] #41 (numbering pre-2026-04-26; not the post-mortem entry of the same number — this one is the PR#22 lesson recorded earlier and is unchanged).

## Next PR (after PR#31 merges)
- **PR-C4 — RETIRED.** Class-2 attribution miss collapsed as a side-effect of PR-C3.1 (LegislationEvent is committee-agnostic; see [Class-2 collapse note](#class-2-collapse-via-legislationevent-pr-c31-side-effect) above). Re-open only if committee-name accuracy in Sheet1 is later promoted to a tracked metric.
- **PR-C5 — Unclassified pattern triage.** X-Ray Section 9 reports **157 unclassified actions** flagged REVIEW. Sample inspection shows they are predominantly *meta rows* — agenda links (`(Agenda)(View Meeting)`), convene anchors (`House Convenes 12:00 PM`), and "Immediately upon adjournment of …" continuations. They don't fit either MEETING_ACTION_PATTERNS or ADMINISTRATIVE_PATTERNS in `pages/ray2.py`/`calendar_xray.py` (and the corresponding KNOWN_NOISE_PATTERNS / KNOWN_EVENT_PATTERNS in `calendar_worker.py`). PR-C5 walks the 157 raw_action distinct values, categorizes each into NOISE (drop) or ADMIN (Ledger), ships pattern additions, and re-runs the X-Ray to confirm REVIEW = 0. **This is the second half of CLAUDE.md's "done" criterion** — when this lands, both meeting bugs and unclassified hit zero and crossover week is mathematically verified clean.
- **PR-C2.1 (deferred — invalidated)** — original Playwright historical scraper plan reverted on 2026-04-25 after headless verification. No public web source has 2026 historical schedules the API doesn't already expose. Kept in this list only so the absence isn't mistaken for an oversight.

## Known bug count (as of 2026-04-26 worker run, post PR-C3.1)
Crossover week, Feb 9-13 2026:
- **Meeting actions without times: 0** ✓ (was 9 — collapsed by PR-C3.1)
- **Unclassified: 157** (Section 9 REVIEW bucket — meta/agenda rows; PR-C5 target)
- LegislationEvent telemetry: 185 attempted / 182 recovered / 3 abstained (zero-overlap or wrong-chamber safety nets working as designed)
- Source-bucket math holds: `sourced_api(12,324) + sourced_convene(32,429) + sourced_legislation_event(182) + unsourced_journal(6,553) + floor_anchor_miss(6,571) + dropped_noise(6,696) = 64,755 = total_processed` (denominator drift = 0)
- Section 7 (Sheet vs LIS time parity): 0 rows missing time in Sheet but with time in LIS — perfect parity on resolvable cases
- Section 8: 0 system alerts
- Ledger Health Check: 428 admin / 0 meeting bugs / 0 unclassified — clean

## Active architecture
Two parallel Streamlit apps and two scheduled workers. Full description in [[architecture/calendar_pipeline]].
- `backend_worker.py` — main product worker ("Mastermind Ghost Worker")
- `calendar_worker.py` — calendar subsystem worker ("Mastermind Ghost Worker 2"), being perfected before merging into v2
- `pages/ray2.py` — X-Ray diagnostic (Streamlit-served)
- `calendar_xray.py` — diff-identical backup of `pages/ray2.py`

## What changes this page
Anything that changes the answer to "what is Tucker working on right now?" — opening/closing a PR, changing the active bug count, shifting the goal, pausing/resuming a thread. The LLM updates this page on every session conclusion.
