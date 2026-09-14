---
tags: [testing, calibration, committee, subcommittee, votes, room]
updated: 2026-09-14
status: active
---

# The room — who actually decides, and how many of them there are

Everything before this page described **bills**. This describes **rooms**. It reads the 28,769 committee
and subcommittee roll calls in [[testing/venue_effect|committee_votes]] (sessions 2023–2026), not
bill-level outcomes. Join to the corpus: **100.0%**; party resolved on member votes: **96.9%**.

`python3 tools/calibration/rooms.py`

## 1. The room is eight people

| | favourable recs (3,898) | fatal recs (1,436) |
|---|---|---|
| members recorded, median | **8** (quartiles 8–9) | **8** (quartiles 7–8) |
| unanimous | 62% | 42% |
| decided by ≤2 votes | 13% | **37%** |

The full House committee is 22 members. The body that decides is a subcommittee of eight, and when it
kills a bill it is not unanimous — 37% of kills are inside two votes.

## 2. Those votes are party-line

| | roll calls | nobody crossed their caucus | somebody did |
|---|---|---|---|
| **fatal** | 1,436 | **86%** | 14% |
| favourable | 3,898 | 82% | 18% |

When somebody does cross, it is a median of **one** member.

**This identifies a mechanism we had measured but not explained.** The majority advantage does not scale
with majority size (r = −0.05, [[testing/calibration_conclusion]]). Now it is obvious why: an eight-seat
room split 5–3 and one split 6–2 produce the same party-line outcome. **Seats past the majority buy
nothing**, because the decisive body is small and votes as a bloc.

## 3. The gap is not access to a hearing. It IS the hearing.

| | bills | never heard | pass if heard | pass if unheard |
|---|---|---|---|---|
| majority patron | 5,227 | 15% | **77%** | 5% |
| minority patron | 3,493 | 19% | **42%** | 3% |

**83% of bills get a recorded roll call in some room, and access is near-equal (85% vs 81%).** Among bills
that were heard, the gap is **+35 points — larger than the raw gap of +31.**

**This corrects an earlier reading.** The "advantage is agenda access, not vote arithmetic" line in
[[testing/calibration_conclusion]] was inferred from the flat majority-size relationship. It is wrong on
the mechanism: the room lets your bill in, and then votes it down along party lines. The flat relationship
comes from bloc voting in a small room (§2), not from agenda gatekeeping.

## 4. Four heuristics that are NULL

These cost as much to establish as the positive results and each one removes a plausible product feature.

1. **Time-since-referral predicts nothing.** Bills silent 3 days after referral pass 51%; silent 60 days,
   44%. Flat across two months (n = 20,726). "Your bill has been sitting a while" is not a signal.
2. **The substitute is worth nothing.** Reported with a substitute 90% (n = 1,381) vs reported clean 91%
   (n = 1,954): **−1 pt, p = 0.39.** Within-patron, within-idea: 84 groups, 92% vs 88% — too thin to
   carry a claim either way. Negotiating the language does not change survival.
3. **The subcommittee discontinuity does not identify.** Pooled it looks perfect — bills that barely clear
   subcommittee pass 83%, bills that barely fail pass 17%. The balance check kills it: **88% of the
   barely-favourable side has a majority-party patron against 16% of the barely-fatal side.** In an
   eight-seat room **a margin of 2 IS the party-line result**, so "close" selects for party, not for
   marginal bills. Kept in the code so nobody rebuilds it.
4. **"A narrow subcommittee kill is survivable for a majority patron" — RETRACTED on concentration.**
   Looked like 74% recovery (61 of 82). **63 of those 82 bills are 2023 House alone, at 89%**; the other
   three session×chamber cells are n = 5, 8, 6 at 40%, 12%, 33%. One cell is not a finding.

## What survives, and what it is worth

**Solid.** The decisive body is ~8 members; 86% of its kills are party-line; access is near-equal and the
gap is realised inside the room; majority size past the threshold buys nothing.

**Not solid.** The 86:1 odds on a subcommittee recommendation (favourable → 90% pass, fatal → 9%) are
**selection-contaminated** — rooms report bills they like. The threshold design that would fix it fails its
balance check (§4.3). Treat 86:1 as a description of where bills die, never as the value of changing a
recommendation.

## Related

[[testing/venue_effect]] · [[testing/persuadability]] · [[testing/carrier_effect]] ·
[[testing/bill_mix_confound]] · [[testing/calibration_conclusion]] · [[index]] · [[log]]
