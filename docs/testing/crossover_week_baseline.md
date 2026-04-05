# Crossover Week Baseline (Feb 9-13, 2026)

## Why Crossover Week
Highest concentration of edge cases in the Virginia GA session:
- ~174 events/week (vs ~80 typical week)
- Bills crossing chambers (House -> Senate and vice versa)
- Mass committee referrals and re-referrals
- Subcommittee actions at peak volume
- Conference committees forming
- Relative time resolution under stress ("upon adjournment of X")

## Baseline Metrics (as of 2026-04-05, build 2026-04-05.2)

### X-Ray Section 9 — Action Classification Audit (THE METRIC)
- Meeting actions WITH times: 10,414
- **Meeting actions WITHOUT times: 1,212** (THE BUG COUNT)
- Administrative actions: 6,413 (1,675 without time = correct Ledger)
- Unclassified actions: 3,150 (pattern gap, being resolved)
- **Accuracy: 89.6%** (10,414 / 11,626 meeting actions have times)

### Ledger Health Check
- Total Ledger rows: 3,237
- Admin (correct): 1,589
- **Meeting actions hiding in Ledger: 979** (subset of the 1,212 bugs)
- Top Ledger bugs by type: passed (408), agreed to (169), read first (149), approved by governor (48), offered (43)

### Previous Metrics
- Rows missing time that LIS has (Section 7): 0 (still holds but only measures matched committees)
- No-LIS-committee-match: 3,237 (all Ledger Updates — expected)
- lis_time_not_concrete: 507

### Root Causes Identified
1. **Convene time gaps (~750 bugs):** Floor actions (passed, read first, agreed to) on dates where convene_times dict has no entry. Expanded name matching + added diagnostic logging.
2. **Committee TBA → child lookup (~230 bugs):** Parent committee has "Time TBA" but subcommittees have concrete times. Added parent→child schedule lookup.
3. **Pattern gap (3,150 unclassified):** Governor's Action Deadline, Scheduled, Left in, etc. not in classification lists. Fixed.

## What "100% Accuracy" Means
1. Every meeting action (vote, report, reading, recommendation) has the time it happened
2. Administrative actions (referrals, printing, filing) are in Ledger with no time expectation
3. Zero unclassified actions (every action type assigned to meeting or administrative)
4. Ledger Health Check shows zero meeting actions hiding in Ledger
5. X-Ray Section 9 bug count = 0
