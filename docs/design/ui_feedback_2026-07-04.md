---
tags: [design, ui, feedback, health, cadence, freshness, va]
updated: 2026-07-04
status: planned
---

# UI + cadence feedback (owner, 2026-07-04) — for the next UI session

Owner notes captured while the Cloudflare deploy was being fixed. All "for later" (UI is Opus+owner
territory). Each item has the diagnosis + the recommended fix so Opus executes without re-deriving.

## F-1 · The two freshness clocks disagree ("4h at top, 1h in the Calendar") — confusing
> **STATUS 2026-07-04: SHIPPED (pending merge) — PR #197.** Implemented as the "show both clocks together"
> variant of the recommended fix below: `TrustHeader` renders "● Bills as of …" + "🗓 Calendar as of …"
> side by side; the in-Calendar pill was removed (moved up, not duplicated). Display-only, no cron change.
> The deeper single-manifest unification (Blueprint 1) still supersedes this later.
- **Diagnosis (correct observation):** the top trust header shows the **bill backend's** `dataAsOf`
  (`bill_tracker.yml`, cron `40 */6 * * *` = every 6h → up to 6h old). The Calendar tab shows the
  **calendar worker's** `AA1` freshness (`calendar_worker.yml`, cron `0 */3 * * *` = every 3h → fresher).
  Two independent workers, two clocks, two cadences — so the numbers legitimately differ. It reads as an
  inconsistency even though both are honest.
- **Do NOT "sync" by forcing identical crons** — the workers have different jobs and LIS-load profiles
  (the bill backend re-derives 3,645 bills from 4 blobs; the calendar worker is meeting-time resolution).
  Coupling their cadence would waste LIS budget on the slower-changing one. The confusion is a DISPLAY
  problem, not a cadence problem.
- **Recommended fix (display honesty, cheap):** the trust header shows ONE "data as of" today; make it
  show the **oldest of the two** with a tooltip/expander breaking it down ("bills 4h · calendar 1h"), so
  the top line is never fresher than the stalest subsystem, and the Calendar's own fresher stamp then
  reads as "this view is newer," not "the app contradicts itself." The Health tab already has both clocks
  (feed-skew) — reuse that data on the product surface.
- **The real unification** lands with [[audits/fable_2026-07/50_state_scaling_architecture]] Blueprint 1
  (CDN inversion): the per-state `manifest.json` carries a per-payload timestamp, so the UI shows one
  coherent "as of" per data kind from a single source. Fold F-1's display fix into that work if it hasn't
  shipped standalone first.

