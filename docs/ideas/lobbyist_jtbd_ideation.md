---
tags: [ideas, product, strategy, commercial, jtbd]
updated: 2026-07-13
status: active
---

# Zoom-out: the lobbyist's jobs, the feature space, and the commercial moat (2026-07-13)

> **Owner ask:** *"assume the role of an experienced lobbyist and bill writer… what tools do you want/need…
> what could make our site unique from competitors and open an avenue for commercial sale… be expansive."*
> This page is the expansive pass — the raw idea space for the owner to NARROW. Nothing here is committed.
> The locked single-org VA spec stays [[ideas/product_vision]]; this is the layer above it (per-state
> features that eventually roll up to the master dashboard).

## 0. Protocols used (so the zoom-out is a method, not a vibe)

1. **Jobs-to-be-Done** (Christensen/Ulwick) — map the lobbyist's *hiring criteria*, not feature wishes.
   The vision doc already found the core job: *never miss, always know, act in time, report with
   confidence*. This pass expands to the FULL job map (a year, not a day).
2. **Day/Year-in-the-Life simulation** (contextual-inquiry stand-in) — walk the VA GA annual cycle
   role-by-role and harvest pains at each step.
3. **Kano model** — classify every idea: *basic expectation* (absence kills the sale), *performance*
   (more = better), *delighter* (differentiator nobody asks for but nobody leaves after).
4. **Amazon Working Backwards** — the mock press release test for the flagship differentiators.
5. **Premortem** (Klein) — "it's 2028 and the product never sold" → reasons → reversed into requirements.
6. **Moat lens** — for each candidate: can FiscalNote/Quorum copy it in a quarter? If yes it's a feature,
   not a moat.

## 1. The personas (four buyers, one platform)

| Persona | Who | What they pay for |
|---|---|---|
| **Contract lobbyist** ("the third house") | 5–15 clients, lives in the GA building Jan–Mar | Time during session; client reports (their billing artifact); not missing anything |
| **In-house GR director** | One org, reports to a GC/CEO | Certainty + defensible reporting up; the current B1 product user |
| **Policy counsel / bill drafter** | Writes/amends bill text | Text tools: diffs, code-section impact, drafting support |
| **Association exec** | Trade association, many members | Member-facing digests, "what we did for you" artifacts |

## 2. A year in the life (VA-specific; where the pains live)

- **Interim (May–Nov):** study commissions, workgroups, regulatory follow-through, client renewals,
  relationship maintenance, fundraisers. *Pain: interim meetings are scattered and poorly surfaced —
  our off-season interim window already ingests them; nobody else covers them well.*
- **Pre-session (Nov–Jan):** drafting requests to DLS, prefiled bill triage begins (~2,500+ bills),
  strategy memos. *Pain: triage — catchlines lie; reading 500 bills to find the 40 that matter.*
- **Session (Jan–Mar, 46/60 days):** THE sprint. Dockets drop late night for 7:30 AM subcommittees;
  amendments and substitutes rewrite bills mid-flight; crossover guillotine; floor calendars; conference
  committees. *Pains: minutes matter; docket-drop at 10 PM; two hearings at once; the substitute nobody
  read; whip counts by hand; testimony prep at midnight.*
- **Reconvened/veto session (Apr):** governor's amendments + vetoes, override math. *Pain: amendment
  text drops late; override whip counts.*
- **Post-session:** client final reports, VA lobbyist disclosure filings, campaign season. *Pain: the
  report and the disclosure are BOTH reconstructions of "what did I do all session" — nobody logged it.*

## 3. The idea space (expansive — Kano tag on each)

### A. Time & attention (the session sprint) — our engine's home turf
- **A1. Docket-drop alert** — "SB204 was just docketed: House Courts Sub #2, tomorrow 7:30 AM, Room B,
  agenda PDF." We already resolve meeting times (incl. "15 min after adjournment" chains) better than
  anyone. *(performance→delighter at our precision)*
- **A2. The Tonight Brief** — auto evening digest: everything docketed tomorrow across tracked bills,
  times/rooms/agenda links/livestreams, collisions flagged. The 10 PM anxiety-killer. *(delighter; the
  daily habit hook)*
- **A3. Hearing-collision radar** — two tracked bills, same time, different rooms → surfaced with which
  is likelier to actually be reached (agenda position!we have AgendaOrder). *(delighter)*
