---
tags: [design, health, frontend, ui]
updated: 2026-07-07
status: active
---

# Alerts as STATE not stream + the 2026-07-07 de-AI pass (applied)

Owner directive (2026-07-07): the Health alerts "need real thinking and fixing… back up and zoom out,
consider how a human looks at this, look into how other dashboards do things"; and **"these colored boxes
scream AI built all over our site."** The visual-language canon (restraint, least-visible-means, saturated
colour is exhausting) is already researched in depth — see **[[design/reading_notes]]** (Few *Information
Dashboard Design* Ch4.2.7 / 7.1.3 / 7.3.1 — the "screams-AI fix, verbatim") and **[[design/information_display]]**
(the north-star + punch-list, PL-8 bullet graphs). This page adds the one thing those don't cover — the
**alert-feed architecture** — and records what was actually changed this session so the canon → applied gap
is visible.

## The new idea: an alert feed is STATE, not a stream

The Health alert panel was a raw **append-only log**: every alert that ever fired, forever, grouped by exact
message text, with internal Python tuple dumps leaking through. That is a debug feed. Every fix I shipped
just *added* a new-style row on top of the old ones, so nothing ever cleared — the owner asked for
self-clearing twice and never got it. How mature status tools (StatusPage / GitHub / Vercel / Datadog /
PagerDuty / Sentry) behave instead:

1. **One verdict at the top** answering the only question a human asks: *do I need to do anything?*
2. **Current STATE, derived from the latest evaluation — not history.** A recovered monitor flips back to OK
   by itself. **This is the self-clearing**: a condition is "active" iff it fired in the most recent cycle;
   the moment the worker stops emitting it, it drops out of the active view. No human "acknowledge".
3. **Resolved → a separate, collapsed history**, rolled up so it's a summary, not a wall.
4. **Group by CONDITION, not exact text** — normalise away volatile numbers/dates/ids so a per-bill
   explosion ("Malformed row for SB587…", "…SB420…") collapses to one row with a count.
5. **Honest, rare severity.** Green/neutral by default; a benign INFO (blank upstream rows, an overnight
   cadence gap) is a quiet note, never an amber "Heads up" competing with real problems.
6. **No internal representation on the face** — plain sentence, debug tail stripped.

### How it maps onto our data (no worker change)
`Metrics_History` already appends one `system_metrics` row + that cycle's `system_alert` rows, all stamped
with the cycle timestamp. So the frontend derives state honestly: `latestCycleTs = max(ts)`; a condition is
**active** iff `lastTs ≥ latestCycleTs − ~6min` (well under the ~15-min in-window cadence); older conditions
self-resolved. Cleared conditions roll up by category ("Timing lag — 289 distinct, 336× total, last 4d
ago"). Implemented in `web/src/views/Health.tsx` (`alertModel`, `groupConditions`, `conditionStem`,
`cleanMessage`, `AlertsPanel`, `ClearedHistory`). The self-clearing is a *reinterpretation* of the existing
log — the worker keeps its full audit trail; the UI shows state.

## De-AI pass — what changed 2026-07-07 (applying the canon)
Per Few's "delineate with the LEAST VISIBLE MEANS" + "saturated colour is exhausting" (already in
[[design/reading_notes]]): **colour must encode state a human needs at a glance; if removing it leaves the
screen calmer without losing meaning, it was decoration.**

| Offender (a filled "colored box" = the AI tell) | Fixed to |
|---|---|
| `.hl-sev` severity pills on every alert row | a single 8px status **dot** |
| Alert feed = a wall of every past alert | verdict line + active-only + collapsed per-category history |
| `.hl-breaker` filled ok/trip pill | dot glyph + neutral text |
| `.hl-skew.danger` red box fill | red **dot**, no box |
| `.trust .pill` header freshness/tracking pills (filled green/red) + ●🗓✓ emoji chrome | dot (CSS `::before`) + neutral text, emoji removed |

### Still filled, deliberately NOT changed this pass (owner's aesthetic call — show, don't silently redo)
- Bill **outcome chips** (Signed / Vetoed / Awaiting / …) on cards + Today counts — colour here is
  *functional* (consistent outcome coding), and restyling the core product surface is a bigger call. Flag to
  owner before touching.
- The **Tracking / Full GA** segmented control — a legitimate toggle-with-selected-state pattern, not a tell.

## Standing rule
New health/status UI starts **calm-by-default**: a verdict, a short active list, a collapsed history. New
colour must encode state. When in doubt, apply [[design/reading_notes]] (Few/RUI), not a template dashboard.
