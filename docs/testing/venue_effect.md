---
tags: [testing, calibration, votes, war-room, indicator, moat]
updated: 2026-09-10
status: active
open_loop: committee_votes member NAMES are raw Members.csv strings, so one member can appear twice ("Green, W. Chad" and "W. Chad Green"); the member-level layer must route through corpus's canonical resolver before it ships.
---

# The venue effect: what a room does to a bill, with content held constant

## The question nobody in the literature can ask

Every published model of committee outcomes predicts survival **from outside the room**.

- **Yano, Smith & Wilkerson (NAACL 2012)**, the standard reference on this exact stage, names the problem
  in as many words: consideration *"behind closed doors, by a Congressional committee."* So they model it
  with the sponsor, the referral, and the bill text.
- **Eidelman, Kornilova & Argyle (COLING 2018)** predict floor action across **1.3M bills in 50 states**
  and find committee information their **most predictive feature** — but their committee feature is the
  **assignment**, not the votes.

Neither has the votes because the datasets everyone uses do not carry them: **Open States has 0 committee
roll calls for Virginia, of 69,422 vote events.**

LIS publishes them. [[testing/kill_points]] reads **19,192**. This page is what they make possible.

## The design: the legislature runs the experiment on itself

Virginia files **companion bills** — the same text in both chambers at once. When one dies and its twin
lives, **content, session, political climate and calendar are all held constant. What differs is the
room.** The General Assembly runs this experiment ~1,400 times per corpus, for free.

**Measured: of 1,443 cross-chamber companion pairs with recorded votes on both sides, 272 (19%) diverged**
— identical text, opposite outcome. **The chamber split on those divergences is 50/50**, so "the House
kills more" explains *nothing*. What varies is which room.

## The finding

Restricted to bills whose **identical twin survived in the other chamber** (5,829 venue observations):

| | content-controlled kill rate |
|---|---|
| base, full committee | **7%** |
| base, subcommittee | **12%** |
| **House Privileges & Elections, subcommittee** | **31%** (+19pp over its kind) |
| House Commerce & Energy, subcommittee | 27% (+15) |
| Senate Education & Health, committee | 22% (+15) |
| House Health & Human Services, subcommittee | 25% (+13) |

**Permutation p = 0.037** across 49 venues, shuffling the outcome *within kind* over 2,000 rounds — so the
test cannot be passed by rediscovering that subcommittees kill more than committees.

**Read it as:** *identical text fares four times worse in this room than in the room its twin went to.*

## Two ways this could have been fake

1. **Multiple comparisons.** 49 venues were scored, so the most extreme is extreme partly by luck. Hence
   the permutation test above, reported rather than assumed.
2. **Circularity, which the first version had.** Scoring by the bill's LAST pre-floor venue is nearly
   tautological — dying in subcommittee *is* having your last vote there — and it produced an absurd 82%
   subcommittee base rate. A bill is now counted as **seen by every venue that voted on it**, with the
   outcome being whether it ever reached a floor vote: a later, separate event. The honest number (12%)
   is a seventh of the circular one.

## What it is NOT

**Not a causal claim about any chair.** A room's docket is routed, not random: leadership decides what
goes where, and a room handed the harder half of a subject will kill more of it even if it treats every
bill exactly as its counterpart would. **The companion design removes the bill's CONTENT as an
explanation. It does not remove ROUTING.** The defensible reading is the actionable one — *identical text
fares measurably worse here* — not *this chair is hostile*.

## Why this is hard to replicate

It needs four things joined, and the joins are where it breaks:

1. **Committee + subcommittee roll calls** — absent from Open States entirely; only in LIS `Vote.csv`,
   whose member ids join **0 of 141** against `Members.csv` until zero-padding is normalised
   ([[failures/assumptions_audit]] #119).
2. **Companion detection** — same text, both chambers, across 22,659 bills.
3. **Venue resolution** — the classifier's ORDER is the whole rule, and a Python precedence bug in the
   first version dropped 4,915 floor votes into "other".
4. **A control for multiple comparisons**, without which the top venue is just the luckiest of 49.

## The member layer, and its open defect

Inside those rooms, members are **not** monolithic: no-vote rates on content-controlled bills range
**0% to 64%** across 150 members with >=60 votes cast. That is the actionable end — which specific member
in the room is gettable, joined to [[testing/persuadability]].

**IT IS NOT READY.** `committee_votes` carries the RAW `Members.csv` name string, so one legislator can
appear twice — measured: *"Green, W. Chad"* (47/104) and *"W. Chad Green"* (34/80) are one person, split.
This is the same name-format class that hid 2,000 bills from every patron finding
([[failures/assumptions_audit]] #115) and merged two legislators via a hyphen (#118). **The member layer
must route through `corpus`'s canonical resolver before any of it ships.** The venue finding above is
bill-level and unaffected.

## Running it

```bash
python3 tools/calibration/venue_effect.py
```

## Related

[[testing/kill_points]] · [[testing/persuadability]] · [[testing/literature]] ·
[[failures/assumptions_audit]] #120 · [[index]] · [[log]]