- **A4. Provable freshness SLA** — "data as of X min ago" is already built; make LATENCY a marketed,
  measured number (the witness log can prove detection-to-alert time). *(basic→performance)*
- **A5. Predicted docket** — before the official docket posts, predict "likely heard next week" from
  committee patterns + referral order (clearly flagged as derived — trust rules apply). *(delighter)*

### B. Text intelligence (the bill-writer's desk)
- **B1. Version diff / substitute redline** — any two versions, one click; alert "the substitute deleted
  your §2 carve-out." LIS publishes full text; nobody reads substitutes in time. *(performance — table
  stakes for counsel, weak in incumbents at state level)*
- **B2. Watch a CODE SECTION, not a bill** — "alert me on anything touching Code of Virginia § 58.1-3506."
  Bills are transient; the code section is the client's permanent interest. *(delighter, high moat — needs
  the amends-map we can parse from bill text/titles)*
- **B3. Catchline lie-detector** — AI summary vs catchline divergence flag ("titled 'technical
  corrections'; actually rewrites SCC rate authority"). Triage killer-app. *(delighter)*
- **B4. Cross-state model-bill radar** — "this VA bill is 91% textually similar to TX HB1234 (died) and
  OH SB77 (passed)" — the multi-state engine's first *product* payoff, and the master-dashboard's unique
  view. *(delighter; strong moat once we're multi-state)*
- **B5. Companion/copycat detection in-session** — House/Senate companions and near-duplicates auto-linked;
  act once, track both. *(performance)*
- **B6. Amendment drafting assistant** — generate amendment text in DLS drafting style, auto-cite affected
  sections, check against the drafting manual. LLM UNDER the trust layer (draft = clearly labeled draft).
  *(delighter; bill-writer persona's hook)*
- **B7. Fiscal-note watcher** — alert when the fiscal impact statement drops + what it says; predicts the
  money-committee re-referral (we already track re-referrals structurally). *(performance)*

### C. People & influence (the relationship layer)
- **C1. Legislator dossier** — per member: votes on YOUR tracked issues, committee seats, patron history +
  pass-rate, district, VPAP campaign-finance + gift-disclosure overlay (public data, linkable). *(performance)*
- **C2. Whip board** — a shared, live support/oppose/undecided board per bill; hallway-updatable on
  mobile; optional model-predicted lean per member (published research: 80–90% roll-call accuracy) —
  ALWAYS labeled predicted vs confirmed (trust layer). *(delighter; the hearing-room tool)*
- **C3. Committee math** — "needs 5 of 8 in Senate Courts; 3 members voted against similar bills twice;
  the 2 swing seats are X and Y." Computable from our archive + votes. *(delighter)*
- **C4. Influence pathfinding** — who co-patrons with whom, who carries what successfully where; "the
  right patron for THIS bill in THIS committee" from historical win-rates. *(delighter)*
- **C5. Patron scouting report** — win-rate by patron × committee × subject; contract lobbyists choose
  patrons — this is money. *(delighter)*

### D. Prediction & odds (the insight layer — the session archive's payoff)
- **D1. Bill survival odds** — calibrated per-stage probability, updated on every action; VA kills ~⅔ of
  bills, mostly in predictable places. *(delighter; must be calibrated + honest per trust rules)*
- **D2. Committee mortality tables** — historical kill-rate per committee/sub (we archive every session;
  this is the historical-tracker §9 park, now with a commercial reason). *(performance)*
- **D3. Deadline math** — "to beat crossover, this bill needs sub + full + 3 floor readings in 9
  legislative days — mathematically tight." Countdown per bill. *(delighter, cheap to build — we have the
  calendar + stage machine)*
- **D4. "Bills like this" outcomes** — same subject/committee/patron-party historical outcomes. *(performance)*

### E. Client & team workflow (the commercial multiplier for firms)
- **E1. Multi-client workspaces** — position per client (support/oppose/watch/amend), per-client tracked
  sets, one lobbyist view across all clients (the §9 park, promoted: THIS is what contract lobbyists pay
  for). *(basic for the firm segment)*
- **E2. Auto client reports** — weekly branded digest per client + the session-end final report generated
  from the activity trail. Lobbyists spend nights building these; it's their INVOICE justification.
  *(performance→delighter; possibly the single strongest commercial hook)*
- **E3. Activity log / CRM-lite** — log meetings/testimony/positions in 10 seconds from the bill card;
  doubles as the compliance record and the report source. *(performance)*
- **E4. Compliance autopilot** — prefill VA lobbyist disclosure filings from the activity log. *(delighter;
  strong lock-in — compliance data is sticky)*
- **E5. Team hearing coverage** — who's in which room; shared live notes pinned to the meeting record.
  *(performance)*
- **E6. Testimony bank** — searchable archive of the org's past testimony; auto-suggest for similar bills.
  *(delighter)*

### F. Coverage expansion (data we don't ingest yet — each is a B2-style inventory question)
- **F1. Hearing audio/video intelligence** — we ALREADY extract livestream links; next: transcript +
  speaker ID + "what did the chair say about my bill at 8:47 AM," with the clip. Incumbents do this for
  Congress; state-level VA coverage is thin. *(delighter; expensive; huge)*
- **F2. Floor session live layer** — floor amendments + votes in near-real-time on floor days. *(performance)*
- **F3. Regulatory follow-through** — Virginia Register / Town Hall: the bill passed; now track its
  regulations. Lobbying doesn't end at enactment. *(performance; expands the season → year-round revenue)*
- **F4. Budget-amendment tracker** — VA's budget bill is its own universe (member requests → committee
  reports → conference); item-level tracking. Deeply underserved. *(delighter for the many budget-driven
  clients)*
- **F5. Interim studies/commissions** — the off-season layer we already partially have (interim window);
  make it a first-class product ("what is the Housing Commission doing with my issue"). *(delighter;
  nobody covers interim well)*

### G. Trust as the moat (our DNA, weaponized)
- **G1. The accuracy guarantee, marketed** — "every meeting action carries its verified time or an honest
  flag — audited nightly against the official record, breaker-protected, public health dashboard."
  Incumbents claim real-time; NOBODY proves accuracy. Our Section-9=0 discipline + Health tab become the
  sales pitch. *(the brand)*
- **G2. Provenance on every fact** — vs AI-slop competitors whose LLM summaries hallucinate: our AI
  features sit UNDER the trust layer (structural ground truth, labeled derivations, "never pretend").
  *(the positioning)*

## 4. Competitive white space (who we'd sell against)

- **Incumbents:** [Quorum](https://www.quorum.us/products/state/), [FiscalNote/PolicyNote +
  StateNet](https://fiscalnote.com/blog/fiscalnote-vs-quorum), Bloomberg Gov, MultiState, StateScape,
  [Plural](https://pluralpolicy.com/), [FastDemocracy](https://fastdemocracy.com/), LegiScan/BillTrack50
  (data-first), new AI-native entrants ([USLege](https://www.uslege.ai/) — 2.4M hrs of hearing video,
  TX-first; [Legible](https://legiblepolicy.com/); Apogee; LobbyScape). Free/nonprofit:
  [VPAP](https://www.vpap.org/) (VA money/people data — complement, not competitor), Open States.
- **Their shape:** enterprise pricing (opaque, reputedly $10k–$50k+/yr), 50-state *breadth* with shallow
  per-state depth, AI bolted on, support complaints (FiscalNote 6.7/10), separate per-state workflows.
- **The white space we'd own:**
  1. **Deep-single-state excellence** at solo-lobbyist pricing — own Richmond first (~1,000 registered VA
     lobbyists + associations + law firms), then replicate state-by-state (the USLege playbook, but with
     our trust layer). Land-and-expand beats 50-shallow-states.
  2. **Provable accuracy** (G1) — the anti-AI-slop positioning exactly as LLM distrust peaks.
  3. **Meeting-time precision** — our resolver handles "15 minutes after adjournment of the full
     committee" chains; that's the single most operationally valuable fact in a 46-day session and the
     hardest to copy (it took us the whole §9 war).
  4. **The contract-lobbyist segment** (multi-client + auto-reports + compliance) — incumbents sell to
     enterprises; the third house is underserved at its price point.
  5. **Interim + regulatory + budget depth** — the parts of the VA cycle the 50-state players skip.

## 5. Business-model sketches (for the narrowing conversation)

- **Per-seat SaaS**, session-aware pricing (e.g., $99–$299/mo solo → firm tiers); annual = 12 mo for 10.
- **Per-client pricing** for firms (aligns to how THEY bill).
- **Association tier** — member portals / branded digests (E2 at scale).
- **Free citizen/journalist tier** — ubiquity moat ("everyone in Richmond checks it"), VPAP-style goodwill,
  the top of the funnel.
- **Data API / white-label** for law firms' internal dashboards.
- **The master dashboard** as the multi-state enterprise SKU later: cross-state watchlists + model-bill
  radar (B4) is its unique view no single-state tool can offer.

## 6. Premortem (why it failed to sell — reversed into requirements)

1. *"Lobbyists trusted their spreadsheets and interns."* → The wedge must save time on DAY ONE with zero
   setup: the Tonight Brief (A2) + auto client report (E2), not a dashboard to configure.
2. *"Quorum copied the feature."* → Sell the moats (accuracy guarantee, time-resolution, per-state depth,
   price), not any single feature.
3. *"LIS changed and the data broke silently."* → Already our religion (drift canaries, breaker, Standard #1).
4. *"They wouldn't pay because the state site is free."* → LIS is free the way raw lumber is a free house;
   sell the minutes-matter delta + the artifacts (briefs, reports, filings) lobbyists already labor to make.
5. *"One state's revenue was too small."* → VA is the proving ground; the machine (Standard #6/#8: zero
   per-state maintenance) is the actual company.
6. *"Compliance/ToS/ethics blowback."* → Public data only, LIS-safety charter already governs; VPAP
   coexists happily; disclosure features must be assistive, never auto-filed.

## 7. The shortlist I'd argue for (a strawman for narrowing — owner decides)

1. **A2 Tonight Brief** — cheapest, daily habit, uses everything we already have (times, agendas, links).
2. **E1+E2 multi-client + auto client reports** — the commercial unlock for the paying segment.
3. **B1 substitute redlining** — highest per-use value during session, buildable from LIS text.
4. **D2/D3 committee mortality + deadline math** — the archive's first insight products, cheap, honest.
5. **G1 the accuracy guarantee** — costs nothing (built), reframes everything as the trust brand.
6. **B4 model-bill radar** — the multi-state flagship; design it into the state-engine duplication now
   (canonical text store per state) so it falls out of expansion instead of needing a retrofit.

## Sources (research pass, 2026-07-13)

- Competitive: [Quorum State](https://www.quorum.us/products/state/) · [FiscalNote vs Quorum](https://fiscalnote.com/blog/fiscalnote-vs-quorum) · [Quorum's comparison](https://www.quorum.us/blog/quorum-vs-fiscalnote/) · [Plural](https://pluralpolicy.com/) · [USLege](https://www.uslege.ai/) · [FastDemocracy](https://fastdemocracy.com/) · [MultiState](https://www.multistate.us/solutions/track-state-legislation-and-regulations) · [Bloomberg Gov state guide](https://about.bgov.com/insights/state-government/successfully-lobby-across-jurisdictions/) · [Legis1](https://legis1.com/platform) · [LobbyScape](https://lobbyscape.com/features/) · [pricing discussion](https://thesoftedge.com/congress-plus-quorum-fiscalnote-alternative/) · [LegiStorm buyer's guide](https://info.legistorm.com/blog/best-public-affairs-software)
- VA ecosystem: [VPAP](https://www.vpap.org/) · [VPAP lobbying/gifts](https://www.vpap.org/lobbying/spending/)
- Prediction research: [AAAS: AI predicts bill passage](https://www.science.org/content/article/artificial-intelligence-can-predict-which-congressional-bills-will-pass) · [NVIDIA/Purdue vote prediction](https://developer.nvidia.com/blog/ai-model-could-predict-which-bills-get-passed/) · [VPF framework](https://arxiv.org/html/2505.12535)
- Protocols: [JTBD (Ulwick/Strategyn)](https://strategyn.com/jobs-to-be-done/) · [JTBD overview](https://www.productplan.com/glossary/jobs-to-be-done-framework) · [product-discovery frameworks](https://productschool.com/blog/product-fundamentals/what-is-product-discovery)

See also [[ideas/product_vision]] (locked B1), [[ideas/product_roadmap]], [[ideas/multi_state_data_strategy]],
[[ideas/multi_state_org_structure]], [[architecture/session_archive]] (the analytics substrate), [[state/current_status]].
