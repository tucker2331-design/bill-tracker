---
tags: [testing, calibration, method, corrections, audit-trail]
updated: 2026-08-01
status: active
---

# Calibration — corrections to the method, and what survived them

**Why this page exists (owner, 2026-08-01):** *"it will be important once we are said and done to be able
to prove our ethic, verify our claims and have a pulse on health."* Every number this project publishes
should be traceable to a test someone else could re-run, **including the tests that turned out to be
wrong.** This is the record of the wrong ones.

---

## Correction 1 — the null model was crediting base-rate DRIFT as skill

**The bug.** Every score was "how much better than predicting the **2023** average". But the average moved:

| | 2023 base | 2024 base | drift |
|---|---|---|---|
| House, got out of committee | 55.7% | 69.1% | **+13.4** |
| Senate, got out of committee | 90.0% | 98.6% | **+8.6** |

**A predictor knowing NOTHING but the new base rate scores +10.7% (House) and +75.8% (Senate)** under the
old null. So every stat was being paid for a shift it had nothing to do with.

**The fix.** Score against the **test-year** base rate, and recentre each learned rate by the drift, so a
stat is judged only on how it SEPARATES bills — not on whether the overall level happened to move.

**What it did to the headline** (House, got out of committee):

| stat | old null (inflated) | corrected |
|---|---|---|
| `patron_in_majority` | 11.8% | **13.3%** |
| `majority_copatron_share` | — | **9.2%** |
| best pair | 14.1% | **15.8%** |

**The House finding survived and got stronger.** Correcting a method does not always cost you the result.

## Correction 2 — the Senate has almost nothing to learn from

| session | chamber | bills | died in committee |
|---|---|---|---|
| 2023 | House | 1,210 | 536 (44.3%) |
| 2024 | House | 1,547 | 478 (30.9%) |
| 2023 | Senate | 852 | 85 (10.0%) |
| **2024** | **Senate** | **737** | **10 (1.4%)** |

**Ten failures.** Any stat catching a few of those scores enormously on error-reduction. That is why the
corrected sweep showed `patron_prior_on_this_subject` at "44%" in the Senate — a stat already measured as
NOISE-to-HARMFUL elsewhere. **All Senate committee-stage results are discarded as unlearnable**, and the
finding that stands is the simple descriptive one: *the Senate committee stage does not filter.*

## Correction 3 — stats were tested in isolation

Scored alone, `patron_in_majority` +5.4% and `committee` +7.2%; **together +16.7%**. Neither alone can
express *"a minority patron in House Courts of Justice"*. Fixed by a systematic **528-pair sweep per
chamber** (33 features), not a hand-picked few.

**Result: pairing adds little once the chamber is separated.** In the House, `patron_in_majority` alone is
13.3% and the best pair is 15.8%. **One variable does nearly all the work**; the pooled +16.7% was mostly
the pair standing in for "which chamber".

## Correction 4 — four stats were invalid measurements

Leakage (`text_versions`: a bill ACQUIRES versions by advancing) and same-session contamination (three
patron voting-behaviour stats). All four retested properly; all NOISE or HARMFUL. See
[[testing/calibration_ledger]].

---

## The Don Scott question — tested, and the data answers it

**Owner's challenge:** the House gap could be an artifact of one aggressive Speaker rather than a durable
institutional fact.

**Three things say otherwise.**

1. **The gap predates him.** It was **+33 in 2023** under a Republican Speaker and Republican majority, and
   **+35 in 2024** under a Democratic one. If it were one Speaker's doing, 2023 should look different.
2. **It is not uniform, so it is not top-down.** Across House committees the gap ranges **+15% to +77%**
   (2023) and **+5% to +68%** (2024) — standard deviation 17–20 points. A Speaker-driven effect would be
   flat across committees.
3. **The SAME committees are harsh in both years — r = +0.75 (n=9)** — *across a change of majority, which
   also changed every committee chair.*

| House committee | 2023 gap | 2024 gap |
|---|---|---|
| Public Safety | +77% | +68% |
| Courts of Justice | +34% | +55% |
| Finance | +39% | +50% |
| Education | +42% | +37% |
| General Laws | +22% | +23% |
| Appropriations | +15% | +10% |
| Transportation | +28% | +5% |

**Best reading: the gap tracks how partisan the committee's SUBJECT MATTER is**, not who holds the gavel.
Public Safety (guns, policing) is the most partisan area in Virginia and has the biggest gap; Transportation
(roads) the smallest. It survived a change of Speaker AND of every chair.

**Caveat kept honest:** r = +0.75 on n = 9 committees over 2 sessions is suggestive, not conclusive. The
owner's underlying concern — that two sessions cannot separate institutions from personalities — is only
*weakened*, not resolved.

---

## Why we cannot just get more years

The Developers Portal points at `legacylis.virginia.gov` for pre-2025 data, and that page documents a
generic pattern: `/SiteInformation/csv/[session_num]/[csv_filename]`. **But only three sessions are
actually published there** — 2022 (partial), 2023, 2024. Every older code 404s, in every format tried
(`<yy>1`, `<yy>2`, `<yy>3`, `20<yy>1`), swept 2000–2024.

The data exists — the LIS session catalog lists 59 sessions back to 1994 — but the API authorization is
**2025/2026 only**, so that route is closed to us. **This is a permission and publishing gap, not a data
gap**, and the fix is a request to DLAS (helpdesk@dlas.virginia.gov, 804-786-9631 — printed on that page),
not another probe. See [[knowledge/legacylis_csv_route]] and [[knowledge/lis_api_authorization]].

---

## What still stands after every correction

1. **House, minority patron, committee stage: a 33–35 point disadvantage**, replicated across a flip of
   control, varying by committee subject matter. Corrected score: **13.3%** better than knowing the base
   rate, the strongest single result in the project.
2. **Majority co-patron share: 9.2%** — and it is the only survivor an org can actually *change*.
3. **The Senate committee stage does not filter** (99% got out in 2024). Descriptive, not predictive, and
   worth telling a user plainly.
4. **No per-bill probability.** Reinforced, not weakened, by these corrections.
