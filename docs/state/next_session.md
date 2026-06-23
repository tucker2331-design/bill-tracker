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
1. **READ the remaining books** (owner: "digest full length books, multiple") — Tufte *VDQI* (2nd ed) deeper, Hearst *Search User Interfaces* (faceted-nav chapters are free online), Munzner *Visualization Analysis & Design*. Bank genuine notes to [[design/reading_notes]] AS YOU GO ("so the brain keeps growing"). Read the calendar-relevant material since the next build leans on it. **(Task #2, in_progress.)**
2. **BUILD the Calendar feature** (after the reading). Integrate the perfected calendar subsystem (the calendar engine / `Sheet1`) into the `web/` Calendar tab: full calendar with committee+floor meetings AND times, the marked **crossover deadline**. The landing's calendar sliver (`web/src/components/CalendarSliver.tsx`) is the "today" window into this. **(Task #3.)**
3. **Health/bugs tab + master site.** Build the Health metrics as **bullet graphs / gauges with danger bands** (owner: "like a car's RPM red zone" = Few's bullet graph — see PL-8 + Task #4 for the metric list + calibration). **CONSTRAINT: the Health page will be ACCESS-GATED to the owner + a few** — operator/admin view, not lobbyist-facing; plan auth-gating for the static-SPA/gviz setup (Cloudflare Access is the clean fit). The master site is the cross-system home for the bug tab + the historical tracker (vision §9). **(Task #4.)**

## Known follow-ups / deferred (not blocking the queue)
- **Floor stage** on the timeline — deferred until the backend emits a structural floor/passed-chamber signal (BILLS.CSV has `Passed_house`/`Passed_senate`; `_build_bills_meta` already reads the flags — emit them to the `Bill_Tracker` tab, then `web/src/data/derive.ts deriveStage` can place a Floor node honestly; an empty node would mislead).
- **Search**: chamber-toggle bug + add per-facet counts + disable zero-count facets (PL-2). (Text overflow already fixed.)
- **Chief-patron FULL name** from the universe `Patrons` field (backend; BILLS.CSV only has the surname) + **co-patrons** via a throttled `LegislationByMember` backfill (no bulk blob).
- **Backend: stamp `session_code`** into the completeness payload (the front end already prefers it, falls back to year-inference).
- **Subject** ingest — no bulk source (deferred; see [[ideas/lis_data_inventory]] §6).

## How we work here (process reminders)
- Every code change → its own branch + PR; wait for **CodeRabbit + Qodo** (Codex rate-limits fast; Gemini sunsets ~2026-07-17). Fold in findings, re-push, re-poll until clean, then squash-merge. Bots review COMMITS not replies; re-anchored stale comments are common — verify the fix is in HEAD.
- LIS-safety: authorized sessions 2025/2026 only; minimize calls; never a metronome. Structural-determinism (no text parsing on the lobbyist path).
- Always push after commits; `docs/` is the brain (not `~/.claude`). Verify front-end changes in the preview (`preview_*`), screenshot proof.

See also [[state/current_status]], [[ideas/product_roadmap]], [[ideas/product_vision]], [[log]].
