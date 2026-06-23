---
tags: [design, ui, redesign, web, owner-feedback]
updated: 2026-06-22
status: active
---

# UI Redesign Spec — owner feedback (2026-06-22)

Direct feedback on the v1 front end ([[design/information_display]] is the principle layer; this is the
concrete change list). Owner's framing: **read full-length design books first, then redesign.** The
overarching verdict: **"the whole thing is stale and screams AI — simple UI, fix that."** So this is not
just feature work — it's a *visual-craft* upgrade (see the Refactoring-UI notes in [[design/information_display]]).

## Landing (Today) — relayout
1. **Rename "Next up"** — confusing. It becomes a **calendar sliver**: *today's* calendar as a **vertical
   column like a paper weekly planner** — the **day name (Monday/Tuesday…) + the numerical date** at the
   top of the column, then the day's events down it. The widget **holds a fixed full-length form** and
   **scrolls internally** if it overflows (don't let it stretch the page).
2. **Stack order on the landing:** **what's-new + the calendar sliver up top, the TIMELINE below them.**
   (Currently the timeline is its own tab only; it should also live on the landing, beneath.)

## Timeline — redesign
3. **Far smoother, less boxy, more integrated** — the current hard-bordered column grid reads as generic.
   Move to a flowing pipeline (a continuous spine/track with nodes), not separate boxes. (Tufte data-ink:
   the counts/flow are the data; the box chrome is noise — see [[design/information_display]] PL-1.)
4. **Crossover divider is taking RIDICULOUS space** — shrink it to a thin marked line/seam on the spine,
   not a full hatched column. It's a *seam*, not a stage.
5. **OPEN QUESTION (owner asked): add a Floor stage after Committee?** → **Recommendation: YES, a thin
   Floor node between Committee and the crossover seam (and again before Governor)** — it's how the
   process actually works (reported from committee → floor vote → cross), and we can populate it
   STRUCTURALLY (BILLS.CSV `Passed_house`/`Passed_senate` + the floor-vote signals), so it's honest, not a
   guess. Keep it a *small* node so it doesn't add confusion or width — the smoother spine has room once
   crossover shrinks (item 4). Label clearly; don't meld with committee.

## Search — bugs (not just polish)
6. **Text runs off the bill boxes** — catchlines overflow. Fix with truncation/ellipsis + wrap rules
   (CSS), and make the box height accommodate 2 lines of catchline. (PL: density without overflow.)
7. **The House/Senate filter buttons don't reliably toggle** — a real state bug in the facet chips. Fix
   the toggle logic so chamber (and every facet) filters correctly + shows active state. (Pairs with
   [[design/information_display]] PL-2: facet counts + disable zero-count facets.)

## Global
8. **"Screams AI / stale / simple"** → a genuine visual identity pass: a real type scale + pairing,
   a considered color system (not default blues), intentional spacing scale, depth/hierarchy, restraint.
   This is the Refactoring-UI work — start from *hierarchy, spacing, and color*, not decoration.

## Sequencing (owner)
- **"First, knock off the first 2 items in your list of 4."** *Interpretation (confirm):* the 4 = the
  four lenses/views; **first 2 = Today (landing) + Timeline** — which is exactly what items 1–5 above
  detail. So: read the books → redesign Today + Timeline first → then Search fixes + the global pass +
  the other lenses. **If "list of 4" meant something else, the owner will redirect.**
- Reading is PREP: digest full-length books (Tufte VDQI, Few, Hearst, **Refactoring UI** for the
  not-look-generic problem, calendar-UI patterns), notes → [[design/information_display]].

See also [[design/information_display]], [[ideas/product_vision]], [[log]].
