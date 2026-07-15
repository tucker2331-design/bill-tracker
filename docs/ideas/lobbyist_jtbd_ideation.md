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
  committees. *Pains: minutes matter; the late-evening docket drop (see the measurement note below); two
  hearings at once; the substitute nobody read; whip counts by hand; testimony prep at midnight.*
  > **Measurement note (2026-07-14, honesty):** the specific "10 PM" was an ILLUSTRATION, never measured.
  > `tools/parity/witness_histogram.py` + `.github/workflows/witness_histogram.yml` are built to measure it
  > from `Schedule_Witness` (ET hour-of-day of every ADDED/CHANGED delta). It could NOT produce the number
  > now: the 2026 session is past the witness's 90-day retention AND the witness auto-sharded to VA·Ops.
  > **Re-run it during the 2027 session to replace "late night" with the real distribution.** Until then the
  > product copy must say "late evening", not a fabricated clock time (A2 below).
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
  times/rooms/agenda links/livestreams, collisions flagged. The late-evening anxiety-killer (the exact drop
  hour is `witness_histogram.py`'s 2027 measurement — don't hardcode "10 PM"). *(delighter; the daily habit hook)*
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

---

## 8. OWNER FEEDBACK ROUND 1 (2026-07-13) + the persona that changes the picture

**[2026-07-14: the "10 PM" claim is now corrected in §2 above + the measurement tool `witness_histogram.py`
built (runs in-season 2027); product copy says "late evening" until measured.]**

Owner verdicts: **A/C/D perfect** (A's "10 PM docket drop" was UNMEASURED illustration — flagged for a real
measurement: a small tool reading `Schedule_Witness` seen-at timestamps → hour-of-day histogram of docket
changes; doubles as a sales slide). **B/F good, explained further** (see response in session; substitute-
redlining and code-section-watch land hardest for a bill-WRITING org; F3 regulations make the product
year-round). **E: single-org FIRST** — perfect the current org's experience, multi-client/commercial later
(matches locked B1 §9; keep the `position` column so it's never a retrofit). **G challenged:** "every time
I get on the site there's a potential issue — will it hold up?" Answer logged: the DATA claim held (breaker
kept all three 66-incidents out of production; Section 9=0 since 06-06), but owner-perception = customer-
perception → three pre-launch requirements: (1) an honest public "days since data incident" metric with a
strict definition; (2) quiet-by-default user-facing health (operator depth stays in the tab); (3) a
hardening gate — N clean weeks + surviving the 2027 cold-start — before any paying user.

### 8a. THE REFRAMED PRIMARY PERSONA: the advocacy org that lobbies for itself
The owner's actual client: an org that supports AND WRITES bills, staffed heavily by **volunteers and
young/inexperienced people**. Not a lobbyist with clients — the client doing its own lobbying without the
experience. Product job: **be the experienced lobbyist they don't have.** Incumbents assume expertise;
mass-advocacy tools (VoterVoice/Capitol Canary/New Mode) are megaphones not brains. The white space:
intelligence + GUIDANCE for non-experts. "Makes a volunteer 80% as effective as a pro."

Feature set (V-series, volunteer-org edition — C/D reframed to their strongest form):
- **V1. The Play-Caller** — per tracked bill: where it sits, WHO decides next (the committee roster), the
  ACTION WINDOW (docket time − now), and what to do (contact list / testify sign-up how-to / attend or
  watch via our livestream links). The stage machine already knows the state; map state→playbook.
