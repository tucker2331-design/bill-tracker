---
tags: [ideas, product, legislators, portfolio, owner-idea, design-research]
updated: 2026-11-18
status: active
open_loop: Legislator page v2 mocked 2026-11-18 in the v9 language (artifact CBPg2ZZ3uoiwiUkbirWL3o, Legislator board, Rep. Lisa Borowski): district map with zoomed inset, district facts, bills vs expected, committees, votes, co-signers, memos, team history — awaiting review.
---

# The legislator portfolio — a member as a whole

> **v2 (2026-11-18), the page used from drafting through introduction to lobbying.** Sections: map (state view with
> the district highlighted by default; a top-right inset zoomed to the district and every district that touches it —
> owner's spec), District (every census measure as count + share vs the state, sorted by how much the district
> differs; places; local governments; senators who share it; income), Bills they carry (k out of committee vs
> expected per session; laws they work on), Committees, How they vote (contested roll calls: with party k of n,
> crossed, rank in party; crossing repeats r 0.84 except across a majority change), Who they work with (co-signers
> both ways, other-party share), Ideas they circulated (memo titles), Our history (team only). Facts only; no score.
> Data: `tools/calibration/pa/pa_legislator_example.py`.

**Owner (2026-11-16/17):** instead of only committees or individual votes, look at a legislator as a whole — to decide
who should carry what, or whenever we need to look at legislators for other reasons, or who is more likely to do what.

**Mockup:** https://claude.ai/artifact/CBPg2ZZ3uoiwiUkbirWL3o (second screen: Rep. Liz Hanbidge, PA House, every number
from PA's public record) · sister page [[ideas/drafting_war_room]] · stats [[testing/pa_replication]],
[[testing/profiles]], [[testing/carrier_effect]].

## 1. Why a whole-member page, and what exists
- The drafting room's hardest question — *who carries it?* — is a question about a person, not a bill. So is "who do we
  call first" in the War Room. Today the facts sit scattered (roster, bill list, votes, our contact log).
- **The field:** commercial tools offer a legislator directory, contact logging and an "effectiveness" score — Quorum's
  is the share of a member's bills out of committee and into law, ranked against party peers; FiscalNote's weights how far
  each bill moves ([Bloomberg via Rep. Peters](https://scottpeters.house.gov/in-the-news/the-moneyball-effect-on-k-street-the-influence-game-gets-scientific),
  [FiscalNote](https://ca.marketscreener.com/news/latest/FiscalNote-Names-Most-Effective-U-S-State-Legislators-24788755/)).
  The research standard is the Center for Effective Lawmaking's State Legislative Effectiveness Score: bills sponsored ×
  how far they move × substantive weight, judged against a **benchmark of what a member like them would do**
  ([CEL](https://thelawmakers.org/legislative-research/legislative-effectiveness-in-the-american-states), APSR 2024).
  CEL found effectiveness rises with majority status, chairs and seniority — the same things our tests found.
- **What none of them do for our user:** say which numbers are *stable traits* (worth acting on) and which are noise,
  and keep every number in "k of n" a volunteer can read.

## 2. What the page holds — only facts, each with its denominator
| section | shows | evidence it is worth showing |
|---|---|---|
| **Who** | party, district, standing this session, first session | structural (roster + export) |
| **What they carry** | per session: bills, out of committee vs **expected**, passed their chamber, became law | the "expected" column is CEL's benchmark idea done our way: same session × chamber × standing × committee. Carrier record repeats session to session: PA r 0.46, VA r 0.46–0.51 |
| **Rooms** | seats and roles now; where their bills went and how far | the seat on the deciding room matters (PA +20 majority; VA subcommittee +14) |
| **Who they work with** | who co-signs their bills, whose they co-sign | co-sponsor ties are public and stable; the chair-as-co-signer effect (PA +40 within sponsor) makes "who signs whose" actionable |
| **Habits that hold** | only traits shown to repeat: carrier record (PA r 0.46), signing with the other party (PA r 0.72, VA 0.78/0.48), focus on one room (PA r 0.60, VA 0.60/0.31) | traits that failed the repeat test are *left off* and listed in [[testing/what_we_left_off]] |
| **How they vote** | VA: persuadability, independence, subject-specific defection ([[testing/persuadability]], [[testing/member_subject]]); PA: after batch 3 | VA measured; PA needs the Open States vote files |
| **Our history** | the team's contacts and positions | team-private (contact log, D1) |

## 3. "Who is more likely to do what" — the line
Describing what a member *has done* is Tier 1. A ranking of who *will* do something is Tier 3 under
[[ideas/predictive_lane]] — it needs the calibration harness and the owner's go/no-go. The mock therefore shows
percentiles and k-of-n facts, not a score. Measured so far: VA first-vote model 85.9% on the locked 2026 test
([[testing/first_vote]]); PA vote models wait on batch 3.

## 4. Rules it must follow
P25 (one template per sentence), P26 (k of n), grey by default, small-caps states, no badges for provenance; names of
real officials with public-record facts only; nothing from the contact log leaves the team.

## 5. MVP cut (proposal)
**First:** Who · What they carry (with expected) · Rooms · Who they work with · Habits that hold — both states, from data
we already parse (VA: LIS + Open States; PA: exports + roster). **Then:** How they vote (PA after batch 3). **Later:**
district facts, money (VA found donor alignment and race margin do not move votes — [[testing/money_and_vulnerability]] —
so they would go to the "left off" drawer, not the page).

## 6. Questions for the owner
1. Its own tab ("Legislators") or reached only by tapping a name?
2. Show percentiles ("ranks 31 in 100 House members") or only the member's own k of n?
3. "Our history" visible to the whole team or per person?
4. Same page for both states now, with PA's votes section marked "not loaded" until batch 3?

## 7. Owner feedback on the desktop mock, and what v5 changed (2026-11-20)
Mock: https://claude.ai/artifact/PZDNqxWPTBVFgJjD7z6aB4.
- **Space and priority:** wide view, 12-column grid. Committees and Recent memos (ideas they're circulating) moved up
  to the first two rows.
- **Rank:** "Party-line rank: 75 of 128 House Democrats (1 = votes with the party most often on contested roll calls)".
- **Who they work with → Repeat co-signers + Whose bills they sign:** patterns, not one-offs. A member is listed only
  with 10+ shared bills AND 1.5× or more their usual rate on other bills from the same party; the committee most shared
  bills went to is shown. Measured on Borowski 2023–26: the top raw co-signer (Sanchez, 35 of 38) signs 86% of all
  House Democrats' bills, so she is left out as habitual; Prokopiak signs 29% of hers against 4% usual (8.1×). 12 of
  135 co-signers and 15 of 141 sponsors meet the rule.
- **Elections next to the map:** placeholder block (2024/2022 general margin, primary, registration). **Open:** the PA
  election-results source (PA Department of State returns or Klarner's state legislative returns) needs the owner's
  OK and a terms check before ingest.

