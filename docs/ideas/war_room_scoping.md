---
tags: [ideas, product, war-room, watchlist, infra, scoping, owner-decision]
updated: 2026-07-13
status: active
open_loop: five owner decisions (IA, write-path, identity, MVP cut, star↔position UX) block the war-room build
---

# War room + shared watchlist — scoping memo (owner decisions required)

> **This is a DECISION MEMO, not a build.** TASK 3 of [[audits/build_wave_2026-07/README]]. It exists because
> the war room is the first feature that needs a **write path** (org state shared across people/devices) and
> a notion of **identity** — architectural forks only the owner can call. Nothing here is built until the
> five decisions below are made. Context: the reframed primary persona (an advocacy org lobbying for its own
> bills, staffed by volunteers) in [[ideas/lobbyist_jtbd_ideation]] §8a/§8b.

## What the war room IS (recap, so the decisions have a referent)

A shared, live coordination surface for the org's priority bills: the deciding committee's roster with an
org-set position per member (support / lean / oppose / unknown) + a short note, the vote math ("need 8 of 15;
have 5, 4 against, 6 unknown"), who's covering which hearing, and call outcomes. It is the whip sheet every
pro shop keeps on a legal pad, made shared and live. **Hard rule already locked** ([[ideas/lobbyist_jtbd_ideation]]
§8b, V4): org-entered opinion is VISUALLY PARTITIONED from LIS-verified fact — two data classes, never
blended, so the trust layer stays clean. Everything the org types is clearly "ours, unverified"; everything
from LIS keeps the bank-grade treatment.

---

## The product's pages today, and why each exists (the IA analysis Decision 1 needs)

| Tab | The question it answers | Whose data |
|---|---|---|
| **Today** | "What just happened / what's on today?" — the anxiety-killer feed + today's calendar sliver | LIS (read) |
| **Calendar** | "When is everything meeting?" — the month/day schedule | LIS (read) |
| **Search** | "Find me a bill / a set of bills" — faceted lookup | LIS (read) |
| **Health** | "Can I trust the data right now?" — the operator/trust surface | our metrics (read) |
| **Changes** (building, [[audits/build_wave_2026-07/README]] TASK 1) | "What changed since I last looked?" | our differ (read) |

**The gap this exposes:** every current tab answers a question about *the legislature* or *our data*. None
answers *"what is OUR organization doing about these bills, together?"* That is a categorically different
question — it's about the org's own state and coordination, not LIS's. That gap is the argument for Decision 1.

---

## DECISION 1 — Information architecture: where does it live?

**Options**
- **(A) A new top-level tab — "Ours" (or "War Room" / "Our Bills").** ⭐ RECOMMENDED. It answers a question no
  existing tab does (see the IA table). It's the org's home base; a volunteer opens it to see "what do we need,
  where do we stand, what's mine to do." It also becomes the natural home for the shared watchlist itself
  (today the star set is per-browser localStorage — see Decision 2), the org positions, and later the whip
  board and assignments.
- **(B) A section inside Today.** Cheaper, no new tab. But Today is a *read* surface about the legislature's
  latest motion; bolting an *interactive org-state* panel onto it muddies both jobs and buries the war room
  below the fold. Rejected unless the owner wants the smallest possible MVP footprint.

**Recommendation:** (A). The org-state question deserves its own front door, and every later feature
(watchlist, positions, whip, assignments) has a home. Keep it a single tab that grows, not a sprawl.

---

## DECISION 2 — The write path (the real architectural fork)

Today the product is **static assets on Cloudflare Workers** — a read-only SPA over gviz. The war room needs
**shared, writable org state** (the watchlist, positions, whip marks, notes) that syncs across the org's
people and devices. Two credible paths:

- **(A) A tiny Cloudflare Worker API route + D1 (SQLite at the edge).** ⭐ RECOMMENDED.
  - *Fit:* the site is already a Worker; adding a few routes (`GET/PUT /api/org/...`) + a D1 binding is the
    native, in-house path. D1 is a real relational store (positions, members, notes, assignments) with
    transactions — the war room's data is relational (bill × member × position), which a flat sheet models
    poorly.
  - *Cost:* modest new surface (a Worker handler, a schema, a migration). Auth handled in Decision 3.
  - *Latency/reliability:* edge-local reads/writes; no Google-quota coupling; independent of the gviz path so
    a war-room outage can't touch the read product.
  - *Scales to 50 states cleanly:* per-org rows keyed by state; no per-state plumbing.
- **(B) A Google Sheet write via an Apps Script webhook.** Keeps ALL state in Sheets (one mental model).
  - *Cost:* an Apps Script `doPost` endpoint + a shared secret; the SPA POSTs deltas. Weak auth (a bearer
    secret in client code is public), Sheets write-quota and latency, and concurrent-write races on a flat
    tab (the exact eventual-consistency class the witness prune was built to avoid). Modeling bill×member
    positions in a flat sheet is awkward and grows messy.
  - *When it wins:* if the owner strongly wants zero new infra and everything auditable in one workbook, and
    accepts weak auth for an MVP with a handful of trusted volunteers.

**Recommendation:** (A) Worker + D1. It's the honest home for relational, concurrent, multi-user org state,
and it decouples the writable surface from the accuracy-critical read path. (B) is a viable throwaway MVP only
if speed-to-first-demo beats everything.

**Migration note either way:** the shared watchlist SUPERSEDES the per-browser `bt.tracked` localStorage set
(`web/src/state/tracking.ts`). Plan a one-time import ("adopt this device's starred bills into the org
watchlist?") so no one loses their stars. The star UI already anticipates this — the two-step untrack copy
says "leaves the shared watchlist for everyone" (shipped #219, currently shown only when the shared list exists).

---

## DECISION 3 — Identity: who is "you"?

- **(A) None — unauthenticated shared board (unguessable URL).** Simplest; anyone with the link edits. Fine
  for a tiny trusted group; no "who marked this" attribution; a leaked link is an open door.
- **(B) Name-pick per device.** ⭐ RECOMMENDED for the MVP. A one-time "who are you?" dropdown (the org's
  member list, editable) stored per device; every position/note/assignment is attributed ("marked by Sam").
  No passwords, no account system — enough to make the whip board meaningful (you can see who still owes a
  call) and to make attribution honest, which volunteers need.
- **(C) Real auth — Cloudflare Access in front of the org tab.** Strongest (SSO, real accounts, per-person
  audit). Right end-state for a paid multi-org product; overkill for the first org. Gate the war-room routes
  behind Access when the product goes commercial.

**Recommendation:** (B) name-pick MVP now, architected so (C) can slot in later (attribution is already
per-identity; Access just replaces the honor-system name with a verified one).

---

## DECISION 4 — The MVP cut (what ships first vs later)

- **MVP (first PR):** the **shared watchlist** + **per-bill org position** (support / oppose / watch / amend),
  attributed (Decision 3B), visually partitioned from LIS fact. That alone converts the star from a private
  bookmark into a shared org signal — the single highest-leverage step.
- **Second:** the **whip board** — the deciding committee's roster with per-member lean + the vote math
  (rosters are structural from our committee data; the lean is org-entered).
- **Third:** **assignments / task routing** — "cover this hearing," "call these members," with call-outcome
  capture feeding the whip board.

**Recommendation:** ship the MVP cut alone, get the org using it for one week, then decide whip vs assignments
by what they actually reach for. Do NOT build all three before real use.

---

## DECISION 5 — How org position coexists with the star (owner flagged this)

The star = "we're tracking this." A position = "our stance is support/oppose/…". They're related but distinct.
Options:
- **(A) Position is a property OF a tracked bill.** ⭐ RECOMMENDED. Starring adds a bill to the shared
  watchlist; a small position control appears on the bill card / war-room row for tracked bills. You can track
  without a stance yet (position defaults "watch"). Clean mental model: track first, take a position when you
  have one.
- **(B) Position replaces/subsumes the star.** Setting any position implies tracking; un-positioning untracks.
  Fewer controls but conflates two acts and makes "just watching, no stance" awkward.

**Recommendation:** (A). Keep the star as the track toggle; add position as an attribute of tracked bills.
The position control lives on the war-room row primarily, mirrored on the bill card.

---

## Summary — the five asks

1. **IA:** new "Ours" tab (rec) vs section in Today.
2. **Write path:** Cloudflare Worker + D1 (rec) vs Apps Script → Sheets webhook.
3. **Identity:** name-pick per device (rec) vs none vs Cloudflare Access.
4. **MVP cut:** shared watchlist + position only first (rec); whip board second; assignments third.
5. **Star ↔ position:** position as an attribute of a tracked bill (rec) vs position subsumes the star.

Once these are answered, this page becomes the build spec (or a new `docs/architecture/war_room.md` does).
No code until then. See also [[ideas/lobbyist_jtbd_ideation]] §8a/§8b, [[audits/build_wave_2026-07/README]],
[[ideas/product_vision]] §9 (clients/positions were parked here from the start).
