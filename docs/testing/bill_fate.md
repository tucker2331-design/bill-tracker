---
tags: [testing, calibration, prediction, fate]
updated: 2026-09-29
status: active
---

# Bill fate at the first committee (2026-09-29)

The five-perspective panel's first recommendation ([[testing/panel_2026-09-29]]): before predicting how members
vote, predict **whether the bill gets a recorded vote at all.** Most bills that die never produce a roll call, so the
member-vote model ([[testing/first_vote]]) only ever sees the bills that got that far.

`tools/calibration/fate.py` · locked test: `frozen/prereg_fate_2026.json` → `frozen/score_fate_2026.json`

## What a bill's fate can be (origin chamber, first decisive committee action)

| outcome | means | 2020–2025 majority-party bills | minority-party bills |
|---|---|---|---|
| Advanced | reported / recommended / re-referred onward | 65–87% by year | 40–53% |
| Killed | tabled, passed by indefinitely, failed to report | 4–11% | 18–38% |
| Continued | carried to next year — **even-year (long) sessions only** | 0–11% | 0–9% |
| Withdrawn | stricken at the patron's request | 1–4% | 2–7% |
| Merged | incorporated into another bill | 2–10% | 3–8% |
| Never taken up | "Left in committee" with no decision | 3–13% | 6–24% |

Killed "by voice vote" is essentially empty in every year (Virginia committees record kill counts), so it is merged
into Killed. Carried-over records (900) and one special-session continuance are excluded and counted.

## The agenda is filtered — majority roll rate

A "roll" is a recorded vote where a party's majority ends up on the losing side (Cox & McCubbins). 2020–2025:

| first votes | roll calls | majority party rolled | minority party rolled |
|---|---|---|---|
| subcommittee | 4,388 | 1.4% | 32.0% |
| committee | 2,785 | 2.4% | 19.9% |
| floor | 718 | 5.6% | 42.9% |

The majority almost never loses a recorded committee vote; bills it opposes mostly die before one. This is the
measured form of "the recorded votes are a filtered sample".

## The model

At filing, from public record only: patron standing, chamber, session length, governor's party, co-patrons at filing
(own party / other party / bipartisan), companion bill (and its patron's party), money committee, patron tenure and
bill count, the patron's and the committee's earlier fate rates, subject history, prefiled, and the fate of the most
similar earlier-year bills. One-vs-rest boosted trees (depth 3, 100 rounds), averaged 50:50 with the baseline —
chosen on 2024 alone, then applied unchanged.

| year-ahead (train on earlier years only) | baseline log loss | model log loss | advance AUC (base → model) |
|---|---|---|---|
| 2022 | 1.279 | 1.235 | 0.638 → 0.676 |
| 2023 | 0.939 | 0.904 | 0.693 → 0.725 |
| 2024 (choosing year) | 1.157 | 1.140 | 0.686 → 0.756 |
| 2025 | 1.006 | 0.962 | 0.744 → 0.809 |
| **pooled, per bill** | | **gain +0.0345, z = 14.5 — accepted** | |

Baseline = each outcome's rate by patron standing × chamber × session length.

## Locked 2026 test (scored once, after the spec was committed)

2,325 bills. Log loss **1.002 vs 1.072** baseline (gain +0.070, 95% 0.063–0.078). "Gets out of committee" AUC
**0.80** (baseline 0.68). Top outcome right 67.4% (baseline 66.2%). Quiet-death AUC 0.70.

**How the chances hold up (2026)** — the number a volunteer would read:

| model's chance the bill gets out of its first committee | bills | actually did |
|---|---|---|
| 80% or more | 163 | 96 in 100 |
| 60–80% | 1,470 | 78 in 100 |
| 40–60% | 489 | 40 in 100 |
| 20–40% | 203 | 19 in 100 |

## What did not help fate

- **GDELT news attention** (patron mentions, topic volume before the committee met; 2025 pilot): no gain, z = 1.1
  (`gdelt_effect.py`).
- **House written testimony and association scorecards were NOT tested on fate:** testimony exists only once a bill
  is on an agenda, and scorecards pick bills after the session — both are downstream of the outcome.
