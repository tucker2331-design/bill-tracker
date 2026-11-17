---
tags: [ideas, product, war-room, drafting, owner-idea, design-research]
updated: 2026-11-17
status: active
open_loop: Design researched + mocked on real PA data (2026-11-17, artifact CBPg2ZZ3uoiwiUkbirWL3o) — awaiting the owner's answers to the four questions at the end before any build.
---

# The drafting room — a War Room for a bill before it has a number

**Owner (2026-11-16/17):** the War Room is for a bill already introduced; also build an assistive room for *designing
and writing* a bill and *choosing who should carry it*. Not every draft is introduced, so organise versions — one idea
offered to many legislators, House and Senate versions, similar versions and duplicates. "I opened the question to what
this could look like … research what it should look like and how it could be useful."

**Mockup (real PA public data; team-private parts are placeholders):** https://claude.ai/artifact/CBPg2ZZ3uoiwiUkbirWL3o
· sister page [[ideas/legislator_portfolio]] · stats behind it [[testing/pa_replication]] (PA) and the Virginia pages
linked inline.

## 1. Who it is for, and what they are missing
Our primary user writes its own bills: an advocacy org staffed by volunteers and newcomers
([[ideas/lobbyist_jtbd_ideation]] §8a — *"be the experienced lobbyist they don't have"*). §8a already named this as
**V9, the org-as-drafter kit** (patron scouting, redlines, code-section radar, deadline math). This page designs it.

