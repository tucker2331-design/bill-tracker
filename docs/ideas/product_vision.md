---
tags: [ideas, product, vision, ui, locked]
updated: 2026-06-18
status: active
---

# Product Vision (B1) — the lobbyist platform

> **Zoom out first:** [[ideas/product_identity]] is the layer above this — what the whole product IS (a
> multi-state legislative operating system; 3 pillars; the origin story). This page is the LOCKED VA
> front-end spec (pillar 1's four lenses); the strategic tools + war room (pillars 2/3) derive from identity.

This is the **locked** product vision from the 2026-06-18 design sessions. It defines what we
build the front end toward. Phase B of [[ideas/product_roadmap]]. The hardest design problem
(the two chambers) is solved; the screens and rules below are decided. Change only with a new
owner decision logged here + in [[log]]. The next chapter is **B2 — the LIS data inventory**,
which answers "what data do we have vs. need" feed-by-feed (several trust-layer gaps below are
literally B2 questions).

---

## 1. North star — what the lobbyist needs (not just wants)
- **User:** a Virginia General Assembly lobbyist. Built for a **single organization** for now
  (multi-client/multi-org is parked — see §9 — but the data model leaves room).
- **The job-to-be-done:** *never miss an action on the bills I'm responsible for; always know
  where each stands; act while I still can; report to my org with confidence.* The deepest fear
  is **missing** something, or being **silently misled** by stale/incomplete data.
- **What "best" means:** honest, fast, complete, intuitive — and above all **trustworthy**. The
  guiding rule for the whole product: **it may not know something, but it must never pretend it
  knows.** (Freshness, completeness, certainty — see §7.)

## 2. Organizing principle — one dataset, four lenses
The bills are the spine. Every screen is the *same* bills asked a different question — this is
what keeps it one coherent product instead of a pile of tabs:
- **by urgency** → "what's new" (the landing's daily feed)
- **by stage** → the **timeline** (the pipeline)
- **by time** → the **calendar**
- **by name / attribute** → **search**

**One global control governs every view: the `Tracking ↔ full General Assembly` switch.** When
it's on Tracking, *every* surface — what's-new, timeline, calendar, search, counts — shows only
the org's tracked bills. Flip to full session and the same surfaces show the whole GA. It is the
only system-level switch; everything else is a filter *within* a view.

## 3. The screens

### 3a. Landing — the daily driver
A priority stack, not three equal panels:
1. **What's new (top, the anxiety-killer).** A vertical feed of *actions on the (tracked) bills*
   as they roll in, with today's date and a back-clicker to page through prior days. **Shows the
   whole day** — NOT a per-user "since you last checked" marker, because several people share the
   system, so everyone must see the complete set and know it's complete. Each row = bill # + what
   happened + time → click to the bill card. **Slack on-demand digest:** message the bot and get
   the day's (or a chosen day's) summary — the catch-up safety net over per-action push (push =
   real-time, digest = "prove I didn't miss anything"). Slack plumbing already exists.
2. **The timeline (hero, middle).** The pipeline (§3b) at a glance.
3. **Mini-calendar (a slim "next up" strip).** Today + tomorrow's meetings/deadlines.

### 3b. Timeline — the crossover-lane pipeline (the centerpiece)
A horizontal pipeline with a **centerline**. **Senate is permanently ABOVE the line, House
permanently BELOW** — regardless of a bill's origin. The payoff: *a bill literally crosses the
line at crossover*, so the word becomes the picture.
- **Stages:** `Prefiled` (on the line) → `Committee` → `Floor` → **✦ crossover divider ✦** →
  `Committee` → `Floor` → `Governor` (on the line). The pipeline **opens** into two chamber lanes
  after prefiling and **converges** back at the governor (prefiled and governor belong to neither
  chamber, so they sit on the centerline). Stages repeat around crossover, so **position = true
  progress** — a bill in its second-chamber committee is visibly most of the way home.
- **Crossover** is a **single session deadline** (a guillotine — miss it in your house of origin
  and the bill dies), not a per-bill event. It is the midpoint divider here AND a marked date on
  the calendar. **Bills that never cross are stranded left of the divider = visibly dead** — a
  glance shows "these died at crossover," which a plain list can't.
- **Overview (collapsed):** each stage shows just a **count per side** (a number above for Senate,
  below for House). Nothing else. No per-bill paths drawn.
- **Detail (committee expanded):** the committee zone opens into a **board** —
  - **Horizontal = committees** (columns), only those that actually hold your bills, ordered by
    pipeline position with **money committees (Finance / Appropriations) last** (a fiscal bill is
    usually re-referred there after its policy committee — a *default axis order*, while each
    bill's real referral path stays exact).
  - **Vertical within a column = subcommittee subheaders**, and under each a stack of
    **rectangular bill boxes** (bill # + catchline) that **expand individually** to the full card.
    Reading *down* a column traces sub → full committee (the sub→full continuity lives here).
  - **Mirrored across the centerline** (Senate committees grow up, House grow down). **Expand one
    side at a time** so the vertical space stays sane ("all committees if they fit, else one").
- **House vs Senate committees are never melded** — they are distinct structural entities with
  distinct codes (`H01–H24`, `S01–S13`). E.g. the money committee is **Senate Finance &
  Appropriations** (combined) vs the House's **separate Finance and Appropriations**. The rule:
  **never display a bare committee name; always the chamber-qualified committee.** The crossover
  divider keeps first/second-chamber committees on opposite sides positionally.
- **Referral badge:** a bill bounced between committees carries a `2nd referral` / `3rd referral`
  badge (we track re-referrals structurally).
- **Actionable vs decided shading:** stages where the org can still influence the outcome read as
  "you can still act"; governor/enacted/dead read as "decided." Lets a lobbyist see "10 still in
  play, 9 decided, 5 died at prefile."
- **Two zoom levels, one geometry:** aggregate = counts above/below per stage; single bill = its
  traced crossing path. Never draw every bill's path at once (spaghetti).

### 3c. Calendar tab
The full calendar (the perfected calendar subsystem is the engine). Crossover and other session
deadlines marked. The mini-calendar on the landing is a window into this.

### 3d. Search tab — find a specific bill, or slice the set
- A **search bar** (type a bill number, a catchline keyword, or a patron → jump to it).
- A row of **filter buttons** — `House bills`, `Senate bills`, `by committee`, by status, by
  patron, by subject — that stack. **No chamber switch** (chamber is just two of the filter
  buttons); the only system switch remains the global Tracking/full one.
- Results render as the **same bill boxes** used everywhere (one reused component). Default sort
  by bill number (the "I know what I want" lookup); offer "most recent action" and "by stage."
- Serves both *known-item* lookup and *browse/discovery* without forcing a mode (faceted search,
  per the info-display literature — Hearst, *Search User Interfaces*).

### 3e. Bill card — the component used in every view
Header: **bill number + catchline + a tracking star** (filled when tracked, outline when not).
**No `H→S` crossover tag** (cryptic; the location already tells you the current chamber). Then a
meta strip + the history. **Every fact carries its source location so they correlate** (§6):
- **Where it is** — committee / subcommittee.
- **Latest vote** — *with where it happened* ("reported from Senate Finance, 15-Y 0-N"), not a
  bare tally.
- **Next meeting** — *with its committee*, from the docket/agenda ("Senate Finance & Appropriations
  — Thu 2/20, 9:00 AM"). If that committee differs from "where it is," a re-referral is coming and
  it's now visible instead of hidden.
- **History** — a real two-column labeled table (`Action` | `Date`), newest first, with the
  **pinned provisional row** (§5) on top when the status feed is ahead of the published history.

### 3f. Bug / health tab — the operator view
Surfaces the diagnostics the system *already* produces: categorized `SYSTEM_ALERT` rows (severity
+ type), circuit-breaker state, last-successful-run freshness (`AA1`), the Section-9 accuracy
count, unclassified count, drift canaries. Pragmatic now (one system); lifts onto the master
dashboard later. This is the *deep* layer of the trust signals in §7 — the lobbyist-facing layer
is woven inline, the operator layer is here.

## 4. Recovered data model
The old front end already carried the whole bill record, all from data we have
(`backend_worker.py:238`): bill number, official title (catchline), status + date, derived
lifecycle, current committee / subcommittee, latest vote, the history list, upcoming meetings.
The bill card in §3e is this model, displayed with provenance.

## 5. The pin (recovered, `shadow_v2.py:420`) — keep + improve
LIS feeds update at different rates, so the **status** feed can run ahead of the **history** feed
— the current status names an action not yet in the action log. The pin fix: if the status text
isn't found anywhere in the history, synthesize a history row dated today, mark it provisional,
and render it at the top. We keep this and **label *why*** it's pinned ("status feed is ahead of
the published history; shown provisionally, never invented"). It is one instance of the broader
**feed-skew** problem — §7 item 3 generalizes it.

## 6. The correlation / provenance rule
Every derived fact on the surface is **tied to its structural source and shown with its location**,
and when we can't confidently make the link we **show the bare fact rather than assert a false
one** (never a probabilistic guess — the same discipline that took the calendar to Section-9 = 0).
The meeting→committee link comes from the docket; the vote→committee link from the action's
committee code. So the card's facts stop being free-floating and become one checkable story.

## 7. The trust layer — the product never lies (first-class, not a feature)
A lobbyist is misled in exactly three ways — **stale, incomplete, or uncertain-shown-as-certain**
— and we guarantee against each. Two audiences: the **lobbyist** (inline trust signals, since they
won't open a bug tab) and the **operator** (the bug tab, §3f). Same signals, two depths.

**What we track today (good):** categorized alerts, the circuit breaker, last-successful-run
freshness, the Section-9 accuracy count, unclassified count, schema/committee/status drift
canaries, the pin, and an independent MinutesBook reconciliation.

**Gaps — should track, don't yet (several are B2 questions):**
1. **Bill-count completeness** — do we have *every* bill LIS has? Our total vs LIS's introduced
   total; alert on drift. *The scariest silent gap — a bill we dropped is invisible to its
   tracker.* We don't watch it today.
2. **Per-bill freshness** — did one tracked bill quietly stop updating while the rest moved?
   "Nothing happened" must mean *nothing happened*, not *we stopped fetching it.*
3. **Generalized feed-skew** — the pin only catches *status ahead of history*; the same skew exists
   for votes, dockets, and the schedule. Flag **any** fact a corroborating feed hasn't confirmed.
4. **A universal provenance / confidence flag** — extend the calendar's `derived_standing` / pin
   discipline to the *whole* product: every derived, assumed, or **unclassified** value is visibly
   marked; an action we couldn't categorize says "couldn't categorize — here's the raw," never
   vanishes.
5. **Explicit scope disclosure** — state what we cover and what we *don't* (amendment text? fiscal
   notes? patron? companion bills?) so **absence of data is never misread as absence of event.**
   This is a direct B2 output.
6. **Surface upstream changes to the lobbyist** — when a drift canary fires (LIS renamed a field,
   added a committee), the lobbyist sees "an LIS change may affect some data," not a silent degrade.

**How it shows:** inline — a **"data as of X ago"** header on every view (red when stale, hard
in-session), **per-bill freshness/confidence badges**, and **provisional flags** on uncertain facts.
The bug tab is the operator's raw view of the same. **The product is allowed not to know; it is
never allowed to pretend.**

## 8. Decisions & why (do not re-litigate)
- **No merger into the old `backend_worker`/`v2_shadow_test`** — forward-build; don't slip the new
  engine into the old case. (Owner, 2026-06-18.)
- **Pipeline is the home, not a separate dashboard** — the overview is glanceable *and* drillable,
  so "dashboard vs jump-in" collapses into one screen.
- **Nest subcommittees inside committees** — a sub is a stage *of* a committee, not after it; the
  sub→full journey reads down a committee column.
- **Senate-top / House-bottom lanes** — encodes chamber in *position*, not labels; makes crossover
  literal; permanent sides = a stable, sticky mental model (one-time legend to learn).
- **Counts first, detail on demand** — overview shows numbers per side; expand for the board.
- **Catchline as the bill's short name for now** (the LIS official one-liner); a plainer
  derived name is a later option once we see many at once.
- **Full-day what's-new, no per-user read-state** — multi-user system; everyone must see the
  complete day.

## 9. Parked / future (explicitly not now)
- **Clients & positions** — single org for now. Leave a `position` column (support/oppose/watch —
  an org stance, cheap to add) in the data model so it isn't a retrofit; no UI yet. The system can
  later be adjusted for a multi-client/multi-org setup.
- **Historical tracker** — a *separate, bigger* design pass: analytics (per-committee survival
  rates, cross-session trends) reading the session archive. The hard part is *what* to show and
  *how*. Build it **state-level** from the start; lands on the master dashboard eventually. Not now
  — designing it would derail B1.
- **Master dashboard** — the eventual home for the bug tab and the historical tracker, once there's
  more than one system to show.

## 10. Hands off to B2
The data inventory must answer, feed-by-feed: what LIS exposes, what we ingest, **how fresh/lagged
each feed is** (item 3), whether we can verify **bill-count completeness** (item 1), and **what we
don't collect** that the features above or the scope-disclosure (item 5) require — including any
data needed for *non-calendar* features that justifies a database expansion.

See also [[ideas/product_roadmap]], [[state/current_status]], [[knowledge/lis_api_reference]],
[[knowledge/lis_api_safety]], [[index]], [[log]].
