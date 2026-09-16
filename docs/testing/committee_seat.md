---
tags: [testing, calibration, carrier, committee, lever, war-room, correction]
updated: 2026-09-16
status: active
---

# Put the bill in the SUBCOMMITTEE your patron sits in

A lobbyist cannot choose the bill, the party, or the year. Between sessions they **can** choose who carries
it — and whether that person has a seat in the room that will hear it is checkable in advance.

`python3 tools/calibration/committee_seat.py`

## The level is the whole finding

**The first version of this page measured the wrong room and overstated the result. Corrected same day.**

| patron is… | pass rate | n |
|---|---|---|
| on the **subcommittee** that hears it | **79%** | 924 |
| on the full committee but **not** the subcommittee | 63% | 760 |
| on neither | 65% | 3,015 |

**Full-committee membership on its own is worth −2 points (p = 0.33) — nothing.** The entire effect sits in
the **eight-person subcommittee seat**, which is the same room [[testing/rooms]] identified as the body that
actually decides. Two findings from different directions landing on the same room is the reason to believe
either of them.

| | subcommittee seat | not | gap |
|---|---|---|---|
| all bills | 79% (924) | 64% (3,773) | **+14** |
| majority-party patron | 86% (716) | 79% (2,262) | +7 |
| **minority-party patron** | **55% (208)** | 43% (1,511) | **+12** |

## Controls

| control | seated | not | gap | |
|---|---|---|---|---|
| **expected difficulty** — easier bills? | 55.3% | 56.0% | **−0.7 pt** | not the explanation |
| **within patron** (117 patrons, bills both ways) | 79% (924) | 61% (2,858) | **+17** | 84 better seated vs 25 worse |
| **within patron × subject** (310 cells) | 81% (717) | 70% (889) | **+11** | p = 1.5e-07 |
| **seat changed** — same patron, same room, same subject (55 cells) | 74% (92) | 66% (87) | +8 | **p = 0.22 — does NOT confirm** |

**The causal design is underpowered and is reported as a failure, not a success.** 179 bills across 55
cells cannot separate the seat from what the patron chose to file that year. What survives is a strong
association that holds through patron, subject and difficulty controls — not a demonstrated cause. The
earlier "+18, p = 9.3e-04" was computed at committee level, where membership is worth nothing on its own;
it was picking up subcommittee changes through the wrong lens and should not be cited.

## It is the seat, not the gavel

Majority-party patrons only (rosters exist for 20251/20261, so two sessions):

| patron role | pass rate | n |
|---|---|---|
| Chair | 90% | 97 |
| **on the subcommittee** | **87%** | 299 |
| Vice-Chair | 82% | 56 |
| not on it | 80% | 1,259 |

Chair is worth about **3 points over simply having a seat**, and vice-chair is worth *less* than a plain
seat. Consistent with the chair-effect retraction in [[testing/calibration_corrections]] — the gavel is not
where the advantage lives.

## How membership is derived, and the guard on it

From **roll calls, not a roster file**: anyone who cast a vote in that subcommittee that session is a member
of it. Rosters exist only for 20251/20261; roll calls cover 2023–2026.

A patron we cannot observe voting anywhere that session is **dropped, never silently recorded as "not on
it"** — that misclassification is the same silent-fallback class this project has shipped five times.
Measured guard cost: **2 bills of 4,699.**

## The companion null — a prolific patron is NOT spread thin

"Go to the delegate who isn't carrying 45 bills" is plausible and false. 219 legislators observed in both a
heavy and a light filing year: heavy **49%**, light **43%** — the *wrong* direction — and the heavy year's
bills are **+4.2 points easier** by expected difficulty, which is most of the gap. Within-year volume
against pass rate: **r = +0.02.**

## What goes on the War Room

One line, checkable before a bill is filed: **does this patron sit on the subcommittee this bill will go
to?** Labelled as an association, not a cause. It is worth most to the minority patron, who has the least
else to work with.

## Limits

1. The causal design fails on power. Treat the number as selection-exposed until a session can be scored
   forward.
2. Committee-vote coverage is 2023–2026 only.
3. Referral is by the clerk, but a patron can draft toward their own subcommittee's jurisdiction. The
   subject control absorbs much of that, not all.
4. Only 20% of bills have a patron seated on their first subcommittee, so this describes a minority of
   situations — see [[testing/coverage]] on why that matters.

## Related

[[testing/rooms]] · [[testing/member_signals]] · [[testing/carrier_effect]] · [[testing/coverage]] ·
[[testing/calibration_corrections]] · [[index]] · [[log]]
