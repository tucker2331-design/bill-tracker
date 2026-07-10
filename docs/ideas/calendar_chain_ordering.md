---
tags: [ideas, calendar, worker, time-resolution, plan, structural]
updated: 2026-07-09
status: active  # §9 residual (19 unplaceables) planned + measured, awaiting go
premise-revised: 2026-07-02  # §1-§6 premise ("chains stranded at 23:59, additive gate tweak") FALSIFIED — see §8
implemented: 2026-07-03  # DATE-AWARE refactor shipped in PR #189 — see §8 tail
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

## 7. Owner re-confirmed on the shipped week-view + added a FRONT-END requirement (2026-06-30, PR #185)
Reviewing the new week-view Calendar ([[design/ui_redesign_spec]] item 3), the owner saw the problem live and
sharpened the requirement — in a single screenshot: "15 minutes after adjournment of House Finance", "1/2 hour
after adjournment of the House", "Immediately upon adjournment of House General Laws", etc. are NOT placed
after the adjournment they reference (still `SortTime=23:59` → sorted to the end, §6), and at least one
relative-time meeting **doesn't name a resolvable body** at all. New directives:
1. **Order the resolvable ones correctly** — the §3 worker fix (resolve the relative chain to a real
   `SortTime`). Unchanged.
2. **The UNSORTABLE ones (no resolvable parent) must be SURFACED to the TOP of the day + visibly HIGHLIGHTED**,
   NOT buried at 23:59 where the position is silently wrong. Rationale: if we cannot time-sort it, don't
   pretend a position — flag it. This is the calendar-surface instance of the trust rule ("allowed not to
   know, never pretend"). **Front-end-safe (Standard #3):** the front end does NOT parse prose — the WORKER
   must emit a **structural flag** on the row (e.g. `TimeClass = relative_resolved | relative_unresolved |
   concrete`, or reuse the existing `⏱️ [NO_*]`/Origin telemetry), and the front end sorts `relative_unresolved`
   to the top of the day with a distinct treatment. So the worker gains a third job: when the §3 resolver
   can't find the parent, TAG the row `relative_unresolved` instead of silently defaulting to 23:59.
3. **Fallback to find the committee** — that IS §3.2 (normalized parent-match against the day's node set); the
   owner wants it attempted, and the tag from (2) is the honest outcome when it fails.
**Net:** the plan grows a small structural-flag output (worker) + a top-surface-and-highlight rule
(front-end, `web/src/views/Calendar.tsx` + `data/calendar.ts`). Still Section-9-sensitive; still worker-first;
the front-end half is display-only over a structural flag.

## 8. ⚠️ PREMISE FALSIFIED (2026-07-02) — the §1-§6 diagnosis was wrong; the fix is a DATE-AWARE refactor

Before writing the §3 fix I built an offline validator (`tools/edge_case_replay/validate_relative_chains.py`)
that AST-extracts `build_time_graph` old-vs-new, pulls the live Schedule API once, and diffs the resolved
maps. Implementing §3 exactly (structural `_is_relative_time_text` superset + normalized committee
parent-match, strictly additive) produced **`changed=0` — a complete no-op on real data.** Instrumenting the
resolver against **3,521 live rows across 443 dates** showed §1-§6 misdiagnosed the root cause. See
[[failures/assumptions_audit#95]]. The measured reality:

1. **`build_time_graph` is DATE-BLIND.** It keys `raw_times`/`resolved_times` by `OwnerName` ONLY — no date.
   Across 443 dates, every meeting of a committee collapses to ONE key (last-write-wins). Measured:
   `house appropriations` = **27 dated meetings → 1 resolved SortTime**; `house adjourned` = a **single
   `5:42 PM`** clock standing in for every day's adjournment. The caller (`calendar_worker.py` ~L5058)
   applies that one name-keyed value to a committee's meetings on ALL dates. So a relative meeting's derived
   order can be right on at most one date per name — broadening the recognition gate (§3.1) changes nothing,
   because the chains aren't failing to be *detected*, they're being resolved on the wrong (date-blind) axis.

2. **The chains are MIS-ANCHORED, not stranded at 23:59.** Of 450 relative-phrase rows: **250 → `∅`**
   (unresolved, mostly empty-description last-writes), and the rest carry "upon adjournment"/"minutes after"
   → they already ENTER the resolver and get a concrete-but-WRONG time. Step 1 anchors "adjournment of the
   House **Appropriations Committee**" to the House **FLOOR** adjourned marker; step 4's loose
   `"adjournment of the house" in rl` intercepts committee references before any committee-match can run — so
   a subcommittee sorts BEFORE its parent committee. The owner's "piled up / mis-ordered" complaint is this
   mis-anchoring, not a 23:59 pile.

3. **"Additive-only, 0 changes" (§4b) is impossible for the real fix.** Correcting the order REQUIRES
   re-pointing already-resolved (derived) SortTimes. The strict gate blocks the fix by construction. BUT the
   rows that must move all have an **empty published `ScheduleTime`** — their SortTime is purely derived; the
   displayed time stays LIS's verbatim relative phrase. So the correct safety gate is **"0 rows carrying a
   real PUBLISHED ScheduleTime move"** (77/450 relative rows have a clock; 373 are empty→derived), with the
   moved derived rows spot-checked for correct **parent-before-child** ordering. (Validator already
   implements this re-framed gate.)

### Revised approach (the actual §3, when this is next picked up)
- **Make `build_time_graph` DATE-AWARE:** group `schedules` by `ScheduleDate`, build the node graph + resolve
  WITHIN each day, and key the output map by `(date, name)` (the caller's `map_key` is already
  `f"{date_str}_{normalized_name}"` — the parent map must match that granularity). This makes "house
  adjourned" per-date and lets committee-parent chains resolve against the SAME day's nodes.
- **Then** the §3.1 (broadened detection) + §3.2 (normalized committee parent-match) changes become
  meaningful, and step 1/step 4 must recognize a COMMITTEE reference ("adjournment of the House **X
  Committee**") and anchor to that committee node, reserving the floor-adjourned anchor for bare-chamber refs.
- **Integrate with the existing date-aware last-resort path** (`adjourned_clock_by_date` +
  `_derive_standing_committee_time`, [[failures/assumptions_audit#76]]) rather than duplicating it — that
  mechanism already resolves per-date adjournment clocks for committees with no per-meeting entry.
- **Validation:** the re-framed gate above (0 published-clock rows move) + a real worker run re-measuring
  Section 9 = 0 (§4c, inherently post-merge in this repo's Actions-from-main flow) + the 15-point audit.
- **Scope:** this is a Section-9-critical refactor of the time engine, NOT the two-gate tweak §3 described.
  It warrants its own focused session and owner awareness (the owner gated this task on "plan fully before
  starting"; the plan is now corrected). The front-end §7.2 surfacing (top-surface + highlight the truly
  unresolvable residual) still applies, gated on the worker emitting a structural `TimeClass` flag.

### ✅ IMPLEMENTED — PR [#189](https://github.com/tucker2331-design/bill-tracker/pull/189) (2026-07-03)
The revised approach shipped exactly as scoped above. `build_time_graph` is now date-aware
(`_resolve_one_day` per day, output `{(date,name):"HH:MM"}`); `_committee_parent` anchors committee
references to the committee node (reserving the floor-adjourned clock for bare-chamber refs); concrete
published clocks always win; a +1-min chain epsilon keeps A→B→C strictly ordered; `_parse_relative_offset_minutes`
handles ½/mixed/unicode fractions. Validated offline (`tools/edge_case_replay/validate_relative_chains.py`):
**SAFETY 0/2,877 published-clock keys move, RESOLUTION 198→428 relative rows concrete**, chains order
parent→children. Three bot fold-in rounds; the notable hardening was replacing a hand-curated UI-caption
denylist (Standard-#1 rot risk CodeRabbit flagged) with a **structural `day_vocab` intersection** (drift-proof).
**§7.2 ✅ SHIPPED (PR [#193](https://github.com/tucker2331-design/bill-tracker/pull/193), 2026-07-04):** the
worker now emits a structural **`TimeClass`** column (`concrete | relative_resolved | relative_unresolved |
""`) — computed in the schedule loop from what the resolver did, stamped in `_append_event` via the
ScheduleClass keyed-map pattern (no API_Cache migration), with `timeclass_*` counters + `timeclass_total`
denominator in SYSTEM_METRICS. The front end sorts `relative_unresolved` meetings to the TOP of their day
with a caution tint + "⚠ unplaceable" badge. Live distribution: concrete=2877 · relative_resolved=408 ·
relative_unresolved=22 · TBA=173. Qodo fold-in also caught that **#189 shipped without a
`WORKER_OUTPUT_LOGIC_VERSION` bump** (Stage-2/incremental signature reuse could serve pre-change rows) —
bumped to `2026-07-04.1` covering both; `TimeClass` added to `_STM_EVENT_KEY_FIELDS`.

**Same-time-parent verification (owner Q, 2026-07-03):** confirmed the +1 chain epsilon anchors each
subcommittee to its RESPECTIVE parent by NAME, not time — proven synthetically (parents at 13:00 vs 14:00 →
children split 13:01 vs 14:01) AND in real data (2025-01-14: House Labor & Commerce AND House General Laws
both at 15:30, each child correctly at 15:31 following its own parent). No mis-anchoring. The interleave
residual (same-time families losing visual grouping) ✅ SHIPPED in the same PR #193 — "Parent - Sub" names
render as a muted parent line + "↳ Sub" (pure typography over the structural name).

## 9. The RESIDUAL 19 — measured 2026-07-09, and the permanent fix (owner: "solve it forever, don't patch it")

Owner reviewed the live week-view and pushed back: "a decent bit of unplaceables that should be easily
placed… fix this big picture, not a patch." **Measured first** (audit #95's lesson), straight off Sheet1:
`select A,B,E,O where O = 'relative_unresolved'` → **19 distinct meetings carrying 370 bill-rows.** (Those 370
also lose their time in the landing "What's new" feed, which skips `unresolved` meetings — same root cause.)

### The 19 fall into exactly three structural classes — every anchor already exists in our data
| Class | N | Phrase | Why the resolver misses it | Anchor (verified present) |
|---|---|---|---|---|
| **A** | 14 | `30 minutes after adjournment`, `30 Minutes after Recess`, `Upon Recess`, `Immediately Upon Adjournment` | phrase names **no body** | the meeting's **own chamber** floor marker for that date |
| **B** | 2 | `Upon adjournment of full committee` | "full committee" is a **self-reference**, not a proper name | the node's **own parent**, encoded in the `Parent - Sub` name |
| **C** | 2 | `Immediately after adjournment of the Elementary and Secondary Education Subcommittee` | the phrase lives in the **Description**, not `ScheduleTime` (row shows `Time TBA`) | a **sibling subcommittee** node on the same day |

**Anchor availability VERIFIED (untruncated scan; a first `limit 900` gviz query truncated and falsely
reported "no marker on 13/15 dates" — never trust a capped gviz result):** all 15 Class-A dates publish a
Senate floor marker with a concrete SortTime, e.g. `01-21 Senate adjourned@13:26` → GL&T = 13:56;
`01-28 adjourned@12:43` → GL&T = 13:13 → Housing (Class B) = 13:14 transitively; `02-06 Senate
recessed@12:40` → "Upon Recess" = 12:40; `01-14 recessed@14:10` → "30 Minutes after Recess" = 14:40. Every
Class-A committee is a Senate committee.

### The permanent fix: an ANCHOR-RESOLUTION LADDER (structure, not a phrase list)
All three failures share one root: **the anchor is IMPLICIT**, and today's resolver only handles an
explicitly-named body. So resolve the anchor *by structure*, scoped to the SAME DAY's node set. For a node on
date `D`, committee `N` (chamber `C` from the name prefix, parent `P` from the `Parent - Sub` lineage):

0. **Source the phrase structurally** — the relative text is `ScheduleTime` when it isn't a parseable clock,
   ELSE the `Description` when `ScheduleTime` is empty. (Closes Class C's *source* gap with one rule, not a
   TBA special-case.)
1. **Ladder — first hit wins, all against that day's nodes:**
   a. **Named body** → match the day's node set (full name; or the sub-segment of a `Parent - Sub` node,
      scoped to the same parent + chamber → sibling). *(Class C, and today's working path.)*
   b. **Self-reference** (`full committee` / `the committee`) → the node's own parent `P`. *(Class B)*
   c. **No body named** → the node's own chamber `C` floor marker for `D`, choosing **adjourned vs recessed
      by the phrase's own verb** (both are published, both exist). *(Class A)*
   d. else → `relative_unresolved` — the honest residual, already surfaced top-of-day with the ⚠ badge.
2. `time = anchor + parsed offset` (or `+epsilon` for pure ordering). Recurse with the existing cycle guard —
   B resolves transitively once its Class-A parent does.

**Why this is "forever," not a patch:** every rung resolves against **LIS's own structural data for that day**
(the node set, the name lineage, the published floor markers) — there is no curated phrase list to rot. A new
phrasing that names a body, says "full committee", or names nothing, lands on a rung *by structure*. The only
text elements remain the **reference kind** and the **offset** — both the already-accepted `derived`
relaxation ([[failures/assumptions_audit#79]]); DISPLAY stays LIS's verbatim string.

**Self-describing (Standard #4), so it cannot silently rot back:** emit a counter per rung
(`anchor_named / anchor_parent / anchor_chamber / anchor_unresolved`) over the existing `timeclass_total`
denominator, and WARN when the `unresolved` rung grows. A new phrasing then surfaces as a *metric*, not a
silent 23:59.

### Validation gates (Section-9-critical — unchanged discipline)
- Reuse `tools/edge_case_replay/validate_relative_chains.py`.
- **SAFETY:** 0 rows carrying a **published** `ScheduleTime` may move (all 19 have empty/derived clocks).
- **RESOLUTION:** `relative_unresolved` 19 → ~0; parent-before-child ordering holds (spot-check 01-28 GL&T →
  Housing, and 01-30 House Appropriations sibling chain).
- **Section 9 (`meeting_unsourced`) stays 0**; breaker green; completeness intact — measured on a real run
  whose `headSha` contains the change ([[failures/assumptions_audit#74]]), never projected.
- **`WORKER_OUTPUT_LOGIC_VERSION` bump is MANDATORY** ([[failures/assumptions_audit#96]]): SortTime *and*
  TimeClass values change, so the Stage-2 / incremental-STM signature must invalidate.
- 15-point pre-push audit, esp. #1 (verb/phrase forms), #14 (threshold calibration).

**Status:** planned + measured 2026-07-09; awaiting owner go-ahead to touch the time engine (his standing gate
on this task: "plan it fully in the brain BEFORE starting"). Blast radius: 19 meetings / 370 bill-rows, plus
those rows gaining times in the landing feed.

See also [[architecture/calendar_pipeline]], [[knowledge/tba_times]], [[failures/assumptions_audit#79]], [[failures/assumptions_audit#95]], [[design/ui_redesign_spec]], [[state/next_session]].
