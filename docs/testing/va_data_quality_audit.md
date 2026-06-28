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
3. **`refidclass_unknown_refid = 5,051` (7.7%)** — refids that didn't match a known namespace (the refid is
   our structural primary key). `refidclass_empty = 26,752 (41%)` is expected (floor/convene + empty-refid
   governor rows), but 5,051 *unknown* (non-empty, unclassified) is a real structural-coverage cohort.
   **Action:** sample them — are they a new refid shape (extend the namespace law) or genuinely junk?
4. **Ledger-collapse volume:** `floor_anchor_miss=6,640 (10.2%)` + `unsourced_journal=2,775 (4.2%)` +
   `unsourced_anchor=4,761` ≈ **21% of rows collapse to Ledger.** All are non-meeting (`meeting_unsourced=0`),
   so not Section-9 bugs — but **confirm none are real actions losing provenance** vs. genuinely-admin
   (signed/placed/ministerial). This is the "no silent source-miss" rule at scale.
5. **`legislation_event_recovered = 1,005 / 3,863 attempts (26%)`** — low recovery. The 74% failures are
   non-meeting rows (Section 9 still 0), but verify they're genuinely unrecoverable (admin) vs. a recovery gap.
6. **HB30 `Conference Committee` 2026-06-19 `TIMING_LAG`** — a conference-committee action with no schedule
   match → Ledger. Likely upstream-limited (LIS published no timed conference meeting, like HB26/HB137), but
   confirm it's honest residue, not a missed source.

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
