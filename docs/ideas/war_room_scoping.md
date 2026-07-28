---
tags: [ideas, product, war-room, watchlist, infra, scoping, owner-decision]
updated: 2026-07-17
status: active
open_loop: Decisions banked (D5 star=binary; D2 write-path=Worker+D1; D3 identity=Access 1-month, no name-pick). IA DECIDED by owner 2026-07-17: the War Room is its OWN tab, "your bills → drill in" (not a region of a bill page — that recommendation was retracted). Mockup v3 drawn + approved ([[design/object_page_patterns]]). Roster/vote data SCOPED + probe-confirmed ([[architecture/roster_and_votes_ingestion]]). STILL OPEN: the MVP cut (D4 — ORCA says cut by downgrading OBJECTS); the votes store (D1 vs blob); companion-bill sourcing; and the predictive Tier-3 go/no-go ([[ideas/predictive_lane]]).
---

# War room + shared watchlist — scoping memo (owner decisions required)

## MOCKUP v4 — owner change list, queued 2026-07-27 (do NOT ship a v3.5; fold these in with the prediction menu)
Owner reviewed v3 and asked for these together with the prediction display, in ONE next mockup:

1. **Delete "Still to clear: full committee → 3 floor readings."** Reads as a description, not data.
2. **Replace "Need 8 of 15 · 5 yes…" with an actual DATA POINT that integrates the threshold.** Owner: make it
   "not look like a description". Direction: put the threshold ON the bar as a marker — the bar already shows
   yes/no/unknown proportions, so a line at the 8-of-15 position turns prose into a readable position.
   The number stops being narrated and becomes something you *see*.
3. **Bill number → patron separator: dash, not a dot.** `HB463 — Cohen`, so it reads as *attributed to*
   rather than two adjacent facts. (Note: this reverses the v1 "· Cohen" styling; it is a deliberate change,
   not drift.)
4. **Co-patrons behind a disclosure on the patron** — on the main bill AND the companion row. Rationale
   (owner): *"so the lobbyists can see who supports it and get a more rounded view of the bills progress."*
   Co-patron count is a real support signal, not decoration. **Sourcing: `/LegislationPatron/api/
   GetLegislationPatronListAsync` is in the endpoint inventory, currently PARKED** — this promotes it. See
   [[ideas/copatrons_backfill]].
5. **Fix the "OURS" zone rule alignment** — the divider next to the label is off-centre. Not intentional.
6. **Rename the "Elsewhere" section** and **link the bill TEXT** on each cross-state row, so a lobbyist can
   *read* the other state's bill rather than only seeing a similarity label.
7. **The prediction menu** — the open item below; the reason v4 waits.

**Why one mockup:** owner, 2026-07-27 — *"don't do two micro versions."* Ship v4 once, with prediction in it.

