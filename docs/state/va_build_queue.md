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
### M3. Account setup flow — name + 3 districts + address escape hatch *(needs P2)*
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

- **F1. Routing** — `web/` has **no router at all**. Six routes: detail + list for legislator, committee,
  subject. Nothing with a URL works until this lands.
- **F2. Write path** — Worker + D1 + Cloudflare Access. Everything org-asserted needs it: the ladder, notes,
  contacts, the interaction log. **The call sheet is a read surface over data that does not exist yet.**
- **F3. Accounts** — Google login, 30-day session. Ask **what to call you** (first name, for office calls) +
  **state house / state senate / federal house** districts. Never store an address. Federal district
  collected, not displayed (Mastermind uses it). One notice line: *"info used for legislative advocacy
  optimization."* 6-month re-confirm at login + manual edit in account settings.

---

## C · REMAINING PROBES (do not gate a mockup)

- **C1. `legacylis.virginia.gov` CSV** — the only lawful pre-2025 route. **Promoted from "someday" by the
  composition finding:** with two authorised sessions, a chair or majority change between them leaves **one
  session** of valid history for that committee. The difference between a stats layer that means something
  and one that does not.
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
- **E2. Composition-break detection** — diff `chair_of()` / `party_split()` across sessions; where they
  differ a pooled figure must show its split. **Correctness requirement, not a feature.**
- **E3. Per-session chamber majority, stored** — the control filter needs it; `party_split()` covers
  committees, chamber needs the same.
- **E4. Coverage window as data** on every stat, so `(2025–2026)` is derived, never typed.
- **E5. Text-diff percentage** — one number serving companion drift, version drift and cross-state
  similarity. `tools/text_corpus/normalize.py` already normalises; the ratio sits on top. Removes three amber
  claims from the product.
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
- **V5. `k of n` everywhere** — no percentage on counts, no threshold, no interval. One rule.

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
