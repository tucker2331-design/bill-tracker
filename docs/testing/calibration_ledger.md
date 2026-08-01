---
tags: [testing, calibration, ledger, stats]
updated: 2026-08-01
status: active
---

# Calibration ledger — every stat tested, so none is tested twice

**Machine-readable source of truth: `calibration_ledger.json`. This page is generated from it.**

**Before proposing a stat, grep this table.** If it is here it has been tested, and the result stands
unless the METHOD changes — a new completed session, a corrected definition, or a fixed leak.

**Method:** fit 2023 -> predict 2024; real bills (HB/SB) only; score = % reduction in mean absolute error vs predicting the session base rate. Positive = better than guessing. Negative = WORSE than guessing.

**Verdicts:** USABLE ≥5% · WEAK 2–5% · NOISE −1 to 2% · HARMFUL <−1% (*worse than guessing*) ·
CONDITIONAL (helps one outcome, harms the other) · DISQUALIFIED (invalid measurement — see the corrected
test it was superseded by).

Scores are **per outcome and do not transfer**. *out* = got out of committee · *pass* = passed its chamber.

| stat | out | pass | verdict | note |
|---|---|---|---|---|
| `patron_in_majority` | 5.4% | 7.9% | **USABLE** |  |
| `committee` | 7.2% | 3.8% | **USABLE** |  |
| `bill_type` | 6.9% | 1.3% | **USABLE** |  |
| `chamber` | 6.9% | 1.3% | **USABLE** |  |
| `majority_copatron_share` | 6.7% | 5.3% | **USABLE** |  |
| `patron_volume` | 6.4% | 0.8% | **USABLE** |  |
| `patron_matches_cmte_majority` | 2.9% | 5.4% | **USABLE** |  |
| `subject_primary` | 2.8% | 3.9% | **WEAK** |  |
| `member_id_band` | 3.6% | 2.5% | **WEAK** |  |
| `cmte_prior_on_this_subject` | 3.5% | 1.9% | **WEAK** |  |
| `subject_cmte_match` | 2.7% | 0.5% | **WEAK** |  |
| `cmte_load` | 2.7% | 1.6% | **WEAK** |  |
| `patron_on_cmte` | 1.2% | 2.6% | **WEAK** |  |
| `patron_bill_rank` | 2.3% | 0.2% | **WEAK** |  |
| `patron_prior_in_this_cmte` | -6.2% | 2.3% | **CONDITIONAL** | Helps on one outcome and is WORSE THAN GUESSING on the other — only ever usable for the outcome it was validated on, never as a general stat. |
| `patron_district_band` | 1.6% | -0.0% | **NOISE** |  |
| `patron_agrees_with_current_cmte` | -17.1% | 1.6% | **NOISE** | Corrected form of `patron_agrees_with_cmte`. PRIOR-session votes against the CURRENT committee roster (both knowable when the bill is referred). -17.1%/+1.6% = HARMFUL. Settled. |
| `patron_generosity` | 1.5% | -0.9% | **NOISE** |  |
| `text_versions_at_intro` | 0.5% | 1.3% | **NOISE** | Corrected form of `text_versions`. counting only versions dated ON OR BEFORE introduction (knowable at filing). +0.5%/+1.3% = NOISE. The original +77.9% was 100% leakage. No gem; settled. |
| `bipartisan_copatrons` | -0.3% | 0.8% | **NOISE** |  |
| `cmte_member_copatrons` | -0.2% | 0.7% | **NOISE** |  |
| `patron_prior_on_this_subject` | -1.0% | 0.7% | **NOISE** |  |
| `patron_count` | 0.3% | 0.6% | **NOISE** |  |
| `committee_size` | -0.4% | 0.5% | **NOISE** |  |
| `copatron_district_spread` | 0.0% | 0.5% | **NOISE** |  |
| `cross_chamber_copatrons` | -0.2% | 0.4% | **NOISE** |  |
| `money_committee` | 0.1% | 0.4% | **NOISE** |  |
| `emergency` | 0.1% | 0.3% | **NOISE** |  |
| `prefiled` | 0.0% | 0.1% | **NOISE** |  |
| `subject_count` | -0.2% | 0.1% | **NOISE** |  |
| `patron_network_breadth` | -0.4% | -0.1% | **NOISE** |  |
| `patron_prior_rate` | -2.5% | 1.0% | **HARMFUL** |  |
| `has_chief_copatron` | -2.2% | -0.1% | **HARMFUL** |  |
| `bipartisan_chief_pair` | -2.9% | -0.3% | **HARMFUL** |  |
| `patron_prior_loyalty` | -2.0% | -1.9% | **HARMFUL** | Corrected form of `patron_party_loyalty`. prior-session votes. -2.0%/-1.9% = HARMFUL. Settled. |
| `patron_party` | -7.4% | -2.5% | **HARMFUL** |  |
| `patron_prior_floor_win_rate` | -5.6% | -2.8% | **HARMFUL** | Corrected form of `patron_floor_win_rate`. prior-session votes. -5.6%/-2.8% = HARMFUL. Settled. |
| `text_versions` | 32.8% | 77.9% | **DISQUALIFIED** | RETESTED PROPERLY 2026-08-01 — counting only versions dated ON OR BEFORE introduction (knowable at filing). +0.5%/+1.3% = NOISE. The original +77.9% was 100% leakage. No gem; settled. |
| `patron_floor_win_rate` | 5.5% | 9.0% | **DISQUALIFIED** | RETESTED PROPERLY 2026-08-01 — prior-session votes. -5.6%/-2.8% = HARMFUL. Settled. |
| `patron_party_loyalty` | 6.5% | 6.8% | **DISQUALIFIED** | RETESTED PROPERLY 2026-08-01 — prior-session votes. -2.0%/-1.9% = HARMFUL. Settled. |
| `patron_agrees_with_cmte` | 6.0% | 5.0% | **DISQUALIFIED** | RETESTED PROPERLY 2026-08-01 — PRIOR-session votes against the CURRENT committee roster (both knowable when the bill is referred). -17.1%/+1.6% = HARMFUL. Settled. |

**All four DISQUALIFIED stats have now been retested properly (2026-08-01) and every one is NOISE or
HARMFUL.** The apparent signal was leakage or same-session contamination in all four cases. Settled — do
not re-run.

## Not yet tested — no result exists, do not assume one

Timing within the session · docket position (no pre-2025 docket) · vote margins · companion bills ·
fiscal impact (not published in bulk) · committee **chair** identity (no role field in the legacy roster) ·
patron seniority (start dates absent from the roster source) · cross-state comparison.

## Re-run only if
1. A new completed session lands (2025 closes → refit 2023+2024 → test 2025).
2. A definition is corrected — quote the new score, never the old one.
3. The outcome definition changes.

Narrative: [[testing/calibration_results]] · method and its weaknesses: [[testing/calibration_scope]].