> **⚠️ READ THE BOTTOM FIRST — most of these decisions are now MADE.** The five "DECISION" sections below are
> the **original memo as written on 2026-07-13**; their *Recommendation* lines are **historical, and several
> were overruled**. The owner's actual calls live in **[[#OWNER DECISIONS — 2026-07-16]]** and
> **[[#OWNER DECISIONS — 2026-07-16 (round 2)]]** at the foot of this page, and those SUPERSEDE anything above.
> Most important trap: **D3's "name-pick" recommendation is DEAD** (owner: *"it needs to be automatic or not
> exist"*) — identity is **Cloudflare Access**. Do not build from a Recommendation line without checking its
> decision block.
>
> **This is a DECISION MEMO, not a build.** TASK 3 of [[audits/build_wave_2026-07/README]]. It exists because
> the war room is the first feature that needs a **write path** (org state shared across people/devices) and
> a notion of **identity** — architectural forks only the owner can call. Context: the reframed primary persona
> (an advocacy org lobbying for its own bills, staffed by volunteers) in [[ideas/lobbyist_jtbd_ideation]] §8a/§8b.
>
> **Still open:** the **MVP cut** (D4), the **IA** (D1 — a recommendation now grounded in
> [[design/object_page_patterns]]: the war room as the org-owned *region* of the bill page rather than a new
> tab, which would retire D1's option (A)), and the **mockup** that must precede any code.

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


---

## Accounts, districts, and the "Involved" status (owner, 2026-07-27)

### Identity + districts — we never hold an address
Login with Google (or equivalent), 30-day session ([[ideas/predictive_lane]] D3). On first login we ask:
1. **What to call you** — first name, used when a volunteer identifies themselves to a member's office.
2. **Their districts** — state house, state senate, federal house.

**We ask for DISTRICTS, not addresses.** Owner: *"no one wants to give away their address, it's weird,
especially to a vibe coded site… that way I don't ever have to keep anybody's personal data nor imply I want
it."* If a user doesn't know their districts, an address lookup resolves them — **resolve and discard, never
persist.** "We don't store addresses" must be architecturally true, not a promise in a policy.

- **Federal house district: collect, do not display.** Used by the Mastermind federal product; asking once
  beats a second popup later.
- **Notice copy:** ONE short line — *"info used for legislative advocacy optimization"* — not a per-field
  disclosure. Owner: house district is the least invasive thing we ask for.
- **Re-confirm every 6 months** from signup, at login: *"still your districts?"* with a change affordance.
  Plus a manual edit path in account settings (name, districts).

### OPEN — the redistricting trigger has NO SOURCE YET (do not build on it)
I proposed an event-triggered re-confirm ("when new maps take effect, everyone re-confirms") **without naming
where that signal comes from.** Owner caught it. Recording the state honestly:

- **The roster CANNOT detect it.** `roster.py` gives district *numbers* and who holds them. A boundary can move
  while the number stays "23" — invisible to us. Do not assume the roster covers this.
- **Candidates to VERIFY (none confirmed):** Census TIGER/Line state-legislative-district files (SLDU/SLDL);
  the Virginia Redistricting Commission / Division of Legislative Services. Each needs a probe for
  availability, update cadence, and terms — the same diligence LIS got ([[knowledge/lis_api_authorization]]).
- **Decision for now: ship the 6-month periodic re-confirm ALONE.** It needs no external source and it
  eventually catches a boundary change anyway. The event trigger is an enhancement gated on a real source,
  not a requirement. **Better to ship the mechanism that needs nothing than to block on one I invented.**

### NEW STATUS — "Involved" (replaces the top tracking level)
Owner: *"for status of tracking we need an involved status which should replace the highest status now and
will basically indicate we played a role in the introduction and/or writing of that bill text."*

**REVISED by owner same day: it REPLACES the top tier, it is not an addition.** *"I don't want too many
options then they lose their meaning."* Ladder = Involved / Supporting / Watching / Opposing (+ one more
oppose flavour, OPEN — see [[state/va_build_queue]] B0). The full ladder and the open question live there.

**This is different in kind from the levels below it and that matters:**
- The other tracking levels are an **intensity dial** — how much attention we're paying.
- **"Involved" is a claim of fact** — we wrote it, or we got it introduced. Not a priority setting.
- It is **ORG-ASSERTED** (P20a): LIS cannot confirm we drafted anything, so it lives below the trust rule with
  our other intel, never presented as a sourced fact.

**It unlocks a stat we otherwise could not compute.** "Has this legislator ever carried a bill of ours?"
requires knowing which bills are ours *by authorship* — which is exactly what Involved records. Without it,
that relationship is unrepresentable. So it is not just a label; it is the input to the relational stats
below.

### Call sheet — requirements (owner, to be mocked next)
Not a phone script. **It must serve an in-person office visit as well as a call.** Content is an assembly of
stats we already compute — no generated prose, so it does not violate P25:
- **Relational, and this is the point:** how often they voted with us (`k of n`) · whether they have ever
  carried a bill of ours (needs Involved) · how many times we have contacted them, **by whom**, and when ·
  the outcome/tone of the last contact.
- **Behavioural:** how often they cross party lines · their record on this bill's subject code · their
  record before the committee holding this bill.
- Owner's framing: *"relational info is important in politics."* The sheet's job is to walk in already
  knowing the relationship, not to be told what to say.
