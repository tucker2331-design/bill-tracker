---
tags: [knowledge, lis, api]
updated: 2026-04-25
status: active
---

# Virginia LIS API Reference

## Public developer portal

The full LIS API surface is documented at <https://lis.virginia.gov/developers>
(rendered by the React SPA — `curl` returns the shell, headless Chrome with
`--virtual-time-budget=20000 --dump-dom` renders the real content). Each
service has a per-service doc page at
`https://lis.virginia.gov/developers/<ServiceName>` which lists endpoints,
verbs, parameters, and response schema. **This portal is the source of
truth — update this page from there, not from grep'ing the SPA bundle, when
adding a new endpoint.**

## Two API keys (don't confuse them)

There are two publicly-discoverable `WebAPIKey` values in production today:

| Key | Source | Works for |
|---|---|---|
| `81D70A54-FCDC-4023-A00B-A3FD114D5984` | `calendar_worker.py` (legacy worker) | `Schedule/api/getschedulelistasync`, `Committee/api/getcommitteelistasync`, `Session/api/GetSessionListAsync` |
| `FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9` | `lis.virginia.gov/handleTitle.js` (the SPA's own utility script) | All new MVC-style endpoints (LegislationEvent, LegislationVersion, AdvancedLegislationSearch, ...). Returns 401 if absent or replaced with the legacy key. |

Both are `WebAPIKey` HTTP header values. Both are PUBLIC — they appear in
unauthenticated browser context. There is also a separate `Partner WebAPIKey`
header for partner-tier APIs, which we don't have.

## Session-code formats — the gotcha

Two formats coexist:

- **Legacy 3-digit form** — `261` (year + session-type-digit). Accepted by
  the Schedule / Committee / Session APIs.
- **Full 5-digit form** — `20261` (year + session-type-digit, year-prefixed).
  Required by all new MVC-style endpoints (LegislationEvent etc.). 3-digit
  form returns `"Provided Session Code is invalid"` on those.

Both forms reference the same session. When in doubt, query
`Session/api/GetSessionListAsync` and use the `SessionCode` field directly
(it's already the 5-digit form on records, but the legacy endpoints back-map).

The numeric `SessionID` is yet a third identifier (e.g. `59` for the 2026
Regular Session) — used by some endpoints as `sessionID` parameter.

## Available API services (full inventory)

Verified against the public dev portal 2026-04-25. Items in **bold** are
currently used by `calendar_worker.py`. Items marked _(in scope for
PR-C3+)_ are queued for integration.

| Service | Public reads | Used? | Notes |
|---|---|---|---|
| AdvancedLegislationSearch | yes (POST search bodies) | no | Bill search by criteria; backs the SPA's bill-search UI |
| Authentication | (login only) | no | Not for public scraping |
| Calendar | yes | no | Floor calendar (chamber order-of-business), distinct from committee Schedule |
| **Committee** | yes | **yes** | `getcommitteelistasync?sessionCode=261` — already integrated |
| CommitteeLegislationReferral | yes | no | Reserved for future committee-attribution work (PR-C4 retired 2026-04-26 — see [[state/current_status#class-2-collapse-via-legislationevent-pr-c31-side-effect]]; this endpoint becomes the primary tool if Sheet1 `Committee` accuracy is later promoted to a tracked metric) |
| CommunicationFileGeneration | (generation) | no | |
| Contact | (admin) | no | |
| Legislation | yes | no | Bill metadata by ID list |
| LegislationByMember | yes | no | Bills by sponsor |
| LegislationCollections | yes | no | User watchlists |
| LegislationCommunications | yes | no | |
| **LegislationEvent** _(in scope for PR-C3)_ | yes | no | **Per-bill action history with `EventDate` (minute-precision timestamps).** This is the secondary time source for Class-1 bug recovery. See full spec below. |
| LegislationFileGeneration | (generation) | no | |
| LegislationPatron | yes | no | |
| LegislationSubject | yes | no | |
| LegislationSummary | yes | no | |
| LegislationText | yes | no | Bill text + versions |
| **LegislationVersion** _(in scope for PR-C3)_ | yes | no | **Bill-number → LegislationID lookup. Required hop before calling LegislationEvent.** |
| Member | yes | no | Delegate / Senator info |
| MemberVoteSearch | yes | no | |
| MembersByCommittee | yes | no | |
| MinutesBook | yes | no | Daily journal source — could be useful for journal-collapse work |
| Organization | yes | no | |
| PartnerAuthentication | (partner only) | no | |
| Person | yes | no | |
| Personnel | (admin) | no | |
| **Schedule** | yes | **yes** | `getschedulelistasync?sessionCode=261` — already integrated. **Note: ~16% of session-month entries have empty `ScheduleTime`; some committee meetings are missing entries entirely. This is the data gap PR-C3 fills.** |
| **Session** | yes | **yes** | `GetSessionListAsync` — already integrated |
| Statistics | yes | no | Session statistics dashboards |
| User | (account) | no | |
| Vote | yes | no | Vote tallies |

## Currently integrated endpoints (used by `calendar_worker.py`)

### Session API

`GET https://lis.virginia.gov/Session/api/GetSessionListAsync`

- Returns all 58 sessions back to 1994.
- Key fields: `SessionID` (numeric), `SessionCode` (5-digit string e.g. "20261"), `SessionYear`, `IsActive`, `IsDefault`, `SessionEvents[]`.
- `SessionEvents` contain: `EventName`, `ActualDate`, `ProjectedDate`.
- Event types: "Session Start", "Adjournment", "Prefile Date", "Reconvene".
- 2026 Regular Session: `SessionID=59`, `SessionCode="20261"`.

### Committee API

`GET https://lis.virginia.gov/Committee/api/getcommitteelistasync?sessionCode={code}`

- Returns committees for a given session.
- Key fields: `CommitteeID`, `Name`, `CommitteeNumber` (H01-H24, S01-S13), `ChamberCode` (H/S), `ParentCommitteeID`.
- `ParentCommitteeID` is null for top-level committees, integer for subcommittees.
- Session 261: 25 top-level committees confirmed.

### Schedule API

`GET https://lis.virginia.gov/Schedule/api/getschedulelistasync?sessionCode={code}`

- Returns ALL scheduled meetings for the session — past + present + future. Range observed: Oct 2022 → Dec 2026 (3,381 entries).
- Key fields: `OwnerName`, `ScheduleDate`, `ScheduleTime`, `Description` (HTML), `IsCancelled`, `RoomDescription`, `CommitteeNumber`.
- **`sessionCode` parameter is silently IGNORED** — same payload returned for `261`/`251`/`241`/anything (always returns active session).
- **~16% of entries have empty `ScheduleTime`** during active session months (Jan/Feb/Mar). Cluster on House committees (Privileges and Elections, Finance, General Laws, Labor and Commerce). When `ScheduleTime` is empty, `Description` often contains a dynamic time ("Immediately upon adjournment of House Education"); the worker's `build_time_graph()` resolves these.
- **Some real committee meetings are missing entries entirely** — confirmed via the crossover audit: HB111/505/972 met in House P&E on Feb 12 (per HISTORY.CSV) but the API has zero P&E entries on that date. Same for HB609 / House Finance on Feb 12. These are the Class-1 bugs that LegislationEvent recovers.

## In-scope endpoints (PR-C3)

### LegislationVersion API — bill-number → LegislationID lookup

`GET https://lis.virginia.gov/LegislationVersion/api/GetLegislationVersionbyBillNumberAsync?billNumber={billNum}&sessionCode={fivedigit}`

- **Auth:** `WebAPIKey: FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9` (the SPA public key, NOT the legacy worker key).
- **`sessionCode` MUST be 5-digit** — `20261`, not `261`. Legacy form returns "Provided Session Code is invalid".
- Returns `{LegislationsVersion: [{LegislationID, LegislationNumber, ChamberCode, SessionID, ...}]}`.
- LegislationID is stable per session — safe to cache in-memory across cycles.
- Example: `HB111` in session `20261` → `LegislationID=98749`.

### LegislationEvent API — per-bill action history with timestamps

`GET https://lis.virginia.gov/LegislationEvent/api/GetPublicLegislationEventHistoryListAsync?legislationID={id}&sessionCode={fivedigit}`

- **Auth:** same `FCE351B6-...` public key.
- **Both params required** — error message says `"Please provide a LegislationID and a SessionCode"` if either is missing.
- Returns `{LegislationEvents: [...]}`. Each event:
  - `LegislationEventID` (numeric), `EventCode` (e.g. `H8122` "House committee offered"), `EventDate` (`YYYY-MM-DDTHH:MM:SS` — **minute-precision wall-clock time**), `Description`, `LegislationNumber`, `ChamberCode`, `SessionCode`.
  - `CommitteeNumber` and `CommitteeName` may be `None` for vote-style events. **Caveat (post-PR-C3.1): this endpoint gives us TIME but not always COMMITTEE for the vote-style actions. The TIME recovery alone was sufficient to collapse all 9 crossover-week bugs (Class-1 + Class-2) because the project's accuracy metric is meeting actions without times, not committee-name accuracy. PR-C4 retired 2026-04-26 — see [[state/current_status#class-2-collapse-via-legislationevent-pr-c31-side-effect]].**
  - Reference fields: `ReferenceID`, `ReferenceNumber`, `ReferenceTypeID`, `ReferenceType` (e.g. "Vote"), `ActorType` (e.g. "House"), `LegislationTextID`.
  - `BillHistoryReferences[]` — child array of supporting documents (PDFs, fiscal impact statements).
- **EventDate is the actual recorded action time.** Verified for the 4 Class-1 bugs:
  - HB111 (Feb 12 P&E): `2026-02-12T21:02:00`
  - HB505 (Feb 12 P&E): `2026-02-12T21:02:00`
  - HB972 (Feb 12 P&E): `2026-02-12T21:03:00`
  - HB609 (Feb 12 Finance): `2026-02-12T09:24:00`
- Two-step lookup pattern: `LegislationVersion → LegislationID → LegislationEvent`. LegislationID lookup is cacheable; events refresh per-cycle.

## Data Sources (Azure Blob)

### HISTORY.CSV

`https://lis.blob.core.windows.net/lisfiles/{sessionYear}/HISTORY.CSV`

- Alternative: `https://blob.lis.virginia.gov/lisfiles/{sessionYear}/HISTORY.CSV`
- Session 261 (year 2026): 60,694 rows.
- Key columns: BillNumber, HistoryDate, Description, History_refid.
- History_refid encodes committee codes: "H14" (direct), "H14V2610034" (vote-style).

### DOCKET.CSV

`https://lis.blob.core.windows.net/lisfiles/{sessionYear}/DOCKET.CSV`

- Committee meeting bill assignments.
- Senate committees S01-S13 confirmed.
- Key columns: bill number, date, committee/description.

## Known Quirks

- Schedule API `ScheduleTime` can be relative ("upon adjournment of the Senate"); see `build_time_graph()`.
- Description field is HTML, may contain links to PDF agendas.
- HISTORY.CSV encoding is ISO-8859-1, not UTF-8.
- Some blob URLs use different subdomain patterns (blob.lis vs lis.blob).
- `History_refid` may be empty for some action types (floor actions, executive actions).
- `sessionCode` is silently ignored on Schedule API but strictly enforced on new MVC endpoints (and in 5-digit form only there).
- Two distinct WebAPIKeys are required across the API surface — neither alone covers all endpoints.

## See also

- [[knowledge/lis_dom_scraping]] — when API isn't enough, headless Chrome bypass for the SPA.
- [[architecture/calendar_pipeline]] — how these endpoints flow through the worker.
- [[testing/crossover_audit]] — the audit that identified the Class-1 / Class-2 bug split this API set is meant to fix.
