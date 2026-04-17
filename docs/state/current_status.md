---
tags: [state, live]
updated: 2026-04-16
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Feb 9-13, 2026 (crossover week).

## Active focus
**PR-B (metrics visibility + diagnostic hint) open.** Two targeted fixes on top of PR-A now that PR#25 has merged and run in production: (1) viewport slice was silently dropping the `SYSTEM_METRICS` row (stamped `Date=today`, outside Feb 9-13 window) so X-Ray Section 0 rendered blank; (2) NO_SCHEDULE_MATCH / NO_CONVENE_ANCHOR rows now carry a `DiagnosticHint` column showing `bill_locations[bill]` + nearest-3 same-chamber Schedule API candidates so the 9 in-window bugs can be triaged without re-running the worker.

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| TBD | `claude/pr-b-metrics-visibility-diagnostic` | **Open — PR-B** | (1) Exempt `Origin in {system_alert, system_metrics}` from viewport slice so denominator row reaches Sheet1. (2) Add `DiagnosticHint` column populated ONLY on source-miss rows (`journal_default` / `floor_miss`). Sheet1 schema: 10 → 11 columns. See [[failures/gemini_review_patterns]] #36-#37. |

## Recently closed
- **PR#22** `claude/pr22-offered-admin-override` — closed unmerged. Premise invalidated. See [[failures/assumptions_audit]] #41 and [[failures/pr22_post_mortem]].
- **PR#23** `claude/docs-obsidian-brain` — merged 2026-04-16. Obsidian brain consolidation.
- **PR#24** `claude/pr23-gemini-review-fixes` — merged 2026-04-16. Gemini review follow-ups for PR#23 (placeholder link, severity alignment, `<module>` consistency, log accuracy, section-anchor wikilink).
- **PR#25** `claude/worker-source-miss-visibility` — merged 2026-04-16. PR-A landed (all 5 source-miss visibility changes + Gemini review fixes #31-#35). Worker run confirmed counters wired (denominator = 63,081 mutually-exclusive buckets). Metrics row never reached Sheet1 due to viewport bug → PR-B.

## Next PR (after PR-B merges)
**Attack the largest unsourced category revealed by X-Ray Section 0 once SYSTEM_METRICS is visible.**
Once PR-B is running and Section 0 renders the denominator, identify which of `unsourced_journal` / `unsourced_anchor` / `floor_anchor_miss` / `dropped_ephemeral` is largest. Each follow-up PR must cite before/after counts from Section 0 to meet CLAUDE.md Standard #7.

## Known bug count (as of last measured X-Ray)
Crossover week, post-PR#21 (PR#22 never merged):
- Meeting actions without times: **9**
- Unclassified: **9** (same bucket; see breakdown in [[testing/crossover_week_baseline]])
- Caveat: **this 9 is the symptom count, not the source-miss count.** True source-miss rate will be higher once instrumentation lands. See [[state/open_anti_patterns]].

## Active architecture
Two parallel Streamlit apps and two scheduled workers. Full description in [[architecture/calendar_pipeline]].
- `backend_worker.py` — main product worker ("Mastermind Ghost Worker")
- `calendar_worker.py` — calendar subsystem worker ("Mastermind Ghost Worker 2"), being perfected before merging into v2
- `pages/ray2.py` — X-Ray diagnostic (Streamlit-served)
- `calendar_xray.py` — diff-identical backup of `pages/ray2.py`

## What changes this page
Anything that changes the answer to "what is Tucker working on right now?" — opening/closing a PR, changing the active bug count, shifting the goal, pausing/resuming a thread. The LLM updates this page on every session conclusion.