## F-2 · Cadence is FIXED, not activity-correlated ("does it speed up with schedule items, slow without?")
> **STATUS 2026-07-05: BUILT (in review) — PR #198.** Guardrail #5 shipped exactly as scoped below: both
> workers now fire on a fast cron and self-throttle to real meeting windows (calendar ~15m in-window /
> ~3h quiet; bill ~hourly active / ~6h quiet), keyed off ONE structural signal (`Sheet1!AC1`). So the
> answer to the owner's question is now **YES** — it speeds up with schedule items and slows without.
> Details in [[knowledge/lis_api_safety]] (guardrail #5 row + cadence ledger) and `cadence.py`.
- **Answer: NO — not yet.** Both workers run fixed clocks (calendar every 3h, bills every 6h). The
  meeting-driven / activity-correlated cadence the owner is describing is **guardrail #5 in
  [[knowledge/lis_api_safety]], explicitly ❌ NOT PRESENT** — it's a documented owner proposal (2026-06-17)
  gated behind guardrails 1/2/4 (all now shipped), so it is now UNBLOCKED to build.
- **What it should do (from the charter):** trigger = a STRUCTURAL meeting on the Schedule API (concrete
  time, not an admin HISTORY row); in a meeting window (+ a tail) bump the calendar worker to ~15 min to
  catch votes/reports within minutes; drop to hourly / 3h when nothing is scheduled; slowest tier when the
  forward calendar is empty. Load tracks the legislature, never a blind metronome (Standard #8).
- **Recommendation:** this is a real backend feature (not UI) and a strong candidate for the next VA
  backend piece — it directly improves freshness DURING sessions (when lobbyists care most) at LOWER
  average off-season load. Scope it as its own PR against the charter; it also naturally shrinks F-1 (a
  faster in-session calendar clock makes the two numbers closer when it matters). See the cadence policy
  section of [[knowledge/lis_api_safety]].

## F-3 · Health "at a glance" rings — confusing what each represents; make warnings actionable
Owner: *"the one ring with a warning says Sustainability audit check but just says 1 warning above it… what
do the top and bottom each represent, and why is the bottom-left missing a bottom one. Have the warning say
more or be clickable so it takes you to where the warning is."*
- **What the ring encodes today (HealthVitals):** each of the 4 donuts is a CATEGORY (Accuracy /
  Completeness / Freshness / Stability). The **big number + word ("1 warning")** = the worst-of rollup of
  that category's LIVE internal segments. The **small line below ("✓ … check passed" / "✕ … check
  FAILED")** = the INDEPENDENT outside guard (GitHub Actions) for that category — a different thing (live
  signal vs outside cross-check). That two-things-on-one-ring is exactly what reads as confusing.
- **F-3a — label the two lines.** Add tiny prefixes so they're self-describing: the rollup line →
  "Status: 1 warning"; the badge line → "Verified: Sustainability audit ✓". Removes the "what is top vs
  bottom" ambiguity outright.
- **F-3b — the "missing bottom line" is Freshness.** Freshness has NO independent outside guard (there's
  no oracle for "is our clock right"), so `vitalVerify` returns undefined and no badge renders → it looks
  like a ring is "missing" its bottom line. Fix: render an explicit muted "Verified: — (no outside check
  applies)" placeholder so all four rings are visually parallel and the absence is EXPLAINED, not blank.
- **F-3c — make the warning descriptive + clickable (the owner's main ask).** The rollup word ("1
  warning") should (a) say what it is on hover/expand (category + the segment that's amber, e.g.
  "Stability · 1 active WARN alert"), and (b) be a click target that scrolls to / filters the Alerts feed
  below to that item (anchor link within the Health tab). The data is already on the page — this is
  wiring, not new signals.

## F-4 · "Why do we have these alerts, can you solve them?"
- **Current live state (2026-07-04, post-#190):** exactly **ONE** SYSTEM_ALERT —
  `[WARN:DATA_ANOMALY] Malformed HISTORY row for HB923 on 2026-03-09: empty description after chamber`.
  The flood is gone (#190); this is a single honest flag.
- **What it is / is it solvable:** LIS itself published a HISTORY.CSV row for HB923 dated 2026-03-09 with
  an EMPTY description after the chamber prefix. Verified: HB923's derived history has 19 rows and NONE on
  03/09 — i.e. the blank row carried no recoverable action; the worker correctly refused to fabricate one
  and flagged it (Standard #4/#6, honest-not-silent). **It is an UPSTREAM data defect, not a system bug —
  nothing to "fix" in our code, and nothing lost (the row was genuinely empty).**
- **Options (owner decision, low stakes):** (a) LEAVE IT — it's one honest flag, and a malformed upstream
  row is legitimately worth a human glance the first time; (b) if empty-description rows recur and are
  ALWAYS confirmed content-less, add a narrow `empty_history_row` benign class (counter, not WARN) so only
  NOVEL malformations alert — but only after confirming a sample are all truly empty (never blanket-hide a
  class that could carry a real hidden action). Recommend (a) until it recurs; it is not a launch blocker
  and the Health tab is otherwise green (Section 9 = 0).

See also [[design/ui_redesign_spec]], [[design/health_operator_tab]], [[knowledge/lis_api_safety]] (cadence),
[[audits/fable_2026-07/50_state_scaling_architecture]] (freshness unification via the manifest).
