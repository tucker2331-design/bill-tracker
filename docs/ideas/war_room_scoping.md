---
tags: [ideas, product, war-room, watchlist, infra, scoping, owner-decision]
updated: 2026-07-17
status: active
open_loop: Decisions largely banked (D5 star=binary; D2 write-path=Worker+D1; identity=Access 1-month, no name-pick; IA has a RECOMMENDATION awaiting the owner from [[design/object_page_patterns]] — war room as a REGION of the bill page, not a tab). Build now blocked on the MOCKUP (owner rule: mock up before code), on member/committee ROSTER ingestion (zero ingested today), and on the MVP cut.
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

---

## OWNER DECISIONS — 2026-07-16 (updates the five asks above)

### ✅ D5 — Star ↔ position: DECIDED = option (A), per the owner, verbatim intent
> *"the star simply signifies if it's one we are tracking and involved with or not. the level of involvement —
> whether wrote it / support it / hate it — is a different question."*

**Locked:** the **star is a binary "are we tracking/involved with this"** toggle. **Position** (wrote it /
support / oppose / watch / amend) is a **separate attribute** of a tracked bill, never conflated with the star
and never implied by it. A bill can be tracked with no position yet. This matches the shipped two-step-untrack
copy and [[ideas/product_vision]] §9's parked `position` column.

### ✅ D2 — Write path: DECIDED = Cloudflare Worker + D1, conditional on "free + will hold up" — VERIFIED
Owner: *"i guess the cloudflare thing assuming its free and will hold up for what we need it for."* Verified
against Cloudflare's current published limits (2026-07-16) rather than assumed:

| D1 free plan | Limit | Our realistic need (war room) |
|---|---|---|
| Rows **written**/day | **100,000** | watchlist + positions + whip marks ≈ **low hundreds/day** at peak |
| Rows **read**/day | **5,000,000** | see the read-budget note below |
| **Storage** total | **5 GB** | thousands of rows ≈ **single-digit MB** |

**Verdict: holds with ~100× headroom**, even at 10 states. Three honest caveats recorded so they're designed
for, not discovered:
1. **Over-limit = ERRORS, not surprise billing.** D1 returns errors when the daily cap is hit (it does not
   silently bill). Good for a free product — but it means the war room MUST fail-open and MUST NOT be able to
   break the READ product. This is exactly why the write path stays decoupled from the gviz read path.
2. **Reads deserve one design thought at scale.** A naive "re-read the whole watchlist on every page load"
   (500 rows × many loads × many users) climbs toward the 5M/day read cap. Mitigation is ordinary (read once
   per session / cache at the edge) — not a blocker, just a rule to write down now.
3. Limits reset daily 00:00 UTC.

### 🔄 D3 — Identity: REOPENED — the rejection was based on my bad explanation, not the facts
Owner: *"3 won't work — most people use this from a link on their browser + that requires a web app and
appstore approval which we never planned for."* **Correction: NONE of the identity options require an app,
an app store, or an install.** All three are plain-browser, link-first:
- **(A) none** — shared unguessable link; no attribution.
- **(B) name-pick per device** — a dropdown stored in the browser. Works from a link, BUT it identifies the
  *browser*, not the person: two devices = two picks, a shared computer misattributes, and it is honor-system.
- **(C) Cloudflare Access** — **verified 2026-07-16: browser-based, NO client software or end-user install**;
  free for **up to 50 users**; login via **one-time PIN emailed to the user** (or a third-party SSO). The
  flow is literally: click the link → type your email → paste the 6-digit code → you're in.

**Revised recommendation: (C).** The owner's own constraint — *"most people use this from a link on their
browser"* — is precisely how Access works, and unlike (B) it gives REAL per-person identity that follows a
user across devices (so whip attribution means something). It also solves, with the same mechanism, the
long-standing requirement that the **master/HQ site be gated to the owner + a few execs**
([[ideas/product_identity]] topology) — one auth story for both, free at our size.

