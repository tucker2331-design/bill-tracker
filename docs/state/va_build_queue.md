---
tags: [state, queue, product, war-room, virginia]
updated: 2026-07-27
status: active
---

# VA build queue — everything decided in the 2026-07-27 design block

Virginia only. `current_status.md` stays MOVE-only (NOW ≤3); **this is the ordered backlog those three are
drawn from.**

**Ordering rule (owner, 2026-07-27):** *"put the scoping that ensures the mockups are even possible ahead of
the mockup."* So **probes that gate a mockup run first** — drawing a screen whose data may not exist wastes
the draw. Everything else follows dependency order: an item a probe could invalidate never precedes it.

---

## P · PROBES THAT GATE A MOCKUP — run first, each is small

### ~~P1. Bill → subject linkage~~ — ✅ **RESOLVED 2026-07-27**
**What is already CONFIRMED:** LIS publishes a structural subject taxonomy —
`LegislationSubject/api/GetSubjectReferencesAsync` returns **505 subjects**, each with `SubjectIndexID` +
`SubjectNumber` (e.g. Abortion = 3005). That is the **dictionary of categories**.

*(Was: the index — which bills carry which subject — was unfound. Resolved below.)*

**RESOLVED.** The index is `POST AdvancedLegislationSearch/api/GetLegislationListAsync` with
`{"SessionID": 59, "SubjectIndexID": n}` — the subject→bills inverse, which is the direction we wanted.
Verified on both authorised sessions. **Counts arrive free in the `X-Pagination` header**, so the Search
facet counts (V2) need no extra query design. **Trap recorded: zero results are HTTP 204 with an empty
body**, not `200 []`. Full spec: [[knowledge/lis_api_reference]].

**It also caught a fabrication of mine:** there is **no "Privacy" subject** — mockups v5–v8 used
`Privacy · 3421` and I invented both the name and the number. Real analogues: Consumer Protection (75),
Databases (644), Information Management and Technology (758). **M1/M4 must use a real subject.**

⚠ **M1 (call sheet) and M4 are UNBLOCKED.**

### ~~P2. Address → district lookup + the re-ask signal~~ — ✅ **RESOLVED 2026-07-27**
Owner: *"we just need to know when to ask them to put their new districts in… that said I sort of wanted a
way they could put their address in and see that info pop up to then be manually put in. so check for both."*

**Two separate questions, both required:**
1. **Address → districts** (the escape hatch, now a confirmed requirement not a nicety): a lookup that takes
   an address and returns state house / state senate / federal house districts, which the user then **enters
   manually**. Resolve and discard — the address is never stored. Candidates to verify: Census Geocoder,
   Google Civic Information, Open States people-by-location. Check terms and cost for each.
2. **The re-ask signal** — *when* do we prompt for new districts? **Check the cheap thing first:** we need a
   **date**, not geometry. If new maps carry a publishable effective date anywhere (VA Redistricting
   Commission / Division of Legislative Services), the shapefile question is moot and the probe ends. Only if
   no date is obtainable, look at Census TIGER/Line SLDU/SLDL vintages as a diffable proxy.

**Why this needed a probe at all:** `roster.py` returns district *numbers* and who holds them — a boundary can
move while the number stays "23", so redistricting is **invisible to everything we currently ingest.** That
gap was mine: I proposed an event-triggered re-confirm without naming a source.

**RESOLVED — one federal API answers both halves, no key, stores nothing.** Census Geocoder
(`geocoding.geo.census.gov`) returned all three districts in a single verified call: Senate 14, House 78,
Congressional 4. Full spec: [[knowledge/district_lookup]].

**The re-ask signal turned out to need no new source at all.** The district-layer NAME carries the map
vintage — `2024 State Legislative Districts`. Geocode **one fixed public address** (the Capitol) on a slow
cron and watch that year; when it changes, prompt everyone to re-confirm. Zero PII, one call, **no
shapefile** — the reframe (*we need a date, not geometry*) ended the probe, so **TIGER/Line is not needed**.