**What the field offers today** (research, 2026-11-17):
- Practitioner guides (state advocacy toolkits) agree on the decisions but give only rules of thumb: start with your own
  legislators or one tied to the district; prefer the chair or a senior member of the committee the bill will go to;
  pick someone who can build support, not just the most sympathetic; recruit a few committee members as co-sponsors;
  have a back-up to the lead sponsor; the legislator will ask who supports and opposes it; ask early (drafting offices
  are busiest before session). Sources: [Citizens Count](https://www.citizenscount.org/how-to/advocate/how-do-i-request-new-law-or-bill),
  [Represent.Us — identifying a bill sponsor](https://represent.us/wp-content/uploads/2023/12/resourcelibrary_IdentifyingABillSponsor_logo.pdf),
  [Blue Avocado](https://blueavocado.org/community-and-culture/legislative-support/), [Hawaii LRB](https://lrb.hawaii.gov/par/?p=980).
- Commercial tools (Quorum, FiscalNote) start at introduction: tracking, a legislator directory, and an "effectiveness"
  score (share of a member's bills out of committee / into law). None is built around the decisions made *before* filing.
- Research: lobbying works mostly as a *subsidy to allies* — information and labour given to legislators who already
  agree (Hall & Deardorff 2006, [APSR](https://www.cambridge.org/core/journals/american-political-science-review/article/abs/lobbying-as-legislative-subsidy/AE4B5D8AB9C2487BB78C2A51BB53E03F)).
  For a drafting org that means the carrier choice is the big lever, not persuading opponents.
- **PA practice:** a member circulates a **co-sponsorship memo** (plain-language intent + invitation to sign) before the
  bill is drafted and numbered. That memo is a public, structured early signal of an idea before it is a bill.

**The gap:** the guides say *what* to decide; nobody shows the evidence for each decision for *this* idea in *this*
legislature. We hold that evidence for two states.

## 2. The decisions, and the evidence we hold for each (claim class in brackets)
| decision before filing | what the screen shows | measured evidence |
|---|---|---|
| **Has this been tried?** | every earlier bill that changed the same part of the law: carrier, room, how far | [measured] committees remember: VA died before → dies again 80% vs 26% ([[testing/room_memory]]); PA same-carrier refile 93% vs 35% (OR 24), 25% of PA bills reuse an earlier title |
| **Which room will it go to?** | the room this part of the law is sent to, and that room's record for majority- and minority-party sponsors, *k of n* | [measured] VA: the code title decides the room; room worth +11 to +18 ([[testing/venue_shopping]]). PA: room rates 16–56%; same part of the law in the higher-rate room +4 pts. The room is set by *what the draft amends* — a drafting decision |
| **Who carries it?** | members of the room + past carriers, each with standing, seat, own record vs expected, prior carries of this part of the law — **sorted by name, not ranked** | [measured] majority standing (VA +26; PA within-member ±33 across the 2023 flip — [[testing/bill_mix_confound]]); seat on the deciding room (VA subcommittee +14; PA committee +20); PA majority chair's own bills 80% vs 41%; carrier record is a stable trait (PA r 0.46, VA r 0.46–0.51 — [[testing/carrier_effect]]) |
| **Whom to ask to co-sign?** | the room's majority chair; majority-party members of the room | [measured] chair co-signs: VA 92% vs 70%; PA +40 pts within sponsor (123 better, 23 worse). Majority co-sponsor share is usable in both ledgers. **Not** "add a cross-party co-sponsor": VA retracted that lever on clean data (+4 pts, p 0.39) |
| **One chamber or both?** | the House/Senate twin history for this part of the law | [measured] when twins split, the House one lived 47% (PA, 312 of 667) / ~50% (VA): the room decides, not the chamber ([[testing/venue_effect]]) |
| **How to word it?** | the title form your draft uses, with its record | [measured] amend an existing law vs create a new one: VA +18 / +14; PA +4 / +3 — small in PA ([[testing/enacting_clause]]) |
| **Which version went where?** | versions × legislators × status (offered / agreed / declined / filed), House and Senate twins | [team-entered] no public source: drafts that are never filed exist only because the team records them |

Everything in the first six rows is **public record we already ingest** (VA: LIS + Open States; PA: the Bill History
exports + roster feed). The seventh is the team's own data.

## 3. The objects (nested-object test, [[design/object_page_patterns]])
- **Idea** (its own page; the unit the team thinks in) → has many **Versions** (text, author, date; one may be a
  House/Senate twin of another) → each Version has many **Offers** (to one legislator: offered / agreed / declined) →
  an agreed Offer becomes a **Filed bill** (HB/SB), which opens today's War Room bill page.
- **Part of the law** (structural: VA code section from the enacting clause; PA statute + section from the title) is
  the join that finds earlier bills and the likely room. It is a fact about the draft, not a "similar bill" judgement —
  so it passes P20c (no smuggled judgement). True duplicates (same text) are flagged only by the text comparer
  ([[architecture/text_similarity]]), never by title.
- **Legislator** links out to the [[ideas/legislator_portfolio]].

## 4. Screens (mocked)
1. **Idea page** — header (idea, the part of the law, team-only notice); four count tiles; *Tried before*; *Where it
   would go*; *Who could carry it*; *Co-sponsors to ask*; *One chamber or both?*; *Versions*.
2. **Versions board** (next mock) — one row per version, columns per legislator offered, cells = status; twin links.
3. **Filing hand-off** — when a version is filed, the idea page links to the War Room bill page and keeps the history.

## 5. Rules it must follow
- P25: every sentence is one template with values (*"k of n bills from majority-party sponsors got out"*); no prose
  per case. P26: counts always with their denominator.
- [[ideas/predictive_lane]]: facts (Tier 1) only. A ranked "best carrier" list is a Tier-3 prediction and needs the
  calibration gate + the owner's go/no-go — so the carrier table is sorted by name.
- Privacy: drafts and offers are the most sensitive data the product would hold — team-private (Worker + D1, the
  contact log's path), never in the public sheet.
- Visual: grey by default, small-caps text for states, no colour bands ([[design/dashboard_and_visual_language]]).

## 6. MVP cut (proposal)
**Build first (public data, no new source):** the idea page's *Tried before*, *Where it would go* and *Who could carry
it* — for both states, from data we already parse. **Then** the team-private Versions/Offers store (D1). **Later:**
text upload + redline between versions (B1), cross-state "tried elsewhere" (Open States JSON text), the co-sponsorship
memo as an early signal (PA), any ranking (Tier 3, gated).

## 7. Questions for the owner
1. Who may see a draft — the whole team, or only its author until shared?
2. Full draft text inside the product, or a link to the team's own document?
3. "Who could carry it": stay a fact table sorted by name (Tier 1), or earn a ranked list through the calibration gate?
4. One state per idea, or an idea that spans states (the same policy drafted for VA and PA)?
