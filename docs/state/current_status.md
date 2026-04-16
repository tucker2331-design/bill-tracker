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
**Framework audit + silent-fallback remediation.** User identified that Section 9 was "only measuring the bugs we wanted to look at" — the worker has silent source-miss paths that hide un-timable rows instead of surfacing them. See [[failures/pr22_post_mortem]] for the framework lesson, [[state/open_anti_patterns]] for the concrete lines of debt, and [[workflow/source_miss_visibility]] for the new rule.

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| 22 | `claude/pr22-offered-admin-override` | **To be closed by user** | Premise invalidated. Will not merge. See [[failures/assumptions_audit]] #41 and [[failures/pr22_post_mortem]]. |

## Next PR (proposed, not yet approved)
**PR#23 — Worker instrumentation for source-miss visibility.**
1. Replace silent `"Journal Entry"` default in `calendar_worker.py` ~line 1181 with a visible `⏱️ [NO_SCHEDULE_MATCH]` tag + Bug_Logs row (`TIMING_LAG`).
2. Replace silent `continue` in ephemeral-language filter (~lines 1248-1261) with `alert_rows.append(...)`.
3. Tag Memory Anchor fallbacks for admin verbs too (not just dynamic), so provenance is preserved (~lines 1158-1167).
4. Preserve the `Journal Entry` origin column through the `📋 Ledger Updates` rename (~lines 1269-1275), so downstream can distinguish "admin action" from "un-timable meeting action."
5. Add X-Ray Section 0: "Rows processed / sourced / unsourced / dropped" — the denominator.

Not to be started without user approval. Current branch is dead once PR#22 is closed; PR#23 starts on a fresh branch from `origin/main` per [[workflow/branching_rules]].

## Known bug count (as of last measured X-Ray)
Crossover week, post-PR#21 (PR#22 reverted):
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
