# Crossover Week Baseline (Feb 9-13, 2026)

## Why Crossover Week
Highest concentration of edge cases in the Virginia GA session:
- ~174 events/week (vs ~80 typical week)
- Bills crossing chambers (House -> Senate and vice versa)
- Mass committee referrals and re-referrals
- Subcommittee actions at peak volume
- Conference committees forming
- Relative time resolution under stress ("upon adjournment of X")

## Baseline Metrics (as of 2026-04-03, commit a42ddb2)
- X-Ray total rows: 20,783
- Rows missing time that LIS has: 0 (perfect)
- Journal entries collapsed: 13,250
- No-LIS-committee-match count: 4,229 (expected to decrease with parent fallback)
- Mismatch warnings: 343 (52% timing lag, 27% sub->parent, 21% cross-chamber)
- Worker runtime: ~4min 10-15s (up from ~2min before crossover window shift)

## What "100% Accuracy" Means
1. Every committee event that had a real scheduled time on LIS shows that time
2. Administrative/ledger actions show as "Journal Entry" under "Ledger Updates"
3. No phantom committee cards (all noise collapsed)
4. No false mismatch warnings surfaced to user
5. Subcommittee actions inherit parent committee time
6. Re-referral destinations correctly identified
