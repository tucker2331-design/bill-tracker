---
tags: [design, ui, information-display, reference, web]
updated: 2026-06-23
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
| **Tufte — *The Visual Display of Quantitative Information*, 2nd ed.** (owner's #1) | ✅ **deep-read 2026-06-23** ([[design/reading_notes]]) | data-ink, chartjunk, the lie factor, **small multiples** (calendar grid = small multiples), data density / shrink, graphical integrity |
| **Tufte — *Envisioning Information*** | ✅ deep-read 2026-06-23 | layering & separation, **micro/macro readings** (overview+detail in one geometry), the "smallest effective difference", 1+1=3 clutter |
| **Few — *Show Me the Numbers* / *Information Dashboard Design*** | ✅ read in full 2026-06-22 | tables vs graphs, "remove non-data pixels, enhance data pixels", at-a-glance, color for attention, bullet graph |
| **Munzner — *Visualization Analysis & Design* (Ch5 Marks & Channels)** | ✅ **deep-read 2026-06-23** ([[design/reading_notes]]) | **encoding-channel effectiveness ranking** (position > length > area > color); expressiveness/effectiveness; separable channels; popout — justifies the timeline + calendar encodings |
| **Hearst — *Search User Interfaces* (Ch1 + Ch8 Flamenco)** | ✅ **deep-read 2026-06-23** ([[design/reading_notes]]) | 7 SUI guidelines; faceted nav: integrate browse+search, fluid refine/expand, **avoid empty result sets**, **facet counts as scent**, per-facet removable chips, recognition>recall |
| Gestalt / typography / WCAG | ✅ baseline | proximity, alignment, hierarchy, tabular figures, never color-alone, contrast, focus |
| **Prater (OOUX/ORCA) · Salesforce record page · NN/G tabs · Jira issue view · provenance-in-UI** | ✅ **deep-read 2026-07-17** ([[design/object_page_patterns]]) | the **central-object page** — objects-not-features, compact layout (card↔page one source), next-steps vs past-activity, when tabs fail, control-vs-content (the sidebar question), **§5b/P20 the provenance partition** |
| **Norman — affordances vs *signifiers*** ([jnd.org](https://jnd.org/signifiers-not-affordances/)) | ✅ **read 2026-07-17** | **§5c/P21** — discoverability comes from signifiers, not affordances; names the scroll-cue failure we already shipped a fix for |
| **Wroblewski — web form design** ([label placement](https://www.lukew.com/ff/entry.asp?504) · [layout](https://www.lukew.com/ff/entry.asp?1502)) | ✅ **read 2026-07-17** | **§5c/P22** — the product's FIRST input surface (the war room); label placement, primary-vs-secondary action weight, no decoration |

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

## 5b. Provenance — the two-truths rule (the product's own constraint)

Unlike every CRM/issue-tracker this product resembles, we carry **two classes of truth**: **LIS-verified fact**
and **org-entered intel**. Blending them is forbidden ([[ideas/lobbyist_jtbd_ideation]] §8b V4). The
provenance-in-UI literature does not solve this (it studies *analytic* provenance, not *source* provenance —
see [[design/object_page_patterns]] §5), so the rule is derived from the canon above:

- **P20 · Partition provenance by POSITION, never by color or opacity; label both regions.** Source is an
  encodable attribute, so choose its channel deliberately (Munzner). **Opacity is wrong** — it reads
  "provisional/low-confidence", which is false about the org's own highest-value intel and inverts the
  emphasis (P10). **Color is wrong** — P10 reserves saturation for attention/exception states, and the org
  layer is a permanent half of the page, not an exception; spending the attention channel on an always-on
  distinction burns it. **Position is right** — Munzner's top-ranked channel, the canon's preferred grouping
  device (P17: proximity/whitespace, not lines), always-on without shouting, and it leaves color free. Add a
  **text label** per region (P19 — never encode by one cue alone).
  → **THIS PRODUCT:** the classes **never share a region**; in the War Room this draws the Access/write boundary
  at the same line ([[design/object_page_patterns]] §5–6). **The partition is spatial at whatever level the data
  mixes** — page *regions* for a homogeneous zone, *column groups* (a vertical rule + per-group headers) where a
  single row must carry both, as in a committee roster. A **cell** never blends them.
- **P20b · Amber marks "we could be WRONG in a way you can't check" — not "we computed it."** (Refined 2026-07-17
  after the War Room v2 review.) If every computed value gets the provisional chip, amber becomes noise and stops
  meaning anything (the rainbow failure, one hue at a time). **Arithmetic is exact** — `5 of 15`, a party ×
  position cross-tab, a days-remaining count — and takes **no marker**; its honesty rides on its inputs, which are
  already labeled by zone. **Deterministic procedure** ("still to clear: full committee → 3 floor readings") is
  likewise unmarked. **Amber is for the probabilistic**: text-similarity matches, model predictions — claims whose
  error the reader cannot audit from the screen.
- **P20c · Trace every claim to a source, mechanically — writing the rule down does NOT install it.** Proven the
  hard way (see [[log]] 2026-07-17): two messages after documenting that *"a column headed 'similar bills' smuggles
  a derived claim into a sourced group"*, the same session shipped *"every Republican who has voted on **this
  issue** voted no"* into a mockup as if it were fact. *"This issue"* has **no endpoint** — it's a judgment. The
  check that works is the audit, not the intention: **for each claim on a surface, name the endpoint or delete the
  claim.** Corollary (Standard #7): if the source is *"a model"*, there must be a measurement plan before it is
  ever drawn — a column on a mockup is a promise.
- **P20a · There are THREE classes, not two** (found by drawing — [[design/object_page_patterns]] §5b):
  **sourced** (an official system recorded it — VA LIS *or another state's*) → plain text, source named;
  **derived** (*our software's claim about* facts — "94% same text as TX HB2060") → **the existing
  `.chip.provisional` amber**, which already means "we inferred this" for meeting times; **asserted** (the org's
  belief) → the OURS zone. Collapsing *derived* into *sourced* lets **a computed guess wear a recorded vote's
  clothes** — the exact failure the trust layer exists to prevent (Standard #3). Beware a column headed
  "similar bills": the *similarity* is derived even when the *votes* are sourced.

## 5d. Composite scores — never a lone number (the decomposition law)

**P23 · A computed score is shown WITH its faithful decomposition — signed component contributions, each with the
evidence behind it — never as a bare number.** (Owner 2026-07-17, on the predictive lane: *"we shouldn't only
give a number… one component could be particularly relevant — the committee pass rate is high, counter-weighting
that the members lean no, so it lands in the middle; that's important context."*) A single number hides the
*fight between its parts* — exactly the context a user needs. This forces a modeling constraint, not just a
layout: the model must be **interpretable by construction** (a **glass-box additive model / GAM / EBM**), because
a post-hoc "explanation" of a black box can be **unfaithful** (Rudin 2019), and for a trust-moat product an
explanation that might be wrong is worse than none.
→ **THIS PRODUCT:** every Tier-3 prediction ([[ideas/predictive_lane]]) renders as its **breakdown by default** —
each factor's contribution, its sign (what's pushing up vs down), and the base-rate + n or exact math under it.
The composite is the **DERIVED** class (amber, §P20a); its components decompose back into SOURCED facts,
DETERMINISTIC math, and ORG reads — so the breakdown **re-separates the three trust classes**. Same instinct as
Tufte's graphical integrity (show the whole, show the parts) and P6 (never a number without its context).

## 5e. The client-facing alarm law (owner criticism, 2026-07-25 — after the false red Accuracy ring)

**P24 · On a client-facing trust surface, RED means "our published output is verifiably wrong" — nothing else —
and every alarm self-diagnoses in structured fields, not prose.** Born from a real failure: LIS batch-updated
its carryover flags without its status strings; our published value stayed CORRECT, but an internal consistency
check tripped a red Accuracy ring, and the owner-as-client couldn't tell "everything is broken" from "a
pedantic internal disagreement." The Health tab is **client-facing for executives** (owner decision), so:
- A check disagreement that does **not** impeach the published value is a quieter class — never red-accuracy.
- Every alarm row carries: **what disagrees with what** (published value vs which check) · **scope with its
  denominator** (443 of 3,633) · **"published output matches LIS: YES/NO"** — the one field a client actually
  needs. No jargon, no AI-generated prose (owner: "don't translate data issues to English, but I don't want an
  AI to have to diagnose it every time").
- **A false red is an INCIDENT** on our own days-clean ledger (`false_alarm` class,
  [[architecture/incident_counter]]) — the alarm system is product, held to the data's standard.
- Structural corollary: display bands derive from the **same verified verdicts** that write the ledger — a
  frontend judgment that can go red while every guard passes is a second, unaudited alarm system.

## 5c. Interaction & input — the canon for the product's first WRITE surface

Everything above governs *display*. The war room is the first thing in this product a human **types into**
([[ideas/war_room_scoping]]), and we had no rules for it. These two close that gap.

- **P21 · Affordance ≠ signifier. Discoverability comes from the SIGNIFIER.** Norman coined "signifier"
  precisely because designers kept building real affordances nobody could see: *"affordances define what
  actions are possible; signifiers specify how people discover those possibilities… signifiers are of far more
  importance to designers than are affordances."* The design question is never "can this be done?" but **"is
  there a perceptible signal that the right user will discover it?"**
  → **THIS PRODUCT — we have already paid for this lesson.** The scrollable panels on the landing page were
  genuinely scrollable (the affordance existed) and the owner reported *"i dont see any indication that there
  is more info scrollable"* — an affordance with **no signifier**. The CSS-only shadow failed for the same
  reason; the visible fade + chevron (#216) is the signifier. **Rule: every interactive region must carry a
  perceptible signal, and "it works if you try it" is not a design.** Applies next to the war room's
  editable cells — an org position that only reveals itself as editable on hover is the same bug.
- **P22 · Form design: top-align labels; weight the primary action; never decorate an input.** Wroblewski, on
  eye-tracking (Penzo): **top-aligned labels are fastest** — they "only require a single eye fixation to take
  in both input label & field"; **left-aligned are slowest** by fixation count, but are the right choice
  "when you want users to carefully consider each input" or scan unfamiliar/optional fields; right-aligned
  save vertical space at the cost of a ragged left edge. **Primary actions** (save/submit) get stronger visual
  weight (colour/bold/fill) and align with the inputs; **secondary actions are de-emphasised** to prevent
  mis-clicks. And his echo of P1/P2: *"information consists of differences that make a difference"* —
  backgrounds and rules around inputs impair scanning.
  → **THIS PRODUCT:** the war room's note/position inputs use **top-aligned labels**; the whip board — where a
  volunteer should *deliberately* consider each member — is the documented exception where **left-aligned**
  earns its cost. One primary action per surface, everything else quiet. No boxes-around-boxes (P7).

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
| **PL-8** | **Health metrics as bullet graphs / gauges with threshold bands** (owner 2026-06-23: "like the red zone on a car's RPMs") — each metric as a measure against good/warning/**danger** bands + a target marker, so a red-zone reading is instant; repeat as small multiples. This is **Few's bullet graph** (his invention for exactly this). Calibrate danger thresholds from the steady-state + existing alert floors (e.g. keyword-mismatch ~0.03% safe / >1% red; freshness green→amber→red by age). | Health | P4 (small multiples), P10 (color=attention), Few bullet graph |
| **PL-9** | **Calendar tab = month grid (small multiples of days) + day/agenda column, one geometry** (micro/macro). Time encoded by **vertical position** (Munzner #1 magnitude channel — never color/size); hairline grid (data-ink); **today + the crossover deadline are the only loud cells** (Few attention / Munzner single-channel popout); weekends/out-of-month = quietest tint (smallest effective difference). Meeting chip = committee+chamber by spatial group + quiet hue + text label (never color-alone). "Time TBA"/derived times honestly marked (trust layer). Designed empty state off-season. Full build rules in [[design/reading_notes#Synthesis — Calendar UI patterns]]. | Calendar | P4, P9 micro/macro, P10, Munzner channels, Few palette |

---

## 7. Meta-rule for the front end (the one-liner)
**Spend ink and color only on data and on what the lobbyist must notice; encode with position, weight,
and whitespace before lines and boxes; show the overview and the detail in one honest geometry; and never
let a number, a facet, or a fact appear without its context.** Everything above is a corollary.

See also [[ideas/product_vision]] (the screens this serves), [[index]], [[log]].
