---
tags: [knowledge, lis, api]
updated: 2026-07-31
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

## Reference / controlled-vocabulary endpoints (the "dictionary" endpoints)

**LIS publishes its controlled vocabularies as runtime-fetchable reference lists.** Consume these and runtime-validate against them (Standard #1: static values must have runtime validation that alerts on drift) instead of hardcoding/guessing the vocabulary. Discovered 2026-05-31 by probing `/developers/<Service>` + enumerating `Get…ListAsync` methods — see [[failures/assumptions_audit#58]].

### LegislationStatus list — the controlled Status vocabulary

`GET https://lis.virginia.gov/Legislation/api/GetLegislationStatusListAsync` (auth: `FCE351B6-…` key)

- Returns `{"References":[{"LegislationStatusID":int,"Name":str,"DisplayName":str, ["LegislationVersionID":int]}, …]}`.
- **52 entries** as of session 20261 (50 unique `Name`s — "Governor's Veto"/"Governor's Recommendation" each appear twice with different IDs). `Name` is what the per-event `Status` field carries (e.g. "Enrolled-House", "In House"); `DisplayName` is LIS's coarser label (e.g. "Enrolled-House" → "Enrolled").
- **Use:** the PR-C7.1b structural router groups these `Name`s into meeting (in-session: "In House", "Engrossed", "Reported Out-*", readings, conference, blank) vs admin (post-passage/clerical: "Enrolled-*", "Pending Governor's Communication", "Awaiting Governor's Action", "Approved", "Acts of Assembly Chapter", …). Grouping lives in `tools/c7_1b_eventcode_namespace/structural_router.py` (`ADMIN_PIPELINE_STATUSES` / `MEETING_INSESSION_STATUSES`); `validate_status_grouping()` checks our grouping covers the live list every run and alerts on a new/unseen status. Owner-approved as "consuming the source," not a banned dictionary.
- **Sibling probes that 404'd** (do not retry): `GetLegislationEventTypeListAsync`, `GetReferenceTypeListAsync`, `GetEventTypeListAsync` under both `/Legislation` and `/LegislationEvent`. But the **`…ReferencesAsync`** form DOES exist — see next.

### LegislationEvent type reference — the controlled EventCode vocabulary (discovered 2026-06-03)

`GET https://lis.virginia.gov/LegislationEvent/api/GetLegislationEventTypeReferencesAsync?sessionCode=20261` (auth: `FCE351B6-…` key)

- Returns **3,912 entries** for 20261, each keyed by `EventCode` (LIS's structural identifier, e.g. `S5620`, `H4130`, `G7210`) with fields: `LegislationDescription`, `CalendarDescription`, `JournalDescription`, `VoteDescription`, `LegislationChamberCode`, `ActorTypeID`, **`AdministrativeAction`**, **`IsPassage`**, `IsPassed`, `CommitteeComplete`, `CommitteeDescription`, `IsPublic`, `IsActive`, `ReconsiderationDescription`, `ActionReferences`, `EventReferences`.
- **This is LIS's own EventCode↔description map — the authoritative join between a HISTORY/event description and its structural EventCode.**
- **What the flags do and DON'T give you:**
  - `AdministrativeAction=true` flags only **37 SESSION-procedural** types (Adjourn, Call to Order, Period of Devotions, Elections) — NOT bill admin actions. "Signed by President" / "Placed on Calendar" are `AdministrativeAction=false`. **So it is NOT a meeting-vs-admin flag for bill actions** — don't use it as one.
  - `IsPassage=true` (68 codes) = passage votes (already caught by VoteTally).
  - `CommitteeComplete=true` (~2,372 codes) marks committee-context events.
  - There is **no clean meeting/admin category field.** The meeting/admin split must still be derived structurally (vote/timestamp/ministerial/G-prefix/Status).
- **Uses (PR-C7.1n):**
  1. **Admin recovery for date-drift-blank rows** — `build_admin_recovery_index()` / `recover_admin_route()` in `structural_router.py`: when a row can't be matched to its event by date (HISTORY date vs LegEvent date drift 1-9 days on governor/conference/reconvene actions), look the outcome up in these descriptions and route admin iff every mapped EventCode is admin (G-prefix or ministerial). Dictionary-free (LIS's own vocabulary), zero maintenance. See [[failures/assumptions_audit#69]].
  2. **The ministerial law** ([[failures/assumptions_audit#67]]) uses per-EventCode timestamp/vote behavior from the cache; the reference's canonical descriptions make it auditable.
- **Further standardization opportunities (not yet built):** (a) an EventCode drift monitor — alert when a data EventCode is absent from this reference (LIS added a new type), the EventCode analogue of `validate_status_grouping`; (b) extend recovery to re-anchor a row to its authoritative LegEvent date (fixes the date-drift at the join key, not just the route).


### Bill ↔ subject LINKAGE — RESOLVED 2026-07-27 (queue item P1)

**The dictionary and the index are two different endpoints.** `LegislationSubject` has exactly ONE method
(`GetSubjectReferencesAsync`) — it is the *dictionary* of categories and contains no bill data. The *index*
(which bills carry which subject) lives on the search service:

```
POST https://lis.virginia.gov/AdvancedLegislationSearch/api/GetLegislationListAsync
     WebAPIKey: <LIS_PUBLIC_API_KEY>
     Content-Type: application/json; charset=utf-8
     X-Pagination: {"PageNumber":1,"PageSize":50}
     body: {"SessionID": 59, "SubjectIndexID": 503}
```

- **`SessionID` (numeric), NOT `SessionCode`.** 20251 → 57, 20261 → 59 (derive at runtime from
  `Session/api/GetSessionListAsync`; never hardcode — Standard #1/#5).
- **Response `X-Pagination` header** carries `TotalCount`/`TotalPages`/`HasNext` — the count is available
  without walking pages, which is exactly what the Search facet counts need (PL-2 information scent).
- **⚠ Zero results return HTTP 204 with an EMPTY BODY, not 200 with `[]`.** A naive `json.loads(resp)` raises.
  Read `TotalCount` from the header and treat 204 as a legitimate empty set — **not** an error and **not** a
  missing subject. Same class as the sentinel-value confusions in [[failures/assumptions_audit]] #53.
- **Verified 2026-07-27** on session 20261: baseline (session only) = 2,836 bills; 20251 = 1,989. Of 12
  sampled subjects, 10 returned bills (Absentee Ballots 503 → 11, Administration of Government 2 → 108,
  Insurance 38 → 62, Internet 1080 → 6, …). Two returned 0 (Abortion 502, Constitutional Officers 624) —
  genuinely empty for that session, confirmed against a working baseline.
- The dictionary entry shape is `{"SubjectIndexID": int, "Subject": str, "SubjectNumber": str}` — **505
  entries**, `SubjectIndexID` range 1–1224, all unique. **`SubjectIndexID` is the join key**, not
  `SubjectNumber`.
- Discovery method (no blind probing): the LIS SPA bundle at `/static/js/main.*.chunk.js` declares its own
  API surface and the search-criteria field names. Read the client, then make one well-formed call.

**⚠ CORRECTION — there is NO "Privacy" subject.** Mockups v5–v8 used `Privacy · 3421`; **both the name and
the code were fabricated by me**, and the probe caught it. The real analogues are **Consumer Protection (75)**,
**Databases (644)**, **Information Management and Technology (758)**. Any mockup or spec referencing subject
3421 must be corrected.

**Unblocks:** Search subject facet + its counts, the Subject profile, the call-sheet subject row, and the
War-Room "voted on bills in this category" column.

## Currently integrated endpoints (used by `calendar_worker.py`)

### Session API

`GET https://lis.virginia.gov/Session/api/GetSessionListAsync`

- Returns all 58 sessions back to 1994.
- Key fields: `SessionID` (numeric), `SessionCode` (5-digit string e.g. "20261"), `SessionYear`, `IsActive`, `IsDefault`, `SessionEvents[]`.
- `SessionEvents` contain: `EventName`, `ActualDate`, `ProjectedDate`.
- Event types: "Session Start", "Adjournment", "Prefile Date", "Reconvene".
- 2026 Regular Session: `SessionID=59`, `SessionCode="20261"`.
- **`DisplayName` + `SessionType` were UNDOCUMENTED here until 2026-07-31** — the response also carries
  `DisplayName` ("Regular Session" / "Special Session I"), `SessionType` ("Regular"/"Special"),
  `SessionTypeID`, and `SessionYear`. **This is the authoritative human label for a session**, so the
  front-end masthead shows `f"{SessionYear} {DisplayName}"` instead of inferring one.
  **Do NOT derive the label from the code's last digit** ("20262" → special): that is an inference about a
  format nobody promised, and LIS publishes the answer. Probed live 2026-07-31: `20261` → "Regular Session",
  `20262` → "Special Session I" (`IsActive=True`).

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

> **🧭 CLASSIFICATION FIELDS — LIS classifies every action; consume this, do NOT build a dictionary or text-match.** (Promoted to a callout 2026-05-31 after we reached for text/dictionary 4× while these sat here unused since PR-C3 — see [[failures/assumptions_audit#57]].) Each event carries LIS's OWN structural type. **Authoritative measurement** (`probe_referencetype.py`, 37 bills / **1,068** events, file-captured):
> - **`ReferenceType`** — observed values + counts: `Vote` (473), `<blank>` (291), `LegislationText` (115), `LegislationFile` (86), `Committee` (61), `Subcommittee` (41), `Legislation` (1).
> - **`VoteTally`** — present ⟺ a recorded vote (266 events). The single cleanest meeting signal, but NARROW (only recorded votes; misses readings/reports that are also meetings).
> - **`IsPassed`** (bool), **`EventDate`** wall-clock time presence.
>
> **`ReferenceType` is NOT a clean binary router** (measured, do not over-trust): `Vote` includes non-votes ("Read first time", referrals) and only 262/473 carry a `VoteTally`; `<blank>` mixes floor meetings ("Read third time") with admin ("Enrolled", "Governor's Action Deadline"). **What routes cleanly:** `VoteTally` present → meeting; `LegislationText` + `LegislationFile` → documents/admin (201 events); `Committee`/`Subcommittee` ReferenceType → referral/assignment = admin. **Hard middle:** the `<blank>` + Vote-without-tally bucket needs the full-dataset measurement. Confirmed false-positive codes: H5601/S5601 = `LegislationText`, **G7210 = `<blank>`** (not "Communication"), none with a `VoteTally`. **`Description` is the plain-English meaning to DISPLAY (identical to LIS's site); the structural fields are for internal calendar-vs-ledger ROUTING. Never show a raw code to a lobbyist; never derive what LIS already labels.**
  - `BillHistoryReferences[]` — child array of supporting documents (PDFs, fiscal impact statements).
- **EventDate is the actual recorded action time.** Verified for the 4 Class-1 bugs:
  - HB111 (Feb 12 P&E): `2026-02-12T21:02:00`
  - HB505 (Feb 12 P&E): `2026-02-12T21:02:00`
  - HB972 (Feb 12 P&E): `2026-02-12T21:03:00`
  - HB609 (Feb 12 Finance): `2026-02-12T09:24:00`
- Two-step lookup pattern: `LegislationVersion → LegislationID → LegislationEvent`. LegislationID lookup is cacheable; events refresh per-cycle.

## Data Sources (Azure Blob)

### HISTORY.CSV

`https://lis.blob.core.windows.net/lisfiles/{sessionYear}/HISTORY.CSV` — **canonical, authoritative.** HTTP 200, ~4.7 MB, ISO-8859-1; CNAMEs to `blob.lvl04prdstr02c.store.core.windows.net`.

- ⚠️ **Dead alias (do not use):** `https://blob.lis.virginia.gov/lisfiles/{sessionYear}/HISTORY.CSV` — verified NXDOMAIN universally as of 2026-05-05. The CNAME to the canonical Azure host has been removed by LIS. Worker fallback that tried this URL first wasted ~10s + emitted a misleading WARN every cycle from PR-C7's first run through 2026-05-06; dropped in PR-C7.0.3. See [[failures/assumptions_audit#52]].
- Session 261 (year 2026): grew from 60,694 (project baseline) to 65,169 data rows + 1 header by 2026-05-05.
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
- Use `lis.blob.core.windows.net` ONLY for blob fetches. The legacy `blob.lis.virginia.gov` CNAME alias is dead (NXDOMAIN) — see HISTORY.CSV note above.
- `History_refid` may be empty for some action types (floor actions, executive actions).
- `sessionCode` is silently ignored on Schedule API but strictly enforced on new MVC endpoints (and in 5-digit form only there).
- Two distinct WebAPIKeys are required across the API surface — neither alone covers all endpoints.
- **Schedule entries can carry a RELATIVE time, not a clock time** (discovered 2026-06-03). Senate committee meetings are routinely scheduled as `ScheduleTime="15 minutes after the Senate adjourns"`. This is resolvable, NOT timeless: LIS also publishes a `OwnerName="Senate adjourned"` marker with the concrete clock time that day → `build_time_graph()` anchors the offset to it (#79 / [[failures/assumptions_audit#70]]).
- **A per-meeting Schedule entry can be MISSING ENTIRELY even though the committee met** (discovered 2026-06-05). SJ209's 3/10 Senate P&E meeting reported a bill (13-Y vote) but P&E's Schedule listings stop after 3/03 — no 3/10 row. The concrete time is still derivable from the committee's OWN published data: its **modal standing pattern** ("15 minutes after the Senate adjourns", 6/6 regular-session meetings) + the day's published "Senate adjourned 5:19 PM" = 5:34 PM. Implemented as `_build_standing_schedule_maps()` + `_derive_standing_committee_time()`, a FLAGGED last-resort (`Origin="derived_standing"`, X-Ray surfaces it as ASSUMED) that fires only after every real source. See [[failures/assumptions_audit#76]]. **This corrects the prior "SJ209 is irreducible" note — it was reconstructable from the committee's recurring published behavior.**

### MinutesBook (committee minutes — the authoritative meeting record)

`https://lis.virginia.gov/MinutesBook/api/getpublishedminutesbooklistasync?sessionCode={5d}&chamberCode={S|H}`

- The official published committee minutes (discovered 2026-06-05). Returns `Minutes[]` with `CommitteeName`, `MinutesDate`, `MinutesStatus` ("Closed"/"In Progress"), and `MinutesFiles[]` (HTML + JSON blob URLs). **Authoritative confirmation that a committee met on a date** — e.g. it confirms P&E's 3/10 meeting (book #3853, "Closed").
- Quirk: the `MinutesFiles` blob URLs currently 404 (publish/access gap, 2026-06-05), so the minutes CONTENT isn't fetchable via that path; and committee times in the minutes are recorded relatively anyway. Use the book LIST as a meeting-existence signal; derive the time via the standing-schedule path above.
- `getcommitteeminutessummaryasync` requires auth (401); `getminutesbookinteractivecalendarasync` needs `referenceNumber`+`sessionCode`.
- **HISTORY action date vs LegislationEvent date DRIFT 1-9 days** for governor / conference / reconvene actions (discovered 2026-06-03). The HISTORY.CSV date is NOT always the authoritative event date; the LegislationEvent date is. Any exact-date join between a HISTORY row and a LegEvent will miss these. Key off EventCode (via the EventType reference), not the date. See [[failures/assumptions_audit#69]].
- **`BILLS.CSV` is a fourth bulk blob** (`lisfiles/{session}/BILLS.CSV`, ~3,646 rows = every bill, one fetch — alongside HISTORY/DOCKET/VOTE). Columns: `Bill_id`, `Bill_description`, `Patron_id`/`Patron_name` (CHIEF patron only — no co-patrons), `Last_house_committee_id`/`Last_senate_committee_id` (structural codes), boolean outcome flags `Vetoed`/`Approved`/`Passed`/`Passed_house`/`Passed_senate`/`Failed`/`Carried_over`/`Emergency`, `Chapter_id` (Acts of Assembly chapter = ENACTED), `Full_text_doc1..6`, `Introduction_date`. The bulk source for patron + structural outcome (bill_tracker PR3). **No subject blob exists** (clean 404 on SUBINDEX/SUBJECT/etc.).
- **`LegislationStatus` feed ≠ `GetLegislationStatusListAsync` reference (LIS internal inconsistency, 2026-06-22).** The bill-list feed (`getlegislationsessionlistasync`) emits a bill status of bare **"Continued"** (442 bills in 20261) that is ABSENT from LIS's OWN published status list (which carries "Continued To"/"Continued to House"/… — action forms, not the bill-status form). Consequence: do NOT validate bill statuses against a status-name allow-list (hardcoded or runtime-fetched) — it false-flags forever. Derive bill outcome STRUCTURALLY from BILLS.CSV flags + `Chapter_id`, and validate any text fallback against those flags (self-calibrating), not against a name list. Also: `Chapter_id` present ⇒ enacted even when `Approved=N` (joint resolutions chapter without a Governor's signature).

## See also

- [[knowledge/lis_dom_scraping]] — when API isn't enough, headless Chrome bypass for the SPA.
- [[architecture/calendar_pipeline]] — how these endpoints flow through the worker.
- [[testing/crossover_audit]] — the audit that identified the Class-1 / Class-2 bug split this API set is meant to fix.
