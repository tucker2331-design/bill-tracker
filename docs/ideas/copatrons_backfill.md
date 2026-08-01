---
tags: [ideas, va, patrons, lis, deferred, plan]
updated: 2026-07-04
status: superseded
---

# Co-patrons — SUPERSEDED 2026-08-01: it is one bulk CSV

> **STOP. Do not execute the plan below.** `Sponsors.csv` is a bulk blob
> (`lisfiles/20261/Sponsors.csv`, 1.05 MB, HTTP 200) carrying `MEMBER_NAME, MEMBER_ID, BILL_NUMBER,
> PATRON_TYPE` — 18,221 rows across 3,595 bills, with a structural coded `PATRON_TYPE` vocabulary
> (`1001 - Chief Patron` appears exactly 3,595 times, 1:1 with the bills). **No endpoint discovery, no
> ~148 calls, no cadence decision.**
>
> **Why it was missed:** the blob is case-inconsistent (`BILLS.CSV` works, `Bills.csv` 404s;
> `Sponsors.csv` works, `SPONSORS.CSV` 404s), and we only ever knew of 4 files where the publisher lists
> 17. See [[knowledge/legacylis_csv_route]].
>
> The Phase-0 / guardrail analysis below is retained only as a record of what was believed.



The last VA product data item. **Chief patron is DONE** (full name, free from the universe payload —
PR #195). Co-patrons are a genuine bounded-backfill FEATURE, not a quick add. This page records exactly
what was confirmed 2026-07-04 and the build plan, so a future session executes without re-deriving.

## Confirmed facts (verified this session — do not re-probe LIS blindly)
- **Universe list endpoint** (`Legislation/api/getlegislationsessionlistasync`) carries a `Patrons` list
  per bill, but it is **CHIEF-ONLY** — verified all 3,645 lists are size 1, every `PatronTypeID==1`.
  So the free source that gave us the chief-patron full name does NOT include co-patrons.
- **BILLS.CSV** is **CHIEF-ONLY** too (reference: `Patron_id`/`Patron_name` = "CHIEF patron only — no
  co-patrons"). Not a source.
- **`LegislationPatron` endpoint** exists (per-bill, auth-required, non-bulk) → ~3,645 calls to cover
  every bill = a **ban risk**. REJECTED.
- **`LegislationByMember` endpoint** exists ("Bills by sponsor", per-member) → ~148 members = a
  **bounded, ban-safe** number. This is the path. BUT the exact URL/params are **UNKNOWN** — 3
  well-formed guesses 404'd, and lis.virginia.gov/developers is a SPA whose endpoint catalog is only in
  its JS bundle (not fetchable as text).

## Phase 0 — endpoint discovery (the blocker; needs browser/DOM tooling, ~1 h)
Use the [[knowledge/lis_dom_scraping]] technique (headless Chrome) OR inspect the developer-portal JS
bundle / a live member page's network tab to capture the real `LegislationByMember` request: exact path,
query params (likely `sessionCode` + a member key — `MemberID` or `MemberNumber`), and the response
shape. **Confirm it distinguishes chief vs co-patron per (member, bill)** (a `PatronTypeID`/`Name` like
the universe list). Record the verified endpoint in [[knowledge/lis_api_reference]]. Gate: one member's
response parsed, co-patron rows identifiable.

## Build plan (once the endpoint is confirmed)
1. **Member roster** (no new bulk risk): the ~148 distinct `MemberNumber`s are already in the universe
   payload's `Patrons[*].MemberNumber` (we fetch it anyway) — collect them there, or the `Member`
   endpoint. No separate roster call needed.
2. **Fetch + invert:** for each member, `LegislationByMember` → their bills with patron-type; keep the
   co-patron (PatronTypeID != 1) relationships; invert to `bill → [{name, member_number}]`.
3. **Schema:** append a `Co-Patrons (JSON)` column to `Bill_Tracker` (same append-then-shift-completeness
   discipline as the Floor columns — see [[failures/assumptions_audit#96]]: BUMP
   `WORKER_OUTPUT_LOGIC_VERSION`, and the front-end `gviz.ts` COL/COMPLETENESS_COL migration-safe read).
4. **Front end:** the bill card lists co-patrons under the chief patron (Omni-Schema: a normalized
   `co_patrons: [{name, id}]` field — see [[audits/fable_2026-07/50_state_scaling_architecture]] B2).
5. **Reconciliation counter:** `copatrons_bills` + a sanity check (sum of co-patron edges vs member bill
   counts) with a denominator; alert on an anomalous drop (Standard #1/#7).

## Guardrails + cadence (the reason this is a deliberate decision, not a quick add)
- 148 calls per backfill: **conditional fetch** where the endpoint supports it (ETag/If-Modified-Since);
  **jitter** + the **hard cap** already in the guarded session; **activity-correlated cadence**
  (guardrail 5): OFF-SEASON = a one-time static backfill (co-patrons don't change); IN-SEASON = a modest
  refresh (daily is ample — co-patron additions are not minute-sensitive). This ongoing in-session load
  must be justified against the charter before shipping — hence "deliberate decision."

## Why deferred (honest rationale)
(a) Phase-0 endpoint discovery needs browser tooling not in this session; (b) it adds ongoing in-season
LIS traffic that the charter says must be justified + cadence-set, not added casually; (c) it's a
SECONDARY display feature (chief patron + position + votes + calendar are the core, all shipped).
**Recommendation:** build alongside the [[audits/fable_2026-07/50_state_scaling_architecture]] CDN
inversion / Omni-Schema work (the data layer is being reworked then anyway), OR in a focused session that
has DOM tooling for Phase 0. Not a launch blocker.

See also [[ideas/lis_data_inventory]], [[knowledge/lis_api_reference]], [[knowledge/lis_api_safety]].
