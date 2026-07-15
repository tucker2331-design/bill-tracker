---
tags: [architecture, design, strategy, information-display, decision]
updated: 2026-07-15
status: active
---

# Where the strategic tools live — NOT on the bill card (research-grounded)

Owner question (2026-07-15): the pillar-2 strategic tools (committee roster + each member's vote history +
the live count — the *"who decides this, how do they vote, who do I flip"* instrument) — do they belong on
the bill card, or somewhere else? Owner's instinct: the card is *already crowded*. He asked what the design
research says, not just intuition.

## Answer: the card stays the FACT SHEET; strategy lives on its own surface, entered FROM the card.

### What the research says (this project's canon + the wider literature)
- **The product is built on DRILLING** (this project's own established pattern, [[design/information_display]]
  P9/P18 + [[design/reading_notes]]): count → bills → **card**. The bill card is already the *"details on
  demand"* terminal of that drill. Hanging a second analytical layer on it is detail-on-detail — it breaks
  the very progressive-disclosure spine the product uses everywhere else.
- **Shneiderman's Visual Information-Seeking Mantra** — "overview first, zoom and filter, then details on
  demand." The whip analysis is a *zoom on a specific analytical question* ("how do I move this?"), which is
  a distinct drill target, not more fields on the summary.
- **Few / Tufte — one view answers one question well; 1 + 1 = 3 clutter** ([[design/information_display]]
  P7). The card answers *"what is this bill and where does it stand?"* The whip tool answers *"how do I win
  it?"* — a different job, a different granularity (a roster × vote-history matrix is itself dense). Two jobs
  on one surface makes both worse; the owner feeling "crowded" is this principle firing.
- **Progressive disclosure (Nielsen/NNg) + cognitive load (Hick's law)** — move the complex/advanced work to
  a secondary surface so the primary (did something happen to my bill?) stays instant. More controls on the
  card = a slower primary decision.
- **Focus + context (Munzner)** — the right split: put the *context* on the card (a compact "in Senate Ed &
  Health · 15 members decide" line that is the entry point), put the *focus* (the full roster + vote records
  + count) on the dedicated surface. Context travels with the bill; focus gets the room it needs.

### The shape it implies
- **Bill card:** unchanged as the fact sheet. At most a single compact affordance in the "Where it is" area —
  e.g. *"Path to passage →"* / *"Committee math →"* — showing the deciding body + a member count, linking out.
  (This is the focus+context "context" line; it does NOT add the analysis to the card.)
- **A dedicated strategy surface (pillar 2)** — a per-bill (or per-committee) workspace: the committee
  roster as a small-multiples table, each member's vote record on similar/related bills, party/district, and
  the live support/oppose/unknown count. This is where the war-room whip board and the committee-math tool
  converge — they are the same surface (pillars 2 + 3 meet here). Register/canon design rules apply
  ([[design/dashboard_and_visual_language]]): structural facts, reserved color, augment-not-decide
  ([[ideas/product_identity]] — the tool stops at the judgment line, never "call Senator X").

### Why this also HELPS the holistic architecture
It stops the bill card from becoming the junk drawer every feature gets bolted onto, and it gives pillar 2 a
real home in the product's topology: the fact surfaces (Today/Calendar/Search/card) + the trust surface
(Health) + the **strategy/coordination surface** (whip/committee-math + war room). Three coherent zones, one
dataset — exactly the derive-from-identity structure [[ideas/product_identity]] calls for, instead of a mosh
of card widgets.

**Status:** design decision recorded; BUILD is gated behind (a) VA reaching gold-standard on pillar 1 and
(b) the war-room owner decisions ([[ideas/war_room_scoping]]) since the strategy surface and the war room are
the same surface. Data is confirmed available (rosters / member votes / committee memberships on our key).

See also [[ideas/product_identity]], [[ideas/lobbyist_jtbd_ideation]] §C (the strategic-tool ideas),
[[design/information_display]], [[design/reading_notes]].
