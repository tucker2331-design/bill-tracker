---
tags: [ideas, product, identity, vision, strategy, north-star]
updated: 2026-07-15
status: active
---

# Product identity — what this fundamentally is (the north star above the feature specs)

> Written 2026-07-15 from the owner's own account of the product's origin + intent, so every future design
> decision derives from a coherent identity instead of accreting features we like. [[ideas/product_vision]]
> is the LOCKED VA front-end spec (the four lenses, the screens); THIS page is the layer above it — what the
> whole thing IS and where it's going — and everything, including the war room and the strategic tools,
> gets derived from here. Owner rule (2026-07-15): a new direction NEVER means leaving in-flight work
> unhardened — see [[workflow/hardening_is_non_negotiable]].

## The one line
**A multi-state legislative operating system for an advocacy organization that lobbies for its own agenda —
a "brain in HQ + operators on the ground" command center, built on a completely-owned, health-verified copy
of each state's legislative data.**

## Where it came from (the owner's arc — this is the "why", and it explains what's load-bearing)
1. **The problem:** on Virginia's LIS you must babysit a browser tab to know what's happening to your bills;
   the standard alternative (Lobbyist-in-a-Box) paywalls you at ~4 bills before a full enterprise
   subscription. So the owner set out to build a **free alternative for his organization**.
2. **The realization about DATA:** the only way to *guarantee* the data you need is always clean is to
   **collect all of it from the jump.** → This is why bank-grade completeness/accuracy is not a feature, it
   is the foundation. You cannot *replace* LIS unless your copy is provably as complete as LIS.
3. **The realization about REPLACEMENT:** once you hold it all, there's no reason to switch back to LIS — so
   the product becomes *your* LIS (a single pane), not a supplement to it.
4. **The realization about CONTROL:** you're no longer a consumer of LIS's generic shape — you're **in the
   driver's seat**, free to tune the product for how your org actually works, not the incumbent's mold.
5. **The realization about SCALE + HEALTH:** with chapters across states, you imagine seeing everything you
   need at once across states — and you quickly realize the **health of the data is as important to see as
   the data itself** (if you're trusting one pane instead of N state sites, you must be able to *see* that
   the pane is faithful). This is why the Health/trust layer sits under everything.
6. **The realization about AMBITION:** the endgame is the **ultimate multi-state lobbying machine** — the
   owner is the *brain in HQ* (big ideas, big bills, strategy in hard situations); operators are on the
   ground in each state. The product must therefore also **compress expensive strategic thinking into stable
   tools** and **keep HQ + the field organized, aware, and active together.**

## The three pillars (everything the product does is one of these, over the owned dataset)
1. **Complete, health-verified, single-pane visibility** — the always-clean LIS replacement. Every state's
   full legislative data, owned from the jump, with its *trustworthiness visible alongside it* (Today,
   Calendar, Search, the bill card, and Health as the trust spine under them all). This is
   [[ideas/product_vision]]'s "one dataset, four lenses."
2. **Strategic decision tools** — instruments that compress the hard, time-consuming analysis a good
   lobbyist does, so a smart operator makes the call faster. The canonical job (owner's own best example):
   *"I need this bill passed → who sits on this committee → how do they normally vote → who do I need to
   convince?"* Rosters, vote histories, committee math, whip counts, patron/influence pathfinding.
3. **Team coordination** — HQ + field operators staying organized, aware, and active together on the bills
   they track and the bills they introduced (the "war room": shared watchlist, org positions, the whip
   board, assignments).

Pillar 1 exists today (VA). Pillars 2 & 3 are the leverage — and the commercial moat — and they are where
the org-response half of the product lives. The "war room" is not a bolt-on; it IS pillars 2+3.

## The hard rule for pillars 2 & 3 — augment, never decide (owner, reaffirmed 2026-07-15)
The tools **surface the structured facts and stop at the judgment line.** A whip tool shows the 15 members,
each one's vote record on similar bills, and the current count — and the *human* decides who to convince. It
**never** says "call Senator X," because no data can accurately splice all the relevant human factors to make
that call, and faking it would both mislead and insult the operator's expertise. Trust their brains; give
them stable, structural tools (never data dumbed into prose — the same doctrine that governs the lobbyist
data path, [[failures/gemini_review_patterns]] / Standard #3).

## The topology — per-state sites + one exec master site (long-standing, see [[ideas/multi_state_data_strategy]])
- **Each state is its OWN individual site.** A state's team needs (and has) access only to that state's data
  — no cross-state access. This is why the Sheets are organized `<Jurisdiction> · <Role>` (VA·Live/Ops/Archive,
  NY·Live…).
- **One master site sits ABOVE them, gated to the owner + a few execs** — the HQ cockpit: everything at once
  across states, macro trend tracking, portfolio + health rollup. It is the eventual enterprise SKU and the
  brain's-eye view.
- **Sequencing (owner-locked, do not deviate):** **VA is the gold standard — finish it ENTIRELY first, then
  DUPLICATE + fine-tune per state.** Do NOT touch other states or build the master site until VA is done —
  the master site only makes sense once there are several states to pull from, and duping a finished template
  is the efficient path. The master dashboard is [[ideas/product_vision]] §9 "not now."

## What this means for the work right now
"Finishing VA to the gold standard" now explicitly includes **pillar 2 strategic tools** (VA is the template
that gets duped, so its strategic tooling is in scope), built on data we've confirmed is available on our
existing key (member rosters, member vote records, committee memberships, contact-with-district — see
`tools/parity/consumed_endpoints.json` probe findings). This is NEXT-direction, executed to standard, and
NOT at the expense of hardening pillar-1 work already in flight.

See also [[ideas/product_vision]] (the locked VA spec), [[ideas/lobbyist_jtbd_ideation]] (the expansive
feature space + the volunteer-org persona), [[ideas/multi_state_data_strategy]] (the topology),
[[ideas/war_room_scoping]] (pillars 2+3 build decisions), [[architecture/strategic_tools_placement]].
