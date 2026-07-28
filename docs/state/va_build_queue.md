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

### P1. Bill → subject linkage — gates **M1 (call sheet)**, M4, and the Subject profile
**What is already CONFIRMED:** LIS publishes a structural subject taxonomy —
`LegislationSubject/api/GetSubjectReferencesAsync` returns **505 subjects**, each with `SubjectIndexID` +
`SubjectNumber` (e.g. Abortion = 3005). That is the **dictionary of categories**.

**What is NOT yet confirmed: the index.** The dictionary tells us the categories exist; it does not tell us
*which bills carry which category*. Those are two different endpoints. We have the list of all subjects — we
have not yet found the route that answers *"HB463 carries subject 3421"* or its inverse *"list every bill
under 3421."*

**Owner is right that the categorisation exists** — LIS displays subjects on bill pages, so the data is real.
**I over-stated the risk earlier by saying four features "change shape if it doesn't exist."** They almost
certainly do exist. The honest statement: **the data is near-certain, the route and its authorisation are
unverified**, and unverified is unverified — that is the rule that caught the 2020 error. Expect a quick win.

Probe: find the bill→subject route (or the subject→bills inverse), confirm it is inside the 2025/2026
authorised surface, record it in [[knowledge/lis_api_reference]].

### P2. Address → district lookup **and** the re-ask signal — gates **M3 (account setup)**
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

**Ships regardless of outcome:** the **6-month periodic re-confirm** needs no external source. Never let this
probe block accounts.

### P3. VPAP terms of service — human read; gates the money row on **M1**
`vpap.org` returned **403 to automated fetching**; terms could not be read programmatically and were not
worked around. Search results indicate the site advertises RSS/API/downloads. **A human reads the terms before
any scoping** — the same diligence LIS got. Feeds the campaign-finance / gift-disclosure overlay (ideation C1),
absent from every mockup so far. Only *adds* a row to the call sheet, so it is the least blocking of the
three — but cheaper to answer before drawing than after.

---

## M · MOCKUPS — design only, no code

### M1. THE CALL SHEET ← first mockup *(needs P1; P3 optional)*
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

- **E1. Vote-history join** — `VOTE.CSV` already holds every member-vote pair; parse to per-member records.
  Zero extra API calls. Feeds nearly every number on the call sheet.
- **E2. Composition-break detection** — diff `chair_of()` / `party_split()` across sessions; where they
  differ a pooled figure must show its split. **Correctness requirement, not a feature.**
- **E3. Per-session chamber majority, stored** — the control filter needs it; `party_split()` covers
  committees, chamber needs the same.
- **E4. Coverage window as data** on every stat, so `(2025–2026)` is derived, never typed.
- **E5. Text-diff percentage** — one number serving companion drift, version drift and cross-state
  similarity. `tools/text_corpus/normalize.py` already normalises; the ratio sits on top. Removes three amber
  claims from the product.
- **E6. Co-patrons** — `/LegislationPatron/…`, inventoried, not built.

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