**Scales free:** the same endpoint returns state legislative districts for every state (Standard #6) — state
#2 inherits it unchanged.

**Small open item:** confirm CORS allows a browser-side call. If not, proxy via the Worker and use-and-drop
the address in the same request — never a log line, never a row.

⚠ **M3 (account setup) is UNBLOCKED.** The 6-month periodic re-confirm remains the floor and runs regardless.

### ~~P3. VPAP terms of service~~ — ✅ **RESOLVED 2026-07-27 — VPAP not needed**
Owner reported VPAP prohibits sub-licensing, and asked the right question: **where do THEY get it?**

**Answer: the Virginia Department of Elections publishes the filings itself** —
`https://apps.elections.virginia.gov/SBE_CSV/CF/<YYYY_MM>/`, monthly CSVs **1999 → 2026_07**, no key, no
registration, refreshed daily. VPAP is an aggregator of this. Verified live; full spec in
[[knowledge/campaign_finance_source]].

**Their terms govern their compilation, not the public record underneath it** — so the restriction simply
does not reach us. And ELECT is *better* sourcing: the filings themselves rather than someone else's
normalisation (Standard #3), no intermediary who can change terms, and history back to 1999.

**Standing rule this establishes:** when an aggregator's terms block us, find the agency they file with.
Aggregators exist because the primary source is inconvenient, not because it is closed.

⚠ **M1's money row is UNBLOCKED** — no owner action needed after all.

---

## M · MOCKUPS — design only, no code

### ~~M1. THE CALL SHEET~~ — ✅ **DRAWN 2026-07-27** · https://claude.ai/code/artifact/d44f5427-ce9c-4647-beea-595b685d71c3
What a volunteer opens **in the hallway or outside an office door.** Owner: *"we don't just want info on the
legislator, otherwise we would go to their profile."*

**Defining constraint: the INTERSECTION of member × THIS bill × subject — not a member profile.** A profile
answers *who is this person*; the call sheet answers *what do I need to know about this person, for this bill,
right now.* **Test: if a fact would read the same on any bill, it belongs on the profile instead.**

Must carry:
- **Which bill we are advocating for, and which side we are on** — the sheet is meaningless without it.
- **Subject-specific record** — how they vote on bills in *this* category (`k of n`). *(needs P1)*
- **This committee** — their record before the committee currently holding the bill.
- **Relational — the part that makes it ours:** voted with us `k of n` · has carried a bill of ours (needs the
  Involved status, D1) · contacts: how many, **by whom**, when, and how the last one went.
- **Cross-aisle tendency** — how often they break with their party.
- Serves an **in-person office visit** as much as a phone call.
- No generated prose (P25). Every line is an assembly of numbers we already compute.

**DRAWN on REAL data** — SB615 *Consumer Data Protection Act; online device pricing*, patron Sen. Stella G.
Pekarsky, before **Senate General Laws and Technology** (id 33, **16 members**, chair **Jeremy S. McPike**),
subject **Consumer Protection (75)** with **17 bills** in 2026. All fetched live from the authorised session
while drawing. Every figure is tagged `LIS` (fetched) or `EXAMPLE` (needs E1/F2).

**Real data surfaced a fact I would not have invented:** the patron **sits on the committee hearing her own
bill.** It is now a line on the sheet.

**The proposal-audit hook fired on this publish and caught two real defects** — first time the enforcement
worked on live output: (a) a zone header read *"How he handles bills like this"* — **"like this" is the
derived-claim tripwire** — now *"On Consumer Protection bills"*; (b) the contact stat said **3 contacts**
while the log showed **2 rows**. Both fixed pre-publish.

### M2. Position + tracking ladder popup *(unblocked — the enum is settled, see D1)*
### ~~M3. Account setup flow~~ — ✅ **BUILT, not just drawn** (`components/FirstRun.tsx`). The mockup step
was skipped deliberately: the form is four fields and one escape hatch, so drawing it first would have cost
a round-trip to learn nothing the build did not.
### M4. Bill card / War Room rendering the new statuses *(needs P1 for the subject column)*

---

## D · DECISIONS

### D1. The tracking ladder — SETTLED (owner, 2026-07-27)
"Involved" **replaces** the top tier; it is not an addition. *"I don't want too many options then they lose
their meaning."* **Oppose stays one layer** — the symmetric-authorship idea (an "Amending" mirror) is dropped.

| Tier | Meaning |
|---|---|
| **Involved** | we wrote it and/or got it introduced |
| **Supporting** | actively working for it |
| **Watching** | tracking, no position |
| **Opposing** | actively working against it |

All four are **org-asserted** (P20a) — LIS cannot confirm we drafted anything, so they live below the trust
rule with our other intel, never rendered as sourced fact. **This is the enum; the write path (F2) can now
proceed.** "Involved" is also the only thing that makes *"has this member carried a bill of ours?"*
computable — without it that relationship is unrepresentable.

### D2. MVP cut — ORCA says cut by downgrading OBJECTS, not by trimming features. Open.

---

## F · FOUNDATIONS

- ~~**F1. Routing**~~ — ✅ **BUILT + BROWSER-VERIFIED 2026-07-28.** `web/src/state/router.ts` (~70 lines,
  **no new dependency** — this app has two runtime deps and the route set is flat; a router library would
  triple that and add an upgrade treadmill, Standard #8). Routes: the five tabs plus list + detail for bills,
  legislators, committees, subjects. `parseRoute`/`routePath` sit adjacent and a round-trip test proves
  `parse(path(r)) === r` for all 13. **The War Room tab now exists** and renders tracked bills from real data.
  Verified in a browser, not just typechecked: deep link opens the right bill, Back closes it, unknown routes
  fall back without blanking, a nonexistent bill id does not crash, nav links are real `<a href>` so
  middle-click and copy-link work, zero console errors, no overflow at 1280 or 700px.
- ~~**F2. Write path**~~ — ✅ **MERGED 2026-07-29 (#237).** Schema live; Migration applied to the remote D1 2026-07-28; both
  constraints verified against the real database (`stance='bogus'` → CHECK failure; missing `state` → NOT NULL
  failure). Worker API + **Google ID-token verification** built (Access rejected on its per-seat pricing
  model — [[architecture/verification_durability]]). Sign-in shipped with it, so the door is hung. **Remaining before it carries
  real data: the D1 second-oppose-tier decision (the enum), and wiring the War Room's position control to
  `PUT /api/positions`.**
- ~~**F3. Accounts**~~ — ✅ **BUILT 2026-07-28.** Sign-in (`web/src/state/auth.ts` + `components/SignIn.tsx`,
  verified live: button renders, zero console errors, **no token in localStorage** — held in memory only, so
  one XSS cannot steal an identity that outlives the tab). **First-run form built** — display name + three districts, which is what turns
  "Saved as tucker2331@gmail.com" into "Saved as Tucker".
  **The privacy property is topology, not policy:** the Census lookup runs in the BROWSER, so the address
  never reaches our infrastructure and there is no code path on our side that could store one — the only
  occurrence of the word "address" in `worker/index.js` is the comment explaining its absence. Verified
  against the live Census API with two real addresses (Capitol → 14/78/4, Arlington → 40/2/8) so it cannot
  be returning a canned answer.
  **The profile gate has three states, not two** — `undefined` (not checked) / `null` (no profile) /
  object. Collapsing the first two would flash the form on every load for people who already filled it in.
  Original scope below. Ask **what to call you** (first name, for office calls) +
  **state house / state senate / federal house** districts. Never store an address. Federal district
  collected, not displayed (Mastermind uses it). One notice line: *"info used for legislative advocacy
  optimization."* 6-month re-confirm at login + manual edit in account settings.

---

## C · REMAINING PROBES (do not gate a mockup)

- **C1. `legacylis.virginia.gov` CSV** — **PROBED 2026-07-27. NO BULK CSV ROUTE FOUND. This is a bad
  result and it matters.**
  What is there: `legacylis.virginia.gov` is live and serves the **2024 session** (`ses=241`) as
  **CGI-generated HTML pages** (`/cgi-bin/legp604.exe?241+…`) — bill tracking, committees, members,
  calendars, statistics. Every link on the home page is a page, not a file. `SiteInformation/csvinfo.html`
  404s. The DLAS "data center" page is network infrastructure, not data distribution.
  **The LIS Developers Portal says pre-2025 data should come from "legacylis.virginia.gov via CSV
  download", but I could not find where that download lives.** Stopped rather than brute-force URLs — that
  is the blind-probing the owner has ruled out twice.
  **Why this is worse than an inconvenience:** the only alternative visible today is scraping those CGI
  pages, which is **text parsing on the lobbyist path — forbidden by Standard #3**, not merely undesirable.
  So the honest position is: **we may be stuck at two sessions of history**, which means a committee with a
  composition break (6 of 25 — E2) has ONE usable session, and the stats layer stays thin until either
  (a) the CSV route is found, or (b) LIS authorises earlier sessions on the new API.
  **NEXT — owner-actionable, not another probe:** ask DLAS directly where the historical CSVs are. They are
  the publisher; one email settles what an afternoon of guessing will not.
- **C2. Open States bulk download** — blocked on a login. Gates cross-state comparison.

---

## E · DATA LAYER

- ~~**E1. Vote-history join**~~ — ✅ **BUILT 2026-07-27.** `tools/votes/vote_history.py` + 9 structural
  tests. Zero extra LIS requests — a re-parse of a blob the worker already downloads.
  **Measured (20261):** 11,175 rows · **9,129 with per-member detail** · **318,264 member votes** ·
  147 distinct members. Roster reconciliation: 148 members vs 147 voters — **exactly one (`H0368`) never
  voted, zero orphan votes**, so the MemberNumber join is clean.
  **The finding that matters for the product:** 2,046 roll calls carry **no per-member detail**, and that is
  mostly *correct* — 1,245 are `VSV*` voice/standing votes, which have no roll call **by nature**. Treating
  them as a parse failure invents a bug; treating them as "no votes" understates a member's record. They are
  counted and categorised by id shape, never dropped.
  `agreement()` encodes the rule that **an absence is not a disagreement** — a vote not cast leaves both
  numerator and denominator alone.
- ~~**E2. Composition-break detection**~~ — ✅ **BUILT 2026-07-27.** `tools/roster/composition.py` + 9 tests.
  **MEASURED across the two authorised sessions: 6 of 25 committees broke** — *all six are chair changes,
  **zero** majority flips.* Examples: General Laws and Technology (33) **Ebbin → McPike**; Education and
  Health (25) **Hashmi → Favola**; Health and Human Services (197) **Sickles → Willett**.
  **This settles the owner's "is it a chronic condition?" worry with a number:** pooling is safe for **19 of
  25** committees and unsafe for 6 — frequent enough to matter, rare enough to be livable.
  Returns **structured fields, never a sentence** (P25 — the caller renders one invariant template), counts
  unknown-party members in the total but never lets them form a majority, reports present→absent chair as a
  real change, and `pooling_is_safe()` **fails closed** on any read error.
- ~~**E3. Per-session CHAMBER majority**~~ — ✅ **BUILT 2026-07-27.** `chamber_composition()` +
  `detect_chamber_break()` in the same module. **Measured:** 20251 H **D51–R49**, S **D21–R19**; 20261 H
  **D63–R37**, S **D21–R19**. **No chamber majority break across the authorised window** — D held both
  chambers in both sessions.
  **Building it caught a correctness bug in my own first version.** `members()` returns everyone who
  **served**, not everyone **seated** — 20261 returned 106 House / 42 Senate people against 100 / 40 real
  seats, the extras being `Outgoing` (6) and `Inactive` (2). Since the majority test is `seats*2 > total`,
  the inflated denominator is not cosmetic: in the regression test, counting 6 departed Republicans **flips
  a D 51-seat majority into an R one**. Now filtered to `status == "Active"` (exactly 100 and 40), with
  non-seated members **counted in `served_not_seated`, never dropped silently**.
- ~~**E4. Coverage window as data**~~ — ✅ **BUILT 2026-07-28.** `tools/votes/coverage.py` + 10 tests.
  A window is computed **from the rows a figure was actually derived from** and travels with it, so
  `(2025–2026)` can never be a literal that was true the day it was typed — the same class as the fabricated
  `(2020–2026)`. **Zero rows yields `None`, never a plausible span**: "no data" and "data covering 2025–2026"
  must not render identically. `exceeds_authorized()` turns a pre-2025 claim into a detectable compliance
  fault rather than a display quirk, and the authorised set is **imported** from `lis_authorization.py`
  rather than copied — the code gate caught that duplication on first write, and a compliance rule that can
  drift silently is the worst possible thing to have two copies of.
- ~~**E5. Text-diff percentage**~~ — ✅ **BUILT 2026-07-27.** `tools/text_corpus/textdiff.py` + 9 tests.
  **Removes three claims from the DERIVED (amber) class into exact math:** companion drift, version drift,
  cross-state similarity. "High overlap" was our unauditable judgement; a diff percentage is deterministic
  arithmetic on two texts we hold.
  Distinct from `normalize`'s jaccard/containment — those compare **shingle sets** ("was this drafted from
  that?"); this compares **sequences** ("how much changed?"). Both are wanted.
  **Missing text returns `None`, never 0% and never 100%** — absence of a side is evidence of neither
  sameness nor difference (same sentinel trap as audit #53). `difference_label()` emits the number and its
  unit only — **no banding** ("minor edits" / "substantial rewrite" would re-introduce exactly the
  interpretation the owner removed).
  `drift_from_introduced()` is one comparison, **not a sum of steps** — summing double-counts twice-edited
  text and can exceed 100%.
- **E6. Co-patrons** — **PARTIALLY PROBED 2026-07-27, param form UNRESOLVED.** The bill-search response
  carries **chief patron ONLY** (verified: 0 of 108 sampled bills had >1 patron), so co-patrons really are
  absent from the route we now use. The bundle shows the right endpoint is
  `LegislationPatron/api/GetLegislationPatronsByIdAsync`, returning `{Patrons:[…]}` where
  `DisplayName == "(Chief Patron)"` marks the chief and **the remainder ARE the co-patrons**. Tried
  `?sessionCode&legislationID`, `?legislationID`, `/{id}` — all 404.
  `GetLegislationPatronListAsync` returns **400** on the same params (route exists, params wrong) and is the
  *member→bills* direction, not bill→patrons. **Stopped rather than brute-force the parameter space** (owner
  rule). Next: find the bundle's fetch helper to see how it composes the query.

---

## V · DISPLAY

- **V1. Window × control dual filter** — applied together, independent. Expect `n` to collapse under a control
  filter in early years; that is the honest answer, not a reason to hide the control.
- **V2. Search per-value facet counts** against the current filter state — what makes zero-count disabling
  work. Query-shape requirement, not styling.
- **V3. Search empty state = browse index** — four object rows with counts; `ours` the only subdivision.
- **V4. Subject profile page** — stat list banked in [[ideas/predictive_lane]].
- ~~**V5. `k of n` everywhere**~~ — ✅ **BUILT 2026-07-28.** `web/src/data/frequency.ts` + 15 tests.
  Implements P26 **as amended**, not as originally written — no percentage companion, no sample threshold,
  no "too few" label, no Wilson interval. All six clauses were re-read against the canon before writing,
  not recalled. A test asserts the formatter **has no code path that can emit a `%`**.
  `n = 0` returns null rather than `"0 of 0"`: no observations is a different claim from zero successes,
  and the caller must render absence as absence. `complement()` exists because the owner asked for "voted
  against us" explicitly — burying it in a subtraction hides the more actionable half.

---

## R · RECORDED, NOT QUEUED

- **R1. The backtest** — settles which stats carry signal. Both PROVISIONAL blocks wait on it. Not a blocker
  for mockups.
- **R2. Mobile** — deferred (owner). **Why it is not a CSS afternoon:** the trust partition is a *vertical
  rule between column groups* — a horizontal device. On a narrow screen the LIS columns collapse, so the
  partition does not compress, it **disappears**, and "ours" silently becomes the whole table. A mobile pass
  must re-invent the partition vertically.
- **R3. Tier-3 individual prediction** — owner go/no-go, gated on the calibration harness.
- **R4. In the vault, in no mockup yet** ([[ideas/lobbyist_jtbd_ideation]]): VPAP money overlay (C1),
  influence pathfinding / co-patron network (C4), pinned verified fact sheet (V5), constituent-×-committee
  intersection (V3), after-hearing recap (V6).
