---
tags: [testing, va, data-quality, health, sustainability, active]
updated: 2026-06-25
status: active
scope: va
---

# VA Data-Quality Audit — the "clean sustainable data" optimization

Owner (2026-06-25): **clean, sustainable data is the top priority** — VA is the STANDARD for every future
state, so its data must be impeccable before we generalize. The Health tab surfaced some "slightly
concerning numbers." This page is the live diagnosis + the investigation queue. Snapshot from the live
`SYSTEM_METRICS` row (calendar worker, 2026-06-25; `total_processed=65,375`).

## Headline: the core metric still holds ✅
- **`meeting_unsourced = 0`** — every MEETING action still has a time (Section 9 = 0). The achievement is intact.
- **Bill completeness = 100%**, 0 history-vs-universe anomalies. Patron 100%.
So nothing here is a crisis. These are SECONDARY edges to smooth for a truly clean/sustainable VA standard.

## The edges to investigate (priority order)
1. **`invariant_violations = 1`** — ✅ **ROOT-CAUSED + FIXED 2026-06-25** (`claude/va-invariant-derived-standing`).
   It was NOT an I3 (0 concrete rows carry a `[NO_*]`/empty time; the 482 "Time TBA" are legit LIS values).
   It was a **FALSE I2**: `derived_standing` (the #76 flagged-assumed SJ209 time, 1 row, emitted in
   production) was **missing from `_VALID_ORIGINS`**, so that lone row tripped the origin-enum invariant
   **every cycle**. Fix = register `derived_standing` (one line) → `invariant_violations` should go **1→0**
   on the next worker run (live-validation gated on a run — [[failures/assumptions_audit#74]]). The stale
   doc I2 list (also omitted `executive_default`) updated to match the live `_VALID_ORIGINS`.
   **Residual finding (separate, deferred):** the I2 alert IS pushed by `_append_event` (code is correct),
   yet only the `TIMING_LAG` alert was visible on the sheet — so the alert HISTORY isn't fully surfaced
   (only the latest). That's Health gap #2 (alert history / Bug_Logs) + worth checking the Actions logs.
2. **`gap_minutes = 179.43`, `gap_cause = normal`** — ✅ **RESOLVED 2026-06-25: NOT a bug.** The cron is now
   `0 */3 * * *` (every 3 h — changed because the 15-min cron backed up on ~16-19 min runtime), and the
   thresholds AUTO-SCALE: `GAP_WARN = SCHEDULE_CADENCE_MINUTES(180)×2 = 360 min (6 h)`, `GAP_CRITICAL =
   QUIET_WINDOW(420)+360 = 780 min (13 h)`. So a ~3 h gap is correctly `normal`; freshness IS trustworthy.
   The `20/60` was the 15-min-era value — **stale doc fixed** in [[architecture/calendar_pipeline]]. (The
   Health freshness gauge bands lower(6,12,24) happen to align well; could pin danger to 13 h exactly.)
3. **`refidclass_unknown_refid = 5,051` (7.7%)** — ⏸️ **SCOPED (safe, an optimization — not a bug).** The
   classifier **SURFACES** UNKNOWN_REFID rows (never routes them admin), so they're safely handled, not
   silently mis-routed (consistent with `meeting_unsourced=0`). Reducing the count = a structural-coverage
   optimization: sample the distinct unknown refid *shapes* from HISTORY.CSV (needs the dynamic session blob
   path) — if one shape dominates, extend the namespace law; if heterogeneous, honest residue. **Deferred.**
4. **Ledger-collapse volume (~21%)** — ✅ **CONFIRMED SOUND 2026-06-25 (live sheet).** 7,826 Ledger rows, all
   correct collapse origins (`floor_miss` 3,402 / `journal_default` 2,765 / `admin_default` 1,659). A text
   spot-check for "meeting verbs" hit 906 rows, but they are **clerical document rows** ("Bill text as passed
   House (HRxxxER)") — the regex over-matched "passed" (the very text-fragility we avoid). **No real meeting
   actions are losing provenance** — the structural signal (`meeting_unsourced=0`) is correct.
5. **`legislation_event_recovered = 1,005 / 3,863 (26%)`** — ✅ **fine.** The 74% failures are non-meeting
   rows (Section 9 = 0), i.e. admin rows that legitimately have no meeting time to recover. Not a gap.
6. **HB30 `Conference Committee` `TIMING_LAG`** — ✅ **honest upstream residue** (LIS published no timed
   conference meeting, like HB26/HB137). The lone surfaced row; never a meeting-without-time bug.

## ✅ Dive conclusion (2026-06-25): the data IS clean/sustainable
The headline metrics were already perfect (Section 9 = 0, completeness 100%). The dive found **exactly one
real defect** — the false `invariant_violations=1` (the unregistered `derived_standing` origin), **fixed in
PR #176** (→ 0 on the next worker run). Everything else is correct (gap classification), doc-drift (fixed),
or safe-by-design residue (unknown-refid surfaced; Ledger collapse sound; recovery failures are admin; HB30
upstream-limited). **The only forward optimization is edge #3** (reduce the 5,051 unknown refids — deferred).
The remaining work is OBSERVABILITY (the Health gaps below), not correctness.

## Health-tab observability gaps (owner: "what's missing?" — 2026-06-25)
The Health gauges surface the *counts*; the deeper trust layer (vision §7 lists several as "should track,
don't yet") is still missing. Priority gaps to BUILD (folds into the Health-tab follow-up + the data work):
1. **Invariant-violation DETAIL** — which row + which invariant (this audit proved the count alone is
   undiagnosable). The fix in edge #1 above (per-row `DATA_ANOMALY` alert) makes it show in the alert feed.
2. **Alert HISTORY, not just the latest** — the tab shows one `SYSTEM_ALERT`; surface the recent feed (`Bug_Logs`).
3. **Drift canaries** — `validate_status_grouping` / G-code (`validate_governor_eventcodes`) / committee-map
   drift fire on UPSTREAM changes but aren't on the tab (the early warning that LIS changed something).
4. **Independent reconciliation result** — the MinutesBook 99.67% tripwire (our strongest "are we right?").
5. **Sentinel + sustainability-audit status** — the 5-layer durability guard's latest verdicts ([[architecture/verification_durability]]).
6. **Per-bill freshness** (§7 #2: did one bill quietly stop updating?), **feed-skew** (§7 #3), and
   **universe-vs-LIS-introduced-total** (§7 #1: is the universe itself complete, not just records==universe).
7. **Trend sparklines** — gauges are point-in-time; reading the session archive for each metric's trajectory
   shows DIRECTION (is drift growing?) — the real early-warning. Pairs with [[architecture/session_archive]].

## Method (per the brain discipline)
Read the LIVE Sheet1 via gviz (raw strings, not pandas auto-NaN — [[failures/assumptions_audit#66]]); diagnose
the specific rows; fix only what's real, each with a before/after on the live metric on a run whose `headSha`
provably contains the change ([[failures/assumptions_audit#74]]). Every fix → [[failures/assumptions_audit]].
Generalizable lessons → the SHARED brain ([[workflow/cross_state_brain]]) so NY/PA inherit them.

See also [[design/health_operator_tab]] (the gauges that surfaced these), [[architecture/calendar_pipeline]]
(the counters' definitions + the breaker), [[state/current_status]].
