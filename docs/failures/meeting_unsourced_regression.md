---
tags: [failure, handoff, calendar, breaker, section-9]
updated: 2026-07-12
status: archived
---

# ✅ RESOLVED — the `meeting_unsourced` 0→66 regression (was an UnboundLocalError, audit #105)

> **RESOLUTION (2026-07-12):** the 66 was never §9, never the agenda-column semantics, never cache warmth.
> The agenda-links capture block referenced `normalized_name` **26 lines before its binding** in the schedule
> loop → `UnboundLocalError` on the first meeting row → swallowed by the schedule block's broad
> `except Exception` and alerted as *"🚨 LIS Schedule API failed during run: local variable 'normalized_name'
> referenced before assignment"* (status=OFFLINE) — the production alert stream NAMED the bug on all three
> trip cycles, and every diagnosis pass read it as a transient LIS outage. With the schedule loop dead:
> skeleton rows −2,713, `timeclass_*` absent, convene anchors lost (`sourced_convene` −1,278), 66
> meeting-routed actions unsourced, breaker trip. Full post-mortem: [[failures/assumptions_audit#105]].
>
> **Fixed + hardened in [PR #214](https://github.com/tucker2331-design/bill-tracker/pull/214)** (placement
> after the binding; the except SPLIT so a code bug alerts CRITICAL/UNKNOWN with type+line instead of wearing
> the OFFLINE costume; pyflakes `undefined name` gate = pre-push check 17 — it flags the original at 5625:38).
> **§9 re-merged in [PR #215](https://github.com/tucker2331-design/bill-tracker/pull/215)** (exonerated; plus
> the rung-telemetry→SYSTEM_METRICS fold #211 documented but never implemented). Both verified on live
> post-merge cycles: `meeting_unsourced=0`, breaker clear, agenda links populated (859/1,684 meetings).
> The offline STM-diff test prescribed below was never needed — **reading the trip cycles' alert stream in
> `Metrics_History` was the 30-minute shortcut**. Kept below as the historical record of the wrong turns.

## State of the world (2026-07-11)

- **`main` worker = known-good** (`calendar_worker.py` reverted to commit `6b45eb4`'s version, incl. the witness
  gspread-6 fix). Version `2026-07-07.1`. **Verified healthy:** a full recompute wrote `meeting_unsourced=0`,
  breaker clear, no red ring.
- **LIVE frontend/tools (breaker-safe, kept):** auto-refresh + transient `RefreshNotice`, Option-A calendar,
  the agenda card scaffold (`web/src/views/Calendar.tsx` renders `📄 Agenda`/`▶ Watch` from cols P/Q — currently
  empty, so it shows nothing, honest-absent), B-7 stranded-work guard (`tools/open_loops.py`).
- **Reverted / NOT on main (safe in git):**
  - `775e074` — the full PR #211 merge (§9 anchor ladder + §9d `_committee_parent` + agenda cols + auto-refresh + B-7).
  - `7671e18` — the re-ship: agenda cols + auto-refresh + B-7, **§9 removed** (build_time_graph spliced to known-good).
  - Both, on their first full recompute, tripped the breaker at `meeting_unsourced=66`.

## What is RULED OUT (with evidence — don't re-investigate these)

| Hypothesis | Verdict | Evidence |
|---|---|---|
| §9 anchor ladder / `_committee_parent` | **NOT the cause** | Re-shipped WITHOUT §9 → still 66. `build_time_graph` proven **byte-behavior-identical** to known-good on the live Schedule API (0 diffs, script below). |
| Agenda-links worker columns | **Can't touch the metric directly** | `meeting_unsourced` is counted in `_append_event` (`calendar_worker.py:4849`), BEFORE `final_df` exists; the agenda post-pass runs on `final_df` AFTER. Agenda code is purely additive (helper + dict populate + column add + INFO drift alert). |
| READY-debt terminal-skip deletion | **No-op** | `IsTerminal` is FALSE for all 3,645 cached bills (`LegEvent_Bills` tab), so the deleted skip never fired. |
| Off-season LegEvent-cache-warmth noise | **Weakened** | Known-good FULL recompute = 0 on BOTH 17:05 and 21:36 cycles (reliable). If it were pure cache noise, known-good full-recompute would also fluctuate. |

**The paradox:** by elimination the worker CODE looks innocent, yet re-merge → 66 and known-good → 0. The two ran
at different times, so the LegEvent cache (500-bill/cycle refresh cap) differed between them. **The confound not
yet controlled is the LegEvent cache state.** That is the ONE thing the next step must hold constant.

## THE definitive next step (do this first)

**Run the full STM good-vs-new on FROZEN, IDENTICAL inputs** — the `_legislation_event_cache`, `api_schedule_map`,
`docket_memory`, `convene_times`, `df_past`, `bill_locations`. Snapshot those once, then run
`run_sequential_turing_machine` (or the whole `run_calendar_update` row loop) with (a) known-good code and (b) the
re-ship code, and diff `meeting_unsourced` + the ORIGIN of every row.
- If new = 66 and good = 0 **on identical frozen inputs** → a real code effect. Dump the 66 rows
  (`Bill, Date, Committee, Outcome, Origin, LegEventRoute`) and trace which code path flipped their origin to
  `journal_default`/`floor_miss`. (Start at `calendar_worker.py:3751` — the `"Floor" in event_location` →
  `convene_times` lookup → `sourced_convene` else `floor_miss`; and `_recover_time_via_legevent_committee`.)
- If new ≈ good on identical inputs → it's **environmental/cache-warmth**, and the fix is breaker calibration
  (below), not the code.

### Two concrete sub-tasks the STM diff will decide between
1. **A real routing gap** the change EXPOSED — bill actions that should source from a committee's time but the
   committee-source path leaves at `journal_default`/`floor_miss`. Fix that path; then §9/agenda ship cleanly.
2. **Breaker mis-calibration off-season** — the breaker's `Y2` baseline is 0 (`Sheet1!Y2`, read at
   `calendar_worker.py:5061`); the trip is `meeting_unsourced_delta>25 (when baseline>0)` OR `>500` abs. A full
   recompute that legitimately establishes a nonzero off-season floor shouldn't hard-trip from a 0 baseline.
   Consider: let the baseline ESTABLISH on the first post-change full recompute (write Y2 then compare next
   cycle), or widen the off-season absolute floor. **Care:** don't blunt the breaker for a REAL regression —
   only after sub-task 1 proves the 66 are benign/upstream-limited.

## Reproduce / verify commands

```bash
# PROOF build_time_graph(new) == build_time_graph(known-good) on live schedule (0 diffs):
#   AST-extract build_time_graph from two git refs, run both on one live Schedule pull, diff the maps.
#   Pattern lives in tools/edge_case_replay/validate_relative_chains.py (load() + fetch()).

# Dump the live meeting_unsourced rows (once the worker writes them) — are the 66 a STABLE set or do they vary?
#   gviz Sheet1 where LegEventRoute='meeting' and Origin in ('journal_default','floor_miss').

# Re-run the worker: gh workflow run calendar_worker.yml --ref main   (cron is */15; a failed run self-heals next cron)
```

## Meta-lesson (already in [[assumptions_audit#101]])

Three wrong diagnoses this session (§9 → agenda → cache-noise). **A metric that moves under a code change is not
proof the code caused it.** Every guess compared runs at DIFFERENT times with a DIFFERENT LegEvent cache. Hold the
inputs constant (frozen-input replay) before attributing cause. That is why the offline STM diff — not a 4th
guess — is the required next move.

See also [[state/current_status]], [[ideas/calendar_chain_ordering]] (§9), [[ideas/meeting_agenda_links]] (agenda),
[[failures/assumptions_audit#101]].
