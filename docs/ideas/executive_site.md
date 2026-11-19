---
tags: [ideas, executive, operator, multi-state, brainstorm, owner-request]
updated: 2026-11-19
status: stub
open_loop: Executive site brainstorm (owner 2026-11-19) — awaiting the owner's answers to F1–F3; no build until then.
---

# The executive site — brainstorm (owner, 2026-11-19)

> *"start brainstorming about the executive site that will manage these 3 and then newyork as well and whatever we
> add from there. justify its existence … think about why i would need and the difference between my roll as a
> manager of this site and a manager of vot operations. bc i am the only person who operates in both of those spaces
> so i need to see both info about the site generally for all of my clients and then info for my job as vot leg
> manager."*

Claim classes below: **[sourced]** = a file, run or measurement named beside it; **[derived]** = computed from
sourced facts; **[proposal]** = my design choice, open to change.

## 1. Should it exist? The case, and the case against

**The test:** an addition earns a place only if it answers a question nothing else answers, at a cost the owner
pays today. Two questions qualify.

**Question A, the operator's: "Is every site working, correct, and within its limits, and who can get in?"**
On 2026-11-18/19, answering it for California alone took six places [sourced: this session's work]:
1. GitHub Actions job logs: did the job write, and what are the counts?
2. Cloudflare's build checks on pull requests: is the CA build red?
3. Google Cloud, across two projects: the service account lives in `bill-tracker-mastermind`, the sign-in client
   in another.
4. The sheet's Share dialog.
5. The CA Worker's own health page.
6. A headless browser, to see whether Google refused sign-in.

The owner could not do 1, 5 or 6 without me. The same six questions exist for every site: VA, PA and CA are live or
going live, and NY's bill engine already writes daily without a site [sourced: [[ny/state/current_status]]].
That's 4 × 6 = 24 places [derived].

**Question B, the VOT legislative manager's: "What does VOT need to do this week, in every state where we have
bills?"** Each state site shows one state, on purpose. Nothing joins VOT's positions, hearings and contacts across
states. The owner is the only person who needs both answers [sourced: the owner's message].

**The case against:**
- With one client and two states, a basic Health page on each site plus a bookmark folder would do.
- An executive site is another Worker to keep alive, another sign-in surface, and another place that can be wrong.

**Where the line falls [proposal]:** three or more states, or two or more clients. Today there are 3 states plus NY
coming, and "all of my clients" is plural, so the line is crossed. **It should exist**, but it should start as the
thinnest thing that answers A, then B (§5).

## 2. Two roles, kept apart

| | **Operator** (manager of the site) | **VOT legislative manager** (a client user) |
|---|---|---|
| the question | is the platform healthy, correct, within limits, and who has access? | what must VOT do this week, across states? |
| whose data | every client, every state, the infrastructure | VOT's own positions, bills, contacts and team |
| time horizon | now, and drift over weeks | this week and the next deadline |
| what "bad" looks like | a stale feed, a red check, a refused sign-in, a quota near its limit | a hearing on a VOT bill tomorrow with nobody assigned |
| who else will ever need it | maybe one future co-operator | every client's director (their own org only) |

**Rule [proposal]: two lenses, never mixed.**
- Operator data (jobs, quotas, configs) never appears in a client view. Clients shouldn't see infrastructure, and
  the owner shouldn't wade through it while lobbying.
- A switch at the top, **Platform | VOT**, and later one entry per client.
- The VOT lens is built as the *client director's page* with VOT as its first client, not as a VOT special case.
  Every client's director will want "my org, all my states", so building it once serves all of them.

## 3. What each lens would hold

| section | lens | the question it answers | data (exists?) | size |
|---|---|---|---|---|
| status board: one row per state | Operator | is each site fresh, right and reachable? | each sheet's AA1 payload + Metrics_History; each Worker's `/api/health`; GitHub job runs; Cloudflare build checks — **all exist** | S |
| what changed upstream | Operator | did a source start saying something new (a new status value, a new link host)? | the per-state census checks already counted (e.g. `end_status_unclassified`, `links_rejected`) — **exist** | S |
| limits | Operator | are we near a quota? | Sheets 429 retries ([[failures/assumptions_audit]] #160), Actions minutes, the CI cache size (CA saves 1.16 GB a day) | M |
| access | Operator | who can sign in where, per client and state? | `TEAM_EMAILS` per Worker today → the admin-role tables ([[ideas/state_admin_role]]) | M |
| incidents, all states | Operator | what broke, and is it fixed? | Virginia's `Incident_Log` (VA only today) | M |
| onboarding a new state | Operator | how far along is NY (or the next state)? | a checklist per state: source scoped, job writing, sheet, Worker, secrets, sign-in, Health green | S |
| portfolio across states | Client (VOT) | every bill VOT has a position on, in every state, with its stage | each state's D1 `positions` + its Bill_Tracker — **exist** | M |
| this week | Client (VOT) | hearings and floor votes on VOT bills, all states, in one calendar | each state's Sheet1 calendar — **exists** | M |
| team activity | Client (VOT) | who talked to whom, and which of our people are constituents of the legislators who matter | D1 `interactions` + `users` districts — **exist** | M |
| deadlines | Client (VOT) | the next crossover or house-of-origin date in each state | state configs (`crossoverBySession`) | S |

## 4. How it would be built [proposal]
- **Its own Worker** (`bill-tracker-exec`), built from the same site code. It reads every state's sheet with the
  service account and binds every state's D1 database (one Worker can bind several). No state Worker changes.
- **Owner-only sign-in at first** (an `EXEC_EMAILS` list, failing closed like today's team gate), moving to the
  admin-role system once it exists.
- **Read-only at first.** It shows; changes still happen on each state site. A wrong number on an executive page
  must never be able to write anything.

## 5. First step, if you say go [proposal]
The **status board**: one row per state (VA, PA, CA, NY), with data age, last job run, red/green Health checks,
Worker config, the sign-in check, and NY shown as "engine only, no site". Every number already exists, so there are
no new data sources. Then the VOT portfolio and "this week".

## 6. Decisions only you can make
- **F1. Clients.** Is each state site one organization (today's model: a position is keyed by state + bill, so one
  stance per bill), or will several client organizations share a state site with separate positions and teams?
  "All of my clients" suggests the second. That means an organization key on positions, contacts and roles, and it
  has to be settled before the admin role is built. Prior art: [[ideas/product_identity]] defines the product as
  "for an advocacy organization that lobbies for its own agenda" (one org). F1 would widen that.
- **F2.** Is the cross-state client page available to every client's director, or only to you for VOT?
- **F3.** Will anyone besides you ever see the Operator lens (a co-operator)?
