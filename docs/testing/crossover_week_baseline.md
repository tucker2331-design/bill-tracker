# Crossover Week Baseline (Feb 9-13, 2026)

## STATUS — DONE (2026-04-27)

**Both halves of CLAUDE.md "done" criterion HIT for crossover week.**

| Metric | Final | Δ from baseline |
|---|---:|---:|
| Meeting actions without times (Section 9 bug count) | **0** ✓ | -1,138 (-100%) |
| Unclassified actions (Section 9 REVIEW) | **0** ✓ | -731 (-100%) |
| Meeting actions hiding in Ledger | **0** ✓ | -453 (-100%) |
| Worker-side `UNKNOWN_ACTION` counter | 1 → **0** (PR #34 in flight) | -1 outlier |

This page is preserved as the historical progress tracker; the live-state page is [[state/current_status]]. The page is closed-loop — no further bug-count updates expected. Reopen only if a regression surfaces in a future worker run, or if the architecture is reworked in a way that invalidates the metric.

**The two PRs that closed it:**
- [[log#2026-04-26-milestone--meeting-actions-without-times--0-first-half-of-claudemd-done-hit]] — PR-C3.1 (PR #31) collapsed the 9 meeting-bug residue (4 × Class-1 + 5 × Class-2, both via the LegislationEvent fallback's bill+date+chamber keying)
- [[log#2026-04-27-milestone--both-halves-of-claudemd-done-criterion-hit-for-crossover-week]] — PR-C5 (PR #33) collapsed the 157 unclassified residue (5 substring patterns + empty-outcome guard handling pandas NaN)

**The framework lessons that made it possible** (chronological):
- [[failures/pr22_post_mortem]] / [[failures/assumptions_audit]] #41 — PR#22 rejected; reclassification PRs require semantic justification, not metric convenience
- [[workflow/source_miss_visibility]] (PR-A / PR#25) — every source-miss must emit a visible counted signal; no silent defaults
- [[testing/crossover_audit]] (PR#27) — full-universe ground truth proved the 9-bug count was honest
- [[failures/assumptions_audit]] #42 / #43 — PR-C3 N+1 + over-broad gate post-mortem; "candidate-set sizing" check added to pre-push audit
- [[failures/assumptions_audit]] #44 — `git merge -s ours` is the right operation for revert-of-merge feature branches
- [[failures/assumptions_audit]] #45 — "missing pattern" vs "malformed upstream row" are different failure modes (PR-C5.1)

**What this milestone unlocks:** the investigation window can widen from the Feb 9-13 test value to the full session (Jan 14 → May 1) per [[failures/assumptions_audit]] #5. That is the next strategic move (PR-D series) — see [[state/current_status#next-pr-pr-34-in-flight-above]].

---

## Why Crossover Week
Highest concentration of edge cases in the Virginia GA session:
- ~174 events/week (vs ~80 typical week)
- Bills crossing chambers (House -> Senate and vice versa)
- Mass committee referrals and re-referrals
- Subcommittee actions at peak volume
- Conference committees forming
- Relative time resolution under stress ("upon adjournment of X")

## Historical Metrics (as of 2026-04-12, post-PR#16)

### X-Ray Section 9 — Action Classification Audit (THE METRIC)
- Meeting actions WITH times: 10,883
- **Meeting actions WITHOUT times: 459** (THE BUG COUNT)
- Administrative actions: 6,947 with time + 2,784 without = 9,731 total (OK)
- Unclassified actions: 647 with time + 84 without = 731 total (REVIEW)
- **Accuracy: 96.0%** (10,883 / 11,342 meeting actions have times)

### Ledger Health Check
- Total Ledger rows: 3,163
- Admin (correct): 2,710
- **Meeting actions hiding in Ledger: 453** (subset of the 459 bugs)
- Unclassified in Ledger: 0

### Section 4 — Placeholder Time Audit
- Rows with placeholder/missing time: 3,307
- placeholder journal entry: 3,163
- placeholder time tba: 144

### Progress Tracker

| PR | Bug Count | Delta | Key Fix |
|----|-----------|-------|---------|
| PR#14 baseline | 1,138 | — | Classification + NOISE/EVENT cleanup |
| PR#15 | 862 | -276 | Whitespace normalization, session marker fallback |
| PR#16 | 459 | -403 | Sub-panel schedule matching, map overwrite protection |
| PR#17 | 427* | -32 | Subcommittee refid regex fix (1,637 refids unlocked) |
| PR#18 | 544* | +117 | Prefiled/offered classification override. Worker no-op (no Sheet1 rows matched). Apparent +117 was rolling-window expansion, not regression. |
| PR#19 (pending) | 9 target | — | Window alignment: pin worker + X-Ray to `INVESTIGATION_START/END = Feb 9-13`. True crossover bug count revealed. |

\* PR#14-18 numbers were unfiltered totals; the "rolling end date" in the worker made the bug count grow mechanically every day regardless of code changes. PR#19 collapses the metric to the pinned investigation window. Going forward, deltas between PRs are comparable only after PR#19.

### Root Causes Identified
1. ~~**Convene time gaps (~750 bugs):** Fixed in PR#15~~ ✅
2. ~~**Committee TBA → child lookup (~230 bugs):** Fixed in PR#16~~ ✅
3. ~~**Pattern gap (3,150 unclassified):** Fixed in PR#14~~ ✅
4. **Subcommittee refid regex (453 bugs):** Regex missed H14003V... format. Fix in PR#17.
5. **Post-March-14 dates (~353):** No Schedule API data. Not code-fixable without alternative source.
6. **Committee TBA with no sub-panels:** Some committees genuinely have no times anywhere.

## What "100% Accuracy" Means
1. Every meeting action (vote, report, reading, recommendation) has the time it happened ✓
2. Administrative actions (referrals, printing, filing) are in Ledger with no time expectation ✓
3. Zero unclassified actions (every action type assigned to meeting or administrative) ✓
4. Ledger Health Check shows zero meeting actions hiding in Ledger ✓
5. X-Ray Section 9 bug count = 0 ✓

**All 5 satisfied for crossover week as of 2026-04-27.**
