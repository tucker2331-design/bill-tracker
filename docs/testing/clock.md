---
tags: [testing, calibration, clock, calendar, war-room, lever]
updated: 2026-09-22
status: active
---

# Silence, priced by week — bills die on the clock, so measure the clock

Owner, 2026-09-22: *"keep looking for stuff that isnt surface level."* The test he set a message earlier is
the right one: **a finding has to tell you something the action list does not already say.**

`python3 tools/calibration/clock.py` · scope 2020–2026 ([[failures/openstates_committee_gap]])

## Why the calendar and not the votes

[[failures/assumptions_audit|#136]]: when identical bill text is filed in both chambers and the minority
copy dies, **it dies on the clock 69% of the time and on a vote 31%.** Every member-level measure we aimed
at the roll call came back empty because the roll call is not where bills die. This aims at the calendar.

## Silence is not one thing

*"It is week W and my bill still has not been heard."* Of those bills, how many were ever reported?

| | base | wk 2 | wk 3 | wk 4 | wk 5 |
|---|---|---|---|---|---|
| **long session**, majority patron | 63% | 58% | 53% | **35%** | **3%** |
| long session, minority patron | 40% | 37% | 34% | 24% | 1% |
| **short session**, majority patron | 65% | 66% | **46%** | **0%** | 0% |
| short session, minority patron | 35% | 30% | 21% | 0% | 0% |

n = 13,210 bills referred within 21 days of convening.

**Week 2 carries almost no information** — 58% against a 63% base. So "get heard early" is *not* the
finding; the finding is that nothing has happened yet and then the floor drops out. **A volunteer looking at
an empty history in week 2 and in week 4 sees the same screen, and the two mean completely different
things.** That is a fact the action list structurally cannot carry, which is what makes it worth showing.

**Not circular:** the condition (*not heard by week W*) is knowable at week W; the outcome comes later.

## The cliff moves with the session, so the week number cannot be hardcoded

Median day of first-chamber passage: **27, 15, 28, 22, 29, 22, 27** for 2020–2026. Long even-year sessions
cluster near day 28, short odd-year sessions near day 20, and the cliff tracks it — week 4 in long sessions,
week 3 in short ones. A fixed week would be wrong by a week every odd year. **Standard #1: derive the
deadline from the session at runtime.**

Part of the week-5 collapse is the crossover rule itself, which is procedure rather than behaviour. The
informative stretch is **weeks 2 → 4**, where nothing is forcing anything and the rate still halves.

## The room-level version — what a War Room can show before anything happens

| | |
|---|---|
| never acts on the bill at all | **H Rules 23%** … H the Judiciary 0% |
| median day of its first action | H the Judiciary 7 … **S Rules 22** |

**It is a new dimension, not a restatement.** Across the 24 rooms that join cleanly, *never-acts* correlates
**r = +0.08** with how often the room votes no and **r = −0.38** with its majority-party report rate. A room
can be quiet and fast, or quiet and slow; the page already showed the first kind of quiet and not the second.

**Bills in these rooms are not voted down. The session ends on them.** That is the 69% made concrete and
per-room.

## Caveat kept in front

A bill heard late may simply be a low-priority bill, so part of this is selection rather than the clock
acting on its own. The page therefore says what happened to bills in this position and never that the clock
caused it — the same line [[testing/panel_audit]] draws around prediction.

Related: [[testing/bill_states]], [[testing/continuance]], [[testing/venue_shopping]].
