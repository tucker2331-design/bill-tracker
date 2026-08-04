---
tags: [testing, calibration, subjects, war-room, method]
updated: 2026-08-04
status: active
---

# Subject labels extended from 2 sessions to 18

## What exists now

`CiBillSubjects.csv` is published for **2023 and 2024 only** ([[knowledge/legacylis_csv_route]]). That
capped every subject-cut finding at 2 of 18 sessions. `tools/calibration/subject_label.py` extends the
labels to the rest of the corpus.

| | measured |
|---|---|
| bills labelled | **14,839 of 22,659 (65%)** |
| accuracy, cold session with NO abstracts (the floor case) | **96.9%** at 56% coverage |
| accuracy, sessions WITH abstracts (75% of corpus) | **95.2%** at 65% coverage |
| ground truth it was grown from | 3,854 bills |
| top-level subjects | 43 |
| largest composition gap, labelled vs unlabelled | **4%** |
| reproducible | yes — verified under two `PYTHONHASHSEED` values |

Resolutions are excluded corpus-wide (`^[HS]B ` in [[calibration/corpus]]), per the owner's instruction.

## How accuracy is measured, and why the obvious way is wrong

**Seed 2024, label 2023 cold, score against 2023.** A random 75/25 split of the two labelled sessions
scored the same model **95.9%**; cold-session scored **89.9%**. A held-out 2023 bill can be labelled from
its same-session companion, which carries the answer — a shortcut no 2017 bill has. Only cold-session
numbers appear anywhere in this subsystem.

**The accept cutoff is fitted on the OTHER direction** (seed 2023 -> predict 2024), so 2023's labels never
influence the threshold 2023 is then scored against. Fitting it on folds inside one session instead gave a
cutoff that overshot 95% by 3 points and gave up 12 points of coverage — same-session bills score
systematically higher confidence, so an absolute cutoff does not transfer across that shift.

## Why it works: agreement, not a better classifier

Threshold tuning was exhausted early — 48 combinations swept, frontier flat at 43-58% coverage. The gains
came from **combining independent evidence**. Confidence is how many routes concur.

| route | what it is | measured |
|---|---|---|
| `vocab` | the catalogue head IS an LIS subject name | **98.9%**, needs no training data |
| `head` | exact catalogue head ("Elections; early voting." -> "elections") | 96.4% at 36% coverage |
| `headnb` | Naive Bayes over head TOKENS | generalises: 96% of an unseen session's heads share a token, vs 45% matching exactly |
| `near` | nearest labelled title by Jaccard | — |
| `abs` | nearest labelled abstract | +6 points of coverage where abstracts exist |
| `cmte` | majority subject of the first-referral committee | — |

Best single route 96.4%; **three routes agreeing 97.5%**; all five agreeing measured 99.4-100%.

## The coverage-bias question, answered

Owner, 2026-08-03: *"can we be sure the data you did collect isnt concentrated in a certain area … the ones
you dont want to touch are a concetrnation of something that would inform our data."*

**He was right, and it was fixed by the `vocab` route.** Topic coverage before and after:

| topic | before | now |
|---|---|---|
| hate crimes | 24% | **93%** |
| abortion | 32% | **77%** |
| firearms | 81% | **87%** |
| electric utilities | 93% | **97%** |
| parole | 72% | 75% |
| **marijuana** | 31% | **33% — KNOWN GAP, not fixed** |

Session coverage is 91-92% in the two seed sessions and 52-68% elsewhere; that asymmetry is inherent
(the seed sessions have ground truth) and is stated rather than averaged away.

## What it buys

The minority-patron penalty **by topic, across 18 sessions instead of 2** — 25 topics clear
`verify.check()` at n>=40 per standing. Range: **Public Service Companies 63% -> 17% (46pt)** down to
**Alcoholic Beverage Control 61% -> 46% (14pt)**. The ABC result matches the owner's own read that patron
standing barely matters there.

Full table: `python3 tools/calibration/subject_analysis.py`.

## Known limits — do not discover these mid-analysis

1. **Marijuana coverage is 33%.** Any marijuana-specific claim is under-powered.
2. **2023 has no abstracts at all**; 2017-2019 have 43-53%. Coverage is lowest in those sessions.
3. **35% of the corpus carries no label.** Unlabelled is a countable gap, never a default subject —
   `predict()` fails closed rather than assigning a most-common fallback.
4. The label is **one top-level subject**, from a rollup of 654 leaves to 43 parents. Most bills genuinely
   have one after rollup (2,699 of 3,854).

## Why not read the bills

LIS files a bill by **which Title of the Code of Virginia it amends**, not by topic — wetlands under
Fisheries (28.2), kratom under Professions (54.1). Measured blind: judging semantically scored **80%**;
applying the code-location rule deliberately scored **76%**; the structural routes score 95%+. The residual
is a cataloguer's convention, so understanding the bill does not help.

## Related

[[failures/assumptions_audit]] #112 — the four ways the measurement flattered itself.
[[testing/calibration_ledger]] · [[calibration/verify]] · [[knowledge/legacylis_csv_route]]
