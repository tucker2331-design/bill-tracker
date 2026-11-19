---
tags: [ideas, access, roles, admin, multi-state, owner-request]
updated: 2026-11-19
status: stub
open_loop: Per-state admin role (owner 2026-11-19) — not started; needs the clients decision (F1 in [[ideas/executive_site]]) before the data model is built.
---

# Per-state admin role — to-do (owner, 2026-11-19)

> *"add to the to do admin status which unlocks full health page + ability to adjust things like who can log in, see
> what districts they are in on an individual basis and remove or add people. this should be on a state by state
> basis so i could give a state lead the ability to manage day to day things with their team."*

## What it is
Three levels, each state separate:

| role | sees | can change |
|---|---|---|
| **member** (today's everyone) | the state site: bills, calendar, War Room, the basic Health page | their own position and contact entries |
| **state admin** (a state lead) | everything a member sees, plus the **full Health page** for their state | their state's team only: add or remove people, make someone admin, edit each person's districts |
| **owner** (you) | every state, and the executive site ([[ideas/executive_site]]) | everything, every state. A state admin can never remove you |

## What exists today, and what it would replace
- **Who can sign in** is the `TEAM_EMAILS` Worker secret, one per state, that only you can edit in Cloudflare
  (sourced: `worker/team.js`, [[architecture/verification_durability]]). A state lead cannot add a volunteer
  without you.
- **Each person's districts** already have a home: the D1 `users` table carries `home_state`, `district_house`,
  `district_senate`, `district_congress`, `districts_confirmed_at` (sourced: `tools/d1/console_setup.sql`). Nothing
  lets an admin see or correct them yet. They matter because a member who lives in a legislator's district is that
  legislator's constituent, which is the strongest kind of contact (the drafting-room and legislator-page designs
  already use this).
- **The full Health page** is Virginia-only today (`features.health: "full"`); PA and CA show the basic one.

## Build sketch (not started)
1. A D1 table per state: `team_members(email, role, added_by, added_at, removed_at)`, replacing `TEAM_EMAILS`. Seed
   it from today's secret so nobody is locked out.
2. Every role change is written to an audit row (who changed whom, when). Each state always keeps at least one
   admin, and the owner can't be removed. If the table can't be read, sign-in is refused, never opened up
   (the same fail-closed rule as today's team gate).
3. A Team screen for admins: list, add, remove, change role, edit districts.
4. Full Health for admins: the Health screen's "full" mode turns on by role instead of by state, which also needs
   PA and CA to have the parts Virginia's full page reads ([[ideas/state_baseline_parity]]).

## Open questions (yours)
- **Clients first.** If several client organizations share one state's site, roles and positions need an
  organization key too (today positions are keyed by state + bill only). That fork is F1 in [[ideas/executive_site]].
- "See what districts they are in": recorded as each person's own home districts (the existing `users` columns).
  If you meant assigning legislators or districts for a person to cover, that's a different field. Say which.
