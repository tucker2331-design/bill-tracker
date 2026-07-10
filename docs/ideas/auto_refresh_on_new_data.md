---
tags: [ideas, web, product, ux, freshness]
updated: 2026-07-10
status: active
open_loop: Auto-refresh the SPA when new data lands (owner 2026-07-10: "tired of manually refreshing") — probed + scoped, not built
---

# Auto-refresh when new data lands — probed, scoped, recommended

> **Owner, 2026-07-10:** *"probing how to fix the problem of having to manually refresh every time there's new
> data. we attempted to have it auto refresh on streamlit and it was a very frustrating process that i don't
> remember succeeding in."*

**Status: probed + scoped, not built.** One small UX decision (soft pill vs hot-swap) is worth an owner nod
before building; everything else is unblocked engineering.

---

## 1. The past pain was STREAMLIT-specific, and no longer applies

The frustrating attempt was on Streamlit (`test_auto_calender.py` / `pages/ray2.py` — now only the internal
X-Ray). Streamlit's model reruns the whole script on any interaction; auto-refresh needs a third-party
`streamlit-autorefresh` component or a `while True: st.rerun()` hack, `@st.cache_data(ttl=…)` fights the
rerun, and every refresh is a full-page rerun that drops scroll/widget state. It is genuinely fiddly — the
owner's memory of "never quite succeeding" is accurate.

**The product is no longer Streamlit.** It's the React + Vite SPA (`web/`) on Cloudflare Workers. In a SPA,
background refresh without losing UI state is a standard `setInterval`/focus + `fetch` + `setState` pattern.
The thing that made it painful is gone.

## 2. The problem, measured (current SPA behavior)

The SPA loads its data **exactly once, on mount, and never again:**
- `web/src/App.tsx:35` — `useEffect(() => { loadBillData()… }, [])` — empty deps, fires once.
- `web/src/data/calendar.ts:177` — `loadCalendar()` memoizes a module-level `_calPromise` for the page's life.
- There is **no `setInterval`, no `visibilitychange`/focus handler, no polling** anywhere (`grep` confirms).

So when the worker writes new data to the sheet, the open tab shows stale data until a **hard browser reload**.
That is the owner's complaint, and it is a real gap on the product surface (not just the X-Ray).

## 3. Costs, measured (live, 2026-07-10) — this is why naive polling is wrong

| Fetch | Size | Time |
|---|---|---|
| `Bill_Tracker` full (the SPA's main load) | **6.7 MB** | ~3.9 s |
| `Sheet1` calendar projection | **5.7 MB** | ~1.2 s |
| `Sheet1!AA1` (calendar freshness) | ~40 B | ~0.4 s |
| `Bill_Tracker` `dataAsOf` (1-cell) | ~40 B | ~0.3 s |

A naive `setInterval` that re-fetches both payloads is **~12.4 MB per tick** — absurd for an idle tab, and
worse off-season where the data is **static for days** (the GA is adjourned). But a **freshness cell is ~40
bytes.** The asymmetry (40 B to *check* vs 12 MB to *load*) is the whole design.

Both primitives already exist: `loadCalendarFreshness()` reads `AA1`; the bill sheet stamps `Data As Of (UTC)`
in its header. The two feeds run on **different cadences** (bills vs calendar), so each has its own freshness
marker and must be checked independently.

## 4. Recommended fix — FRESHNESS-GATED background refresh

Poll only the two ~40-byte freshness cells; do the 12 MB re-fetch **only when a timestamp actually advances.**

1. **A `useFreshnessGate` hook.** On an interval (default **90 s** — under the prompt-cache-free zone and far
   below any worker cadence) AND on `window` `focus`/`visibilitychange`, fetch the two freshness cells. Compare
   against the `dataAsOf` / `calendarAsOf` already in state.
2. **When bills' `dataAsOf` advanced** → re-run `loadBillData()`, `setData(newData)`. When calendar's `AA1`
   advanced → invalidate `_calPromise` (needs a tiny `invalidateCalendar()` export) and re-run `loadCalendar()`.
   Each feed refreshes independently — a calendar cycle doesn't drag the 6.7 MB bill payload.
3. **Don't yank the view.** For the passive **Landing** feed, hot-swap silently. For **Search / Calendar**
   (the user may be mid-scroll or mid-filter), show an unobtrusive **"New data — refresh" pill** in the
   TrustHeader and swap on click or on next focus. *(This pill-vs-hot-swap split is the one UX call worth an
   owner nod — §7.)*
4. **Off-season is nearly free:** the poll is ~40 B and the gate never opens, so an idle tab costs a few bytes
   a minute and never re-downloads. In-session, it detects the worker's write within ~90 s and does **one**
   big fetch, not one per tick.

The TrustHeader already shows "data as of N min ago"; this makes that number *live* instead of frozen at
page-load, which is the honest version of the same signal.

## 5. Alternatives considered (and why not)

- **Naive interval re-fetch (no gate):** 12 MB/tick, pointless off-season. Rejected on the measured cost.
- **Refresh only on focus (no interval):** good and cheap, but a user who leaves the tab open and *watching*
  (a lobbyist during a live committee day) still goes stale. Keep focus as one trigger, add the interval.
- **Server push (SSE/WebSocket):** there is no app server — the SPA reads Google Sheets directly via gviz, and
  Cloudflare Workers static-assets serves files, not a socket. A push channel would mean standing up
  infrastructure for a problem a 40-byte poll solves. Rejected (Standard: don't add infra a poll handles).
- **Service-worker background sync:** overkill; doesn't help a foreground tab and adds a cache-coherence
  surface.

## 6. Validation / rollout

- Verify in the browser preview: load the app, mutate the freshness cell (or wait for a worker write), confirm
  the tab refreshes within the interval **without a manual reload** and **without losing** the current
  tab/scroll/filter state.
- Confirm the off-season idle cost is just the freshness poll (network panel: ~40 B requests, no 6 MB fetch)
  until a timestamp advances.
- No worker / output change — this is **read-side only** (no `WORKER_OUTPUT_LOGIC_VERSION` implication).
- Watch the gviz request budget: a 90 s poll of one cell is trivial, but confirm it doesn't trip any
  Google-side rate concern on the shared sheet (it won't at this volume; note it for completeness).

## 7. The one owner decision

**Hot-swap vs. "new data" pill on the interactive tabs (Search/Calendar).** Hot-swap is the least friction but
can move the ground under a user mid-scroll; the pill is safe but adds one click. Recommendation: **hot-swap
Landing, pill for Search/Calendar** (swap-on-focus so even the pill usually resolves itself). Cheap to flip
either way once seen live.

## 8. X-Ray (still Streamlit) — separate, lower priority

If the owner also manually refreshes the internal X-Ray (`pages/ray2.py`), the same freshness-gate idea applies
there, but Streamlit-side it carries the historical pain (§1). Lower priority — it's an internal diagnostic,
not the lobbyist surface. Note it; don't bundle it with the product fix.

See also [[architecture/calendar_pipeline]], [[state/current_status]], [[design/information_display]].
