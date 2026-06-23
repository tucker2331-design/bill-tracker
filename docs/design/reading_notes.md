---
tags: [design, reading-notes, ui, information-display]
updated: 2026-06-23
status: active
---

# Design reading notes (per-book deep digests)

Genuine deep-read notes, book by book — the raw material the [[design/information_display]] rules distill
from. Owner directive: digest full-length books, log everything relevant so the brain keeps growing.
Distinguish these (actually read) from synthesis-from-summary (marked as such).

---

## Stephen Few — *Information Dashboard Design* (O'Reilly) — **READ in full (PDF), 2026-06-22**
166 pp. Read closely: Ch4 (visual perception) + Ch7 (design principles). The single most relevant book for
*this* product — it's literally about cramming a dense array of data into one screen, read at a glance, and
it names the exact failure the owner called out ("screams AI / stale"): poor visual design, over-saturated
default colors, and box-chrome clutter.

### The "stale / screams-AI" fix is here, verbatim (Ch4.2.7 + Ch7.3.1) — HIGHEST VALUE
- **Reserve bright, fully-saturated color for the rare cases that must grab attention — used SPARINGLY.**
  Saturated colors "take hold of us and shake us around"; over-bright dashboards are "visually exhausting."
- **Standard palette = colors common in NATURE** — "soft grays, browns, oranges, greens, and blues"
  (earth + sky). They let the viewer "peruse the dashboard calmly," not "stressfully… in response to
  assaulting colors."
- **Background: a barely-discernible PALE color, NOT pure white** — softens the stark foreground/background
  contrast; "more soothing."
- **Text: the MOST LEGIBLE font you can find** — don't use an unusual font to "set a mood" (that's for "a
  poster advertising the circus, not a dashboard"). Fastest to read, least eye-strain.
- → **DIRECT ACTION for `web/`:** replace the default saturated blues with a muted natural palette;
  off-white app background (not `#fff`); saturation ONLY for attention (stale / vetoed / dead / the
  crossover deadline); one clean legible typeface. *This alone kills most of the "AI-generic" feel.*

