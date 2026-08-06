---
tags: [testing, calibration, subjects, war-room, method]
updated: 2026-08-05
status: active
---

# Subject labels: two spaces, 18 sessions

## What exists now

LIS publishes `CiBillSubjects.csv` for **2023/2024 only**; 2025/2026 were backfilled once from the search
API ([[knowledge/lis_api_safety]], 915 requests, zero failures). Ground truth: **6,520 bills across 4
sessions**, up from 3,854 across 2.

**Labels come in TWO spaces because neither answers the other's question.** Run
`subject_label.py --write` and both are produced in one pass, each gated separately.

| space | classes | subj/bill | cold-session acc | null | corpus |
|---|---|---|---|---|---|
| **coarse** | 43 | 1.36 | **95.8%** @ 63% | 13.5% | **76%** |
| **fine** | 458 | 2.31 | **97.6%** @ 26% | 11.4% | **55%** |
| **union** | — | — | — | — | **80%** (18,234 bills) |

**Read every accuracy against its null baseline.** The metric ("is the predicted subject in the true set")
gets easier as true sets grow, so fine's 99.8% and coarse's 97.8% are NOT comparable — most of that gap is
2.31 subjects/bill vs 1.36, not model quality. See [[failures/assumptions_audit]] #114.

- **coarse** — 43 broad subjects. Whole-corpus cuts. 27 topics clear `verify.check()`.
- **fine** — the actual LIS subjects. **The only space that can answer a topic question**, because the
  coarse rollup does not contain Firearms, Marijuana, Zoning, Workers' Compensation, Police or
  Unemployment Compensation at all — they have no parent in the hierarchy file and were being deleted.

Resolutions are excluded corpus-wide (`^[HS]B ` in [[calibration/corpus]]).

## How accuracy is measured, and why the obvious way is wrong

**Seed 2024, label 2023 cold, score against 2023.** A random 75/25 split of the labelled sessions scored
the same model **95.9%** where cold-session scored **89.9%** — a held-out bill can be labelled from its
same-session companion, a shortcut no 2017 bill has.

**The accept cutoff is fitted on the OTHER direction** (seed 2023 -> predict 2024), so 2023 never
influences the threshold it is scored against. Where one cutoff cannot hold 95% on both the cold and the
abstract-bearing direction, it is **escalated in fixed 0.15 steps until both clear**, and the accepted
cutoff is recorded — a stated procedure, not a number chosen to make a check pass.

`--write` REFUSES if either direction of either space falls below 95%.

## The coverage-bias question, answered

Owner, 2026-08-03: *"can we be sure the data you did collect isnt concentrated in a certain area."*

**He was right twice.** First pass: hate crimes 24%, abortion 32%, marijuana 31% — fixed by the vocabulary
route. Second, deeper: the rollup was **deleting** Firearms, Marijuana, Zoning, Workers' Comp, Police and
Unemployment Compensation outright, 56% of all subject mentions. The fine space is that fix.

Largest composition gap between labelled and unlabelled bills: **5%**. Per-session coverage: 64-71% for 2017-2022, 86-93% for 2023-2027.

## What it buys

**Powered (coarse, n>=40 per standing, passes `verify.check()`):** 27 topics. Contracts 62%->16% (47pt),
Public Service Companies 65%->19% (46pt), down to the low-20s.

**Directional (fine, below the power bar — counts, never rates):**

| topic | majority passed | minority passed |
|---|---|---|
| **Firearms** | **82/94** | **1/21** |
| Consumer Protection | 34/47 | 2/16 |
| Contracts | 36/52 | 5/26 |
| Local Government and Officials | 27/40 | 5/20 |

Run: `python3 tools/calibration/subject_analysis.py [--fine] [--bias]`.

## Known limits — do not discover these mid-analysis

1. **Topic-specific pools are thin.** Firearms has 21 minority-patron bills. Directional only; a published
   rate needs a bigger denominator.
2. **20% of the corpus carries no label at all.** Unlabelled is a countable gap, never a default subject —
   `predict()` fails closed rather than assigning a most-common fallback.
3. **2023 has no abstracts**; 2017-2019 have 43-53%. Coverage is lowest there (49-56%).
4. **Coverage is bimodal by topic**, not uniform: most catalogue heads sit near 100%, a minority near zero.
   A head either resolves or it does not, and all its bills share that fate.

## Why not read the bills

LIS files by **which Title of the Code of Virginia a bill amends**, not by topic — wetlands under Fisheries
(28.2), kratom under Professions (54.1). Measured blind: semantic judgement **80%**, deliberately applying
the code-location rule **76%**, structural routes **95%+**.

## Related

[[failures/assumptions_audit]] #112 (four ways the test flattered itself), #113 (`HasNext` lied, ~800
wasted requests), #114 (the rollup deleted the interesting topics), #115 (2023 missing from every patron
finding — name format), #116 (a pessimistic proxy was paying its margin in coverage).
[[knowledge/lis_api_safety]] · [[testing/calibration_ledger]] · [[knowledge/legacylis_csv_route]]
