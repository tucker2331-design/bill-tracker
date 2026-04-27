---
tags: [state, live]
updated: 2026-04-27
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Feb 9-13, 2026 (crossover week).

## Active focus
**🎯🎯 BOTH halves of CLAUDE.md "done" criterion HIT for crossover week.** Worker run on PR-C5 code (PR #33 merged at `313e9a3`) reports X-Ray Section 9 = `0 meeting actions without times` AND `0 unclassified`. Crossover week is mathematically verified clean. The Feb 9-13 benchmark — the hardest concentration of edge cases in the VA GA session — passes the project's stated accuracy metric end-to-end. **PR-C5.1 in flight** (this branch — PR #34) closes the final residual: a worker-side `UNKNOWN_ACTION (1 row)` counter caused by a malformed HISTORY.CSV entry for SB584 on 2026-02-10 (description literally `"S "`, empty refid). Surgical structural guard at `calendar_worker.py:2316` detects empty-after-chamber-strip rows, emits a categorized `DATA_ANOMALY` alert (Zero-Trust visibility per CLAUDE.md Standard #4), skips, and increments `dropped_noise` to keep the denominator math intact. **Next strategic move (PR-D series): widen the investigation window from Feb 9-13 to full session (Jan 14 → May 1)** to stress-test the architecture at session scale per [[failures/assumptions_audit]] #5 ("When to fix: After calendar reaches 100% accuracy, set to session start date" — that gate is now passed). The owner has explicitly noted that v2_shadow_test currently fills a different role (front-end bill page) and will need to be reworked to match the calendar_worker advanced material before any subsystem merger. The forward calendar (upcoming weeks, not just history) is flagged as the more difficult future challenge.

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| 34 | `claude/pr-c5.1-sb584-outlier-and-writeback` | **Open — PR-C5.1** | Bundles (a) the structural malformed-HISTORY-row guard at `calendar_worker.py:2316` that closes the final `UNKNOWN_ACTION (1 row)` counter caused by SB584's 2026-02-10 `"S "` row, and (b) the post-milestone writeback (this page, [[log]] new milestone entry, [[testing/crossover_week_baseline]] closed-loop entry, [[failures/assumptions_audit]] #45 for the new lesson). Diff scope: `calendar_worker.py` + 4 docs files. No X-Ray changes (`pages/ray2.py` / `calendar_xray.py` untouched — diff-identical preserved). Expected next worker run: Section 5 `UNKNOWN_ACTION` 1 → 0; everything else unchanged; Section 8 may show one WARN row for the SB584 anomaly with the dedup_key (flooding-safe). |

## Recently closed
- **PR#33** `claude/pr-c5-unclassified-pattern-triage` — merged 2026-04-27 at `313e9a3`. PR-C5 landed: 5 substring patterns added to `ADMINISTRATIVE_PATTERNS` (`(view meeting)`, `no agenda listed`, `subcommittee info`, `speaker's conference room`, `[memory anchor: admin]`) covering buckets A/C/D/E/F of the 157 unclassified rows; `classify_action()` empty-outcome guard added (`if not lower or lower in ("none", "nan")`) covering bucket B. Files mirrored via `cp` to preserve diff-identical contract. Gemini PR review caught the original `lower == "none"` was missing pandas NaN — fixed mid-flight to `lower in ("none", "nan")` with comment block documenting why substring "nan" in `ADMINISTRATIVE_PATTERNS` would have been unsafe. Worker run delivered the second-half "done" milestone (Section 9 unclassified 157 → 0).
- **PR#32** `claude/pr-c31-docs-writeback-recovery` — merged 2026-04-26 at `c7838c1` (after merge `1b9bfc7`). Recovered the stranded PR-C3.1 writeback commit (`57dfc63`) that was pushed to a now-dead branch after PR #31 merged. Cherry-picked cleanly as `8950c0b` onto a fresh branch from main, then pushed Codex P2 fix (PR #31 row moved out of Open PRs table) and Gemini renumbering (added missing `#41` PR#22 line-level lesson, renumbered my entries to `#42/#43/#44`, updated 4 back-references in lockstep).
- **PR#31** `claude/pr-c3.1-legislation-event-cached` — merged 2026-04-26 at `a0fd135`. Re-introduced the PR-C3 LegislationEvent fallback with two surgical fixes: (a) `_legislation_event_cache` per-cycle keyed by (bill, session) — eliminates the N+1 fetch storm against LIS WAF; (b) gate tightened from `if origin == "journal_default":` to also require `MEETING_VERB_TOKENS` match — collapses candidate set from thousands of admin rows to actual meeting verbs. 13/13 tests passing. Worker run delivered the meeting-bug=0 milestone. Branch ancestry included a `-s ours` merge of main (commit `a2bb618`) to clear the revert-of-merge three-way conflict without force-push — see [[failures/assumptions_audit]] #44.
- **PR#30** `claude/pr-c3-legislation-event-fallback` — **MERGED 2026-04-25, REVERTED 2026-04-26** (revert commit `246cba5` on main). Original PR-C3 implementation hung the GitHub Actions worker for 11+ min (vs normal ~2 min) on the first post-merge cycle. Two compounding regressions, both surgical-fixed in PR-C3.1: N+1 LegislationEvent fetch (no per-cycle response cache) cascading on urllib3 Retry/backoff against the LIS WAF, and over-broad `journal_default` gate firing across the full session window for thousands of admin rows. See [[failures/assumptions_audit]] #42 and #43.
- **PR#29** `claude/pr-c2-gap-detection-witness-log` — merged 2026-04-24. PR-C2 landed: Y1 gap detection + 7 `gap_cause` classes; `Schedule_Witness` change-feed tab; HISTORY-vs-witness reconciliation with 7-day cap. Three rounds of Gemini review folded in. Zero bug-count delta — observability + data-recovery infrastructure.
- **PR#28** `claude/pr-c1-append-event-chokepoint` — merged 2026-04-21. PR-C1 landed: `_append_event()` chokepoint, mass-violation circuit breaker (`Sheet1!X1`/`W1`), state cell `Sheet1!Y1`, GitHub Actions `concurrency` block.
- **PR#27** `claude/crossover-audit` — merged 2026-04-20. Crossover-week full-universe audit confirmed the 9-bug count was real. Bug class distribution: 4 × Class 1 + 5 × Class 2.
- **PR#26** `claude/pr-b-metrics-visibility-diagnostic` — merged 2026-04-17. PR-B landed: `Origin` exemption + `DiagnosticHint` column.
- **PR#25** `claude/worker-source-miss-visibility` — merged 2026-04-16. PR-A landed (5 source-miss visibility changes).
- **PR#24, PR#23** — Obsidian brain consolidation + Gemini review follow-ups.
- **PR#22** `claude/pr22-offered-admin-override` — closed unmerged. Premise invalidated. See [[failures/assumptions_audit]] #41.

## Next PR (PR #34 in flight above)
- **PR-D series — Investigation window widening (Stress Test).** Once PR #34 merges, adjust `investigation_config.py` (`INVESTIGATION_START` = `2026-01-14`, `INVESTIGATION_END` = `2026-05-01`) to open the X-Ray and worker scope to the full 2026 session window. Re-run the worker; review X-Ray Section 9 + Section 5 + Ledger Health Check at session scale. Three outcomes possible: (1) numbers stay clean → architecture validated end-to-end → ready for v2_shadow_test integration discussion; (2) new bug classes surface that the crossover-week sample didn't expose → triage + targeted PR-D.1 / D.2 / etc.; (3) a single bug class dominates the residue → focused fix. Per CLAUDE.md Standard #7: every change cited with before/after counts from Section 0.
- **v2_shadow_test integration (deferred).** Owner-flagged: v2_shadow_test currently fills a different role (front-end bill page); the calendar subsystem we built has more advanced material than v2_shadow_test currently. v2 needs to be reworked to MATCH calendar_worker (not the other way around) before merger. Gated on PR-D series passing.
- **Forward calendar (upcoming weeks, not just history) — owner-flagged hardest future challenge.** All work to date is HISTORY.CSV-backed (past actions). Showing upcoming committee meetings before they happen requires a different signal source (Schedule API for the future window, plus reconciliation against actual outcomes as days pass). Scope and approach TBD; not part of the immediate PR-D queue.
- **PR-C2.1 (deferred — invalidated)** — original Playwright historical scraper plan reverted on 2026-04-25 after headless verification. No public web source has 2026 historical schedules the API doesn't already expose. Kept in this list only so the absence isn't mistaken for an oversight.

## Known bug count (as of 2026-04-27 worker run, post PR-C5)
Crossover week, Feb 9-13 2026:
- **Meeting actions without times: 0** ✓ (was 9 — collapsed by PR-C3.1)
- **Unclassified: 0** ✓ (was 157 — collapsed by PR-C5)
- Worker-side `UNKNOWN_ACTION` counter: 1 (SB584 malformed HISTORY row — closes to 0 with PR #34 / PR-C5.1)
- LegislationEvent telemetry: 185 attempted / 182 recovered / 3 abstained (zero-overlap or wrong-chamber safety nets working as designed)
- Source-bucket math holds: `sourced_api(12,324) + sourced_convene(32,429) + sourced_legislation_event(182) + unsourced_journal(6,553) + floor_anchor_miss(6,571) + dropped_noise(6,696) = 64,755 = total_processed` (denominator drift = 0)
- Section 7 (Sheet vs LIS time parity): 0 rows missing time in Sheet but with time in LIS — perfect parity on resolvable cases
- Section 8: 0 system alerts (will show 1 WARN with dedup_key after PR #34 merges, for the SB584 malformed-row anomaly)
- Ledger Health Check: 428 admin / 0 meeting bugs / 0 unclassified — clean

## Active architecture
Two parallel Streamlit apps and two scheduled workers. Full description in [[architecture/calendar_pipeline]].
- `backend_worker.py` — main product worker ("Mastermind Ghost Worker") — front-end bill page; **needs rework to match calendar_worker advanced material before any subsystem merger** (owner-flagged 2026-04-27)
- `calendar_worker.py` — calendar subsystem worker ("Mastermind Ghost Worker 2"), **architecture proven on crossover week 2026-04-27**
- `pages/ray2.py` — X-Ray diagnostic (Streamlit-served)
- `calendar_xray.py` — diff-identical backup of `pages/ray2.py`

## What changes this page
Anything that changes the answer to "what is Tucker working on right now?" — opening/closing a PR, changing the active bug count, shifting the goal, pausing/resuming a thread. The LLM updates this page on every session conclusion.
