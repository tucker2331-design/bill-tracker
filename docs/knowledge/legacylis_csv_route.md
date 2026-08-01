---
tags: [knowledge, api, compliance, lis, historical, calibration, source]
updated: 2026-08-01
status: active
---

# The legacy LIS CSV route — FOUND (2026-08-01)

**This supersedes [[state/va_build_queue]] C1 ("PROBED 2026-07-27. NO BULK CSV ROUTE FOUND"). The route
exists.** The earlier probe looked for `SiteInformation/csvinfo.html`; the page is
**`SiteInformation/ftp.html`**. One wrong filename was the whole blocker.

## The route

```
https://legacylis.virginia.gov/SiteInformation/csv/<code>/<File>.csv
```

Index page (lists the files, links relative): <https://legacylis.virginia.gov/SiteInformation/ftp.html>

`<code>` is the **2-digit year + session type** (`241` = 2024 regular, `242` = 2024 special) — the same
convention as the modern blob, minus the century. **Not** the modern 5-digit `20241`.

## Why this is the lawful channel

[[knowledge/lis_api_authorization]] quotes the Developers Portal verbatim: *"If you require data prior to
the 2025 session, please use `legacylis.virginia.gov` via CSV download."* This IS that download. The
2025/2026-only rule binds `lis.virginia.gov/*/api/*` and `lis.blob.core.windows.net/lisfiles/*`; the legacy
CSV area is the sanctioned alternative, not a loophole. Support is DLAS's own help desk
(helpdesk@dlas.virginia.gov, 804-786-9631), listed on the page.

## What is actually there — MEASURED 2026-08-01, one HEAD per session

| code | bills | verdict |
|---|---|---|
| `231` | **3,029** | 2023 regular — **COMPLETE, usable** |
| `241` | **3,595** | 2024 regular — **COMPLETE, usable** |
| `242` | 290 | 2024 special — complete for a special session |
| `221` | **363** | 2022 — **PARTIAL, DO NOT USE as a session.** The 2022 regular session ran ~2,900 bills; this holds 363, starting at HB29/HB30 (the budget bills). Whatever it is, it is not a whole session, and treating it as one would silently understate every 2022 denominator. |
| `211` and earlier | — | **404.** Swept every regular session 2000–2021, one request each: nothing. |

Sweep was one `HEAD` per candidate, 0.4 s apart, on the sanctioned host. There is **no directory listing**
(`/csv/` returns 403), so the range can only be established by asking.

## The schema is IDENTICAL to the modern blob — this is the important part

Compared header-for-header against `lisfiles/20261/`:

- **`Bills.csv` — all 41 columns match exactly**, same order, same names (`Bill_id` … `Last_actid`).
- **`History.csv` — matches exactly**: `Bill_id, History_date, History_description, History_refid`.
- **`Vote.csv` — same headerless positional format** (row 0 is a vote id like `H0101V0001`, then
  member/response pairs).

**So `_build_bills_meta` and the HISTORY parser read legacy files unchanged — no mapping layer, no
adapter, no per-era branch.** That was the risk worth checking and it came back clean.

Volumes for `241`: History **55,237 rows**, Vote **9,558 rows**.

## The one real gap: DOCKET is empty

`Docket.csv` is **40 bytes — the header and nothing else** — for every legacy session
(`"Com_no","Doc_date","Doc_no","Bill_no"`). So there is **no committee-docket history before 2025.**

- **Does not block** outcome/vote calibration, which needs Bills + History + Vote.
- **Does block** anything reconstructing *which bills were on which committee agenda* historically — so a
  backtest of docket-derived meeting placement cannot reach back. State that limit rather than discovering
  it mid-backtest.

## What this changes

The calibration base goes from **2 sessions (2025, 2026)** to **4 complete ones (2023, 2024, 2025, 2026)**,
plus the 2024 special. That directly answers the [[state/va_todo_2026-07-30]] §4 blocker
(*"blocked on historical data and that is unsolved"*) and materially loosens §1's composition problem: a
committee with one chair change now has more than a single usable session on each side of it.

**Still true:** pre-2023 does not exist on this route. If the backtest needs a decade, the remaining options
are a DLAS request (they publish it; one email) or LIS authorising earlier sessions on the new API. Both
were already the fallback and neither is now urgent.

## Rules for using it

1. **Never fetch pre-2025 from the blob or the API** — that authorization is unchanged.
2. **Treat `221` as unusable** until someone establishes what it is.
3. **Pin the known-good set** (`231`, `241`, `242`) the same way `LIS_HISTORICAL_AUTHORIZED` pins the
   modern one, so a future sweep cannot silently widen it.
4. **Cache locally.** These files are static — a session that ended in 2024 will not change — so fetch once
   and keep. Re-downloading on every backtest run is load DLAS should not have to absorb.
