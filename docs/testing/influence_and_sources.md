---
tags: [testing, calibration, sources, compliance, fate, influence]
updated: 2026-10-14
status: active
open_loop: Testimony re-collected with each organization's side (va_hodspeak_v2) -- run testimony_lineup.py when the collection finishes; fiscal-statement AMOUNTS need the owner's OK to fetch statement documents from LIS (2025/26 only); money ties need more ELECT months downloaded (owner OK).
---

# Influence, relationships and outside sources (2026-10-14)

Owner, after reviewing a Gemini concept page: *"testimony data has no influence in every context ... you havent looked
hard enough for transcripts ... influence scores and relationship maps definitely could have influence if you find the
numbers ... what is a cbo fiscal score favorability and the other scores ... can u replicate with serious findings?
... be careful with TOS and stay conservative."*

## Sources checked (robots.txt and terms read before any data was taken)

| source | what it has | access | used? |
|---|---|---|---|
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

**Transcripts exist** (video archives on both sides) but every copy sits behind a robots rule or platform terms that
forbid automated collection. The legitimate routes: ask the House and Senate clerks for caption text, or include it in
the DLAS arrangement ([[knowledge/lis_tos_commercial_use]]).

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

## Gemini's three "scores", replicated with real data

| Gemini's score | Virginia's real version | finding |
|---|---|---|
| "Committee Chair Alignment 88%" | chair co-sponsors the bill / has backed the patron | co-sponsoring THIS bill: +22 points within patron (above); past backing: nothing |
| "Bipartisan Co-Sponsor Ratio 79%" | co-patrons at filing, own and other party | real: the co-patrons group passes both forecasting tests (z 7.7 / 11.0, [[testing/first_vote]]); no co-patrons: 20 vs 6 in 100 die without a single yes |
| "CBO Fiscal Score Favorability 64%" | DPB fiscal impact statement | **having** a statement says nothing (z 0.6 with a fair cutoff; the first run's z 10.1 was a leak — [[failures/assumptions_audit]] #142). What the statement **says** (the cost) is untested — needs the documents |
| "Influence 96/100" | legislative effectiveness (CEL method) | rebuilt; adds nothing to fate forecasts (z 1.6) |
