---
tags: [knowledge, api, districts, accounts, privacy, redistricting]
updated: 2026-07-27
status: active
---

# District lookup + the redistricting signal — RESOLVED (queue item P2)

**One federal API answers both halves of P2, needs no key, and stores nothing.**

## The service

```
GET https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress
    ?address=<one-line address>
    &benchmark=Public_AR_Current
    &vintage=Current_Current
    &format=json
```

- **No API key.** No registration, no quota negotiation, no terms attestation. (Contrast LegiScan, rejected
  for exactly that reason — [[knowledge/legiscan_terms]].)
- **Verified live 2026-07-27** against a public building (1000 Bank St, Richmond — the Virginia State
  Capitol). One call returned all three districts we ask for:

| Layer | Returned |
|---|---|
| `2024 State Legislative Districts - Upper` | State Senate District **14** |
| `2024 State Legislative Districts - Lower` | State House District **78** |
| `119th Congressional Districts` | Congressional District **4** |

- District number is in `SLDUST` (upper) / `SLDLST` (lower) / `CD119` (congressional); `NAME` carries the
  human label.

## How we use it — the address never lands anywhere

The user types an address **only if they don't know their districts**. We call this API, show them the three
districts, and they **enter/confirm them**. The address is a transient function argument:

- **Never persisted**, never logged, never sent to our own backend. Ideally the call is made **client-side**
  so the address never touches our infrastructure at all — then "we don't store addresses" is enforced by
  topology, not policy.
- What we store is three small integers the user confirmed. That is the whole point of asking for districts
  instead of addresses ([[ideas/war_room_scoping]]).
- Census is a federal statistical agency, not an ad network — a materially different disclosure than handing
  an address to a commercial enrichment vendor.

**Open (small):** confirm the endpoint sends permissive CORS headers for a browser-side call. If it does not,
the call must proxy through our Worker — in which case the address transits our infrastructure and must be
**used and dropped in the same request**, never written to a log line or a D1 row.

## The redistricting signal — the same API, no shapefile needed

**The layer NAME carries the map vintage** — `2024 State Legislative Districts`. That string is the signal we
were missing.

**Detector:** geocode **one fixed public address** (the Capitol) on a slow schedule and read the year in the
district-layer key. When it changes, the maps have been redrawn → prompt every user to re-confirm their
districts.

- **Zero PII** — a government building, not a person.
- **One call**, on a slow cron. Cheaper than any boundary-file diff.
- **No geometry, no shapefile, no TIGER/Line download.** We only ever needed to know *when to re-ask*, not
  where the lines are — the reframe that ended this probe. Census TIGER/Line SLDU/SLDL is **not needed**.
- Benchmarks and vintages are enumerable (`/geocoder/benchmarks`, `/geocoder/vintages?benchmark=<id>`) if a
  more precise check is ever wanted; the layer-name year is sufficient and cheaper.
- **Fail-open:** if the detector call fails, do nothing and alert — never silently mark districts stale, and
  never block login. The 6-month periodic re-confirm is the floor and runs regardless.

## Why this was a probe at all

`roster.py` returns district *numbers* and who holds them — **a boundary can move while the number stays
"23"**, so redistricting is invisible to every source we already ingest. That gap was self-inflicted: an
event-triggered re-confirm was proposed without naming a source ([[state/va_build_queue]] P2).

## Standards check
- **#1 zero assumptions** — the vintage is read at runtime, never hardcoded.
- **#5 dynamic configuration** — no static district table; the API is the source.
- **#6 50-state scaling** — the same federal endpoint returns state legislative districts for **every**
  state. Nothing here is Virginia-specific, so state #2 inherits it unchanged.
- **#8 zero routine maintenance** — the detector needs no human until it actually fires.
