---
tags: [design, ui, redesign, web, owner-feedback]
updated: 2026-06-22
status: active
---

# UI Redesign Spec — owner feedback (2026-06-22)

> **PROGRESS (2026-06-22, branch `claude/ui-redesign`):** ✅ items **1, 2, 3, 5, 8** done + a full visual
> system overhaul grounded in the reading. Calendar sliver (Today planner column w/ empty state) replaces
> "Next up"; timeline moved onto the landing below what's-new; timeline redrawn as a smooth integrated
> **spine** (continuous centerline + nodes, no boxes); **crossover shrunk** to a thin dashed seam; new
> **tinted cool canvas** (not white/cream) + elevated cards + muted palette + spacing/type scales +
> weight-based hierarchy + shadows-over-borders. Build clean, screenshot-verified, zero console errors.
> **Remaining:** item **4 (Floor stage)** — deferred until the backend emits a floor/passed-chamber signal
> (an always-empty node would mislead); items **6–7 (Search overflow + chamber-toggle bug + facet counts)**
> — next PR (box text-overflow is already fixed globally by the new `.cat` 2-line clamp).


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

## Queued next (owner, 2026-06-23)
- **Drop the standalone Timeline tab** — redundant now that the timeline is on the landing. ✅ DONE (in this PR).
- **Read the queued books** (Tufte VDQI full, Hearst, Munzner) → [[design/reading_notes]], THEN
- **Build the Calendar feature** — integrate the perfected calendar subsystem into the Calendar tab (full calendar w/ times + the marked crossover deadline); the landing sliver is the "today" window. (Task #3; do after digesting calendar-UI knowledge.)
- **Health/bugs tab + master-site content** (Task #4): design what the operator view shows. **CONSTRAINT: the Health page will be ACCESS-GATED to the owner + a few others** — design it as an operator/admin surface (not lobbyist-facing), and plan auth-gating compatible with the $0 static-SPA + gviz setup (e.g. Cloudflare Access, a separate gated deploy, or a token). The lobbyist-facing trust signals stay inline (vision §7); the deep operator layer lives behind the gate (§3f). The master site is the eventual home for the bug tab + the historical tracker (§9).

## Timeline — terminal stages should BRANCH, not end at "To Governor" (owner, 2026-06-23)
Owner UI note (future, not blocking the Calendar work): **the timeline ending just at "To Governor" isn't
representative of how the process actually ends.** A bill's end is not one node — it forks. Wants the tail of
the spine to **branch into the real terminal outcomes**, e.g. after the second chamber: **→ To Governor →
{signed / vetoed}**, **→ continued to next session (carried over)**, **→ failed / died**. Specifically:
**"failed" is currently shown in boxes at the BOTTOM** (the `died-row` DiedStat tiles under the spine) —
"which is nice, but holistically it's really an **action on the table, not a side note**." So **died/failed
+ carried-over should be terminal branches IN the pipeline geometry** (an honest end-state the bill reaches),
not a footnote below it. Design a branching tail: the spine splits into the decided outcomes so "where did
this bill end up" reads directly off position. Keep it honest/structural (we already have `outcome` =
signed/vetoed/dead/carried_over/awaiting_governor + `deriveStage`'s `died`); this is re-geometry, not new data.
→ a Timeline follow-up after Calendar + Health. (Recorded so it isn't lost; relates to the deferred Floor-stage
item — both are "make the pipeline match the real process.")

## Sequencing (owner)
- **"First, knock off the first 2 items in your list of 4."** *Interpretation (confirm):* the 4 = the
  four lenses/views; **first 2 = Today (landing) + Timeline** — which is exactly what items 1–5 above
  detail. So: read the books → redesign Today + Timeline first → then Search fixes + the global pass +
  the other lenses. **If "list of 4" meant something else, the owner will redirect.**
- Reading is PREP: digest full-length books (Tufte VDQI, Few, Hearst, **Refactoring UI** for the
  not-look-generic problem, calendar-UI patterns), notes → [[design/information_display]].

## 2026-06-29 owner feedback (QUEUED — after the observability work lands)

Three items the owner flagged while reviewing the live Health + Calendar tabs. **Queued, not started.**

1. **"Are we right?" panel reads as stale/pointless.** The four independent-verification rows show e.g.
   "verified 7d ago," which looks broken next to a live tab — the owner expected them to update "every time
   the worker runs." **Root cause (not a bug):** those guards run on their OWN cadence (reconciliation +
   completeness are WEEKLY, accuracy sentinel DAILY) — they're independent cross-checks against LIS, by
   design not per-cycle ([[architecture/verification_durability]]). **Fix direction:** make the cadence
   legible instead of hiding it — show "weekly check · last run 7d ago · next in ~1d" (and/or a small
   "next run" countdown), so "7d ago" reads as "on schedule," not "stale." Consider collapsing the four
   into a single compact trust line if the per-row detail isn't earning its space. Lands in
   [[design/health_operator_tab]] when built.
2. **Calendar doesn't render past May** even though the future-calendar feature was built. **Investigate:**
   likely a scrape-window / date-filter bound in the calendar subsystem or the `web/` Calendar reader that
   caps at the session end (2026-05-01) — VA GA is adjourned so HISTORY is static, but the Schedule API may
   still carry future-dated entries the reader is filtering out. Confirm whether the cap is in the worker's
   window, the gviz query, or the month-grid component, then lift it so genuine future events show.
3. **Calendar relayout — weekly-primary + monthly-as-selector (dual function).** Make a large **7-day
   vertical week view** the PRIMARY module at the top: events listed out per day, defaulting to the CURRENT/
   upcoming week, with **back/forward** arrows to page to prior/next weeks. The existing **monthly grid then
   shrinks** and becomes **dual-function**: (a) it keeps the event-widget behaviour it has now, AND (b) it
   **highlights the week currently shown in the macro week-view** and acts as the **week selector** — moving
   the highlighted week-window (click a week / a day) drives the top view. **UI hurdle the owner named:**
   make it INTUITIVE that the monthly grid controls the weekly view (it serves two roles at once) — e.g. a
   visible "week band" highlight on the month + a subtle affordance that the month is a picker, not just a
   display. **✅ SHIPPED 2026-06-30 (PR #185).** **OWNER DECISIONS (2026-06-30):** (a) **layout = week view MAIN +
   compact month grid ALONGSIDE (a sidebar), NOT below** — the month gets *small* (dates + density dots
   only, no big cells/text; "no need to take up extra space"); (b) **dual selection in the month**: a 7-cell
   **week-band** highlight shows which week the big view is displaying AND a single **day-focus** marker
   (dot/ring) shows the picked day — clicking a day BOTH jumps the week view to that day's week AND focuses
   that day (owner: "have it do both… a single highlight and then a 7-piece highlight"); back/forward arrows
   page the week. If the dual-cue proves confusing, fall back to arrows-only — but the dual-cue is the goal.
   Relates to item 2 (the
   week view must be able to page into the future).
4. **Timeline — show VETO + WHERE bills FAILED (design research needed).** Two related asks: (a) **visually
   distinguish VETOED bills** on the timeline (the data already exists: `outcome === "vetoed"`), and (b)
   **incorporate FAILURE into the pipeline geometry so you can see WHERE a bill died** — committee / floor /
   crossover / governor — not just *that* it died. This **sharpens the 2026-06-23 "terminal stages should
   BRANCH" note below** (died/failed + carried-over as terminal branches IN the spine, not the bottom
   `died-row` footnote) and the **Floor-stage item (#5 above)** (a Floor node is a prerequisite for showing a
   floor-stage death) — design all three together. **Design research required (owner flagged):** how to encode
   terminal outcomes + stage-of-death in a pipeline/flow viz without clutter — review [[design/reading_notes]]
   (Tufte data-ink / small multiples, Few popout-for-attention) + [[design/information_display]], and look at
   flow/Sankey + funnel "where it dropped off" patterns; veto likely wants a reserved attention color (Few:
   one meaning per color — `--o-vetoed` is already that). **Data check before designing:** `outcome` gives
   signed/vetoed/dead/carried_over/awaiting_governor today, but "where it failed" needs the *stage of death*
   (the last stage the bill structurally reached) — confirm that's derivable from `deriveStage` / the history
   before committing to a geometry. A Timeline follow-up after Calendar + Health.
5. **Calendar — "after adjournment" ordering + surface the unsortable (owner 2026-06-30, reviewing #185).**
   Relative-time meetings ("15 min after adjournment of House Finance", "1/2 hour after adjournment of the
   House") aren't placed after the adjournment they reference, and one names no resolvable body. FULL plan +
   the new "surface-unsortable-to-TOP + highlight, worker emits a structural flag" requirement live in
   [[ideas/calendar_chain_ordering#7]] — that's the home; this is the pointer. Worker-first (Section-9
   sensitive) + a display-only top-surface rule on the front end.
6. **Calendar — KILL the colored left side-strip on meeting cards; differentiate chamber floor-events by
   FORM, not a bar (owner 2026-06-30). ✅ DOING NOW (PR #186).** The `border-left: 3px solid <chamber>` on
   `.cal-mtg` "screams AI-generated / cheap AI UI." Remove it. Per the design principles ([[design/information_display]]:
   Few — group by whitespace not borders, one meaning per color, saturation reserved for attention;
   Refactoring UI — hierarchy by weight+color, depth via shadow over borders): keep the chamber cue on the
   committee-name COLOR (already there), and give House/Senate **floor session markers** (Convenes / Recessed
   / Adjourned / Reconvened) a distinct QUIETER treatment (they're session context, not committee meetings the
   lobbyist tracks) — e.g. a slim centered "session marker" row (no card chrome, muted, small caps), so the
   committee-meeting CARDS are the visual primary and the floor events read as the connective session tissue.
   NO left bar anywhere. Detect floor markers structurally where possible (see `data/calendar.ts`); the "kill
   the bar" part is unconditional.

See also [[design/information_display]], [[ideas/product_vision]], [[log]].
