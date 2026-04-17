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
**PR-A (worker source-miss visibility) in review.** Instrumentation-only PR — no classification changes. Replaces every silent fallback in `calendar_worker.py` with a visible tag + counted signal, adds the `Origin` column to Sheet1, and surfaces the denominator via X-Ray Section 0. Expected to make the bug count *go up* in the short term (un-hiding what was already broken). Subsequent PRs attack the largest unsourced category.

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| TBD | `claude/worker-source-miss-visibility` | **Open — PR-A, instrumentation-only** | 5 changes per [[workflow/source_miss_visibility]]: NO_SCHEDULE_MATCH tag, ephemeral-drop alert, Memory Anchor admin tag, Origin column preserved through Ledger rename, X-Ray Section 0 denominator. |

## Recently closed
- **PR#22** `claude/pr22-offered-admin-override` — closed unmerged. Premise invalidated. See [[failures/assumptions_audit]] #41 and [[failures/pr22_post_mortem]].
- **PR#23** `claude/docs-obsidian-brain` — merged 2026-04-16. Obsidian brain consolidation.
- **PR#24** `claude/pr23-gemini-review-fixes` — merged 2026-04-16. Gemini review follow-ups for PR#23 (placeholder link, severity alignment, `<module>` consistency, log accuracy, section-anchor wikilink).

## Next PR (after PR-A merges)
**Attack the largest unsourced category revealed by X-Ray Section 0.**
Once PR-A is running in production for one scheduled cycle, read Section 0. Whichever of `unsourced_journal` / `unsourced_anchor` / `floor_anchor_miss` / `dropped_ephemeral` is largest is the next PR's scope. Each follow-up PR must cite before/after counts from Section 0 to meet CLAUDE.md Standard #7.

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
