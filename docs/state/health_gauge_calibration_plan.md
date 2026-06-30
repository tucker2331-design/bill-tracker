---
tags: [state, plan, web, health, archived]
updated: 2026-06-29
status: archived
---

# Health gauge calibration — execution plan + live checklist

> ✅ **DONE 2026-06-29 — merged in PR [#182](https://github.com/tucker2331-design/bill-tracker/pull/182)** (squash). P1 + P2 shipped; P3 deferred. One bot fold-in round (null-session false-green → hide-on-unknown; heuristic docs per Standard #1). Kept for the record; the lessons are in [[failures/assumptions_audit]] if any were generalized.

Fixes the 3 findings from the `/code-review` of merged PR #181 (the Health observability long-tail).
**Persisted here so it survives context compaction.** Ordered by effectiveness (impact ÷ effort·risk).
Scope is entirely `web/src/` (front-end) — **do not touch `calendar_worker.py`, `structural_router.py`,
`pages/`, or `tools/`**. Full rationale: [[testing/va_data_quality_audit]] + the review findings below.

## STATUS — all done
- [x] P1 — cadence-aware feed-skew bands (`web/src/views/Health.tsx`)
- [x] P2 — session-aware source-feed gauge (`web/src/data/health.ts` + `Health.tsx`)
- [x] P3 — DEFERRED (documented in the PR; not implemented)
- [x] tsc + vite build clean
- [x] preview-verified (feed-skew green "in sync"; 0 console errors; source-feed gauge hidden when session unknown)
- [x] PR #182 opened · 1 bot fold-in round · merged (squash) · branch deleted
- [x] brain write-back (log + current_status; this file archived)

Branch: `claude/health-gauge-calibration`

---

## P1 — cadence-aware feed-skew bands (`web/src/views/Health.tsx`)
**Why:** flat `3h/8h` thresholds, but a healthy skew is dominated by the bill backend's 6h cron
(`bill_tracker.yml 40 */6 * * *`) vs the calendar worker's ~15min — so it shows amber "one feed is lagging"
~half of every normal bill cycle. False-warns now, year-round.

**Edit 1a** — after the `higher = (...)` band-preset helper, INSERT:
```tsx
// Feed-skew is dominated by the BILL backend's clock (6h cron, bill_tracker.yml `40 */6 * * *`) vs the
// calendar worker's ~15min. A HEALTHY skew is up to ~6h BY DESIGN; derive thresholds from that cadence so
// the chip only warns when the skew exceeds what the cadence explains. [code-review finding #1]
const BILL_CADENCE_H = 6;
const SKEW_OK_H = BILL_CADENCE_H + 1;        // ≤7h: within one bill cycle (+1h jitter/queue) = healthy
const SKEW_WARN_H = BILL_CADENCE_H * 2 + 1;  // ≤13h: missed a scheduled run; >13h = stalled
```

**Edit 1b** — replace the `hl-skew` chip's two `feedSkewH <= 3 ? ... <= 8 ? ...` ternaries with
`feedSkewH <= SKEW_OK_H ? "ok" : feedSkewH <= SKEW_WARN_H ? "warn" : "danger"` (className) and the message
`<= SKEW_OK_H ? "in sync (the bill backend refreshes every 6h)" : <= SKEW_WARN_H ? "the bill backend is
overdue for its 6h refresh" : "a subsystem has stalled — one clock is far behind the other"`.

## P2 — session-aware source-feed gauge (`health.ts` + `Health.tsx`)
**Why:** off-season `HISTORY.CSV` legitimately never changes (no new actions), so its blob age grows for
months while the cycle clocks stay fresh — the gauge would false-danger the whole adjourned period.
Severity is meaningful ONLY when `Sheet1!S1` = `ACTIVE` (the worker already writes it each cycle).

1. `health.ts` `HealthData`: add `sessionActive: boolean | null;`.
2. `health.ts` `_loadHealth`: add a 4th parallel read `fetchText(gvizUrl("range=S1&headers=0")).catch(... return "")`,
   parse `const s1 = firstCell(s1Txt).toUpperCase(); const sessionActive = s1 === "ACTIVE" ? true : s1 === "ADJOURNED" ? false : null;`,
   and return it.
3. `Health.tsx`: derive `const sessionActive = h?.sessionActive ?? null;` and
   `const blobAgeBands: Band[] = sessionActive === true ? lower(12, 24, 48) : [{ upto: 1e9, tone: "good" }];`
4. `Health.tsx` source-feed `<BulletGraph>`: `max={48} bands={blobAgeBands}`, and a session-aware `sub`
   (in-session = "stale here while cycle clocks green = LIS stopped feeding us (provisional bands)";
   off-season = "HISTORY.CSV legitimately doesn't change — shown for reference, not alarmed").

## P3 — DEFER (document only, do NOT build)
Metrics_History re-stores the full alert set every cycle (~96 near-dup rows/day for one persistent alert);
bounded by the 45d prune so it's not a leak. The witness-pattern fix (append an alert row only when the
cycle's dedup-key set changes, keep the metrics row per-cycle) needs cross-cycle state on the safety-critical
worker path → not worth the risk now. Revisit only if tab growth is measured to matter. **Do not touch
`calendar_worker.py`.**

## Verify
`cd web && npx tsc --noEmit` (clean) → `npm run build` (✓ built). Then `preview_start` (config `web`) →
click Health → `preview_console_logs` level=error (empty) → `preview_snapshot` (feed-skew chip reads
"in sync" green on live data; source-feed gauge stays hidden on live data — that's the correct empty-state,
do not "fix" it). Screenshot for the PR.

## Workflow
Own branch → PR → wait for CodeRabbit + Qodo → fold in (re-verify, push; bots review commits) → squash-merge
+ delete branch. If CodeRabbit hangs "pending" >~10min with `structural-tests` green and no CHANGES_REQUESTED,
merge on the verified state. Brain write-back to main (log + current_status; flip this file to archived).

## Guardrails (DO NOT)
- Touch anything outside `web/src/` (no worker / router / pages / tools).
- Change `BulletGraph.tsx`, `Sparkline.tsx`, `history.ts`, or canary/alert-history code (out of scope).
- "Fix" the source-feed gauge being hidden or the canaries showing "? not checked" on live data — correct
  honest empty-states until the worker's next cycle populates them.
- Add a duplicate `Band` import to `Health.tsx` (it already imports it from `../components/bands`).
- Guess if a FIND block doesn't match verbatim — STOP and report.
