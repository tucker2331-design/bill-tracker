---
tags: [design, reading-notes, ui, information-display]
updated: 2026-06-22
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

## Queued (read next, full where available)
- **Tufte — *VDQI* (2nd ed) + *Envisioning Information*** — deepen beyond the [[design/information_display]]
  synthesis (data-ink, small multiples, layering, micro/macro).
- **Hearst — *Search User Interfaces*** (full chapters online) — faceted nav specifics for the Search fixes.
- **Munzner — *Visualization Analysis & Design*** — encoding-channel effectiveness (position > length > … >
  color hue) to justify the timeline's encodings rigorously.

See also [[design/information_display]] (the rules), [[design/ui_redesign_spec]] (owner change-list), [[log]].