- **V2. Plain-English mode** — every history action translated ("Passed by indefinitely (8-Y 7-N)" → "❌ the
  committee voted 8–7 to kill this bill; usually final for the year"). One mapping table over the
  structural router's verdicts. Tiny cost, category-defining for this persona.
- **V3. Constituent matching** — volunteer address → their legislators → intersect with the deciding
  committee → "Sen. X is YOUR senator AND sits on the deciding committee — your call counts double."
  Converts a volunteer corps into targeted constituent pressure (the highest-leverage contact type).
- **V4. The war room** — committee math (needs 8/15; 5-6-4 solid/against/unknown) + a red/yellow/green
  whip board volunteers update from the hallway; coordinator watches the gap close. (C2+C3 volunteer-tuned.)
- **V5. Verified fact sheet + talking points** — org lead pins ONE approved one-pager per bill; the facts
  (status/votes/next step) render from verified data. Trust layer as a safety rail against volunteers
  misstating facts to members' offices.
- **V6. After-the-hearing recap** — same-day plain-English "what happened to our bill at 8:14 AM"
  (actions+times we already have; F1 clips later).
- **V7. Volunteer task routing** — assignments (cover this hearing / call these 5), checklists, call
  outcomes feeding V4. Lightweight; not a CRM.
- **V8. Shareable momentum cards** — "cleared committee 12–10, two steps from the Governor" social-ready;
  recruits volunteers, feeds donors, markets the platform.
- **V9. The org-as-drafter kit** — patron scouting (C5) for "who carries our bill," substitute redlining on
  THEIR OWN bill (B1), defensive code-section radar (B2), deadline math (D3).

Commercial note: advocacy orgs/nonprofits vastly outnumber pro shops and are priced out of incumbents;
the owner's org is the live design partner for the 2027 session. This persona also strengthens the free-
tier ubiquity wedge (§5).

### 8b. OWNER FEEDBACK ROUND 3 (2026-07-13) — verdicts on the V-series + two elevations

Correction from the owner: the volunteers are inexperienced at LOBBYING, not unintelligent — don't
over-simplify FOR them; give them the same professional-grade information, just complete.

- **V2 plain-English translations → LATER + MAJOR REWORK.** Owner's objection is exactly our own
  silent-fallback doctrine: hand-phrasing per circumstance is endless, and an action WITHOUT a translation
  (unseen phrasing) breaks the dependency the feature created — a missing translation is a silent source-miss
  that trains reliance then betrays it. Do not ship until coverage is structural (translations keyed to the
  router's verdicts/EventCodes with a drift canary, and a designed honest-absent state), not text-matched.
- **V1 Play-Caller → REJECTED as prescriptive automation; KERNEL KEPT.** "Too dynamic to have code telling
  you what to do next" — humans in the loop make the judgment calls (call vs I'll-be-there-tomorrow etc.).
  The kept kernel: the BILL CARD's existing "Where it is" + skeletal "Next meeting" rows grow into a real
  **Now → Next** section (location + docket time + room + agenda/watch links + honest-absent). Four mockups
  delivered for owner choice: https://claude.ai/code/artifact/f1ef8d4e-ed6e-455a-be80-72bed4d02b44
  (A quiet block · B twin cells · C journey strip · D imminent banner; recommendation A+D). Data already
  exists (calendar meetings carry bills/times/links; card has `bill.upcoming`).
- **V3 constituent matching → DELAYED** (org may already use a mass-advocacy tool with this; requires
  volunteers' home addresses = privacy friction). Behind features with proven in-house use cases; ahead of
  individual-lobbyist-only features.
- **V4 war room → owner wants mechanics explained** (done in session; manual-first whip board, org-entered
  intel PARTITIONED from LIS-verified truth — two visibly different data classes on one page). Scoping open.
- **V5 fact sheet → "we basically already have this"** — correct: the verified-data half IS the product;
  the only new piece is org-AUTHORED pinned talking points. Fold that small piece into V4's scoping.
- **V6 substitute redlining → GO, with the owner's constraint understood:** NOT an AI feature. The core is a
  DETERMINISTIC text diff of two LIS-published versions (git-diff-style, reproducible, no model). Optional
  AI summary on top can come later or never. Real cost = ingesting bill text versions (a new source surface).
- **V7 → ELEVATED: THE CHANGE LEDGER.** Owner: What's-new shows new actions by day but can't surface a
  1-count vote correction or a time change — lobbyists shouldn't have to eyeball the timeline for diffs.
  Feature: one place listing EVERY delta with precision and a timestamp — new actions, EDITED history rows
  (LIS corrections — per-bill `LastHistoryHash` infra already detects change; extend to row-level diff),
  schedule time/room/cancellation deltas (Schedule_Witness already logs these), docket adds/drops, vote
  tally changes. Client-side "since you last looked" scoping via localStorage marker (no accounts needed).
  Bonus surface: "LIS revised this vote 12-9 → 12-10" correction alerts — trust-building + genuinely novel.
- **V8 momentum cards → PARKED** (owner unconvinced automated graphics motivate).
- **G expansion → keep the 4 rings** (owner explicitly: don't simplify health yet). **Days-since-incident
  counter: GO — and the PARITY REFRAME (owner, verbatim goal):** "ensure my lobbyists see EVERYTHING they
  could see on the state legislative website." A FLAGGED gap is nearly as costly as an unflagged error —
  both send users back to LIS. So the trust layer's claim expands from "never wrong" to "never less than
  LIS": a continuous **LIS-parity sentinel** (bill-count parity, meeting parity, per-bill action-row parity
  via the existing hashes, vote parity) feeding a user-visible parity statement ("3,645/3,645 bills ·
  1,684/1,684 meetings · verified N min ago") + the incident counter counts BOTH accuracy incidents AND
  parity gaps, + track degraded-minutes (time any user-visible surface showed less than LIS).
- **Infra note surfaced by V4/V7 scoping:** stars/tracking are currently per-browser localStorage; a SHARED
  org watchlist (and any org-authored content) needs a small write path — the first feature to force one.

**Next step agreed:** order the to-do and scope the first items. Candidate order for that conversation:
(1) card Now→Next [pick mockup] · (2) change ledger · (3) parity sentinel + incident counter ·
(4) war-room scoping [needs shared-watchlist infra decision] · then V6 text ingestion.

### 8c. MOCKUP DECISIONS LOCKED (owner, 2026-07-13)

- **Bill card Next-meeting: OPTION 2** — the enriched in-place row (when · room · committee · agenda/watch
  links · countdown as muted text), taking the amber row tint inside ~48h. Mockups:
  https://claude.ai/code/artifact/f1ef8d4e-ed6e-455a-be80-72bed4d02b44
- **Amber collision — OPEN, owner decides which yields (PROCESS CORRECTION 2026-07-13: I banked my
  recommendation as a locked build task without approval — owner: "don't do that without permission again."
  A recommendation is NOT a decision; design changes to live surfaces need explicit owner sign-off before
  entering the build list.)** The fact: `.cal-mtg.unres` (calendar unplaceable meetings) and the chosen
  card Option 2 row both use `--o-carry-bg` amber. Options on the table: (A) unplaceable KEEPS its
  visibility but changes clothes — e.g. a dashed border (uncertainty encoded structurally, no color spent),
  ⚠ + label retained; (B) unplaceable goes quiet (muted-italic TBA treatment) — grounded in post-§9 live
  data (in-window unresolved = 0) but reduces a trust-flag's visibility; (C) the card row moves off amber
  instead (e.g. accent-soft). Data point, not a decision: the unplaceable state is nearly extinct post-§9.
- **Crossed-over chip → neutral grey: CONFIRMED by owner 2026-07-13** (was Senate-purple in BillCard.tsx,
  violating one-meaning-per-color). Goes in the card-build PR.
- **Option 3 top strip: DELAYED** — decent idea, unclear use case; revisit later.
- **Patron on list cards: P1** — patron surname next to the bill number (`SB204 · Deeds`), not a tag.
- **Two-step unstar: APPROVED** as mocked (confirm popover, default = Keep tracking).
- **Flagged product drift (needs owner confirm):** the live card's "crossed over" chip reuses the SENATE
  purple (`chip senate` in BillCard.tsx) — violates one-meaning-per-color; should be the neutral grey status
  chip. One-line fix, bundle with the card build.
- Ledger v2 (register pattern, monochrome): https://claude.ai/code/artifact/17b5817d-247c-4007-9da8-45eeb093ab56
  — a SEPARATE artifact from the card mockups; owner initially only saw the card one (two links in one
  message = one gets lost; surface separate deliverables separately). "Ledger" = internal feature name
  (append-only record of every change, before→after — the accounting sense, on-brand with bank-grade);
  the user-facing tab in the mock is just "Changes". Awaiting owner verdict.

### 8d. ROUND 4 (owner, 2026-07-13) — amber resolved, ledger concerns answered

- **Amber collision: OPTION A CHOSEN by owner** — calendar unplaceable keeps ⚠ + label + top-of-day sort but
  moves to a **dashed border** (form encodes "position uncertain"), zero color; amber becomes exclusively
  "pending — act soon" (card Option 2 row). Mockup delivered (before/after, verbatim calendar CSS):
  https://claude.ai/code/artifact/f1ef8d4e-ed6e-455a-be80-72bed4d02b44 — awaiting owner eyes before it
  enters the build bundle.
- **Ledger concern 1 — data-to-text sustainability ("massive pain / unmappable concepts"):** answered
  structurally. The ledger does NOT translate LIS's unbounded prose (that was V2's fatal flaw). Its kind
  vocabulary is OUR OWN differ's closed set — one template per detectable delta (~6: history row added /
  row content changed / schedule time changed / docketed / off docket / cancelled), each existing because a
  specific field in OUR schema changed. The payload is QUOTED raw data (old → new verbatim; action text
  verbatim), never paraphrased — no dictionary to maintain. Unknown-shape fallback: a change the differ
  can't classify renders the honest generic row ("record changed — view card") + fires a drift canary
  (same pattern as the agenda-label canary). Unmappable-concept-looks-cheap is structurally excluded:
  worst case is generic-but-true.
- **Ledger concern 2 — "these rows all have times but our data rarely does":** the time column is
  DETECTION time (when our worker cycle saw the delta) — always available, it's our own clock; LIS history
  being date-only is exactly why detection time is what's printed. Two honesty notes for the build: label
  it so nobody reads it as "when LIS acted" (bounded by cycle cadence, ~15 min in-session); and consider
  muted grey (not accent) for detection times so the accent-time slot keeps meaning "a real meeting clock"
  as in What's-new.
- **Ledger concern 3 — "how do you know my computer from someone else's":** today, per-browser
  localStorage (same mechanism as stars) — it knows the BROWSER, not the person; devices don't sync;
  a shared computer shares the marker. Ship honest ("since you last looked on this device"), upgrade to
  per-person when the shared-watchlist identity decision lands (already queued). Ledger verdict otherwise:
  owner likes it ("looks good, almost too good").
