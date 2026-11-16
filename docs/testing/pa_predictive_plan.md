---
tags: [testing, prediction, pa, plan]
updated: 2026-11-16
status: stub
open_loop: Owner ask 2026-11-16 ("run VA-style stats on PA to build predictive models") — plan written; step 1 (PA bill-fate baseline on the 2025-26 export) is next, step 3 needs a per-member roll-call source scoped first.
---

# Virginia-style statistics on Pennsylvania — the plan (owner ask, 2026-11-16)

The Virginia work this mirrors: [[testing/bill_fate]] (fate at the first committee), [[testing/first_vote]] (how each
member votes), [[testing/influence_and_sources]] (chair co-sponsorship), [[testing/room_memory]]. Same protocol: a
tuning year, a frozen pre-registration, ONE locked test, every number with its denominator.

## What PA's own data holds (measured on the 2025-26 export, `tools/historical_cache/pa/2025_0/`, 31 Oct 2026)

| field | count | use |
|---|---|---|
| bills + resolutions | 5,269 | the universe |
| actions (verb, committee, date, chamber) | 19,915 | fate: referred → reported / tabled / re-committed / passed |
| actions with a roll-call TALLY, e.g. "(195-8)" | 1,448 | margins only — **no per-member votes** in the export |
| sponsor rows (party, district, sequence: 01 = prime) | 71,213 | patron party, majority status, co-sponsor count, bipartisan co-sponsorship |
| committee rosters (chair / member) | from PA's RSS (`states/pa_roster.py`) | chair co-sponsors the bill? (VA's strongest replicated signal) |

## First measurement — the majority gap (2026-11-16, descriptive, not a model)

Bills only (HB/SB, 4,184), 2025-26 export of 31 Oct 2026. Majority party per chamber from PA's own member feeds
(`parss:Party`: House D 103 / R 100, Senate R 27 / D 23). "Reported" = the bill has any action of verb class
`reported` (out of committee); everything else is still in, or died in, its first committee.

| chamber | prime sponsor | bills | reported out of committee | rate |
|---|---|---|---|---|
| House | majority (D) | 1,780 | 717 | 40% |
| House | minority (R) | 977 | 132 | 14% |
| Senate | majority (R) | 815 | 323 | 40% |
| Senate | minority (D) | 612 | 41 | 7% |

The same shape as Virginia's ([[testing/bill_fate]]: majority bills advance far more often) — so the fate model's
strongest input carries over. Not yet a prediction: no tuning year, no locked test. Script: inline in the session of
2026-11-16; to be moved into `tools/calibration/` with step 1.

## The steps, in order of what the data supports today

1. **Bill fate at the first committee** (VA [[testing/bill_fate]]). Outcomes from PA's own verb classes
   (`states/pa_adapter.VERB_CLASS`): reported / tabled / re-committed / never acted on. Inputs: prime sponsor's party
   vs the chamber majority, co-sponsor count, bipartisan co-sponsorship, chair co-sponsoring. **Fully sourced now.**
   PA is a two-year session: the "tuning year" is the 2023-24 export (needs one more polite download), the locked
   test 2025-26.
2. **Majority roll rate** (VA: majority rolled 1.4-5.6%, minority 20-43%). PA tallies give margins but not which
   party lost — needs per-member votes (step 3), or party-line tallies inferred only as an internal diagnostic.
3. **How each member votes** (VA [[testing/first_vote]], 85.9% on the locked 2026 test). **Blocked on a source:**
   PA's export has tallies only. Scope first: does PA publish per-member roll calls in a bulk or feed form that the
   PA fetch rules allow ([[knowledge/pa_bill_history_xml]] — the per-bill pages are robots-protected)?
4. **Display** stays under [[ideas/predictive_lane]]'s Tier rule: nothing predictive reaches the PA site without the
   calibration gate and the owner's go/no-go — PA's War Room ships with no vote predictions by owner decision.
