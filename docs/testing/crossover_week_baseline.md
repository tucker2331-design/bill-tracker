# Crossover Week Baseline (Feb 9-13, 2026)

## Why Crossover Week
Highest concentration of edge cases in the Virginia GA session:
- ~174 events/week (vs ~80 typical week)
- Bills crossing chambers (House -> Senate and vice versa)
- Mass committee referrals and re-referrals
- Subcommittee actions at peak volume
- Conference committees forming
- Relative time resolution under stress ("upon adjournment of X")

## Current Metrics (as of 2026-04-12, post-PR#16)

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
| PR#20 | 9 | — | Streamlit subpage sys.path prelude (ModuleNotFoundError fix for `investigation_config`). No metric change. |
| PR#21 | 9 | — | `_REPO_ROOT` dir-name check → file-existence probe (Gemini robustness fix). No metric change. |
| PR#22 (simulated) | 1 | -8 | `[chamber] (sub)committee offered` → `ADMIN_OVERRIDE_PATTERNS`. 8 orphan clerical-record rows moved out of Section 9. HB1372 Memory Anchor remains (bucket B — LIS has entry but blank time only). See assumptions_audit #41. |

\* PR#14-18 numbers were unfiltered totals; the "rolling end date" in the worker made the bug count grow mechanically every day regardless of code changes. PR#19 collapses the metric to the pinned investigation window. Going forward, deltas between PRs are comparable only after PR#19.

### Root Causes Identified
1. ~~**Convene time gaps (~750 bugs):** Fixed in PR#15~~ ✅
2. ~~**Committee TBA → child lookup (~230 bugs):** Fixed in PR#16~~ ✅
3. ~~**Pattern gap (3,150 unclassified):** Fixed in PR#14~~ ✅
4. **Subcommittee refid regex (453 bugs):** Regex missed H14003V... format. Fix in PR#17.
5. **Post-March-14 dates (~353):** No Schedule API data. Not code-fixable without alternative source.
6. **Committee TBA with no sub-panels:** Some committees genuinely have no times anywhere.

## What "100% Accuracy" Means
1. Every meeting action (vote, report, reading, recommendation) has the time it happened
2. Administrative actions (referrals, printing, filing) are in Ledger with no time expectation
3. Zero unclassified actions (every action type assigned to meeting or administrative)
4. Ledger Health Check shows zero meeting actions hiding in Ledger
5. X-Ray Section 9 bug count = 0
