---
tags: [testing, prediction, pa, votes, party-position]
updated: 2026-11-18
status: active
open_loop: Party position — the two inputs that could move CONTESTED votes are not in hand: dated co-signatures (the PA co-sponsorship memo) and the bill's own words (memo or text; both are per-document pages under our PA bulk-only rule). Owner decision needed before either is fetched.
---

# Predicting each party's position (PA, 2026-11-18)

Owner: *"if the wall is predicting the party's position, start thinking about how we could predict it and run tests —
we want to know as much as we can."* The wall: if every party's position were known, member-level accuracy would be
98.4% (PA) / 97.3% (VA) — [[testing/pa_replication]], [[testing/first_vote]].

Code: `tools/calibration/pa/pa_party_position.py` → `results_party_position.json`. Target per roll call: did the
majority of the party OPPOSITE the sponsor vote yes? (The sponsor's party voted yes on 96.8% of its own bills' first
roll calls in 2025–26.) Every input is replayed by date. Fit 2017–21 → score 2023–24; fit 2017–23 → score 2025–26.

## Result
| | 2023–24 | 2025–26 |
|---|---|---|
| first roll calls (each chamber) | 1,405 | 1,495 |
| other party voted yes | 78.3% | 78.1% |
| model accuracy / AUC | 81.6% / 0.780 | 82.1% / **0.875** |
| contested roll calls (≥10% no): accuracy / AUC | 48.6% / 0.695 | 72.3% / **0.839** |
| every roll call, with the bill's earlier votes: AUC | 0.791 | 0.888 |

2023–24 is the House flip again: the training years had never seen a Democratic House.

## What carries it (2025–26, AUC of each input alone → AUC lost when removed)
| input | alone | lost without |
|---|---|---|
| co-sponsors from the other party (undated) | 0.778 | 0.040 |
| the room's record with the other party | 0.765 | 0.007 |
| **title words** (fit on earlier sessions) | 0.714 | 0.015 |
| standing (sponsor in the voting chamber's majority, committee/floor, chamber) | 0.681 | 0.008 |
| law record | 0.595 | 0.003 |
| motion kind | 0.553 | 0.020 |
| sponsor record | 0.538 | 0.004 |
| companion bill's earlier vote | 0.540 | 0.002 |
| sponsor / co-sponsor moderation (last session's defection) | 0.670 | −0.006 — redundant with co-sponsors |

**Title words that push the other party to NO:** environmental, permit, regulatory, energy, firearms, abortion,
imposing penalties, hearing board. **To YES:** military, township, bridge, contracts, service, registration, schools.
The content signal is real and stable across both test sessions.

**The other party's committee leader co-signs** (2025–26 roster): that party votes yes **143 of 148 (97%)** vs
76% otherwise (89% when some other-party member co-signed but not the leader). Covers 10% of bills; signatures
undated.

## Reading the bills — pilot (400 random 2025–26 first roll calls)
One reader (the assistant) rated each title: chance the other party votes yes. Inputs shown: sponsor party, chamber,
title. `reading_pilot.json`.

| | AUC | accuracy |
|---|---|---|
| data model | 0.878 | 83.5% (83.0% recalibrated) |
| reading alone | 0.807 | 81.8% |
| model + reading (5-fold) | **0.893** | **87.2%** |
| contested only (113): model / reading / both | 0.868 / 0.630 / 0.823 | 73.5% / 53.1% / 65.5% |

- **Reading titles helps on routine bills and not on contested ones.** A PA title names the statute and section, not
  the policy's direction — exactly the information a party position turns on.
- Leakage check (bills voted after the reader's training cutoff, Jul 2026+): 39 bills with only 3 "no" outcomes —
  inconclusive; treat the reading gain as an upper bound.

## What it would take to move contested votes
1. **Dated co-signatures** — the co-sponsorship memo circulates before filing; who signed it and when is the clean
   version of the strongest input. Per-memo pages: owner decision under the PA bulk-only rule.
2. **The bill's words** — the memo (plain-language intent, ~500–800 words) or the text. Reading budget (assistant):
   titles for all ~5,500 voted bills 2017–26 ≈ 14× this pilot (feasible in one or two limit windows, but it only helps
   routine bills); memos for the ~1,500 bills a year likely to be contested ≈ 1–1.5 M tokens a session (several
   windows); full text for every bill ≈ 20–50 M tokens (not feasible, and not bulk).
3. **Recalibrate after a change of majority** (2023–24 shows the cost of not doing it).
