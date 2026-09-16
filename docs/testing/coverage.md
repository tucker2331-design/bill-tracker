---
tags: [testing, calibration, coverage, product, indicator]
updated: 2026-09-16
status: active
---

# How often does any of this apply to a lobbyist's actual situation?

**Owner, 2026-09-16:** *"finding how often this will actually apply to a lobbyists situation is the right
direction."*

A validated signal that fires on 1% of real cases is a research result, not a feature. This page measures
**coverage** and **increment** for the two candidate surfaces. Both answers lean negative and both are here.

`python3 tools/calibration/coverage.py`

## A. The member × subject screen — sharp, and almost never applicable

The unit is the real one: **one bill arriving in one room**, with the roster who actually cast a vote
standing in for the room. A flag is only *useful* if the flagged member is in the party **opposite** the
patron — a flag on someone already voting your way is worth nothing.

12,939 bill-in-a-room situations, 2024–2026. Flags fitted on 2017–2023 only.

| screen | flags | flag in the room | **useful** flag | crosses vs same-party peers |
|---|---|---|---|---|
| 3 SE + crosses ≥15% | 42 | 3% | 3% | — |
| 3 SE + crosses ≥8% | 161 | 17% | **10%** | **2.8×** |
| 2 SE + crosses ≥8% | 218 | 24% | **13%** | 2.5× |
| 2 SE, no rate floor | 538 | 62% | 39% | 1.6× |

**The within-room payoff is real.** Same bill, same room, same vote: flagged members cross **6.3%** of the
time against **2.2%** for their own-party colleagues sitting beside them (n = 3,420 vs 182,540, p < 1e-16).

### But the funnel kills it

| | situations | share |
|---|---|---|
| bill-in-a-room situations | 12,939 | 100% |
| the bill **lost** this vote | 1,668 | 12.9% |
| …by ≤2 votes, so one member flips it | 366 | 2.8% |
| …a flagged member voted against it | 278 | 2.1% |
| **…both: flippable AND a named target present** | **50** | **0.4%** |

**Of losses, 3.0% had a flippable margin and a named target.** At the tighter 3 SE screen it is 2.0%.

A lobbyist would get a name they could act on roughly **once every 33 losses**. That is not a product
surface. It may still be worth surfacing passively on a bill page — it costs nothing to show when it fires
— but it cannot be the reason anyone buys the tool.

## B. Bill-level triage at referral — 100% coverage, almost no increment

Everything here is known **before** the first hearing. Train ≤2024 (3,385 bills), test 2025–26 (3,640).
Base rate: **34% die**.

| model | AUC | riskiest decile | safest decile |
|---|---|---|---|
| nothing (base rate) | 0.500 | 56% | 30% |
| **what a lobbyist already knows: patron's party** | **0.684** | **68%** | **22%** |
| + which committee it went to | 0.693 | 61% | 17% |
| room × standing as one cell | 0.572 | 41% | 21% |
| + the patron's own track record | 0.654 | 60% | 14% |
| **+ subject** | **0.731** | **70%** | **13%** |

The model separates properly and is decently calibrated — riskiest decile predicted 67%, actually died 70%;
safest predicted 15%, actually 13%; monotone across all ten deciles.

**The increment is the problem.** Against "I know my patron's party":

- AUC 0.684 → **0.731**
- riskiest decile 68% → **70%** — *almost nothing*
- safest decile 22% → **13%** — **this is where the value is**

**The model mostly re-derives "your patron is in the minority."** What it genuinely adds is at the safe end:
identifying the bills a lobbyist can **stop working**. For someone carrying 30 bills, "these four are
already fine" is real time, and it is not something they can eyeball.

## What this means for the product

1. **Do not build the whip-target feature as a headline.** It fires on 0.4% of situations. Show it when it
   fires; never promise it.
2. **The triage list should be sold as de-prioritisation, not prediction.** The riskiest decile tells a
   lobbyist what they already knew. The safest decile tells them something they did not.
3. **Structural room facts remain the strongest unsold asset** ([[testing/rooms]]): an eight-person
   deciding body, 86% party-line kills, kill rates ranging 21%–44% by room. Those need no causal claim and
   apply to 100% of bills.

## Two method bugs found here, both kept in the code

- **A naive rank-based AUC scores a CONSTANT model at 1.000.** The first version of the table had "base
  rate only" at the top looking perfect. `auc()` is now tie-aware.
- **`room × standing` as one cell scores WORSE (0.572) than the two features added separately (0.693).**
  Sparse cells overfit. Left in the printed table so the interaction is not re-attempted.

## Limits

1. Room rosters are inferred from who actually cast a recorded vote, not from a committee roster — members
   absent from the roll call are invisible.
2. The room corpus covers 2023–2026 only; flags use 2017–2023 member-votes from both corpora.
3. "Lost this vote" is derived with motion direction handled ([[testing/contested_vs_routine]]); bills that
   die by clock never appear in the funnel at all.
4. Test-era base rate (34%) drifts from train (41%) — AUC is rank-based and unaffected, but the predicted
   column is mildly optimistic. Same class as Correction 1 in [[testing/calibration_corrections]].

## Related

[[testing/member_subject]] · [[testing/rooms]] · [[testing/contested_vs_routine]] ·
[[testing/persuadability]] · [[index]] · [[log]]
