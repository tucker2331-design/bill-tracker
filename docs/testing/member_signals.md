---
tags: [testing, calibration, votes, war-room, members, null-result]
updated: 2026-09-16
status: active
---

# Independent voters, blocs, and who is in play — one collapse and two nulls

**Owner, 2026-09-16:** *"trying to be able to tell who are the independent voters per say. people who you
need to convince and havent made up their minds"* — plus who moves together, and who is genuinely in play
in a room. Asked with an explicit instruction to spend real time on confounds before running anything.

`python3 tools/calibration/members.py`

## The denominator is the first finding

Of **18,781** committee and subcommittee roll calls, only **3,929 (21%)** have a caucus that actually
split. On the other 79% every member votes with their side, so every member scores as perfectly
predictable. **Every measure on this page is restricted to those 3,929 contested roll calls.** Any
member-level statistic computed on the full set is describing the denominator, not the members.

## 1. Who has not made up their mind — a real trait that collapses

27,271 member-votes inside a split caucus; 157 members with ≥60.

| | |
|---|---|
| split-half reliability | **r = 0.71** |
| 2017–2024 vs 2025–2026 | **r = 0.52** |
| correlation with plain defection rate | **r = 0.92** ← the collapse |

It is a stable trait. It is also **not a new one.** At r = 0.92 with the defection rate there is no
separate "undecided" dimension to model.

**The owner's distinction does not appear in the data.** The idea was that a member who always breaks on
one subject is *predictable*, and only unexplained deviation means genuinely undecided. Conditioning on
subject made out-of-sample prediction **0.1% worse**, not better. Subject carries no information about
whether this member follows their caucus on a contested vote.

**What to ship is the count, not a score.** Members who follow their own caucus least when it splits:

| member | follows caucus | contested votes |
|---|---|---|
| Candi King | 48% | 106 |
| Tim Griffin | 44% | 72 |
| Cia Price | 46% | 183 |
| John McGuire | 56% | 105 |
| Carrie Coyner | 56% | 399 |

A lobbyist can read that without a model behind it. It supersedes the framing in
[[testing/persuadability]], which computed a z-score over *all* votes — the right denominator is the
contested ones.

## 2. Who moves together — NULL, after we corrected our own baseline

**The bug was ours, and it is the reason this section exists.** Chance agreement between two members must
be computed from their **follow rates**, not their yes-rates. Two members who each follow their caucus 85%
of the time agree about **75%** of the time by pure chance. Scoring chance at ~50% — which is what a
yes-rate baseline gives on contested votes — makes ordinary caucus loyalty look like a coalition.

| | within-party pairs, ≥40 shared contested votes |
|---|---|
| pairs tested | 421 |
| Bonferroni threshold | \|z\| > 3.85 |
| significant under the **wrong** baseline | **132** |
| significant under the **correct** baseline (mean chance 65%) | **1** |
| agreeing *less* than chance | 7 |

Out of sample, a randomly chosen qualifying pair sits above chance 48% of the time with a mean excess of
**−1.0 points** — i.e. nothing.

The single survivor: **Nick Freitas and Phil Scott**, agreeing 87% against a 57% chance baseline, and
**90% in the held-out era.** One pair out of 421 is not a coalition structure.

**Direction was never claimed.** Votes are simultaneous, so nothing here could distinguish a leader from a
follower even if blocs had existed.

## 3. Who is actually in play in a room — NULL, it is seat arithmetic

A member is pivotal if flipping their vote alone changes the outcome. The null model: everybody votes their
caucus line, so pivotality is a function of the seat split and nothing else.

| | |
|---|---|
| member-votes examined | 60,031 |
| observed pivotal | **3.7%** |
| party-line null predicts | **11.3%** |
| difference | **−7.5 points** |
| mean per-member excess | −7.89 points |
| members above their own null | 22 of 138 |

Members are **less** pivotal than party-line voting would make them, because dissent piles up on votes that
were not close. There is no personal leverage signal here.

## 4. Reciprocity — NULL, and slightly negative

"I vote for your bill, you vote for mine" is how everyone describes this business. It does not appear.

Cross-party pairs only (so co-partisan agreement cannot explain it), 36,411 votes with at least five prior
reciprocal observations:

| how often THEY backed YOU earlier | you back them now | n |
|---|---|---|
| under 50% | 72% | 3,548 |
| 50–80% | 75% | 12,132 |
| 80–100% | **68%** | 20,731 |

**−4 points, p = 2.9e-05 — the wrong direction.** And the same-year version, which ordinary ideological
agreement would explain, gives the identical −4. So there is neither a trade nor an agreement effect: a
prior favour does no work at all.

## What this leaves for the War Room

One line, and it needs no machinery: **when this room splits, here is how often each member goes with their
own side.** Everything more elaborate than that either collapses into it or fails.

## Limits

1. Contested roll calls are 2023–2026 only (the span of the committee-vote corpus).
2. Members elected after 2023 have too few contested votes to rank; they read as "no record", not as
   predictable.
3. The follow-rate list describes past behaviour on bills that split a caucus. It does not say a member
   will cross on a given bill — same limit as [[testing/persuadability]].
4. Pivotality is computed from members who cast a recorded yes/no; absences are invisible.

## Related

[[testing/persuadability]] · [[testing/rooms]] · [[testing/coverage]] · [[testing/member_subject]] ·
[[index]] · [[log]]
