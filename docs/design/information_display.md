---
tags: [design, ui, information-display, reference, web]
updated: 2026-06-22
status: active
---

# Information Display & UI — design reference (living)

The design north-star for the front end (`web/`), grounded in the information-display canon. **Every
principle below is written as an ACTIONABLE RULE mapped to a specific screen** — this page is meant to
change the product, not just describe theory. It grows as more sources are read (owner queued ongoing
reading — see [[log]]). When a principle changes a screen, it goes on the **punch-list** (§5).

The product's job (from [[ideas/product_vision]]): a lobbyist must *see a lot at once, trust it, and
drill in*. That is precisely the problem the canon below solves — dense, honest, glanceable quantitative
display. The vision's instincts (counts-first, position=progress, one reused component, the trust layer)
are already textbook; this page sharpens them and catches where the current build violates them.

---

## 1. The canon (reading log)
| Source | Status | What it governs here |
|---|---|---|
| **Tufte — *The Visual Display of Quantitative Information*, 2nd ed.** (owner's #1) | ✅ synthesized 2026-06-22 | data-ink, chartjunk, the lie factor, small multiples, data density, graphical integrity |
| **Tufte — *Envisioning Information*** | ✅ synthesized | layering & separation, micro/macro readings, the "smallest effective difference", 1+1=3 clutter |
| **Few — *Show Me the Numbers* / *Information Dashboard Design*** | ✅ synthesized | tables vs graphs, "remove non-data pixels, enhance data pixels", at-a-glance, color for attention |
| **Hearst — *Search User Interfaces* (Flamenco)** | ✅ synthesized | faceted navigation: integrate browse+search, fluid refine/expand, **avoid empty result sets**, show facet counts |
| Gestalt / typography / WCAG | ✅ baseline | proximity, alignment, hierarchy, tabular figures, never color-alone, contrast, focus |
| *(next)* Norman — *Design of Everyday Things*; Wroblewski — forms/mobile; Munzner — *Visualization Analysis & Design* | ⏳ queued | affordances, input design, encoding-channel theory |

---

## 2. Tufte — the quantitative core

**P1 · "Above all else, show the data." Maximize the data-ink ratio.** Data-ink = the non-erasable,
non-redundant ink that encodes the numbers. Erase everything else; erase redundant data-ink.
→ **THIS PRODUCT:** the **lane counts ARE the data** — they must dominate; column borders, panel
chrome, and background fills are non-data-ink and must recede (hairline, low-contrast). The **history
table** needs no gridlines — alignment + whitespace separate rows (Few's "remove non-data pixels").
*Current violation:* the timeline columns have dashed borders + a panel background competing with the
numbers → lighten them (punch-list PL-1).

**P2 · No chartjunk.** No decoration that tells the viewer nothing new — no gradients-for-looks, no
shadows, no 3-D, no moiré. Decoration is allowed ONLY when it encodes data.
→ **THIS PRODUCT:** the crossover **hatch is legitimate** — it encodes "deadline/danger" (functional,
not decorative). Drop any purely cosmetic gradients/shadows on bill boxes and chips. Keep surfaces flat.

**P3 · The lie factor = (size of effect shown) ÷ (size of effect in data); aim for 1.0.** Visual
magnitude must be proportional to data magnitude.
→ **THIS PRODUCT:** if a count is ever rendered as a **bar/area** (e.g. a future per-committee load bar),
the length must be strictly proportional — never a min-height floor that inflates small values. The lane
stages must be **equally spaced** (or spaced by real progress) so "position = progress" doesn't lie. Today
the counts are plain numbers (lie-factor-safe); preserve that honesty if we add visual encodings.

**P4 · Small multiples.** Repeat the same small graphic, same scale/structure, varying one variable — the
eye compares effortlessly.
→ **THIS PRODUCT:** the **§3b committee board IS a small-multiples grid** — every committee column is the
identical structure (sub-headers → bill boxes), so the lobbyist compares committees at a glance. Build it
that way: same column template, same box, same vertical scale; the only variable is *which* bills. The
per-side stage counts are already a small multiple (same cell, varied stage).

**P5 · Maximize data density; trust the reader.** Dense, well-organized displays respect the user — show
many numbers in a small space rather than one-fact-per-screen.
→ **THIS PRODUCT:** lobbyists WANT density (the vision's "see a lot at once"). Default to compact bill
boxes; don't pad. The Today feed should show the whole day, the Search grid many boxes. Resist the urge to
"breathe" by hiding data — breathe with whitespace *between* groups, not by showing less.

**P6 · Graphical integrity / context.** Numbers shown without comparison mislead. Show the whole, show the
baseline.
→ **THIS PRODUCT:** counts always carry their **denominator** (the trust header's "N of N", the outcome
distribution as a set, the `_rate` metrics). Never a bare "12 dead" without "of 3,645".

## 3. Tufte (Envisioning Information) — layering, separation, micro/macro

**P7 · Layering & separation; "1 + 1 = 3".** Every added element also adds the *relationships between*
elements — clutter grows faster than content. Layer by visual *value/weight*, not by adding boxes/lines.
→ **THIS PRODUCT:** the **bill card** has three layers — primary (bill# + catchline + star), secondary
(the meta strip: where/vote/next), tertiary (history). Encode the hierarchy with **type weight/size and
whitespace**, NOT with nested boxes/borders. Fewer rules, more contrast of value.

**P8 · The smallest effective difference.** Make distinctions as subtle as they can be while still doing
the job — loud contrasts fight each other.
→ **THIS PRODUCT:** Senate/House already differ by **position** (above/below the line), so the blue/red
can be *quiet* (it's a redundant cue, not the only one). Outcome chips: distinguish by a soft tint +
label, not six saturated colors. Reserve saturation for P10.

**P9 · Micro/macro readings.** The best displays read at both the overview AND the detail level in one
geometry.
→ **THIS PRODUCT:** the **timeline already does this** (macro counts → drill to bill boxes). Keep the two
zoom levels in ONE geometry; never a separate "dashboard vs detail" page (the vision's locked decision).

## 4. Few + Hearst — dashboards & search

**P10 · "Remove the non-data pixels; enhance the data pixels." Reserve saturated color for attention.**
Color is a precious signal — spend it on what must be noticed, not on decoration.
→ **THIS PRODUCT:** **red is reserved** for stale-data, vetoed/dead, and the crossover deadline — the
"look here" states. Everything else stays neutral/quiet. The "data as of X ago" header goes red only when
genuinely stale (hard in-session). *Audit the CSS so red never appears decoratively.*

**P11 · Tables for look-up, graphs for patterns.** Match the medium to the job.
→ **THIS PRODUCT:** **history = a table** (exact Action | Date — the vision's two-column ask; right-align
dates). **Timeline = a graph** (the pipeline pattern). **Search results = scannable boxes** (look-up).
Don't graph what should be a table, or tabulate what should be a picture.

**P12 · At-a-glance, single screen, position carries importance.** The critical view fits without
scrolling; top-left / top = most important; size encodes priority.
→ **THIS PRODUCT:** the **Landing priority stack** (what's-new top = the anxiety-killer, timeline hero,
next-up strip) is exactly this. Keep the most-feared info (new actions, stale warnings) top-most.

**P13 · Faceted navigation (Flamenco design goals).** Integrate browse with keyword search; allow fluid
refine ↔ expand; **show a count next to every facet value**; and **avoid empty result sets** (never let a
filter combination silently return nothing).
→ **THIS PRODUCT — Search:** the stacking filter chips are faceted nav. **Add per-facet counts** (e.g.
"House (1,842)", "Vetoed (31)") so the user sees the shape before clicking — and so a zero-count facet is
visibly disabled (prevents the empty-result dead-end). Keep the search bar + facets unified (no mode
switch), default sort by bill# (known-item), offer "most recent action"/"by stage" (browse). User must
always feel in control (show active filters as removable chips).

**P14 · Arrangement is information.** Sort order encodes meaning.
→ **THIS PRODUCT:** money committees **last** on the board axis (the vision's rule — fiscal re-referral is
downstream); bill# default sort; the history newest-first; the feed newest-day-first. Order is never
arbitrary.

## 5. Typography, Gestalt, accessibility (the baseline that makes the above legible)

- **P15 · Typographic hierarchy, few sizes.** 2–3 type sizes per view; weight + size set reading order.
  → bill# bold/mono, catchline regular, meta small/muted. **Tabular figures for all numbers** (counts,
  tallies, dates) so columns align (already `font-variant-numeric: tabular-nums` — keep enforcing it).
- **P16 · Alignment & the grid.** Left-align text, **right-align numbers/dates**; consistent gutters.
  → the history table's Date column right-aligns; lane counts center on their stage; the Search grid is a
  consistent column grid.
- **P17 · Proximity & whitespace (Gestalt).** Group by nearness, separate by space — not by lines (P1).
  → the card's meta facts group tightly; history sits apart by whitespace, not a divider rule.
- **P18 · Progressive disclosure.** Summary first, detail on demand.
  → bill box → expands to card; timeline counts → drill to boxes; card summary → "more" for long text.
  Never front-load everything.
- **P19 · Never encode by color alone (WCAG 1.4.1); meet contrast (1.4.3); visible focus (2.4.7).**
  → chamber = position + color + (on the card) a label; outcome = tint + **text label**; the
  `:focus-visible` ring shipped in the foundation — keep it on every interactive element. Verify
  blue(Senate)/red(House) are distinguishable under deuteranopia (position saves us, but check contrast).

---

## 6. Punch-list — concrete `web/` changes this reference justifies
Prioritized; each cites the principle. Fold into the next front-end polish PR.

| # | Change | Screen | Why (principle) |
|---|---|---|---|
| **PL-1** | Lighten lane column borders + panel fill so the **counts dominate**; remove any box shadow/gradient on bill boxes/chips | Timeline, boxes | P1 data-ink, P2 chartjunk |
| **PL-2** | **Add per-facet counts** to the Search filter chips; **disable zero-count facets** (no empty-result dead-ends); show active filters as removable chips | Search | P13 Flamenco |
| **PL-3** | Bill card: re-layer by **type weight + whitespace**, not nested boxes; right-align history dates; tabular figures on tallies | Bill card | P7, P11, P15, P16 |
| **PL-4** | **Audit red usage** — restrict saturated red to stale/vetoed/dead/deadline; quiet the Senate/House hues (position already encodes side) | global | P8, P10, P19 |
| **PL-5** | Build the **§3b committee board as small multiples** (identical column template, money-committees last, sub-headers, mirrored across the centerline) | Timeline detail | P4, P14 |
| **PL-6** | Ensure all numbers use tabular figures; verify chamber/outcome are not color-only (add labels) + check colorblind contrast | global | P15, P19 |
| **PL-7** | Outcome distribution + completeness always shown **with denominator** ("N of N") | Today, Health | P6 |

---

## 7. Meta-rule for the front end (the one-liner)
**Spend ink and color only on data and on what the lobbyist must notice; encode with position, weight,
and whitespace before lines and boxes; show the overview and the detail in one honest geometry; and never
let a number, a facet, or a fact appear without its context.** Everything above is a corollary.

See also [[ideas/product_vision]] (the screens this serves), [[index]], [[log]].
