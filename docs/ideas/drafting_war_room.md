---
tags: [ideas, product, war-room, drafting, owner-idea, design-research]
updated: 2026-11-18
status: active
open_loop: v4 queued — input becomes law + part, records shown at that level, memo feed section (§0.7); v3 awaiting review; product build not started.
---

# The drafting room — a War Room for a bill before it has a number

**Owner (2026-11-16/17):** the War Room is for a bill already introduced; also build an assistive room for *designing
and writing* a bill and *choosing who should carry it*. Not every draft is introduced, so organise versions — one idea
offered to many legislators, House and Senate versions, similar versions and duplicates. "I opened the question to what
this could look like … research what it should look like and how it could be useful."

**Mockup (real PA public data; team-private parts are placeholders):** https://claude.ai/artifact/CBPg2ZZ3uoiwiUkbirWL3o
· sister page [[ideas/legislator_portfolio]] · stats behind it [[testing/pa_replication]] (PA) and the Virginia pages
linked inline.

## 0. v2 — the PRE-INTRODUCTION toolkit (owner 2026-11-18)

**Owner:** *"what you're showing would only be this good if a similar version had been introduced before … consider
what tools and info a lobbyist would want to get their bill introduced in the first place … the lobbyist can
manipulate the scenario more … e.g. demographic or district info: this will be especially important for this
community, who represents a lot of these people."* Then: *"'14 nursing homes' and '18% over 65' — always both."*

**Reframe:** after filing you watch a fixed bill; before filing the drafter still controls what it says, which law it
changes (→ the room), its size and cost, who carries it, who signs on, when it is filed and which chamber goes
first. The page answers the questions a legislator asks before saying yes, and lets the drafter try versions.

### 0.1 The flow (mocked on one worked idea: care for nursing-home residents, PA House)
1. **Who it affects, and where** — statewide tiles; map of 203 districts (grey ramp, by share or by beds); top-10
   table with count + share + places + seats. Source: [[knowledge/district_profiles]].
2. **Which room, and what comes after** — choose the law → where bills amending it went (k of n); then the gates:
   the room's record for majority/minority sponsors, House Appropriations, the floor, Senate Appropriations — each
   its own k of n, **never multiplied**.
3. **Who could carry it** — members of that room, A–Z, with standing, seat, district numbers, new member, bills filed,
   past carries. Facts, not a ranking ([[ideas/predictive_lane]] Tier 3).
4. **One district's case** — the leave-behind: one template, numbers change (P25), margins shown.
5. **Support** — our members by district (team data, districts not addresses), co-sponsors to ask, Senate partner
   (shared residents), Senate twin.
6. **When to file** — out-of-committee rate by month of filing for the chosen standing.
7. **Versions and offers** — team-only.

