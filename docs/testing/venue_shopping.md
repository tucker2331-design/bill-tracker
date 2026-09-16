---
tags: [testing, calibration, venue, committee, lever, war-room]
updated: 2026-09-16
status: active
---

# Which room the bill lands in is worth 10–18 points

First-committee pass rates across Virginia committees run **46% to 75% — a 29-point spread.** The question
is whether that is the rooms differing or just the bills they happen to receive.

[[testing/venue_effect]] answered a neighbouring version with **cross-chamber companion pairs** — identical
text, two chambers, different survival. This is the **within-chamber** version, and it is the one a lobbyist
can act on, because drafting decides jurisdiction and jurisdiction decides the room.

`python3 tools/calibration/venue_shopping.py`

## The design

Group filings of the same bill idea, in the same chamber, that were referred to **different committees**.
Rank the two rooms by their own pass rate computed **leave-this-group-out**, so a group can never define
the rate it is then scored against. Require the two rooms to differ by at least 5 points. Compare how the
group's own filings fared on each side.

## Every control makes it larger

| control | friendlier room | harsher room | gap | p |
|---|---|---|---|---|
| subject clause (loose) | 62% (660) | 54% (478) | **+8** | 4.7e-03 |
| exact title (tight) | 54% (82) | 42% (71) | +11 | 1.6e-01 |
| **+ same patron** | 68% (173) | 53% (139) | **+15** | 6.9e-03 |
| + same standing | 60% (495) | 54% (407) | +6 | 7.1e-02 *(now marginal)* |
| **+ same YEAR** | 62% (183) | 41% (178) | **+21** | 5.2e-05 |

Sign tests agree: on the loose cut, 120 groups did better in the friendlier room against 62 worse
(p = 2.4e-05); same-patron, 51 against 18 (p = 1.2e-04).

**The year control is the one that matters.** Two filings of one idea usually sit in different years with
possibly different patrons, so the naive version could be the regime effect
([[testing/bill_mix_confound]]) wearing a costume. Holding the year fixed — same year, same chamber, same
subject, different room — the effect is **+21 points**, the largest of any cut. It is not the calendar and
it is not the patron's party.

## The honest weak spot

The **exact-title** arm is +13 points at **p = 0.07** on 195 bills. It agrees in direction and magnitude
with every other cut, but it is underpowered and cannot carry the claim alone. The looser cuts buy their
power by allowing the two filings to differ in wording, which is exactly where "the referral changed because
the bill changed" would hide.

What makes the finding credible despite that is corroboration from an independent design:
[[testing/venue_effect]] holds text **exactly** constant across chambers and finds the same thing.

## How much discretion is there? — measured, and it narrows the claim

The venue effect is only a lever if the room is not predetermined. Measured three ways, tightening each
time, and **the answer depends entirely on how tightly you define "the same bill":**

| grouping | groups | went to >1 room | median top-room share |
|---|---|---|---|
| our 39 coarse subjects (chamber × subject, ≥60 bills) | 45 cells | 76% show real spread | **58%** |
| the bill's own title subject clause (≥6 bills) | 106 | 69% | **89%** |
| **character-identical full title** (≥2 bills) | 390 | **28%** | **100%** |

**The coarse-label version overstates it.** At the exact-title level, referral is largely determined:
roughly seven in ten identical bills go to exactly one room.

**That cuts a specific way, and the direction matters.** It argues *against* "the same bill can land
anywhere" — and *for* the drafting reading, because a room determined by content is a room that changes
when the content changes. What is NOT measured here is how far a drafter can actually move it; the
identical-title design cannot see that by construction.

When identical bills *did* split, the rooms differed by a median of **10 points**:

| title | rooms | their pass rates |
|---|---|---|
| abortion; born alive infant, treatment and care | H08 / H24 | 72% / 66% |
| restricted driver's license; issuance for mul… | S03 / S11 | 59% / 75% |
| judges; maximum number in each judicial district | S03 / S13 | 59% / 70% |
| virginia economic development partnership auth… | H02 / H11 | 54% / 69% |

## What it means for the War Room

Jurisdiction follows the code section a bill amends, and that is a drafting decision made before filing.
**Of everything measured in this calibration line, this is the earliest point at which a lobbyist can move
the odds, and the largest single move available.**

It pairs with [[testing/committee_seat]]: choose the room, then choose a carrier who sits on its
subcommittee.

> **Recomputed 2026-09-16** after fixing the Senate room-code split (see [[testing/profiles]]). The key
> same-year control got **stronger** (+18 → +21); the same-standing arm weakened to +6 and is now marginal
> at p = 0.07, so it no longer carries weight on its own.

## Limits

1. The tight control is underpowered (p = 0.07). Treat the magnitude as 10–18 points, not a point estimate.
2. **Referral is mostly determined by the bill.** Seven in ten character-identical bills go to one room, so
   "shop the same bill to a friendlier committee" is not the lever — redrafting toward a different
   jurisdiction is. **How far drafting can actually move the room is NOT measured**, and the identical-title
   design cannot measure it.
3. Room rates are first-committee pass rates over 2023–2026, the span of the committee-vote corpus.
4. `S5V` / `S4V` style codes are floor-vote venues appearing as a first stop; they are left in the table
   rather than filtered, because filtering on a code pattern we have not verified would be a guess.

## Related

[[testing/venue_effect]] · [[testing/committee_seat]] · [[testing/rooms]] ·
[[testing/bill_mix_confound]] · [[index]] · [[log]]
