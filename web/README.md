# VA Bill Tracker — front end (B3)

A $0 static SPA (React + Vite + TypeScript) for a Virginia General Assembly lobbyist. Built toward
the locked product vision (`docs/ideas/product_vision.md`): one dataset, four lenses, a global
Tracking↔full-GA switch, and a trust layer that never pretends to know.

## How it gets data
It reads the worker's output **straight from the Google Sheet via gviz** — the same auth-free path
the X-Ray uses — so there is no backend to run. `bill_tracker.py` writes the `Bill_Tracker` tab
(every-6h schedule); this app fetches it client-side.

- Source of truth: `Bill_Tracker` tab, sheet `1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM`
  (`src/config.ts`). The completeness/trust payload is read from cell **R1** of that tab.
- **Requirement:** the sheet must be **link-readable** (Share → Anyone with the link → Viewer).
  gviz reflects the request `Origin` in `Access-Control-Allow-Origin`, so the browser `fetch`
  works cross-origin from the Pages domain (verified).

## Views
- **Today** — the what's-new feed (full day, paged), an outcome summary, and a "next up" strip.
- **Timeline** — the crossover-lane pipeline: Senate above the centerline, House below; a bill
  literally crosses at crossover. Counts per side per stage; click a count to drill into the bills.
- **Calendar** — upcoming committee meetings (the full calendar integrates from the calendar subsystem).
- **Search** — faceted: search box + stacking filter chips, reusing the one bill-box component.
- **Health** — the operator trust signals (completeness, freshness, outcome derivation, patron coverage).

The bill card (every fact tied to its source + the recovered pin) is the component reused everywhere.

## Develop / build
```bash
cd web
npm install            # if the sandbox npm cache errors: npm install --cache .npm-cache
npm run dev            # local dev server (Vite)
npm run build          # type-check + production build → dist/
npm run preview        # serve the built dist/
```

## Deploy (Cloudflare Pages, free)
Connect the repo; set **Root directory** = `web`, **Build command** = `npm run build`,
**Output directory** = `dist`. No env vars or secrets (data is read client-side from the public sheet).

## Notes / follow-ups
- Tracked set + the global scope live in `localStorage` for now (clients/positions are parked in the
  vision §9). The ★ on any bill builds the Tracking set.
- Chief patron is the BILLS.CSV surname today; the bill-universe `Patrons` field carries the full name
  + MemberID (a planned backend upgrade). Co-patrons need a separate throttled `LegislationByMember`
  backfill (no bulk blob exists) — deferred. See `docs/ideas/lis_data_inventory.md`.
