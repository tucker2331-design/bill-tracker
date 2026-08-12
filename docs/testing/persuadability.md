---
tags: [testing, calibration, votes, war-room, indicator]
updated: 2026-08-07
status: active
---

# Persuadability: which legislators actually move

## Why this is different from everything before it

Every earlier finding describes **bills** — what passes, which chamber kills more, how minority patrons
fare. None of it changes what a lobbyist does on a Tuesday morning, because **nobody lobbies a chamber**.

This is the first member-level indicator, built from `_vote_people.csv` in every session archive —
**2,688,366 individual member votes across 69,422 roll calls**, which had been sitting unused.

## The measure

**Persuadability = the within-cohort z-score of a member's defection rate**, where defection is voting
against the majority of one's own party on the same roll call.

**Why a z-score and not the raw rate.** Defection is dominated by structural position, not temperament:

| | defection rate |
|---|---|
| House minority | 5.8% |
| House majority | 1.2% |
| Senate minority | 2.0% |
| Senate majority | 0.7% |

A raw ranking is therefore just a list of House minority members — something any lobbyist already knows.
Excess over cohort in percentage POINTS is no better: it still favours high-baseline cohorts and never
surfaces a single Senator. The z-score compares a member only against others in the same chamber, same
party-status, same year.

## It is a TRAIT, not a description — this is the part that matters

A number is only actionable if it predicts the future. Measured:

- **Stability year -> next year: r = 0.68** (n = 602 member-pairs)
- bottom quartile one year averages **z = -0.63** the next; top quartile **+0.90**
- on the raw (unadjusted) rate the same test gives r = 0.71, with the top third defecting **4x** as often
  as the bottom third the following year

**Persuasion is also concentrated**, which is what makes the list usable: in 2024-2026 the **top 20
members account for 42% of all defections**, top 30 for 53%. A lobbyist does not need to know 140 people.

## Running it

```bash
python3 tools/calibration/votes.py --swing
```

## Limits — state these before anyone acts on the number

1. **Floor votes only.** Open States captures no committee roll calls for Virginia (measured: 0 of 69,422
   have a committee classification). Most bills die in committee, so this describes the wrong venue for
   the most consequential decisions. Closing it needs a committee-vote source.
2. **2023 and 2027 have no member-level votes at all** — 2023 ships `votes.csv` but no `vote_people.csv`.
   Nine sessions carry member votes, not eighteen.
3. **A defection rate is past behaviour, not a promise.** It says where persuasion has somewhere to go,
   not that a given member will flip on a given bill.
4. **4.6% of votes carry no party** and are excluded from defection (they still count for turnout).

## Data quality — three defects found and fixed getting here

- **Hyphenated surnames merged two legislators.** `_tk` split "Convirs-Fowler" into ["convirs","fowler"],
  so its last token matched "Fowler" and **Kelly Convirs-Fowler's votes were counted as Kelly Fowler's** —
  13,056 vote rows against 7,883 real roll calls. Virginia's roster carries several such names. A
  per-(roll call, member) collision counter now guards it and reads **0**.
- **Organizations are corpus-wide, not per-session.** Looked up inside their own archive, **22,791 roll
  calls (33%) had a blank venue** while their motion text plainly said "Read third time and passed House".
  Open States ids are global; each archive ships only the orgs it defines.
- **146,220 votes (5.4%) had unresolvable voter names.** Bare surnames ("Howell") are ambiguous statewide
  but unique within a chamber; initial-first names ("R. Lee Ware") keyed on the initial; and Hashmi, Brewer
  and Guzman are real legislators **absent from the 350-entry roster**. Now **2,821 unresolved, all of them
  the string "Mr. Speaker"**, which is not a member name.

**Missing parties are DERIVED, then validated.** For members the roster omits, party is inferred from
agreement rates with each caucus, and checked by re-predicting members whose party IS known: **191/192 =
99.5%**. This is not the chamber-control derivation this project got wrong twice — that inferred a 52-48
body-level majority where a few errors flip the answer; this is a per-member question with hundreds of
observations each.

## Related

[[testing/subject_labels]] · [[testing/calibration_ledger]] · [[failures/assumptions_audit]] #115 (the same
name-format class of bug hid 2,000 bills from every patron finding) · [[index]] · [[log]]
