---
tags: [ideas, calendar, worker, time-resolution, plan, structural]
updated: 2026-06-23
status: planned
---

# Plan — Resolve "after committee X" meeting CHAINS (calendar ordering)

Owner re-raised twice (2026-06-23): committee meetings scheduled *"Immediately after the Transportation and
Public Safety Subcommittee"* / *"1/2 hour after adjournment of the House"* currently **pile up at the end of
the day, alphabetically**, instead of in their real chain order. Owner directive: **queue it; plan it fully
in the brain BEFORE starting** (it's a Section-9-sensitive worker change). This is that plan.

## 1. The problem, exactly
A handful of meetings/day (House Appropriations / General Laws / Labor & Commerce subcommittee chains) have
no `ScheduleTime`; LIS expresses their time **only as prose** in the `Description`: a transitive dependency
("A is after B, B is after C, C is 15 min after the House adjourns"). The worker's `build_time_graph`
(`calendar_worker.py:2824`) is a **recursive resolver** meant to handle exactly this — but two gaps leave
their `SortTime = "23:59"` (the unresolved default), so the front end sorts them to end-of-day:

1. **Recognition gate too narrow** (`resolve_node`, ~L2857): `dynamic_markers = ["upon adjournment",
   "minutes after", "hour after", "recess"]`. It does NOT match `"Immediately after …"`, plural
   `"… hours after"`, `"1/2 after adjournment"`, `"15 minutes adjournment"` — so those nodes are treated as
   non-relative → `parse_24h_time` can't read a clock → 23:59.
2. **Parent match too literal** (~L2871): `found_parent = next((p for p in raw_times if len(p) > 5 and p in
   rl), None)` matches the parent committee by **substring of the raw node key**. But the Description uses
   the **short** committee name ("Transportation and Public Safety Subcommittee") while the node key is the
   **full** name ("house appropriations - transportation and public safety subcommittee") → `p in rl` fails.

**Confirmed in data (Feb 11 / Jan 27 chains):** `SortTime` is `23:59` for the chained subcommittees;
`ScheduleID` / `VersionSequence` do NOT encode the order either. So **no structural field carries the
order** — it lives only in the prose dependency.

## 2. Why this is a WORKER fix, not front-end (and why it's allowed)
- The front end must stay **display-only / structural** (Standard #3): it shows fields, it does not parse
  prose. So the front end cannot derive the order — it can only sort by `SortTime`. Therefore the resolution
  must produce a correct structural `SortTime`, which is the **worker's time engine's job**.
- The worker resolving relative times is the **already-owner-accepted `derived` relaxation** ([[failures/assumptions_audit#79]] / `derived_standing`): flagged, validated against structural data, DISPLAY stays
  LIS's verbatim string. This plan EXTENDS that accepted resolver to the transitive chains — it does **not**
  add a new brittle keyword list on the lobbyist path. The anchor (published "[chamber] adjourned" clock) and
  the parent set (the day's actual schedule nodes) are **LIS's own structural data** ("consuming the source",
  the same justification owner approved for the status-grouping — [[knowledge/lis_api_reference]]).
- ⚠️ The OFFSET phrase ("15 minutes", "1/2 hour", "immediately") is the one text element. Mitigation: for
  ORDERING we only need the **dependency** (which parent), not the exact minutes — assign each child its
  parent's resolved time + a tiny per-step epsilon so the **chain orders correctly** even if the offset parse
  is approximate. Exact display stays LIS's verbatim string. (If we also want an exact clock, parse the
  offset as a flagged `derived` value — but order does not depend on it.)

## 3. The change (build_time_graph / resolve_node)
1. **Relative-detection by STRUCTURE, not keywords.** A node is "relative" when `parse_24h_time(raw)` yields
   no clock AND `raw` references either (a) a published "[chamber] adjourned"/"recess" marker, or (b) another
   schedule node name. Drop the hard `dynamic_markers` gate as the sole signal (keep the markers only as a
   fast-path hint). This removes the maintenance-forever keyword list (the brittleness owner rejected).
2. **Parent match against the day's node SET, normalized.** Resolve the referenced committee to an actual
   schedule node using `normalize_room_key`-style normalization + suffix/contains matching WITHIN the same
   parent-committee + chamber, so short ("Transportation and Public Safety Subcommittee") matches full
   ("House Appropriations - Transportation and Public Safety Subcommittee"). Anchor "after the House/Senate
   adjourns" to the published adjourned clock (already partially done at ~L2866-2876 — keep/extend).
3. **Recurse with the existing cycle guard** (`visited` → "06:00" on a cycle). Verify A→B→C→adjourned
   resolves transitively. Assign `parent_minutes + step_epsilon` so siblings in a chain stay strictly ordered.
4. **Keep `parse_24h_time`'s relative branch** (`["after","upon"]`, L2797) for the offset; ensure it handles
   "immediately" (0), "1/2 hour" (30), plural "hours". Offset only refines the clock; order comes from (3).

## 4. Validation gates (MUST pass before merge — Section-9 discipline)
- **Offline, against the live Schedule API + HISTORY:** (a) every previously-`23:59` chain node now resolves
  to a concrete SortTime that orders the chain correctly (spot-check Feb 11 + Jan 27 against LIS); (b) **0
  already-resolved schedule entries change** (diff the resolved map before/after — additive only);
  (c) **Section 9 (`meeting_unsourced`) stays 0** and no concrete bill-action time shifts (these chains are
  mostly skeleton rows, but some carry bill actions — verify those specifically).
- **On a real worker run** whose `headSha` provably contains the change (the procedural lesson,
  [[failures/assumptions_audit#74]]): re-measure Section 9 = 0, breaker green, completeness intact, and the
  X-Ray ordering. Never a projection — measure the produced rows.
- **15-point Pre-Push Audit**, esp. Points 1 (verb/phrase forms), 7 (no list overlap), 14 (threshold
  calibration — does any SortTime-dependent threshold move?).

## 5. Risk + sequencing
- **Risk:** `build_time_graph` feeds `api_schedule_map`, which times bill ACTIONS → Section 9. A bad change
  could mis-time real meetings. Mitigated by "additive only" (only touch previously-unresolved nodes) + the
  before/after diff + the live Section-9 re-measure.
- **Sequencing:** after the Health tab (Task #4) unless owner re-prioritizes. Its own branch + PR; CodeRabbit
  + Qodo; the full validation loop above; then write-back ([[failures/assumptions_audit]] + [[knowledge/tba_times]] + this page → status `done`).
- **Front end:** NO change needed — once `SortTime` resolves, `web/src/data/calendar.ts toMinutes()` already
  orders by it. (The relative-time DISPLAY already shows LIS's verbatim Description.)

## 6. Interim (current shipped state, PR #166)
The chains show LIS's verbatim relative-time text ("Immediately upon adjournment of House Labor and
Commerce") and sit at end-of-day. Honest (real LIS text, after the timed session) but not yet positionally
ordered. Acceptable to ship; this plan is the follow-up that makes position exact.

See also [[architecture/calendar_pipeline]], [[knowledge/tba_times]], [[failures/assumptions_audit#79]], [[state/next_session]].
