---
tags: [ideas, product, war-room, drafting, owner-idea]
updated: 2026-11-16
status: stub
open_loop: Owner idea 2026-11-16, scoped only — needs the owner's answers to the open questions below, then a grey-by-default mockup before any build.
---

# The drafting War Room — before a bill has a number (owner idea, 2026-11-16)

**Owner, in their words:** the War Room is designed for a bill already introduced; it would also be nice to have an
assistive War Room for designing and writing a bill and choosing who should carry it. Not all drafts get introduced,
so organise versions for different legislators — one bill, many legislators — then House and Senate versions, similar
versions and duplicates. "Just a start of an idea of what it would have to cover."

Sister page: [[ideas/legislator_portfolio]] (who should carry it is a portfolio question). Prior art in the vault:
[[ideas/war_room_scoping]] (the introduced-bill War Room), [[ideas/predictive_lane]] (the tier rule for any
prediction shown), [[architecture/text_similarity]] (the comparer).

## What it has to hold — the objects, from idea to introduced bill

| object | what it is | where it comes from |
|---|---|---|
| **Policy idea** | the thing the team wants, in plain words | the team (typed) |
| **Draft** | a text of that idea | the team (uploaded / typed), versioned |
| **Carrier version** | the draft as offered to ONE legislator (their edits, their name) | the team; one idea → many |
| **Chamber twin** | the House and Senate versions of the same draft (companion bills) | the team, then LIS once introduced |
| **Similar bill** | a past or current bill with near-identical text (this state, or another) | the comparer (structural text similarity), never a guess shown as fact |
| **Introduced bill** | the draft once it has an HB/SB number — hands off to today's War Room | LIS |

An idea that is never introduced stays in the drafting room with its history; an introduced one links both ways
(the War Room bill page shows "drafted here, offered to N legislators, carried by X").

## The jobs it answers (lobbyist's words)

1. **Who should carry this?** Ranked, with the reasons shown (portfolio facts, not a black-box score).
2. **House or Senate first — or both?** Which committee each chamber would send it to, and that committee's record on
   bills like it.
3. **Has this been tried?** Similar bills, how far they got, who carried them, why they stopped.
4. **Which version is where?** Every version, who has it, its status (offered / declined / agreed / filed).

## What the data can already support (sourced; claim class in brackets)

- **Similar text** [measured]: the comparer is calibrated on real Virginia bills (+0.846 separation, W3 in
  [[state/current_status]]); companion detection + drift exists (W4). Cross-state corpus is blocked on Open States'
  bulk download needing a login ([[architecture/text_similarity]]).
- **Room memory** [measured, VA]: committees remember ideas — odds ratio 15.2 for the same room vs 5.5 elsewhere
  ([[testing/room_memory]]); not yet owner-approved for display (Standard #3 call on exact-title equality).
- **Carrier signal** [measured, VA]: the committee chair co-sponsoring the bill — 92% advance vs 70%, same patron
  ([[testing/influence_and_sources]]); replicated on 2026.
- **Not available from any public source:** drafts that were never filed. They exist only because the team enters
  them — so the drafting room is a team-private store (the Worker + D1 path the contact log already uses), never the
  public Sheets layer.

## Open questions for the owner (answer before a mockup)

1. Who may see a draft — the whole team, or only its author until shared? (Drafts are the most sensitive thing the
   product would ever hold.)
2. Do drafts carry full text in the product, or a link to the team's own document?
3. Is "who should carry it" a ranked list with reasons, or a shortlist the team builds with the facts beside it?
   (A ranked list is a Tier-3 prediction under [[ideas/predictive_lane]] and needs the calibration gate first.)
4. One state at a time, or an idea that spans states (the same policy drafted for VA and PA)?
