---
tags: [testing, calibration, sources, compliance, fate, influence]
updated: 2026-10-14
status: active
open_loop: Fiscal-statement collection (2025/26, fiscal_statements.py) running -- parse and run fiscal_effect.py when done.
---

# Influence, relationships and outside sources (2026-10-14)

Owner, after reviewing a Gemini concept page: *"testimony data has no influence in every context ... you havent looked
hard enough for transcripts ... influence scores and relationship maps definitely could have influence if you find the
numbers ... what is a cbo fiscal score favorability and the other scores ... can u replicate with serious findings?
... be careful with TOS and stay conservative."*

## Sources checked (robots.txt and terms read before any data was taken)

| source | what it has | access | used? |
|---|---|---|---|
| **Internet Archive — "virginiageneralassembly" collection** | 1,083 committee/floor meetings 2008–2026 with **closed-caption text files** (2026 House: 143 items; Senate 2023–25: ~127) | robots.txt disallows only /control/ and /report/; advancedsearch + metadata are its public programmatic interface | **Yes — caption text only, never video** (`ia_transcripts.py`) |
| House committee video (Sliq Harmony, `sg001-harmony.sliq.net/00304`) | every House committee/subcommittee meeting since 2020; the platform supports captions | robots.txt **`Disallow: /` for all** | **No** — one page was read before the rule was seen; nothing more |
| Senate committee video (Granicus, `virginia-senate.granicus.com`) | Senate meetings since 2017 | robots.txt **`Disallow: /` for all** | **No** |
| Senate YouTube channel | the same video, auto-captions | YouTube terms: captions only through its API, and caption download is for the video's owner | **No** |
| Committee minutes | — | LIS help: minutes are not kept for committees or subcommittees | does not exist |
| HODSpeak (House Clerk's public-comment site) | written testimony per bill per meeting | robots.txt empty (allowed) | **Yes** — counts and organization names only, never a person's name, locality or text |
| Lobbyist Registration Database (Secretary of the Commonwealth) | registrations and expenditure reports by principal | the state page says the database "is experiencing technical problems"; no public link; contact lobbyist@governor.virginia.gov | No — no bill-level positions in it, and no working access |
| The Accountability Project copy (2016–2019, from a records request) | 4,673 registration/expense rows | site account (via MuckRock) | No — no bills or legislators, and assistants may not create accounts |
| Center for Effective Lawmaking — State Legislative Effectiveness Scores (through 2025) | a peer-reviewed effectiveness score per legislator | robots allow; **site terms: content "may not be reproduced, modified, or used without CEL's express written permission"** | **No** — their published METHOD was rebuilt from our own records instead |
| Fiscal impact statements (Dept. of Planning and Budget) | the cost of each bill | dates are in HISTORY.CSV (already held); the documents are on LIS (`BillHistoryReferences`) | dates used; **amounts need the owner's OK** (LIS API, 2025/26 only) |
| ELECT campaign finance | contributions, incl. member-to-member giving | agency files, no key (see [[knowledge/campaign_finance_source]]) | only 2023-10 and 2024-01 held; more months need the owner's OK to download |

**Transcripts — the workaround (2026-10-14).** The official hosts forbid automated collection, but the **Internet Archive**
mirrors General Assembly meetings with the broadcast closed captions (upper case, `>>` at each speaker change, bills read
as "SENATE BILL 1265"). `ia_transcripts.py` takes the caption text only; `transcripts.py` cuts each meeting into per-bill
segments (minutes debated, speaker turns, public speakers, stated support/opposition, legislators named, motions heard);
`transcript_effect.py` tests them. Coverage is the Archive's, not ours: dense for the 2026 House and 2023–25 Senate.

**Campaign finance:** ELECT (`apps.elections.virginia.gov`) now answers "Access Denied" to automated requests, even for
robots.txt — treated as a refusal; not worked around. Money ties use the two months already held (2023 election).

## Relationships and influence → does the bill get out of its first committee? (`influence_fate.py`)

Never tested before on fate (relationships and chairs were tested on member votes only). Year-ahead, 2022–2025,
fate.py's model plus one group, per-bill log loss pooled:

| group | inputs | z | verdict |
|---|---|---|---|
| co-sponsorship network | who signs on to the patron's bills, cross-party supporters, PageRank | 1.8 | no new information |
| chair ties | patron chairs the committee, chair's party, chair backed the patron before, patron backed the chair, chair on this bill | −1.1 | no new information |
| effectiveness record (our rebuild of the CEL method) | share of the patron's earlier bills that passed their chamber / became law | 1.6 | no new information |

The model already carries most of this through patron standing, the patron's own record and co-patron counts.

**But one relationship is a large, specific lever — the committee chair co-sponsoring THIS bill:**

| | same patron, same session | result |
|---|---|---|
| chair is a co-patron of this bill (2020–2025) | 260 of 283 advanced (92%) vs 70% of that patron's other bills | better for 140 patrons, worse for 18, p ≈ 1e-24 |
| the same, 2025 only (co-patrons verified as at filing) | 64 of 65 (98%) vs 77% | better for 38, worse for 1, p ≈ 1e-10 |
| chair co-sponsored the patron's EARLIER bills | 69% vs 65% | 191 better, 191 worse — **no effect** |

The relationship history does not matter; the chair's name on this bill does. Still an association (a chair may sign on
to a patron's strongest bill) — same caveat as co-patrons ([[testing/first_vote]]).

## Chair ALIGNMENT, measured from the chair's own record (`chair_alignment.py`, 2026-10-14)

Owner: "chair alignment is how much the chair aligns with the bill". Inputs, earlier sessions only: the chair's yes rate
on this patron's earlier bills, on near-identical earlier bills, the chair–sponsors distance on the left-right map, same
party. **Year-ahead, added to the fate model: z = 3.1 — passes, barely** (gain in 2022, 2024, 2025; loss in 2023).

| same patron, same session, bills before differently-aligned chairs | result |
|---|---|
| chair backed ≥ 75% of this patron's earlier bills | 72% vs 63% advanced; patrons better 172, worse 158 (p = 0.47) — no clear within-patron effect |
| chair backed ≥ 75% of near-identical earlier bills | 9 bills — too few |
| **money:** the chair's campaign gave to the patron's (2024–25 bills, 533 member-to-member gifts) | 72% vs 70%; better 12, worse 5 (p = 0.14) — leans positive, unproven |
| **money:** the two campaigns share ≥ 5% of donors | 71% vs 63%; better 49, worse 37 (p = 0.24) — leans positive, unproven |

## Gemini's three "scores", replicated with real data

| Gemini's score | Virginia's real version | finding |
|---|---|---|
| "Committee Chair Alignment 88%" | the chair's own record on this patron's and similar bills, distance on the left-right map | small but real: passes the forecast test at z = 3.1. Separately, the chair CO-SPONSORING the bill: +22 points within patron |
| "Bipartisan Co-Sponsor Ratio 79%" | co-patrons at filing, own and other party | real: the co-patrons group passes both forecasting tests (z 7.7 / 11.0, [[testing/first_vote]]); no co-patrons: 20 vs 6 in 100 die without a single yes |
| "CBO Fiscal Score Favorability 64%" | DPB fiscal impact statement | **having** a statement says nothing (z 0.6 with a fair cutoff; the first run's z 10.1 was a leak — [[failures/assumptions_audit]] #142). What the statement **says** (the cost) is untested — needs the documents |
| "Influence 96/100" | legislative effectiveness (CEL method) | rebuilt; adds nothing to fate forecasts (z 1.6) |

## What is said in committee (Internet Archive captions, `transcripts.py` / `transcript_effect.py`, 2026-10-14)

303 meetings collected (caption text only); 204 session meetings; **3,205 bill debates matched to bills** (2026 House
1,843; 2026 Senate 975; Senate 2019–2025 387); 1,424 with a recorded vote the same day. Parser note: 2019 captions are
upper case with `>>` speaker marks, 2023+ captions are mixed case without them and split "House Bill / 1104" across
lines — the first parser found bills in 2 meetings, the fixed one in 162.

**1. Debate vs the room's vote that day** (median): unanimous yes 1.0 min, 3 turns, public speakers in 5%; party-line
1.9 min, 5 turns, 12%; mixed split 2.1 min, 7 turns, 10%. Contested votes get about twice the airtime.

**2. Forward-looking — bills the committee PASSED, heard in their own chamber (649):**

| at the committee hearing | passed full chamber | became law |
|---|---|---|
| public opposition stated | 85% vs 92% | 59% vs 67% |
| debate over 10 minutes | 87% vs 91% | 53% vs 68% |
| members of the public spoke | 82% vs 92% | 54% vs 68% |

Holds within committee-vote shape, smaller: unanimous-yes bills with stated public opposition became law 67% vs 76%
(58 vs 304 bills); split-vote bills where the public spoke 44% vs 57% (54 vs 233). Consistent, small samples — a signal,
not a proven effect. Not tested as a model input: the coverage is mostly 2026, the locked test year.

**3. Who speaks:** legislators named in a bill's debate broke from their party's majority that day 5.2% of the time
(24 of 460) vs 2.7% for everyone else (816 of 30,415) — engagement goes with defection (same meeting, descriptive).

**Definition trap fixed:** the corpus `passed` flag means "had a passage vote", not "became law" (2025: 1,139 vs 721).
`transcript_effect.py` and `influence_fate.py` (effectiveness record) now read the Governor's approval / chapter.

## Testimony by WHO and WHICH SIDE (`testimony_lineup.py`, 2026-10-14)

HODSpeak re-collected 2021/2022/2024/2025 with each organization's side (1,404 House meetings; organization names and
counts only). Each organization's lean is LEARNED from earlier years — how Democrats and Republicans actually voted on
bills it supported vs opposed — never assigned by hand (375 organizations with a lean for 2022, 564 for 2024, 735 for 2025).

| test | result |
|---|---|
| **does the bill get out of committee** — House bills with testimony before their first decision (2022: 1,167; 2024: 1,446; 2025: 1,075), stacked on fate.py year-ahead | **ACCEPT, z = 3.9**, gain in every year (+0.028 / +0.007 / +0.003) |
| member votes, year-ahead stacked (5.9–11.9% of ballots carry a known lineup) | z = 0.8 — no gain |
| lineup vs the actual party gap at the first vote (214 bills) | r = 0.45 |
| two-sided fights (organizations on both sides, 25 bills) vs one-sided (189) | mean |party gap| 0.77 vs 0.55 |

**The stakeholder lineup predicts whether a bill MOVES, not how members vote** — the panel's prediction from Butler &
Miller (lobbying predicts agenda progress, not committee votes). The earlier "no influence" result came from counting
comments; who is on which side is what carries the signal.

**Effectiveness record, rerun with the true "became law" (Governor's approval / chapter):** z = 2.4 — still no.

## Does it hold beyond the sample? (2026-10-14, `replicate_2026.py`, `.cache/transcript_check.py`)

| finding | check | result |
|---|---|---|
| chair co-sponsors the bill | each year separately, same patron | 2020 85% vs 66% (26 better / 6 worse) · 2021 98 vs 87 (18/1) · 2022 84 vs 56 (20/4) · 2024 90 vs 69 (38/6) · 2025 98 vs 77 (38/1) — every year p < 0.002 (2023: no patron with both kinds) |
| chair co-sponsors the bill | **2026, never used to choose it** | **91% vs 73%; 43 better, 7 worse, p = 2e-7 — replicates** |
| chair alignment (chair's own record vs the bill) | **2026, trained 2020–2025** | **z = 3.2 on 2,325 bills — replicates** |
| contentious hearing → less often law | one row per bill, controlling for unanimous vote, patron's party, chamber | odds ratios 0.62–0.72, **p = 0.07–0.17 — not established**; 383 of 467 bills are the 2026 House, the Senate has too few |
| testimony lineup → bill fate | 2026 replication | pending (2026 House testimony being collected) |
