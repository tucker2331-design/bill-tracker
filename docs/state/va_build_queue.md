---
tags: [state, queue, product, war-room, virginia]
updated: 2026-07-27
status: active
---

# VA build queue — everything decided in the 2026-07-27 design block

Virginia only. Built from the War Room / entity-stats / Search design session. `current_status.md` stays
MOVE-only (NOW ≤3); **this is the ordered backlog those three are drawn from.**

Ordering rule: **mockups first** (they cost nothing and change what gets built), **then probes** (they can
delete work), **then foundations**, then the layers that sit on them. An item that a probe could invalidate
never precedes that probe.

---

## A · MOCKUPS — design only, no code

### A1. THE CALL SHEET ← top of the queue
The thing a volunteer opens **in the hallway or outside an office door.** Owner: *"we don't just want info on
the legislator, otherwise we would go to their profile."*

**The defining constraint: it is the INTERSECTION of member × THIS bill × subject, not a member profile.**
A profile answers "who is this person"; the call sheet answers "what do I need to know about this person *for
this bill, right now*." If a fact would read the same on any bill, it probably belongs on the profile instead.

Must carry:
- **Which bill we're advocating for**, and which side we're on — the sheet is meaningless without it.
- **Subject-specific record** — how they vote on bills in *this* category (`k of n`, subject code).
- **This committee** — their record on the committee currently holding the bill.
- **Relational** (the part that makes it ours): voted with us `k of n` · has carried a bill of ours
  (needs [[#B0-involved-status|Involved]]) · contacts: how many, **by whom**, when, and how the last one went.
- **Cross-aisle tendency** — how often they break with their party.
- Serves an **in-person office visit** as much as a phone call.
- No generated prose (P25). Every line is an assembly of numbers we already compute.

### A2. Position + tracking ladder — the popup, with the ladder below settled first
### A3. Account setup flow — name + 3 districts, and the 6-month re-confirm
### A4. Bill card / War Room with the new statuses rendered

---

## B · DECISIONS TO SETTLE (no research needed, just a call)

### B0. The tracking ladder — Involved REPLACES the top tier, it is not an addition
Owner: *"I don't want too many options then they lose their meaning."* Settled:

| Tier | Meaning | Class |
|---|---|---|
| **Involved** | we wrote it and/or got it introduced | org-asserted |
| **Supporting** | actively working for it | org-asserted |
| **Watching** | tracking, no position | org-asserted |
| **Opposing** | actively working against it | org-asserted |

**OPEN — the second oppose tier.** Owner: *"the disagree with version maybe like two different versions of
that, not much."* The honest difficulty: **"Involved" has no clean mirror.** Its positive meaning is
*authorship*, and the opposing-side equivalent of authorship is writing the substitute or amendment that guts
a bill — a real lobbying activity, but arguably a different axis rather than a stronger flavour of "Opposing."
Two candidate shapes, owner picks:
- **(a) symmetric authorship** — *Amending* as the oppose-side top tier (we're writing the changes), or
- **(b) intensity only** — *Opposing* plus a lighter *Concerned* for "we don't like it but aren't working it."

Do not build the write path until this is chosen; it is the enum.

### B1. MVP cut (D4) — ORCA says cut by downgrading OBJECTS, not by trimming features.

---

## C · PROBES — each can delete or reshape work below it. Run before building on them.

### C1. Bill → subject linkage  ← **highest-value probe**
The 505-subject taxonomy is confirmed (`SubjectIndexID`), **the route that maps a bill to its subject codes is
not found.** Gates: the Search subject facet, the War Room "on privacy bills" column, the entire Subject
profile, and the subject half of the call sheet. **If it doesn't exist, four features change shape.**

### C2. Redistricting signal — scoping (owner asked for this explicitly)
**Why it needs a probe at all:** `roster.py` returns district *numbers* and who holds them. A boundary can
move while the number stays "23" — so redistricting is **invisible to every source we currently ingest.** I
proposed an event-triggered re-confirm without a source; this is that debt.

Scope of the probe — answer for each candidate, then stop:
1. **Census TIGER/Line state legislative districts (SLDU/SLDL)** — does it publish VA upper/lower district
   boundaries, on what cadence, under what terms, and is there a stable version/vintage field we could diff?
2. **Virginia Redistricting Commission / Division of Legislative Services** — is there a machine-readable
   boundary or effective-date publication, or is it PDF/press only?
3. **Is a boundary file even needed?** A cheaper signal may exist: a published *effective date* for new maps.
   We do not need geometry — we only need to know **when to re-ask users**. If a date is obtainable, the
   entire shapefile question is moot. **Check this one first; it may end the probe.**

**Decision already made regardless of outcome:** ship the **6-month periodic re-confirm alone** — it needs no
external source and eventually catches a boundary change anyway. The event trigger is an enhancement, never a
blocker. Do not let this probe hold up accounts.

### C3. VPAP terms of service — human read required
`vpap.org` returned **403 to automated fetching**, so its terms could not be read programmatically and were
not worked around. Search results indicate the site advertises RSS/API/downloads. **A human must read the
terms before any scoping**, same diligence LIS got. Feeds the campaign-finance / gift-disclosure overlay
(ideation C1), which is currently absent from every mockup.

### C4. `legacylis.virginia.gov` CSV — the only lawful pre-2025 route
**Promoted from "someday" by the composition finding.** With only 2025–2026 authorized, a chair or majority
change *between those two sessions* leaves **one session** of valid history for that committee. This path is
the difference between a stats layer that means something and one that doesn't.

### C5. Open States bulk download — blocked on a login. Gates cross-state comparison.

---

## D · FOUNDATIONS — gate large amounts of the above

### D1. Routing — `web/` has **no router at all**
Six routes: **detail + list** for legislator, committee, and subject. Nothing with a URL works until this
lands. (Subject needs both — it is a filter *and* a profile.)

### D2. Write path — Worker + D1 + Cloudflare Access
Everything org-asserted depends on it: the ladder (B0), notes, contacts, the interaction log. **The call sheet
is a read surface over data that does not exist yet.**

### D3. Accounts — Google login, 30-day session
Ask: **what to call you** (first name, for office calls) + **state house, state senate, federal house
districts**. Never store an address; the lookup resolves and discards. Federal district collected, not
displayed (Mastermind uses it). One notice line: *"info used for legislative advocacy optimization."*
6-month re-confirm at login + manual edit in account settings.

---

## E · DATA LAYER

- **E1. Vote-history join** — `VOTE.CSV` already holds every member-vote pair; needs parsing to per-member
  records. Zero extra API calls. Feeds nearly every stat on the call sheet.
- **E2. Composition-break detection** — diff `chair_of()` / `party_split()` across sessions; where they
  differ, a pooled figure must show its split. **Correctness requirement, not a feature.**
- **E3. Per-session chamber majority, stored** — the control filter needs it; `party_split()` covers
  committees, chamber needs the same treatment.
- **E4. Coverage window as data** on every stat, so `(2025–2026)` is derived, never typed.
- **E5. Text-diff percentage** — one number serving companion drift, version drift, and cross-state
  similarity. `tools/text_corpus/normalize.py` already normalizes; the ratio sits on top. Removes three amber
  claims from the product.
- **E6. Co-patrons** — `/LegislationPatron/…`, inventoried, not built.

---

## F · DISPLAY

- **F1. Window × control dual filter** — applied together and independent. Expect `n` to collapse under a
  control filter in early years; that is the honest answer, not a reason to hide the control.
- **F2. Search: per-value facet counts** computed against the current filter state, which is what makes
  zero-count disabling work. Query-shape requirement, not styling.
- **F3. Search empty state = browse index** — four object rows with counts; `ours` is the only subdivision.
- **F4. Subject profile page** (stat list banked in [[ideas/predictive_lane]]).
- **F5. `k of n` everywhere** — no percentage on counts, no threshold, no interval. One rule.

---

## G · RECORDED, NOT QUEUED

- **G1. The backtest** — settles which stats carry signal. Both PROVISIONAL blocks wait on it. Not a blocker
  for the mockups.
- **G2. Mobile** — deliberately deferred (owner). **The specific problem, recorded so nobody assumes it is a
  CSS afternoon:** the trust partition is a *vertical rule between column groups* — a horizontal device. On a
  narrow screen the LIS columns collapse, so the partition does not get cramped, it **disappears**, and "ours"
  silently becomes the whole table. A mobile pass must re-invent the partition vertically.
- **G3. Tier-3 individual prediction** — owner go/no-go, gated on the calibration harness. No model output
  ships before it.
- **G4. Not in any mockup yet, from [[ideas/lobbyist_jtbd_ideation]]:** VPAP money overlay (C1), influence
  pathfinding / co-patron network (C4), the pinned verified fact sheet (V5), constituent-×-committee
  intersection (V3), after-hearing recap (V6).
