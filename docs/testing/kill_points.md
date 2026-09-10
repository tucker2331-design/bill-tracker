---
tags: [testing, calibration, votes, war-room, indicator, committee]
updated: 2026-09-09
status: active
---

# Kill points: the room where Virginia bills actually die

## The one-line finding

**The subcommittee is the gate. The full committee largely ratifies what it decided.**

| venue kind | venues (n>=40 bills) | share of bills that ever reach a floor vote |
|---|---|---|
| **subcommittee** | 15 | **44% – 73%** |
| committee | 27 | 67% – 93% |

House Finance subcommittee sends **44%** of the bills it votes on onward. House Courts of Justice
*committee* sends **93%**. That is the spread a lobbyist needs before deciding where to spend a session.

## Why nobody else has this

Open States — the source behind most third-party trackers — carries **zero committee roll calls for
Virginia**: 0 of its 69,422 vote events have a committee classification. Its data can only ever describe
the floor.

LIS publishes committee AND subcommittee votes itself, in `Vote.csv`, and this project had never opened
the file. **6,743 committee roll calls and 2,860 subcommittee roll calls**, linked to bills.

## The decisive room is eight people

Measured across every recorded subcommittee roll call:

- median panel size: **8 members**
- **27% are decided by 2 votes or fewer** (763 of 2,860)
- a bill that wins at least one subcommittee vote reaches a floor vote **66%** of the time; one that loses
  every subcommittee vote, **14%** (n = 2,408 / 85, passes `verify.check`)

**So the pivotal quantity in Virginia legislating is routinely one or two people in a room of eight.**

## The floor score transfers to the committee room

[[testing/persuadability]] scores members on floor votes, because Open States covers nine sessions of
those and only two sessions carry committee votes. That would be useless if members behaved differently in
committee — so it was measured:

**Same member, committee vs floor defection: 2.6% vs 2.9%, r = 0.72 (n = 183 members.)**

They behave the same. The nine-session floor score is therefore usable as a proxy for committee behaviour,
which is what makes the two-session committee data go further than two sessions.

Committee-room defection runs **2.4% in both chambers** (n = 136,120 member-votes).

## The circularity that had to be removed first

Scoring "deepest venue reached" against `passed` gives **98%** for bills reaching a floor vote. That is
very nearly a tautology: in the first chamber the floor roll call **is** the passage vote, so it asks
whether a bill that passed, passed.

Every number on this page uses **reached a floor vote** as the outcome — a later, separate event from the
committee-stage question being asked.

## Running it

```bash
python3 tools/calibration/committee_votes.py              # coverage + integrity counters
python3 tools/calibration/committee_votes.py --killpoints # subcommittee as a gate
python3 tools/calibration/committee_votes.py --venues     # per-venue survival table
```

## Limits — read before quoting any number

1. **2023 and 2024 only.** These files exist solely in the legacy CSV cache. The modern blob publishes
   `VOTE.CSV` for authorized sessions and the calendar worker already consumes it, so extending to
   2025/2026 is a fetch, not a new capability. Pre-2023 exists on no route we have.
2. **1,274 of 9,559 roll calls in 241 are published with no member detail** — the vote exists, the names
   were never released. Counted separately from parse failures so neither can hide inside the other.
3. **Venue is text-derived, structurally cross-checked.** `History_description` names the room; the vote
   id's own prefix (`H0101` = House committee 01, subcommittee 01) is the structural check. 274
   disagreements are counted rather than silently resolved. Internal diagnostic only (Standard #3).
4. Committee **names** are scraped for readability only. Grouping is always on the structural code.

## The join, verified not assumed

    Vote.csv     "H0101V0001","H0317","Y",...   headerless, positional member/response pairs
    History.csv  Bill_id -> History_refid       9,283 of 9,283 refids match a Vote.csv id
    Members.csv  MBR_MBRID + chamber            140 of 141 match after zero-normalisation

**`Members.csv` writes `H108`; `Vote.csv` writes `H0108`.** Joined raw, **0 of 141 members match** — a
total join failure that returns an empty result rather than an error, the same shape as the `20251` vs
`2025` bug in [[failures/assumptions_audit]] #114.

## Related

[[testing/persuadability]] · [[testing/subject_labels]] · [[testing/calibration_ledger]] ·
[[failures/assumptions_audit]] #119 · [[index]] · [[log]]
