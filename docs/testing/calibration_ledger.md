---
tags: [testing, calibration, ledger, stats]
updated: 2026-08-01
status: active
---

# Calibration ledger — every stat tested, so none is tested twice

**Machine-readable source of truth: `calibration_ledger.json`. This page is generated from it.**

**Before proposing a stat, grep this table.** If it is here it has been tested and the result stands
unless the METHOD changes — a new completed session, a corrected definition, or a fixed leak.

**Method:** fit 2023 -> predict 2024; real bills (HB/SB) only; score = % reduction in mean absolute error vs predicting the session base rate. Positive = better than guessing. Negative = WORSE than guessing.

**Verdicts:** USABLE ≥5% · WEAK 2–5% · NOISE −1 to 2% · HARMFUL <−1% (*worse than guessing*) ·
CONDITIONAL (helps one outcome, harms the other) · DISQUALIFIED (invalid measurement — superseded).

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
| `dls_tag` | 0.7% | 1.8% | **NOISE** | ADHD round. ADHD/lobbyist frame's strongest tell — the DLS drafting clause after the final semicolon ('; penalty', '; report'). 13 buckets, real variation, no signal. |
| `patron_district_band` | 1.6% | -0.0% | **NOISE** |  |
| `patron_agrees_with_current_cmte` | -17.1% | 1.6% | **NOISE** | Corrected form of `patron_agrees_with_cmte`. PRIOR-session votes against the CURRENT committee roster (both knowable when the bill is referred). -17.1%/+1.6% = HARMFUL. Settled. |
| `patron_generosity` | 1.5% | -0.9% | **NOISE** |  |
| `text_versions_at_intro` | 0.5% | 1.3% | **NOISE** | Corrected form of `text_versions`. counting only versions dated ON OR BEFORE introduction (knowable at filing). +0.5%/+1.3% = NOISE. The original +77.9% was 100% leakage. No gem; settled. |
| `same_day_batch` | 1.0% | 0.1% | **NOISE** | ADHD round. How many bills the patron filed the same day. |
| `bipartisan_copatrons` | -0.3% | 0.8% | **NOISE** |  |
| `cmte_member_copatrons` | -0.2% | 0.7% | **NOISE** |  |
| `patron_prior_on_this_subject` | -1.0% | 0.7% | **NOISE** |  |
| `patron_count` | 0.3% | 0.6% | **NOISE** |  |
| `committee_size` | -0.4% | 0.5% | **NOISE** |  |
| `copatron_district_spread` | 0.0% | 0.5% | **NOISE** |  |
| `cross_chamber_copatrons` | -0.2% | 0.4% | **NOISE** |  |
| `money_committee` | 0.1% | 0.4% | **NOISE** |  |
| `names_locality` | 0.1% | 0.4% | **NOISE** | ADHD round. Catchline names a County/City/Town (a 'courtesy bill'). Only 34 of 2,284, so thin either way. |
| `emergency` | 0.1% | 0.3% | **NOISE** |  |
| `filing_recency_band` | 0.3% | -0.0% | **NOISE** | ADHD round. When in the filing window the bill was introduced, as a percentile of HB/SB only. Raw rates 81/82/73/77% — real variation, non-monotonic, no usable signal. |
| `prefiled` | 0.0% | 0.1% | **NOISE** |  |
| `subject_count` | -0.2% | 0.1% | **NOISE** |  |
| `catchline_segments` | -0.1% | 0.0% | **NOISE** | ADHD round. Semicolon count in the catchline. NO VARIATION: 2,274 of 2,284 have exactly 2 segments, so the 'omnibus catchline' tell does not exist in VA data. |
| `patron_network_breadth` | -0.4% | -0.1% | **NOISE** |  |
| `patron_absence` | -0.9% | -0.2% | **NOISE** | ADHD round. Share of X/A (not voting / abstain) responses. Proposed INDEPENDENTLY by three frames; dead. |
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

## BLOCKED — proposed, could NOT be tested. Not dead. Do not treat as rejected.

| candidate | why it could not be tested |
|---|---|
| `section_citations` | Needs the count of Code of Virginia sections a bill touches. The CATCHLINE contains no § symbols (0 of 2,284) and full bill text is not published in bulk. NOT TESTED — do not record as dead. |
| `draft_lead_time` | Needs the gap between drafting and filing. Full_text_date1 IS the introduction date by construction in every row, so this dataset contains no drafting timeline at all. NOT TESTED. |
| `prior_session_recurrence` | Needs a prior session for the TRAINING year too. With only 2023+2024 usable (2022 is partial), the training year has no prior and the feature is constant in training. Needs a THIRD complete session. NOT TESTED. |
| `fiscal_note_footprint` | Needs History_description parsing for impact-statement rows; deferred, and would need a structural source before shipping. |
| `cross_chamber_companion` | Needs text similarity across chambers; the similarity tooling exists (W2/W3/W4) but catchline-only matching is weak. Deferred. |

**This is the most useful output of the ADHD run:** three of the best ideas are blocked by DATA we do
not hold — full bill text, a drafting timeline, and a third complete session. That is a concrete
acquisition list, not a dead end.

## Re-run only if
1. A new completed session lands (unblocks `prior_session_recurrence`).
2. Full bill text becomes available in bulk (unblocks `section_citations`).
3. A definition is corrected — quote the new score, never the old one.

Narrative: [[testing/calibration_results]] · method and weaknesses: [[testing/calibration_scope]].
