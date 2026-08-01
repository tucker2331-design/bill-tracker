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

---

## The bigger finding: we were using 4 of the publisher's 17 files

Enumerating the legacy page's full file list against the **modern** blob (authorized session `20261` only)
found **9 bulk files we have never used**. Measured 2026-08-01:

| file | bytes (20261) | what it unblocks |
|---|---|---|
| **`Sponsors.csv`** | 1,054,196 | **CO-PATRONS — see below** |
| `Summaries.csv` | 4,253,875 | bill summaries in bulk |
| `VoteStatements.csv` | 372,074 | recorded vote explanations |
| `Amendments.csv` | 59,804 | amendment records |
| `SubCommitteeMembers.csv` | 13,963 | subcommittee rosters |
| `SUBDOCKET.CSV` | 12,595 | subcommittee dockets |
| `Members.csv` | 6,705 | member roster (bulk) |
| `CommitteeMembers.csv` | 6,520 | committee rosters (bulk) |
| `Committees.csv` | 1,858 | committee list (bulk) |

**The blob is CASE-INCONSISTENT and that is why these were missed.** `BILLS.CSV` works and `Bills.csv`
404s; `Sponsors.csv` works and `SPONSORS.CSV` 404s. There is no single casing rule — each filename must be
tried as the publisher writes it. Anyone probing with one convention concludes the file does not exist.

**Genuinely absent from the modern blob** (both casings): `CIBILLSUBJECTS`, `CIPARENTCHILDSUBJECTS`,
`FISCALIMPACTSTATEMENTS`, `SECTION`.

### `Sponsors.csv` closes E6 (co-patrons)

[[ideas/copatrons_backfill]] scoped co-patrons as blocked on DOM-discovering a `LegislationByMember`
endpoint, then ~148 throttled calls per backfill, with a cadence decision needed before shipping.
**It is one bulk CSV we already had access to.**

Schema: `MEMBER_NAME, MEMBER_ID, BILL_NUMBER, PATRON_TYPE`. Measured on `241`: **18,221 rows across 3,595
bills**, and `PATRON_TYPE` is a **structural coded vocabulary**, not prose:

```
1001 - Chief Patron            3,595   (exactly one per bill — 1:1 with the bill count, which validates the file)
1999 - Co-Patron              10,694
2999 - Co-Patron               2,901
1041 - Chief Co-Patron           766
2041 - Chief Co-Patron           143
1051 - Incorporated Chief Co-Patron  28
…plus 1042/1043/1044/1002/1003/2099/1004/1005
```

Patrons per bill: 1,805 bills have one, 614 have two, 273 have three; the maximum is **HJ0302 with 140**.

**This also answers the owner's question about legislators backing a bill without being a co-patron**
(2026-07-31: *"isn't there a way for legislators to show support for a bill without being a co patron? like
it's like being a signature"*). The answer is in the vocabulary: VA distinguishes **Chief Patron**, **Chief
Co-Patron**, **Co-Patron**, and **Incorporated Chief Co-Patron**. The M6 patron dropdown should render
whatever roles the data carries rather than a hardcoded two-way split — that ports to 50 states unchanged.

**Verify before building:** `Sponsors.csv` was confirmed present on `20261` by HEAD. Its schema was read
from the cached `241` copy. Confirm the modern file's header matches before wiring it into `bill_tracker`.

### Subject linkage exists ONLY in history

`CiBillSubjects.csv` is **404 on the modern blob but present on legacy** (`231` 314,409 bytes; `241`
361,270). So [[knowledge/lis_api_reference]]'s "no subject blob exists" is **correct for the current
session and wrong for history**. Both subject files are now cached for `231`/`241`; `242` does not publish
them. A historical subject analysis is possible; a live one still needs the per-bill endpoint.
