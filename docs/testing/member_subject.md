---
tags: [testing, calibration, votes, persuadability, whip, indicator]
updated: 2026-09-14
status: active
---

# Does a member stray on particular subjects — provably, not plausibly?

**Owner, 2026-09-14:** *"if this committee almost kills everything but this person is better on this
subject and tends to stray from their party… we need to find some version of this informative set up that
proves its self as signifigantly better then a guess."*

**The guess to beat is the member's own overall defection rate.** A subject-specific claim must add
something on top of "this person crosses the aisle a lot".

TRAIN 2017–2023, TEST 2024–2026. 2,734,709 member-votes carrying a party and a subject label, from both
vote corpora. Nothing from the test era touches the fit.

`python3 tools/calibration/member_subject.py`

## The structure is real

Member × subject cells (≥40 votes, member ≥300 votes) show **4.32× the binomial variance floor**, and the
residual correlates **r = 0.487** between the two eras (n = 2,709, t = 29).

## But as a general model it FAILS

Out-of-sample log-loss over 1,088,729 held-out votes, both models empirical-Bayes shrunk so the richer one
is not free:

| model | log-loss |
|---|---|
| global rate for everyone | 0.12868 |
| **the guess: the member's own rate** | **0.12394** |
| member × subject | 0.12451 — **0.46% worse** |

**Do not ship a model that scores every member × subject cell.** Most carry no signal, and pricing them
adds noise everywhere to buy accuracy in a few places.

## As a sparse screen it works

**The null is 41%, not 50%.** Of the 2,709 comparable cells, only 41% sit above the member's own baseline
in the held-out era — cells regress downward on average. A coin-flip framing would overstate every screen
below by nine points.

| screen, fitted on TRAIN only | flags | replicate in TEST | vs null | p |
|---|---|---|---|---|
| residual > 1 SE | 545 | 59% | +18 | <1e-16 |
| residual > 2 SE | 288 | 65% | +25 | <1e-16 |
| residual > 2 SE, crosses ≥8% there | 103 | 72% | +31 | 1.2e-10 |
| **residual > 3 SE, crosses ≥8% there** | **71** | **76%** | **+35** | **1.3e-09** |
| residual > 3 SE, crosses ≥15% there | 17 | **100%** | +59 | 6.4e-07 |

**Effect size inside the surviving flags** (71 cells, 32,437 held-out votes): those members cross **8.7%**
of the time there, against **4.8%** for themselves overall (**1.8×**) and **2.7%** chamber-wide (**3.2×**).

| member | subject | train | test | own base |
|---|---|---|---|---|
| Tommy Wright | Alcoholic Beverage Control Act | 55% | **73%** | 10% |
| Sam Rasoul | Alcoholic Beverage Control Act | 30% | **35%** | 2% |
| Phil Scott | Trade and Commerce | 24% | 35% | 12% |
| Nick Freitas | Trade and Commerce | 25% | 27% | 11% |
| David Suetterlein | Public Service Companies | 12% | 22% | 6% |
| Bobby Orrock | Housing | 19% | 19% | 6% |

26 of 34 subjects replicate with r > 0. Strongest: Alcoholic Beverage Control (r = 0.84, 65 cells),
Corporations (0.80), Housing (0.72), Trade and Commerce (0.66), Criminal Procedure (0.50).

## Limits — read these before anyone calls a legislator

1. **It is a screen, not a score.** The general model is worse than the guess. Only flags clearing the
   3 SE + 8% bar carry any validated claim; the 17-flag tier is the only one that replicated perfectly and
   it is 17 cells.
2. **A frequent crosser collects flags.** 44 distinct members hold the 71 flags; Carrie Coyner holds 4 at
   an own-baseline of 14%. Read the "own base" column — a flag on a 14% baseline member is far weaker
   evidence than Sam Rasoul at 2%.
3. **Some of this is knowledge a good lobbyist already has** (the owner's own caveat). Nothing here
   separates "genuine private signal" from "everyone in Richmond knows Tommy Wright on ABC". The claim is
   only that the pattern is *real and persistent*, not that it is *unknown*.
4. **Defection ≠ persuadability.** It says where crossing has happened before, not that a given member will
   flip on a given bill. Same limit as [[testing/persuadability]].
5. Subject labels are our own coarse classifier ([[testing/subject_labels]]), not LIS's.

## Related

[[testing/persuadability]] · [[testing/rooms]] · [[testing/contested_vs_routine]] ·
[[testing/subject_labels]] · [[index]] · [[log]]
