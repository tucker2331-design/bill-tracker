---
tags: [testing, calibration, carrier, committee, lever, war-room]
updated: 2026-09-16
status: active
---

# Put the bill in a room your patron sits in

**The first thing in this whole calibration line that is a lever, survives every control, and a lobbyist
can act on before anything is filed.**

A lobbyist cannot choose the bill, the party, or the year. Between sessions they **can** choose who carries
it — and whether that person has a seat in the committee the bill will go to is checkable in advance.

`python3 tools/calibration/committee_seat.py`

## The finding

7,020 bills with a first committee and an observable patron. **46%** of patrons sit on the committee their
own bill lands in.

| | patron ON it | not on it | gap |
|---|---|---|---|
| all bills | **70%** (3,202) | 56% (3,818) | **+14** |
| majority-party patron | 81% (2,145) | 72% (2,118) | +8 |
| minority-party patron | **49%** (1,057) | 36% (1,700) | **+13** |

## It survives every control

| control | on | off | gap | |
|---|---|---|---|---|
| **expected difficulty** — do committee members just file easier bills? | 58.3% | 56.5% | +1.8 pt | not the explanation |
| **within patron** (186 patrons with bills both ways) | 70% | 57% | **+14** | 116 better seated vs 52 worse |
| **within patron × subject** (657 cells) | 74% | 66% | **+8** | p = 3.4e-07 |
| **seat changed** — same patron, same ROOM, same subject (80 cells) | **71%** (161) | **53%** (152) | **+18** | p = 9.3e-04, 36 better / 16 worse, sign p = 8.4e-03 |

The last row is the one that matters. Committee assignments change between sessions. Holding the person,
the room and the subject fixed, **the only thing that moved is whether the patron had a seat in it** — and
the bills passed 18 points more often when they did.

## How membership is derived, and the guard on it

Membership comes from **roll calls, not a roster file**: anyone who cast a vote in that room that session
is a member. Rosters exist only for 20251/20261; roll calls cover 2023–2026.

The trade-off: a member who never voted in a room they belong to would read as absent. So **a patron we
cannot observe voting anywhere that session is dropped, never silently recorded as "not on it."** That
misclassification is the same silent-fallback class this project has shipped five times. Measured cost of
the guard: **5 bills of 7,025.**

## The companion null — a prolific patron is NOT spread thin

"Go to the delegate who isn't carrying 45 bills" is a plausible heuristic and it is false.

219 legislators observed in both a heavy and a light filing year: heavy year **49%**, light year **43%** —
the *wrong* direction for the heuristic, and the heavy year's bills are **+4.2 points easier** by expected
difficulty, which is most of the gap. Within-year volume against pass rate is **r = +0.02**.

Carrier workload carries no information in either direction.

## What goes on the War Room

One line, checkable before a bill is filed: **does this patron sit on the committee this bill will go to?**
It is worth +8 points after the tightest control available and +18 in the natural experiment, and it is
worth most to the minority patron, who has the least else to work with.

## Limits

1. Committee-vote coverage is 2023–2026, so the seat-change experiment rests on 80 cells and 313 bills.
   The cell-level examples have single-digit denominators and carry no weight individually; only the
   pooled figure does.
2. Membership is at committee level (`H11`), not subcommittee. A patron on the full committee is not
   necessarily in the subcommittee that hears the bill.
3. Referral is by the clerk, not the patron — but a patron can draft toward their own committee's
   jurisdiction. The subject control absorbs most of that; it cannot absorb all of it.
4. `passed` is Open States' `passage` classification, consistent with every other page here.

## Related

[[testing/rooms]] · [[testing/member_signals]] · [[testing/carrier_effect]] ·
[[testing/bill_mix_confound]] · [[testing/coverage]] · [[index]] · [[log]]
