---
tags: [testing, calibration, audit, backtest, war-room, self-assessment]
updated: 2026-09-16
status: active
---

# Does the War Room panel actually hold up? — a backtest against itself

**Owner, 2026-09-16:** *"judge yourself and scrutunize and test this thing. is it really worth anything?
does it hold up under criticism and weird scenarios. then check if it was actually a reliable measure on
bills in the past."*

Every number below is fitted on **2017–2023 only** and applied to **2024–2026** bills at referral. Nothing
from the test era touches the fit.

## 1. As a forecast it is barely better than what a lobbyist already knows

| panel | AUC | top decile passes | bottom decile |
|---|---|---|---|
| **patron's party alone** | **0.692** | **81%** | 28% |
| + the room | 0.693 | 78% | 27% |
| + the carrier's record | 0.707 | 80% | 27% |
| + subcommittee seat | **0.712** | **81%** | 26% |

**The whole panel adds +0.020 AUC over the single fact a lobbyist already has, and the top decile does not
move at all.** The room contributes +0.001. Calibration is reasonable (best decile predicted 83% / actual
81%; worst 28% / 26%) but decile 5 misses badly (57% predicted, 42% actual).

**Do not sell this as prediction.** It is not one.

## 2. Which descriptions survive re-measurement

14 rooms with ≥40 bills in both eras:

| dimension | r, 2017–23 vs 2024–26 | verdict |
|---|---|---|
| **dies on a record** | **0.79** | holds |
| **unanimity** | **0.77** | holds |
| partisan gap | 0.54 | holds *directionally* |
| overall pass rate | 0.36 | weak |
| **rewrite rate** | **0.25** | **DOES NOT HOLD — remove it** |

**The rewrite rate is retracted.** [[testing/profiles]] presented it as "bring finished text or expect a
rewrite." It does not persist and should not be shown.

**The partisan gap is the dangerous one.** It correlates at 0.54, but the median room's gap **moves 11
points between eras**, and two rooms move more than 30: **S12 went −1 → +29; H01 went +55 → +18.** Quoting a
gap computed from history to a client is the single most likely way this panel misleads. It must be
recomputed on the current session, never carried forward.

## 3. Failure modes

| | |
|---|---|
| **The reassurance risk** | Of 61 bills the panel would call safe, **10 (16%) died anyway.** A lobbyist who stops working those accepts that loss rate. HB 773 (Herring, marijuana penalties) and HB 260 (Hope, expungement) both read safe and both died. |
| **The new-member hole** | **37%** of test bills have a carrier with no prior record. The column is blank, and blank is not neutral — a freshman is a real risk the panel cannot see. |
| **Thin rooms** | **42%** of test bills sit in a room × standing cell with fewer than 25 prior bills. |
| **It rarely says anything strong** | A strong read either way fires on **380 of 7,284 bills = 5.2%.** For the other 95% the panel says "about average" — true, checkable, and not worth paying for by itself. |

Where it *does* speak strongly it is right: bills it called very hard passed **17%** against a 70% base
rate; bills it called very good passed **93%**. But that is 20 bills out of 624 in 2026.

## 4. The cold-start objection — measured

**Owner:** *"recalculating every session is only good in retrospect. its no good if the committee is
entirely new and we dont have any data on them."*

Three separate things were conflated, and they resolve differently.

**New MEMBERS — not the problem.** After the November 2023 election the median room kept only **43%** of
its members; **33% of room-sessions have more than half new faces.** But carrying the room's previous gap
forward is **no less accurate when the room churns** — median error 10 points when ≥50% of members are new
against 9 points for a stable room, and the own-history correlation is if anything higher (r = 0.76 on 14
churned rooms vs 0.52 on 31 stable ones; both thin). **A room behaves like the room, not like its roster.**

**Composition does NOT substitute for history.** Predicting a room's gap from who sits in it fails: party
ratio **r = 0.17**, mean prior member loyalty **r = −0.19**. The room's own prior gap gives **r = 0.59**.
There is no composition-based cold start to fall back on.

**New COMMITTEES — a real hole, and rare.** Committees are long-standing institutions here; of 37 observed,
the genuinely new ones are **H14, H24 and S13, all first appearing in 2024** after the post-election
reorganisation. Those have no history and nothing substitutes for it. The honest handling is an explicit
"no read yet" state, never a borrowed number.

## 5. Readiness — the briefing generated for a live session

2026 treated as if it had not happened; every number fitted on ≤2025.

| the briefing can say… | share of 2,326 bills |
|---|---|
| which room it went to | **86%** |
| the carrier's track record | **89%** |
| that room's record for this patron's side | 63% |
| kills by vote or by clock / argues or rubber-stamps | 64% |
| which subcommittee, and whether the patron sits on it | **42%** |
| **both a room read and a carrier record** | **55%** |
| **nothing at all** | **14%** |

**It separates.** Against a 2026 base rate of 70%: the worst quarter of briefings passed **41%**, the best
quarter **85%**.

**The partisan gap is the weakest piece.** Its 2026 error was a **median of 16 points** across 14 rooms —
worse than the 9-point carry-forward error over the longer window. **Show it as a coarse label, never as a
number.**

## 6. The honest verdict

**Worth keeping:**
1. **Carrier lift.** A 73-point range (−42 to +31), split-half r = 0.75, across eras r = 0.48, 6.1× the
   noise floor, drift check r = −0.01. It is a real trait, and choosing a carrier is the lobbyist's actual
   decision. **This is the most valuable number in the project.**
2. **"What kind of fight" — dies on a record (r = 0.79) and unanimity (r = 0.77).** The most reliable
   descriptions here, and they answer a question nobody else answers: do you fight for votes or for a
   docket slot.
3. **The structural facts** — an eight-person deciding body, 86% party-line kills ([[testing/rooms]]).
   These need no persistence test; they are counts, not estimates.

**Remove:** the rewrite rate (r = 0.25).

**Recompute every session, never quote from history:** the partisan gap.

**Never claim:** that the panel predicts whether a bill passes. It adds 0.02 AUC to what the user already
knows.

**The thing this is actually good for** is a briefing: which room, what that room does, who is carrying it
and how they have done. That is worth having and nobody publishes it. It is not a forecast and selling it
as one would be found out in one session.

## Related

[[testing/profiles]] · [[testing/rooms]] · [[testing/coverage]] · [[testing/venue_shopping]] ·
[[testing/committee_seat]] · [[testing/calibration_corrections]] · [[index]] · [[log]]
