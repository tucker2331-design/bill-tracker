---
tags: [testing, calibration, segmentation, bill-type]
updated: 2026-09-14
status: active
---

# Routine bills and contested bills are two different populations

**Owner, 2026-09-14:** *"make sure you are distinguishing between resolutions and bi partisan day to day
passage vs real bills, ie commending resolution vs actual change to the law bc they have diff stats."*

`python3 tools/calibration/contested.py`

## Resolutions were never in scope

`corpus.build()` keeps only identifiers matching `^[HS]B `. HJ / SJ / HR / SR — commendations, memorials,
celebrations — never entered any finding. In the 2026 archive that is **1,271 of 3,637 identifiers
excluded** ("Commending the Community Foundation", "Celebrating the life of…"). Verified: the only prefixes
in the corpus are HB and SB.

## The real problem is inside HB/SB

Charter amendments, technical corrections and uncontested code cleanups are bills, pass near-universally,
and drag every average toward "everything passes".

**The measure is structural, not textual:** what share of the room voted against the bill on the **first
roll call it ever received**. First, so it is fixed before the outcome. Share, not count, so an eight-seat
subcommittee and a hundred-seat floor are comparable. Coverage: 16,065 of 21,760 bills (74%).

**Motion direction is the whole trick.** A motion to table carried 8–0 means the room unanimously opposed
the bill while recording **zero "no" votes**. The first version of this classifier counted raw no-votes and
marked those bills "unopposed" — exactly backwards. Opposition is the NO count on a favourable motion and
the YES count on a fatal one. "Failed to recommend reporting" is a *favourable* motion that lost, so it is
not in the fatal list.

## The headline number splits in two

| opposition on the first roll call | bills | share | majority patron | minority patron | gap |
|---|---|---|---|---|---|
| nobody against | 8,664 | 54% | 86% | 77% | **+9** |
| 1–10% | 657 | 4% | 87% | 79% | +8 |
| 10–25% | 1,356 | 8% | 86% | 62% | **+25** |
| 25–40% | 1,669 | 10% | 85% | 35% | **+50** |
| over 40% | 3,719 | 23% | 21% | 2% | +19 |

**Consensus bills are 54% of the corpus and pass 83%. Contested bills pass 44%.**

- On **consensus** bills the majority advantage is **+9 points**.
- On **contested-but-alive** bills (10–40% against) it is **+35 points**.

**The pooled "+26 points" this project has been quoting is an average over these two populations.** It is
not wrong, but it is the wrong number for any specific bill: it overstates the penalty on a routine bill by
three-fold and understates it on a fought one. Quote it split, never pooled.

## Limit

The "over 40%" band is **not** a harder version of the same thing. A first roll call that lopsided usually
*is* the kill, so that band selects on the outcome and its +19 is not comparable to the bands above it.

## Related

[[testing/rooms]] · [[testing/bill_mix_confound]] · [[testing/calibration_conclusion]] · [[index]] · [[log]]
