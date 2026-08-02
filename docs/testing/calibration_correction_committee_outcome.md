---
tags: [testing, calibration, correction, method, audit-trail]
updated: 2026-08-02
status: active
---

# Correction — the committee outcome was wrong, and an independent source caught it

**This is the correction the Open States cross-check existed to find, and it landed in the direction I did
not expect: the second source was right and our authoritative-source derivation was wrong.**

## What was wrong

"Did the bill get out of committee?" was derived from the LIS last-action code:

```python
survived = not last_actid.endswith("94")     # "Left in <Committee>"
```

`94` was verified — 621/621 in 2023, 487/488 in 2024 — and that verification was **real but irrelevant**.
It confirmed that `94` *means* death in committee. It never asked **whether `94` is the only way a bill
dies there.** It is not.

**Measured across both sessions: eight last-action suffixes never once co-occur with chamber passage.**

| suffix | meaning | 
|---|---|
| `94` | Left in committee *(the only one the old rule caught)* |
| `90` | **Passed by indefinitely in committee** |
| `40` | Continued to next session in committee |
| `93` | Stricken from docket by committee |
| `92` | Failed to report (defeated) in committee |
| `97` | Passed by indefinitely, with letter |
| `98` | Tabled in committee |
| `81` | Stricken at request of patron |

## What it did to the numbers

| | bills | died in committee, OLD rule | **CORRECTED** |
|---|---|---|---|
| 2023 House | 1,210 | 536 (44%) | **598 (49%)** |
| 2024 House | 1,547 | 478 (31%) | **708 (46%)** |
| 2023 Senate | 852 | 85 (10%) | **298 (35%)** |
| **2024 Senate** | **737** | **10 (1%)** | **238 (32%)** |

**The Senate is the disaster case.** It kills bills with *"Passed by indefinitely"* (`90`), not *"Left in
committee"* (`94`). Counting only `94` found **10** Senate committee deaths in 2024 when there were **238**.

## The conclusion that has to be withdrawn

**Claimed, twice, in writing: "the Senate committee stage does not filter — it reports out 90% then 99% of
everything."** That was an artifact of the broken rule.

| | majority patron | minority patron | gap |
|---|---|---|---|
| Senate 2023 — old rule | 90% | 92% | −2% |
| **Senate 2023 — corrected** | **77%** | **54%** | **+23%** |
| Senate 2024 — old rule | 98% | 99% | −1% |
| **Senate 2024 — corrected** | **79%** | **54%** | **+25%** |

Also withdrawn: *"the Senate is unlearnable, only 10 failures to learn from"* — there are 238.

## What survives, and is now stronger

| | majority | minority | gap |
|---|---|---|---|
| House 2023 | 66% | 30% | **+35%** |
| House 2024 | 67% | 36% | **+31%** |
| Senate 2023 | 77% | 54% | **+23%** |
| Senate 2024 | 79% | 54% | **+25%** |

**The majority-standing effect is real in BOTH chambers, in both sessions, across a change of control.**
That is a broader and better-supported finding than the one it replaces. The chamber *difference* was the
artifact; the *effect* was not.

## How the cross-check found it

Open States classifies actions into a normalised vocabulary (`committee-passage`, `passage`, `reading-3`)
that is the **same across all 50 states**. Comparing 2023 bill-by-bill against LIS:

- **coverage: every LIS bill present** (LIS-only = 0)
- **chamber passage: 2,062/2,062 = 100.0% agreement**
- **committee passage: 82.5%** — 360 disagreements

**The 100% on passage is what made the 82.5% diagnosable.** A source that agreed everywhere would have
proved nothing; a source that disagreed everywhere would have been suspect. Agreeing perfectly on one
outcome and diverging on another localised the fault precisely — and inspection showed the divergent bills
ending on `S0490 Passed by indefinitely`, `H1193 Stricken from docket`, `S0481 Stricken at request of
patron`.

## Lessons

1. **Verifying that a rule is RIGHT is not verifying that it is COMPLETE.** "621/621 of code `94` are
   committee deaths" was true and licensed nothing. The question never asked was *"what fraction of
   committee deaths are code `94`?"* — 10 of 238 in the 2024 Senate.
2. **A near-zero rate is a smell, not a finding.** "1% of Senate bills die in committee" should have been
   read as *the detector is broken*, not as *the Senate is permissive*. I instead built a narrative on it
   and repeated it.
3. **This is what a second source is for.** Not redundancy — falsification. The value came from Open States
   disagreeing with the authoritative source in a specific, localisable way.