### 0.2 What the tests said (PA, `tools/calibration/pa/pa_drafting.py` → `results_drafting.json`)
| idea | result | on the page |
|---|---|---|
| law amended → room | 74% of titles name one law; for 175 laws with 20+ bills, 83% (bill-weighted) went to the usual room; 83 of 175 go to one room 90%+ | shown (simulator) |
| money gate | House Appropriations returned 3,881 of 4,241 (92%); only 2 of 1,124 House bills that skipped it passed. Senate returned 1,675 of 2,347 (71%) | shown |
| file early | same member, first 3 months vs later: +5.2 pts (715 better / 556 worse); last 6 months 16% (maj) / 3% (min) | shown |
| new members | median 8 vs 14 bills (majority); out rate about the same (+1.7 pooled, +0.1 within member) | shown ("no penalty") |
| Senate twin | out 44% vs 37% (maj), 12% vs 10% (min); law 13% vs 11% — observational | shown, modest |
| district make-up → who carries a subject | 2 of 16 subject×chamber tests held (farming Senate p .015, schools House p .028); ~1 expected by chance | **did not hold** — numbers are the argument, not a forecast |
| most-affected sponsor gets it out more | signs flip by subject | **did not hold** |
| twins whose sponsors share residents | 49% vs 53% (156 of 844 pairs) | **did not hold** |
| bandwidth (a member's 30th bill) | raw 47% → 30% (maj) but −2.1 within member | small, not shown |
| co-sponsorship memo | 95% of 2025–26 bills have one; the 5% without did far better (leadership vehicles) | not a lever |

Virginia ran the district question on VOTES already ([[testing/first_vote]] round 3: census district make-up added
nothing, 85.5% vs 86.1%). PA now says the same for who CARRIES a subject. Two states, same answer: district make-up is
persuasion material, not a predictor.

### 0.3 Design principles applied (the owner asked "which graphs, figures, models, simulators")
Count + share together; map for *where* + table for *how many* (never map-only); the simulator for choices the drafter
controls (chips) with k-of-n gates, never a composed probability; A–Z fact table for carriers; one-template fact
sheet; grey data, blue only for links and the selected district, amber/red only for caution/"did not hold".

### 0.4 What cannot be shown yet (owner was asked to be told)
Member votes (Open States login — owner pastes 5 links) · tried in other states (other states' Open States files) ·
bill cost (PA fiscal notes are per-bill pages; our PA rule is bulk-only) · allies/opponents (PA lobbying disclosure not
scoped) · money by district (funding file not fetched; the school-district join exists) · child-care centres,
enrolment (separate sources) · close vs safe seats (election results; VA found no effect on votes) · personal ties
(no occupation field) · 24 PA hospitals not placed.

### 0.5 Owner review of v2 (2026-11-18) — queued after the stats work
*"The map is good."* Changes asked for, in the owner's words where possible:
1. **Per-draft inputs.** Residents 65+ and nursing homes are one example — how does the page find the affected people
   and places for ANY draft? Does the site infer them or does the team enter them? (Design: the team picks from the
   measure list in [[knowledge/district_profiles]]; any inference from the draft must be structural and shown.)
2. **The map per draft** follows from 1: whichever measure the team picks shades the map.
3. **Consolidate.** Sections are huge — collapse them, use drop-downs.
4. **Cut the text.** Too many small and large text lines; keep what matters. "Write as concisely as possible always on
   a site." Owner is considering writing the whole site in Simplified Technical English (owner wrote "STC").
5. **Simple technical names.** "Which room it goes to, and what comes after" is a terrible name.
6. **Why those bills?** For each draft, how are the earlier bills chosen — what counts as similar? (Today: the law the
   title names — state that rule on screen, or replace it.)
7. **How is "who could carry it" chosen?** Make it clear it is NOT the prediction model (today: members of the room
   the law usually goes to, A–Z).
8. **What is "one district's case"?** Name and explain it (the one-page leave-behind for a meeting).

### 0.6 v3 — the answers (2026-11-18, same artifact, Main board)
- **Two team inputs drive the page:** *Law it changes* (in the product: search the laws named in titles) and *Who it
  affects* (pick one of 16 census measures or 4 place types). A third, *Sponsor's party*, picks which record to show.
  Nothing is guessed from the draft's text.
- **The map and the top 10 follow the pick**, any measure: share for people (with the measure's own base — households
  for renters, workers for farm jobs, adults for veterans), count for places.
- **Sections collapse** (only "Where they live" opens by default); each closed row shows a one-line summary.
- **Short names:** Where they live · Committee path · Earlier bills · Possible sponsors · District sheet · Support ·
  Filing time · Versions.
- **Rules on screen:** Earlier bills = "same law named in the title" (and why some are off-topic); Possible sponsors =
  "members of the committee this law usually goes to, A–Z, facts only — not a prediction"; District sheet = "one page
  for one district; leave it at the meeting".
- Less text: one source line per section; the evidence lives on its own board.

### 0.7 Owner, 2026-11-18 (after v3)
- **District info stays.** "Not a historical predictor of who carries" ≠ "a bad lobbying tool": this is about
  introductions, and members answer to voters. The page shows it as the argument; the evidence board says "not a
  forecast · shown".
- **Law AND part.** The team picks the law and the part of it (PA titles: "…Human Services Code, in public
  assistance…"; VA: the code section). Measured (`results_law_part.json`, House 2017–24): the part barely moves the
  committee (usual committee 80.9% by law → 83.3% by law + part) but moves the odds a lot — Public School Code
  charter schools 4% out vs school health services 24%; Title 18 riot 5% vs assault 23%; Tax Reform Code realty
  transfer tax 52% vs the whole-law bills 9%; Human Services Code public assistance → Health 68%. **v4: the input
  becomes "law + part", and every record on the page is shown at that level (law-only as fallback when the part has
  few bills).**
- **Memo feed** → "memos in circulation on the same law" (ideas before they are bills); see
  [[testing/pa_party_position]].

---
*v1 research (2026-11-17), kept for its sources:*

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

## 8. Owner feedback on the desktop mock, and what v5 changed (2026-11-20)
Mock: https://claude.ai/artifact/YSsrrSEFrFUtuGK4brkFf9 (generator `tools/design_mocks/desktop/`, facts
`tools/calibration/pa/pa_mock_v5.py`).
- **Space:** the site's wide view (1560px, as the Calendar uses) and a 12-column grid; panels sit side by side in rows.
- **"Only 3 laws?"** No. The 3 were picked for the example to show a steering choice. The law field now searches all
  **612 laws named in PA bill titles 2009–26** (26,971 of 36,652 bills name one; 271 laws have 5+ bills).
- **Who it affects:** all 20 measures we hold (16 Census + 4 place counts), now grouped. More are cheap to add (same
  Census pipeline); say which groups matter.
- **Committee path:** the four boxes are now a left-to-right flow, each step with a percent, "k of n" and who it counts.
- **District sheet → One-pager facts:** lines to paste into the team's own one-pager, with a copy button; no PDF.
- **Support → Co-sponsors to ask:** a measured topic pattern: current members who co-sign bills on this law at 1.5× or
  more their usual rate (5+ bills). A raw count put the members who sign everything on top.
- **Earlier bills:** quantified (bills since 2009 · finished their session · of those got out · of those became law)
  and the matching rule named (the law's name in the title: text matching, Standard #3 decision still open).
- **Elections on the map:** a second shading layer ("seat safety") and a last-margin column, both waiting on PA
  election results; "first bill in our data" (tenure floor, from 2009) is real now.
- Names follow the new rule in [[workflow/design_proposal_protocol]] (technical name + plain meaning in brackets).