### Ch7.1.3 — "Delineate groups using the LEAST VISIBLE MEANS"
- Gridlines, borders, background fills are **non-data pixels** → "only as visible as necessary."
- **White space is the least-visible means** — use it to separate groups whenever possible. When density
  forbids whitespace, **subtle/LIGHT borders** ("you'd be surprised how light lines can be and still do the
  job"), never heavy ones.
- → ACTION: the timeline's hard dashed column borders + panel fills are too heavy — group by whitespace; if
  a separator is needed, hairline. (= [[design/information_display]] PL-1.)

### Ch4.3 — Gestalt (perception does the grouping for you)
- **Proximity:** near = same group; **white space alone usually suffices to separate** (no box needed).
  Proximity also steers scan direction — items closer *horizontally* read as L→R rows; closer *vertically*
  read as top→bottom columns. → arrange the landing's reading order with spacing, not rules.
- **Similarity:** shared color/shape/size = same group → tie a bill's related facts with consistent
  encoding; tie the same datum across views with the same color.
- **Enclosure:** a border/fill binds items — but it's a HEAVIER means than proximity (use last, per 7.1.3).

### Ch4.2.6 — Limits to perceptual distinctness
- There's a hard limit to how many distinct values of ONE attribute (e.g. shades of gray, hues) we can tell
  apart at a glance. Pick a small set and **stick to it**. → cap the outcome palette (6 outcomes is near the
  limit — lean on label+tint, not 6 loud hues); keep chamber to its two hues + position.

### Ch7.1.4–7.1.5 — comparisons
- **Support meaningful comparison:** place comparable items together, share a unit, add comparative values
  (%, ratios). → show outcome counts WITH their % of total; lane counts side-by-side are already comparable.
- **Discourage meaningless comparison:** never let one color mean two different things across the screen
  (his example: yellow = "satisfactory" in one place, a category in another). → one meaning per color, always.

### Ch7.4 — interaction
- **Launch to detail by clicking the DATA ITSELF**, not separate buttons; keep launch actions CONSISTENT;
  hover for precise values. → our drill (count→bills, box→card) already follows this; keep it consistent and
  on the data. Saves chrome (no extra buttons).

**Net for the redesign:** muted natural palette + off-white ground + saturation-for-attention + legible type
+ whitespace-over-borders + consistent color meaning + click-the-data. Few basically pre-wrote the fix list.

---

## Wathan & Schoger — *Refactoring UI* — **digested (detailed summary, not the full paid text), 2026-06-22**
THE craft book for "looks amateur/generic → looks designed." Concrete, numeric rules (the antidote to
"screams AI"). Pairs with Few: Few says *what colors/whitespace philosophy*; RUI says *the exact system*.

- **Hierarchy — "emphasize by DE-emphasizing."** Don't enlarge the primary; **mute the secondary/tertiary**.
  Use **font weight + color, not size alone**: normal 400–500, emphasis 600–700; **2–3 text colors** (dark
  primary / grey secondary / lighter-grey tertiary). On colored backgrounds, **hand-pick a same-hue text
  color** — never semi-transparent white (washed out). Minimize labels: "12 left" > "In stock: 12".
- **Spacing — start with TOO MUCH, then remove.** Non-linear scale, ~25% steps:
  **4·8·12·16·24·32·48·64·96·128·192·256**. **Space BETWEEN groups > space WITHIN** a group (kills ambiguity).
  Don't fill the full width just because it's there.
- **Color — build it in HSL.** **8–10 greys**, **5–10 shades** of each primary, semantic accents
  (red/green/yellow). "**Greys don't have to be grey**" — tint cool (blue) or warm (yellow/orange). Bump
  saturation as lightness → 0% or 100% so shades don't wash out; rotate hue toward bright for light tints.
- **Depth — ~5 elevation levels; two-part shadows** (one soft+offset = direct light, one tight+dark =
  ambient); flat-depth via color shift (lighter = closer). Replace borders with **bg-shift / shadow /
  spacing** wherever possible.
- **Typography — hand-picked type scale** (12·14·16·18·20·24·30·36·48·64; px/rem, never em); a family with
  **≥5 weights**; **line length 45–75 chars**; **line-height inversely proportional to size** (small ~1.5,
  headlines ~1.0); baseline-align mixed sizes (don't center); letter-spacing up for ALL-CAPS, tighter for
  bold heads.
- **Dense data / tables — combine label+value** ("3 bedrooms"), de-emphasize the label; **right-align
  numbers**; give tables hierarchy (group related columns) instead of flat equal columns.
- **Finishing polish (cheap, high-impact):** an **accent bar/border** (colored rectangle atop a card, under
  a headline, beside an alert) "requires no talent but significantly elevates polish"; subtle bg texture
  (≤30° hue, low contrast); **design empty states as a feature** (illustration + the CTA, hide irrelevant
  chrome until content exists).
- → **`web/` VISUAL SYSTEM to implement** (the concrete redesign tokens): adopt the spacing scale + type
  scale above; build an HSL palette (tinted greys, off-white ground per Few, muted Senate/House hues,
  saturated red ONLY for stale/dead/deadline); hierarchy via weight+color; replace box borders with
  spacing/shadow; add ONE accent bar (e.g. the chamber color as a thin lane edge); real empty states (the
  off-season "no upcoming" should be a designed empty state, not a grey sentence).

## Tufte — *The Visual Display of Quantitative Information* (2nd ed) + *Envisioning Information* — **DEEP-READ 2026-06-23**
Owner's #1. Earlier we had a synthesis ([[design/information_display]] §2–3); this is the deeper pass the
owner asked for, focused on the parts the **Calendar build** leans on (a calendar grid IS a small-multiples
structure) and on the timeline.

### Small multiples — the single most calendar-relevant idea — HIGHEST VALUE
- Tufte, verbatim: *"At the heart of quantitative reasoning is a single question: **Compared to what?**
  Small multiple designs, multivariate and data bountiful, answer directly by visually enforcing
  comparisons of changes, of the differences among objects, of the scope of alternatives. For a wide range
  of problems in data presentation, **small multiples are the best design solution.**"*
- Definition (the load-bearing constraint): a series of the same graphic **using the same scale and axes**,
  varying ONE variable, placed adjacently so the eye compares effortlessly. *Same everything except the one
  thing that changes.* Once the reader decodes ONE panel they've decoded them all — the design teaches its
  own reading.
- **→ DIRECT ACTION for the Calendar build:** a **month grid is small multiples of days** — every day cell
  is the identical template (date number in the same corner, events stacked the same way, same height
  rhythm), the only variable being *which* meetings fall there. Build it that way: one `DayCell` component,
  one internal layout, repeated 28–31×. Do NOT special-case cells (except today/deadline as the *attention*
  exception). The committee board (§3b) is the other small-multiple (identical column per committee).
- Small multiples are also the honest answer to "many meetings across many days": don't animate or paginate
  what you can show adjacently — adjacency beats memory (compare side-by-side, never across a click).

### Data density + the Shrink Principle
- Maximize the **data matrix** shown within reason; *"most graphs can be shrunk way down without losing
  legibility or information."* Trust the reader with density (matches Few P5 + the vision's "see a lot at once").
- **→ CALENDAR ACTION:** prefer a compact agenda/day column that shows the *whole* day over a sparse grid
  that shows three events and a "+N more". A lobbyist wants the day entire. The month grid is for *navigation
  context* (macro); the day/agenda is for *reading* (micro) — show both, in one geometry (micro/macro, below).

### Micro/macro readings (Envisioning Information)
- The best displays read at BOTH the overview and the detail level **in one geometry** — "the more
  information, the calmer and quieter the display ought to look." A dense field of fine detail, when
  organized, reads calmly at a distance AND rewards a close look.
- **→ CALENDAR ACTION:** the calendar should give a *macro* read (which weeks are busy, where the crossover
  guillotine falls) AND a *micro* read (this Thursday's 9 AM Senate Finance meeting) without switching
  screens — the month strip for shape, the day column for detail, on one page. This is exactly the
  landing-sliver (today window) ↔ Calendar-tab (full) relationship the owner specified.

### Data-ink, smallest effective difference, layering (reinforced, now applied to the calendar)
- **Data-ink:** erase non-data ink; the *events* are the data, the grid lines are not — hairline the grid,
  let whitespace and alignment do the separating (Few's "least visible means" agrees).
- **Smallest effective difference (EI):** make distinctions *as subtle as they can be while still working* —
  loud contrasts fight. → days differ by their date label + content; weekends/today differ by the *quietest*
  cue that reads (a faint tint, not a saturated block). **Reserve the one loud mark for the crossover
  deadline** (the guillotine) — that is the cell that SHOULD shout, per Few's "saturation = attention."
- **Layering & "1+1=3":** every added rule also adds the *gaps between* rules as new visual noise; clutter
  grows faster than content. → don't box every cell AND every event AND every group; pick one separator
  level and let proximity carry the rest.

---

## Tamara Munzner — *Visualization Analysis & Design* (CRC, 2014), Ch5 "Marks & Channels" — **DEEP-READ 2026-06-23**
The rigor the brain was missing: *which* visual channel to spend on *which* attribute, ranked by how
accurately humans decode it. This is the theory that **justifies the timeline's and calendar's encodings**
(and catches where we'd be spending a strong channel on a weak need).

### Marks vs channels
- **Marks** = the geometric primitives (points, lines, areas). **Channels** = the ways to *control their
  appearance* (position, length, angle, area, color, shape, …). A visualization = marks + the channels that
  encode data into them.
- **Two principles, always front of mind:**
  - **Expressiveness:** encode *all of — and only —* the information in the attribute. (Don't imply order
    where there is none: e.g. don't put categorical committees on a position axis as if they were ranked,
    unless the order is real — our money-committees-last axis IS a real order, so it's expressive.)
  - **Effectiveness:** **match the most important attribute to the most effective channel.** Salience of the
    channel should track importance of the attribute.

### The channel rankings (memorize — this is the payoff)
**Magnitude / ordered channels**, MOST → LEAST accurate (use for quantities, time, progress):
1. **Position on a common scale** (aligned)
2. **Position on an unaligned scale**
3. **Length** (1D size)
4. **Tilt / angle**
5. **Area** (2D size)
6. **Depth** (3D position)
7. **Color luminance**
8. **Color saturation**
9. **Curvature**
10. **Volume** (3D size)

**Identity / categorical channels**, MOST → LEAST effective (use for *what kind*, no order):
1. **Spatial region** (grouping by location)
2. **Color hue**
3. **Motion**
4. **Shape**

(Roots: Cleveland & McGill's accuracy experiments + Mackinlay's ranking. Position wins because it's
judged on a common aligned scale; area/color are systematically mis-estimated — area especially is
*underestimated* by a power law, which is why bubble sizes lie.)

### → DIRECT ACTIONS for `web/` (this reorders some of our instincts)
- **The timeline is RIGHT to use position for progress** — stage = horizontal position on a common scale is
  the #1 channel; "position = progress" is not just a slogan, it's the most accurate possible encoding. Keep
  counts as *length/number*, never as area (area is rank #5 and lies).
- **Chamber = spatial region (Senate above / House below the line) is the #1 *identity* channel** — better
  than the blue/red hue (rank #2). So the position split is doing the real work and **the hue can stay quiet**
  (it's a redundant cue) — this independently confirms PL-4 (quiet the chamber hues; position already encodes
  side). Color hue is for *category*, never for *quantity*.
- **Calendar:** time-of-day and date are *ordered/magnitude* → encode with **position** (vertical position in
  a day column = time; horizontal/grid position = date). Do NOT encode meeting time with color or size.
  Committee/chamber on a meeting chip = *identity* → spatial grouping first, then hue. A meeting's *duration*
  (if we ever show it) = length (rank #3), honestly proportional (Tufte lie-factor).
- **Don't over-spend strong channels:** position is precious — reserve it for the data that matters most
  (progress, time), not for decorative layout.

### Separable channels, popout, discriminability
- **Separable vs integral:** position and hue are **separable** — the eye reads them independently, so we can
  safely encode *two* attributes (stage via position + outcome via hue) with no interference. (Size+hue are
  more integral — combining them muddies both.) → our timeline (position=stage, hue=chamber/outcome) is a
  separable, safe pairing.
- **Popout (preattentive):** a single differing item on ONE channel "pops" in <200 ms regardless of
  distractor count — but popout *fails when you combine channels* (a red-AND-circle target among red squares
  and blue circles requires serial search). → for "look here NOW" signals (stale, vetoed, the crossover
  deadline) use **one** strong channel difference (a saturated hue *or* a unique shape, not a subtle combo) so
  it preattentively pops. This is the perceptual mechanism *under* Few's "saturation for attention."
- **Discriminability — limited bins:** each channel affords only a handful of reliably-distinguishable steps
  (e.g. ~6–12 categorical hues max; far fewer if small or adjacent to other colors). → cap the outcome
  palette (we have 6 — at the limit; lean on label+tint, exactly as Few Ch4.2.6 warned).

---

## Marti Hearst — *Search User Interfaces* (Cambridge, 2009, free online) — **DEEP-READ 2026-06-23**
Read Ch1 (Design of SUIs) + Ch8 (Integrating Navigation with Search = faceted nav). The authority behind the
vision's faceted-search decision (§3d) and the Search punch-list (PL-2). Directly actionable for the Search
fixes AND the calendar's filtering.

### Ch1 — the 7 design guidelines for search UIs (apply to Search + every filtered view)
1. **Offer efficient + informative feedback** — show results immediately; highlight query terms in context
   (but *don't over-highlight* or the effect is lost); make results sortable; suggest refinements.
2. **Balance user control with automation** — handle ranking/stemming/spell-fix transparently; never force a
   change the user didn't ask for.
3. **Reduce short-term memory load** — keep the query/context visible in the form; support history;
   **integrate navigation with search via faceted metadata** (recognition over recall).
4. **Provide shortcuts** — deep links, "answer" displays for well-defined needs (e.g. type a bill # → jump
   straight to the card).
5. **Reduce errors** — **avoid empty result sets** via query previews + term expansion; fix vocabulary
   mismatch with careful labels.
6. **Small details matter** — entry-form *width* influences query length; result *ordering* shapes what users
   learn; suggestion prominence is decisive.
7. **Aesthetics matter** — layout, whitespace, typography, coherence correlate with *perceived* usability.
- The throughline: *"search is a means towards some other end, rather than a goal in itself"* and *"a mentally
  intensive task"* → **keep it simple; simplification measurably reduces errors** (their elderly-user study).
  *"The job of the search UI is to aid users in the expression of their information needs, in the formulation
  of their queries, in the understanding of their results, and in keeping track of their progress."*
- **Recognition over recall** (memory psychology): *"it is often easier to recognize a word or name than to
  think it up."* → present browsable facets/options rather than make the lobbyist conjure a committee name.
- **The vocabulary problem** (Furnas): two people pick the same term for a thing only ~10–12% of the time. →
  never rely on the user typing our exact label; map keywords → facets; offer the facet they can recognize.
- **Sorting / chronological:** sortable columns let users "visually compare those criteria." Users often
  **prefer recency order** for their own/temporal info (vs relevance). → Search default = bill# (known-item),
  but offer **"most recent action"** prominently; the what's-new feed and calendar are inherently recency-first.

### Ch8 — Flamenco faceted navigation (the deep specifics behind PL-2)
- **The 5 Flamenco design goals** (the charter for our filter chips): flexible navigation · **seamless
  integration of browse + keyword search** (no mode switch — matches the vision's "no chamber switch, chamber
  is just two filter buttons") · **fluid alternation between refining and expanding** (no action feels
  terminal/irreversible) · **avoid empty result sets** · *"at all times allow the user to retain a feeling of
  control and understanding."*
- **Facet counts = information scent** (Fig 8.9): show the count next to every facet value *before* the user
  clicks, so they see whether a path is fruitful or empty. **A zero-count facet is visibly disabled** — this
  is the structural prevention of the empty-result dead-end. (= PL-2, now grounded.)
- **Separate the breadcrumb trail PER facet** — don't mix sponsor + committee + status + date in one linear
  path (confusing). Each facet is its own removable component: *"eliminate an entire facet by clicking the
  iconic ✕, or expand up within a category by clicking a parent term."* → show active filters as **per-facet
  removable chips**, not one mixed string.
- **Hierarchical facets / progressive disclosure** — show the immediate children of the current selection;
  reveal grandchildren on hover; selecting a parent surfaces the next level as a new facet below (the eBay
  Express pattern). → e.g. Topic > sub-topic, or Committee (chamber) > sub-committee.
- **Keyword→facet bridge** — map a typed term to a facet value when possible ("Ella Fitzgerald" → *Artist:*;
  for us "Finance" → *Committee: Senate Finance & Appropriations*, a patron surname → *Patron:*) instead of a
  blind full-text scan.
- **Categories vs clusters:** fixed human facets are **predictable + learnable** (users build a stable mental
  model); auto-clusters adapt to the query but cost "consistency, coherence, comprehensibility." → our facets
  are fixed structural fields (chamber, committee, status, patron) — the right call for trust.
- **Study results (32 users, 35k-item collection):** faceted nav was preferred ~88–91% over a Google-Images
  baseline; *self-described "keyword people" migrated to clicking facets as they learned the system.* The
  grouping itself was the biggest time-saver and **reduces the anxiety of hidden results / dead-ends** — which
  is *exactly* the lobbyist's deepest fear (vision §1: "the deepest fear is missing something"). Faceted
  navigation is a trust feature, not just a convenience.
- **Pitfalls to avoid:** vague catch-all facets ("Other/Misc") erode trust; mislabeled categories worse than
  none. → only expose facets whose values are precise + structural.

---

## Synthesis — Calendar UI patterns (cross-source, for the Task #3 build) — **2026-06-23**
Pulling the above + current calendar-UI practice into the concrete rules the Calendar build will follow.
(Sources: Tufte small multiples/micro-macro, Munzner position-for-time, Few palette/attention, plus modern
calendar-UX surveys — agenda-vs-grid, overflow, today/selected differentiation.)

- **Two views, one geometry (micro/macro):** a **month grid** for navigation *context* (which weeks are hot,
  where crossover falls) + a **day/agenda column** for *reading* the day in full. The landing **sliver is the
  day view of "today"**; the Calendar tab adds the month for shape. Don't make the user choose a mode to get
  both — let the grid drive the day column.
- **Month grid = small multiples of days** (one `DayCell` template ×31). Hairline grid (data-ink). **Today**
  and the **crossover deadline** are the *only* cells allowed a loud cue (Few attention + Munzner popout via a
  single strong channel). Weekends/out-of-month days: the quietest possible tint (smallest effective difference).
- **Time = vertical position** (Munzner #1 magnitude channel). In the day column, events ordered by resolved
  time, time shown as a tabular figure, "Time TBA" honestly labeled (never faked — ties to the calendar
  subsystem's `derived_standing`/TBA discipline and the trust layer). **Never encode time with color/size.**
- **Meeting chip = identity** (committee + chamber): spatial grouping + quiet hue + a text label (never
  color-alone, WCAG). Chamber via the same Senate/House hue used everywhere (one meaning per color, Few).
- **The crossover deadline is a *seam*, not a stage** (owner) — on the calendar it's a single **marked date**
  (the guillotine), the loud red the palette otherwise withholds. It's the one place saturation is earned.
- **Overflow:** modern grids show 2–3 events + "+N more"; but Tufte/Few say a lobbyist wants the day *entire*
  → prefer the day column (scrolls internally, the sliver's fixed-height pattern) over truncating. Grid cell
  shows a **count/density dot**, click → full day. (Density as the macro signal, completeness on drill.)
- **Empty state as a feature** (Refactoring UI): off-season "no meetings — GA adjourned, fills in 2027" is a
  *designed* empty state, not a grey sentence — the sliver already does this; carry it into the full calendar.
- **Trust inline:** a "data as of X ago" freshness cue; if a meeting time is derived/TBA, mark it (vision §7
  — "allowed not to know; never to pretend").

## Still queued (lower priority — read if a feature needs it)
- **Tufte — *Envisioning Information*** full (color, maps, layering) — have the calendar-relevant core; revisit
  if we add maps/cartograms (50-state).
- **Norman — *Design of Everyday Things*** (affordances) + **Wroblewski** (forms/mobile) — for the eventual
  mobile pass + the tracking-star/filter affordances.

See also [[design/information_display]] (the rules), [[design/ui_redesign_spec]] (owner change-list), [[log]].
