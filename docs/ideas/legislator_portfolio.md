---
tags: [ideas, product, legislators, portfolio, owner-idea]
updated: 2026-11-16
status: stub
open_loop: Owner idea 2026-11-16, scoped only — needs the owner's answers to the open questions below, then a grey-by-default mockup before any build.
---

# The legislator portfolio — a member as a whole (owner idea, 2026-11-16)

**Owner, in their words:** instead of only looking at committees or individual votes, look at a legislator as a
whole — to decide who should carry what, or generally when we need to look at legislators for other reasons, or to
see who is more likely to do what.

Sister page: [[ideas/drafting_war_room]] (its "who should carry this?" reads from here). Prior art:
[[ideas/predictive_lane]] (REFRAME 2026-07-27: an entity-statistics layer, not a prediction widget — this page is
that layer's member view), [[architecture/roster_and_votes_ingestion]], [[testing/first_vote]].

## What one member's page holds — facts first, every number with its denominator

| section | facts | source (VA today) |
|---|---|---|
| **Who** | party, district, chamber, years served, leadership / chair roles | roster ingest (#236, structural) |
| **Carries** | bills as chief patron, by subject and by how far they got (advanced / killed / carried / law), this session and past | Sponsors.csv + HISTORY.CSV (bulk blobs we already fetch) |
| **Co-sponsors** | whose bills they sign, who signs theirs (across party?) | Sponsors.csv |
| **Rooms** | committees and subcommittees they sit on; their vote record there | roster + VOTE.CSV (318,282 member-vote pairs, W5) |
| **Votes** | how often with their party, on what kinds of bills they break | VOTE.CSV |
| **Our history** | the team's contacts and positions with this member | contact log (D1, team-private) |

Each section is a count out of a total ("carried 14 bills, 9 advanced"), never a bare rate — Standard #7.

## "Who is more likely to do what" — the line we must not cross without the gate

Describing what a member HAS done is Tier 1/2 (measured history). Ranking members by what they WILL do is Tier 3 and
needs the calibration harness and the owner's go/no-go ([[ideas/predictive_lane]]). Measured so far in Virginia:
the first-vote model scored 85.9% on the locked 2026 test (room outcome 91.5%) ([[testing/first_vote]]); content
predicts which opposite-party member crosses, AUC 0.51 → 0.70 held out ([[testing/content_votes]]). Neither is
approved for display yet.

## Multi-state

The page is the same for every state, fed by that state's roster and votes. PA has a roster (committee members from
PA's own RSS, `states/pa_roster.py`) but no per-member votes ingested yet — see [[testing/pa_predictive_plan]].

## Open questions for the owner

1. Where does it live — its own tab ("Legislators"), or reached by tapping any member name anywhere?
2. Which sections first? (Carries + Rooms are fully sourced in VA today; Votes needs a display decision.)
3. Does "who should carry X" rank members (Tier 3, gated), or show a shortlist with facts beside each?
4. Our-history section: visible to the whole team, or per person?
