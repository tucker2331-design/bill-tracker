---
tags: [ideas, web, product, ux, freshness]
updated: 2026-07-10
status: shipped
---

# Auto-refresh when new data lands — ✅ SHIPPED 2026-07-10

> **Owner, 2026-07-10:** *"probing how to fix the problem of having to manually refresh every time there's new
> data. we attempted to have it auto refresh on streamlit and it was a very frustrating process that i don't
> remember succeeding in."*

**Status: SHIPPED & browser-verified.** Freshness-gated background refresh with a transient notice. Files:
`web/src/data/refresh.ts` (cheap stamp reads), `data/calendar.ts invalidateCalendar()`,
`components/RefreshNotice.tsx` (the transient toast), and the gate in `App.tsx` (interval + focus), with
`calRefresh` threaded to the three calendar-consuming components. Verified in the preview: the notice fires on
a real stamp change with the correct per-feed label, does NOT false-fire on a formatting difference, and a
no-change poll stays silent.

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
3. **Swap the data in, then explain the change with a TRANSIENT notice** (owner 2026-07-10). The data updates
   in place (no reload); a brief line — *"Updated with the latest data"* — fades in at the corner and
   **auto-dismisses after ~4 s**. Its ONLY job is to tell a person *why the page just changed under them* — it
   is **not** a status indicator and **not** a "how fresh is the data" readout (that already lives in the
   TrustHeader; duplicating it would be noise). No persistent pill (owner: "we have too many pills and they
   scream AI UI"), no silent swap (owner: "could be confusing"). It appears only on an actual change event,
   then it's gone.
4. **Off-season is nearly free:** the poll is ~40 B and the gate never opens, so an idle tab costs a few bytes
   a minute and never re-downloads. In-session, it detects the worker's write within ~90 s and does **one**
   big fetch, not one per tick.

Keep the distinction sharp: the TrustHeader's "data as of N min ago" is the **state** (always visible,
answers *how current*); the transient notice is the **event** (momentary, answers *why did this just move*).
This build also makes the header's number go *live* (re-derived on each refresh) instead of frozen at
page-load — the honest version of the same signal.

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

## 7. Owner decision — SETTLED (2026-07-10), and BUILT

Owner: *"do neither [pill nor silent swap] — we have too many pills and they scream AI UI, and hot-swapping
could be confusing. Just a quick thing that goes away, because it's only to tell a person why their site
suddenly changed, not to show how long since the data's been refreshed. Understand the distinction."* →
**`RefreshNotice`**: a plain toast (rounded rectangle, deliberately NOT a pill), bottom-centre, that fades in
on a refresh and auto-dismisses after ~3.5 s. It reports the EVENT ("Updated with the latest bill/calendar
data"), never the STATE (freshness age stays in the TrustHeader). `prefers-reduced-motion` honoured.

## 8. Implementation notes (2026-07-10)

- The stamp refs hold the **raw cell string only**, never a `Date` round-trip. The first build seeded them
  from `Date.toISOString()` (`…54.000Z`) while the poll re-read the raw cell (`…54Z`) — a formatting mismatch
  that fired a phantom "calendar updated" on the very first poll. Caught in the browser test (label said "bill
  & calendar" when only the bill was faked). Refs are now raw-only on both seed and adopt.
- **Hidden-tab guard:** `check()` bails when `document.visibilityState === "hidden"`, so a backgrounded tab
  doesn't poll. (This also means the automated preview reports "hidden" and the gate must be tested with a
  `visibilityState` override — noted for the next person.)
- Each feed refreshes independently: a calendar cycle invalidates the calendar cache + bumps `calRefresh`
  (re-running the three consumers' `loadCalendar` effects) WITHOUT dragging the 6.7 MB bill payload, and vice
  versa.

## 8. X-Ray (still Streamlit) — separate, lower priority

If the owner also manually refreshes the internal X-Ray (`pages/ray2.py`), the same freshness-gate idea applies
there, but Streamlit-side it carries the historical pain (§1). Lower priority — it's an internal diagnostic,
not the lobbyist surface. Note it; don't bundle it with the product fix.

See also [[architecture/calendar_pipeline]], [[state/current_status]], [[design/information_display]].
