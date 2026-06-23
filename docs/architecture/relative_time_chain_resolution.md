---
tags: [architecture, calendar, time-resolution, planned, owner-feedback]
updated: 2026-06-23
status: planned
---

# Relative-Time Chain Resolution (PLANNED — not started)

**Owner directive (2026-06-23):** the calendar must order a meeting that's "after committee X" to appear
**after committee X**. Owner: *"que it and then really plan it out if it's a big change. establish a full
plan in the brain before you start."* This is that plan. **Do not start until reviewed.** It is a careful,
Section-9-sensitive change to the calendar subsystem's time engine.

Relates to: [[knowledge/tba_times]], [[architecture/calendar_pipeline]] (Time Resolution Priority),
[[failures/assumptions_audit#70]] (the relative-after-adjournment sort fix), `calendar_worker.py`
`build_time_graph` (~L2824).

---

## 1. The problem
Some committee meetings — heavily the **House Appropriations / General Laws / Labor & Commerce subcommittee
chains** — are scheduled by LIS with **no `ScheduleTime`** and a relative-time `Description` that references
**another meeting**, forming a dependency chain. Measured Feb 11, 2026 (House Appropriations):

| Meeting | LIS Description |
|---|---|
| …Commerce, Agriculture & Natural Resources | "15 minutes after adjournment of the House" (anchor) |
| …Transportation & Public Safety | "Immediately after the Commerce, Agriculture and Natural Resources Subcommittee" |
| …Health & Human Resources | "Immediately after the Transportation and Public Safety Subcommittee" |
| …Elementary & Secondary Education | "Immediately after the Health and Human Resources Subcommittee" |
| …General Government & Capital Outlay | "Immediately after the Elementary and Secondary Education Subcommittee" |
| House Appropriations (full) | "Immediately after the General Government and Capital Outlay Subcommittee" |

The worker leaves their `SortTime = "23:59"` (unresolved), so on the calendar they sort to **end-of-day in
alphabetical order**, not their true chain order. The lobbyist-facing calendar should reflect the real order.

## 2. Why there is NO structural shortcut (measured 2026-06-23)
- **`SortTime`** is the worker's structural sort key — but it's the very thing left unresolved (`23:59`).
- **`ScheduleID` / `VersionSequence`** (Schedule API) do NOT match the chain order — Feb 11 House Approps:
  ScheduleID `2990` = the LAST node ("after General Government…"), `2993` = an early node; VersionSequence
  is unrelated too. Neither encodes the agenda order.
- The dependency is expressed **only in LIS's free-text `Description`**.
- → Resolving the order **requires interpreting that prose**. That is the **worker's** job (the structural
  time engine), as accepted relative-time resolution (the flagged #70/#79 relaxation), **NOT** front-end
  text parsing (Standard #3 forbids it on the lobbyist path; the worker resolution is the sanctioned path,
  validated against structural data). The front end stays pure: it orders by `SortTime`.

## 3. Root cause in `build_time_graph` (`calendar_worker.py:2824`)
The function IS already a recursive chain resolver (`resolve_node` → `resolve_node(found_parent, visited)`
with a cycle guard). Two gaps stop it on these chains:
1. **Recognition gate too narrow** (L2857–2858): `dynamic_markers = ["upon adjournment", "minutes after",
   "hour after", "recess"]`. "**Immediately** after X", "2 **hours** after" (plural ≠ `hour after`),
   "after adjournment" (bare), "minutes adjournment" (no "after") **don't match** → the node is treated as
   a clock time → `parse_24h_time` can't parse → `"23:59"`. (Same narrow-list trap I hit + reverted in the
   schedule loop; do NOT "fix" it by enumerating more phrasings — that's the brittle path. See §4.)
2. **Parent matching by substring is fragile** (L2871): `found_parent = next((p for p in raw_times if
   len(p) > 5 and p in rl), None)` requires the **full** node key
   ("house appropriations - transportation and public safety subcommittee") to be a substring of the
   relative string, but LIS's Description uses the **short** name ("transportation and public safety
   subcommittee") → no match even if the gate passed.

## 4. The structural-clean fix (the approach, not enumerated keywords)
Replace the brittle keyword gate with **structural tests**, and make parent-matching robust against the
real node set:
- **Relative test (no keyword list):** a node is relative iff `parse_24h_time(raw_str)` does **not** yield a
  concrete clock time **AND** `raw_str` references another scheduled committee node. Anchors on STRUCTURE
  (is it a clock? does it name a real node?) — survives any new phrasing, zero maintenance (Standard #1/#8).
- **Parent match against the day's actual node set:** match the referenced committee against the set of
  `OwnerName`s scheduled **that day**, via the worker's existing normalized committee matching
  (`normalize_committee` / `COMMITTEE_CODE_MAP` / `LOCAL_LEXICON`). Pick the **longest / most-specific**
  scheduled committee whose normalized name is contained in the relative string; prefer same-chamber,
  same-parent. This binds the dependency to LIS's own structural committee set — not a guess.
- **Resolve recursively** (already supported), keep the cycle guard (`if name_key in visited: return …`).
- **Base case** ("after adjournment of the House/Senate") already anchors to the published
  "[chamber] adjourned" clock marker (`_adjourned_key`) — keep unchanged.
- **Offset parsing** — `_parse_relative_offset_minutes` already handles "N minutes"/"N hours"; verify it
  maps "immediately" → 0 and "1/2 hour" → 30.

## 5. Invariants / risks (Section-9-critical)
`build_time_graph`'s output (`resolved_parent_map`) sets `sort_time_24h` for schedule entries, which bill
**ACTIONS inherit when they match** → changing resolution **can shift Section 9**.
- **INVARIANT 1 — additive only:** the change must ONLY add resolutions for currently-unresolved (`23:59`)
  nodes; it must NOT change any node that currently resolves to a concrete time. Verify by diffing
  `resolved_parent_map` before/after over the full-session snapshot: every currently-concrete value
  identical; only `23:59` nodes gain values.
- **INVARIANT 2 — termination:** the recursion must terminate on malformed/cyclic chains (cycle guard).
- **INVARIANT 3 — no false anchors:** a chain that can't bind to a real scheduled node stays `23:59`
  (honest unresolved) rather than guessing — never invent an order.

## 6. Validation plan (per [[failures/assumptions_audit#74]] — measure on a run whose headSha contains the commit)
1. **Offline:** run `build_time_graph` on the live Schedule snapshot before/after; assert (a) all
   previously-concrete nodes unchanged (Invariant 1), (b) the ~20 chain nodes now resolve to concrete times
   in the correct order (Commerce < Transportation < Health < Elementary < General Gov < full Approps),
   (c) no nonsensical times, (d) termination on the full set.
2. **Section-9:** after merge, verify on a real worker run whose `headSha` provably contains the commit —
   Section 9 stays **0**, unclassified **0**, completeness intact, breaker green. (Projection ≠ measurement.)
3. **Front-end:** no change needed — confirm the chains now appear in order (orders by `SortTime`).

## 7. Front-end interaction
**None required.** `web/src/data/calendar.ts` already sorts by `minutes` (from `SortTime`) and displays
LIS's `Description` verbatim as the time. Display and structural sort are independent: once the worker
resolves the chain `SortTime`s, the existing front end orders them correctly. No parsing crosses to the UI.

## 8. Sequencing
After the current calendar PR ([#166](https://github.com/tucker2331-design/bill-tracker/pull/166)) lands.
Its own focused **worker PR** through the full 15-point Pre-Push Audit + the Gemini/CodeRabbit/Qodo loop.
Until then: the ~5–6 chained subcommittees/day sit at end-of-day with LIS's "after X" text shown (readable
order, not yet positionally exact) — an honest interim, no invented order.

See also [[architecture/calendar_pipeline]], [[knowledge/tba_times]], [[state/next_session]], [[log]].
