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
1. **`invariant_violations = 1`** (should be 0; persistent). One row failed a write-time invariant
   (I1 schema / I2 Origin / I3 concrete-source-carries-no-`[NO_*]`). Per [[architecture/calendar_pipeline]]
   it should emit a `DATA_ANOMALY/CRITICAL` alert, but only a `TIMING_LAG` alert is visible. **Action:**
   find WHICH row + WHICH invariant; confirm the violation is surfaced (if not, that's a visibility gap).
2. **`gap_minutes = 179.43` but `gap_cause = normal`** — 179 min (~3 h) exceeds the documented
   `GAP_WARN=20` / `GAP_CRITICAL=60` thresholds, yet it's classified "normal." Either the off-season cadence
   was relaxed (then the thresholds/AA1-freshness gauge need recalibration to match) or the classification is
   wrong. **Action:** reconcile the gap thresholds with the actual current cadence so freshness stays trustworthy.
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

## Method (per the brain discipline)
Read the LIVE Sheet1 via gviz (raw strings, not pandas auto-NaN — [[failures/assumptions_audit#66]]); diagnose
the specific rows; fix only what's real, each with a before/after on the live metric on a run whose `headSha`
provably contains the change ([[failures/assumptions_audit#74]]). Every fix → [[failures/assumptions_audit]].
Generalizable lessons → the SHARED brain ([[workflow/cross_state_brain]]) so NY/PA inherit them.

See also [[design/health_operator_tab]] (the gauges that surfaced these), [[architecture/calendar_pipeline]]
(the counters' definitions + the breaker), [[state/current_status]].
