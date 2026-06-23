---
tags: [state, live, handoff]
updated: 2026-06-23
status: active
---

# ▶️ START HERE — next session kickoff

Read this first (then [[index]], [[state/current_status]], [[state/open_anti_patterns]]). Written at the
end of a long 2026-06-22/23 session that shipped the bill backend, ban-safe scheduling, the front end,
the design research, and a full UI redesign — all merged to `main`. Pick up the **owner queue** below.

## Where things stand (all MERGED + live on main)
- **Backend** `bill_tracker.py` — PR1 spine + PR2 structural position + PR3 patron/structural-outcome. Live-validated (3645/3645, patron all, outcome 1:1). Writes the `Bill_Tracker` tab.
- **Scheduling** — `bill_tracker` runs every 6h (ban-safe: quiet hours + jitter, guarded session). The legacy 15-min `backend_worker` is **paused**. (#163)
- **Front end** `web/` — React+Vite+TS SPA, reads the sheet via gviz; tabs **Today · Calendar · Search · Health**. Foundation (#164) + the redesign (#165): tinted canvas, calendar sliver, smooth timeline spine, visual system. Runs locally: `cd web && npm run dev` (localhost:5173); build `npm run build`.
- **Design brain** — [[design/information_display]] (rules + punch-list PL-1…8), [[design/reading_notes]] (Few read in full + Refactoring UI), [[design/ui_redesign_spec]] (owner change-list + progress).

## The owner queue (do in this order — tasks #2 → #3 → #4)
1. ✅ **READ the remaining books** — DONE 2026-06-23. Genuine deep-reads of Tufte *VDQI* (small multiples → a month grid IS small multiples of days), Munzner *Visualization Analysis & Design* (the channel-effectiveness ranking → time=position, chamber-by-position), Hearst *Search User Interfaces* (Ch1 + Ch8 faceted nav) banked to [[design/reading_notes]] + a Calendar-UI-patterns synthesis; [[design/information_display]] PL-9 added. Owner also queued discovery items (McCandless *Information is Beautiful*, a dashboard case-study article, CLEVER°FRANKE) — see reading_notes "Reading / discovery queue". **(Task #2 ✅.)**
2. 🟡 **BUILD the Calendar feature** — **PR [#166](https://github.com/tucker2331-design/bill-tracker/pull/166) OPEN** (2026-06-23). Integrated the calendar subsystem (`Sheet1`) into the `web/` Calendar tab read-only via gviz (same workbook, column projection): month grid (small multiples) + day agenda, committee+floor meetings WITH times, the marked **crossover deadline** (2026-02-17), Tracking-scope filter, "Time TBA" kept honestly, session-cached. Build clean, verified live, zero console errors. **Awaiting CodeRabbit + Qodo → fold in → merge.** The landing sliver (`web/src/components/CalendarSliver.tsx`) stays the DOCKET-based "today" window for now (wiring it to the same Sheet1 engine is a follow-up — avoids loading ~5 MB on the landing). **(Task #3 🟡.)**
3. **Health/bugs tab + master site.** Build the Health metrics as **bullet graphs / gauges with danger bands** (owner: "like a car's RPM red zone" = Few's bullet graph — see PL-8 + Task #4 for the metric list + calibration). **CONSTRAINT: the Health page will be ACCESS-GATED to the owner + a few** — operator/admin view, not lobbyist-facing; plan auth-gating for the static-SPA/gviz setup (Cloudflare Access is the clean fit). The master site is the cross-system home for the bug tab + the historical tracker (vision §9). **(Task #4 — NEXT.)**

## Known follow-ups / deferred (not blocking the queue)
- **Floor stage** on the timeline — deferred until the backend emits a structural floor/passed-chamber signal (BILLS.CSV has `Passed_house`/`Passed_senate`; `_build_bills_meta` already reads the flags — emit them to the `Bill_Tracker` tab, then `web/src/data/derive.ts deriveStage` can place a Floor node honestly; an empty node would mislead).
- **Search**: chamber-toggle bug + add per-facet counts + disable zero-count facets (PL-2). (Text overflow already fixed.)
- **Chief-patron FULL name** from the universe `Patrons` field (backend; BILLS.CSV only has the surname) + **co-patrons** via a throttled `LegislationByMember` backfill (no bulk blob).
- **Backend: stamp `session_code`** into the completeness payload (the front end already prefers it, falls back to year-inference).
- **Backend: stamp the session's `crossover_date`** into the completeness payload — the Calendar (PR #166) currently pins it in `CROSSOVER_BY_SESSION` (front end can't derive it without LIS); emit it so the guillotine marker is structural, not a constant. Same shape as the `session_code` stamp.
- **Calendar display-time format** is shown verbatim from LIS (mixes "9:00 AM" / "9:00 a.m."). LIS-parity is intentional; normalize only if the owner wants uniform formatting.
- **Wire the landing CalendarSliver to the Sheet1 engine** (it's DOCKET-based today) so the "today window" and the full Calendar share one source — needs the ~5 MB load to not hit the landing (lazy/shared cache).
- **Subject** ingest — no bulk source (deferred; see [[ideas/lis_data_inventory]] §6).

## How we work here (process reminders)
- Every code change → its own branch + PR; wait for **CodeRabbit + Qodo** (Codex rate-limits fast; Gemini sunsets ~2026-07-17). Fold in findings, re-push, re-poll until clean, then squash-merge. Bots review COMMITS not replies; re-anchored stale comments are common — verify the fix is in HEAD.
- LIS-safety: authorized sessions 2025/2026 only; minimize calls; never a metronome. Structural-determinism (no text parsing on the lobbyist path).
- Always push after commits; `docs/` is the brain (not `~/.claude`). Verify front-end changes in the preview (`preview_*`), screenshot proof.

See also [[state/current_status]], [[ideas/product_roadmap]], [[ideas/product_vision]], [[log]].