## OWNER DECISIONS — 2026-07-16 (round 2)

### ✅ D3 — Identity: DECIDED = Cloudflare Access; name-pick is DEAD
Owner rule, verbatim intent: *"name pick is an extra step no one wants to do — it needs to be **automatic or
not exist**."* That kills option (B) outright and is a good general principle: **an identity mechanism that
asks the user to do clerical work every time is not an identity mechanism.** Remaining: (A) none, or
(C) Access. Owner: *"yeah if the cloudflare login is free and will stay logged in like other sites (ie not a
constant pain in the ass re-logging in / verifying)."*

**VERIFIED 2026-07-16 (Cloudflare docs, not assumed):** Access session duration is **configurable from 15
minutes to 1 MONTH**, default 24h, settable globally / per-application / per-policy. **We set it to 1 month.**
So the real UX is: click the link → email → 6-digit code → **stay logged in for a month** → one code again.
After first login it IS automatic (a session cookie), satisfying the owner's rule.
**Honest caveat, stated not buried:** 1 month is the MAXIMUM — this is not "logged in forever" like Gmail. A
volunteer re-enters an emailed code roughly once a month. Mild, non-zero. If even that is too much, the
fallback is (A) none (an unguessable link, no identity, no attribution).

### ⚠️ STANDING CONCERN — the free-tier cap risk (owner, 2026-07-16)
Owner: *"this whole cloudflare limits thing is slightly worrying — we need to be really careful and aware of
that and constantly on the lookout for a free alternative without caps."*

**Honest finding: a "free, uncapped" hosted store does not exist** — someone pays for the servers, so every
free tier caps or carries rug-pull risk. Surveyed: Supabase free (pauses on inactivity), Neon free (0.5 GB,
autosuspend), Turso (plans changed), self-hosted SQLite on a ~$5/mo VPS (uncapped but costs money + ops),
GitHub-as-store (free but hostile to concurrent writes), Sheets (what we use — also capped: API quotas + the
10M-cell ceiling we already manage). None is free + uncapped + good.

**So the protection is NOT finding an uncapped mirage — it is these three rules, which are now design law:**
1. **PORTABILITY is the real insurance.** D1 is plain **SQLite** — export/migrate is trivial. If Cloudflare
   ever changes terms, we lift the file to any SQLite host, a VPS, or back to Sheets. Keep the schema plain
   (no vendor-specific features) so this stays a one-day move, never a rewrite. This is the strongest answer
   to the owner's worry.
2. **A USAGE CANARY, same discipline as the LIS-safety guardrails.** Measure real daily writes/reads against
   the cap and alert at ~25% — we must never be *surprised* by a cap. (Also catches a runaway-bug write storm,
   which is the ONLY realistic way we hit 100k writes/day at our size.)
3. **DECOUPLING (already the design).** A cap hit degrades the war room ONLY; the read product (gviz) is
   untouched and the accuracy path never depends on it.

**Scale reality check that bounds the whole worry:** our need is ~hundreds of writes/day against a 100,000/day
cap (~100× headroom), and even if it ever went paid, a workload this small costs a few dollars — the downside
is bounded and tiny. The risk is a *terms change*, and portability (rule 1) is what neutralizes that.

### 📐 PROCESS — mock up the war room BEFORE any code (owner, 2026-07-16)
Owner: *"once you get to the war room do a mock up before you start writing code so I can get an idea of what
we are working with."* Standing requirement. **But the honest sequence is: the product-architecture synthesis
FIRST, then the mockup, then code** — because DECISION 1 (does the war room get its own tab, or live inside an
existing surface?) is exactly what the synthesis answers, and a mockup would otherwise have to *assume* the
answer and bake in the "mosh of features" the owner warned about. Mockups obey the design canon
([[design/dashboard_and_visual_language]] — read it before drawing).

