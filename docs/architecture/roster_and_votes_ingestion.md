---
tags: [architecture, ingestion, roster, votes, war-room, scoping]
updated: 2026-07-17
status: active
open_loop: SCOPED, not built. Endpoints + fields all probe-confirmed structural (chair/party/district/votes). Unresolved before build — (1) companion-bill sourcing has no confirmed endpoint; (2) the votes store must NOT be Sheets (volume blows the 10M-cell ceiling) — D1 vs Azure-blob-mirror is an owner/architecture call; (3) whether roster/vote ingest lives in calendar_worker or its own worker.
---

# Roster & member-vote ingestion — scoping (the data under the War Room)

> **Status: SCOPED by live probe, NOT built.** Every field claimed by the War Room mockup
> (https://claude.ai/code/artifact/ef78b6ce-4d68-410d-918d-20db9ad6605c) was verified against the **live LIS
> API, session 20261** on 2026-07-17 — measure-first ([[workflow/reasoning_doctrine]]), not assumed. This page
> records exactly what LIS returns so the build is mechanical. It is a READ-from-LIS ingest, architecturally
> separate from the org WRITE path ([[ideas/war_room_scoping]] D2, Worker+D1).

## Why this exists
The War Room's entire "FROM LIS · verified" column group — committee roster, who chairs it, each member's party
and district, and their past votes — sits on data **we do not ingest today**. This was the hard blocker under
the whole feature. The blocker is now **de-risked to zero unknowns on the data itself**: it is all present and
all **structural** (Standard #3 — codes and ids, never text parsing).

---

## What the probe confirmed (2026-07-17, session 20261, `WebAPIKey` legacy key)

### 1. Committee roster + THE CHAIR — `MembersByCommittee/api/GetCommitteeMembersListAsync`
Params: `committeeID` (int, **required** — `committeeNumber` alone 400s), `sessionCode`. Wrapper:
`{MemberList, Success, FailureMessage, CacheKeyName}`. 31 rows for H21. Per-row fields:

| Field | Example | Use |
|---|---|---|
| `MemberID` | 170 | join key to member detail + votes |
| `MemberNumber` | `H0285` | stable structural id |
| `MemberDisplayName` / `PatronDisplayName` | "C.E. Cliff Hayes, Jr." / "Hayes" | display |
| **`CommitteeRoleTitle`** | **`Chair`** | **the chair question — ANSWERED, structural.** Vocab on H21: `{Chair:1, Vice-Chair:1, Member:29}` |
| `CommitteeRoleID` | 3 | structural role code (don't parse the title) |
| `VotingSequence` | 1 | committee vote order |
| `Seniority` | 0 | ranking |
| `AssignDate` | 2020-01-08 | tenure |

**→ The mockup's chair/vice-chair badges are a structural field read, not a heuristic.** This was the one
genuinely-unknown item flagged on the mockup; it is resolved.

### 2. Member detail (party + district) — `Member/api/GetMemberByIdAsync`
Params: `memberId`, `sessionCode`. Carries everything the roster row's LIS side needs beyond the name:

| Field | Example | Use |
|---|---|---|
| **`PartyCode`** | `D` | **the party-math table (9R·6D) — structural** |
| **`DistrictID` / `DistrictName`** | 91 / `91st` | district column |
| `ChamberCode` / `ChamberName` | `H` / `House` | chamber |
| `GABEmailAddress` / `GABPhoneNumber` | deljanderson@house.virginia.gov | contact scaffolding (org may want) |
| `MemberStatus` | `Active` | drop inactive/resigned members |
| `RoomNumber`, `SeatNumber`, `LastElectionDate` | — | dossier extras (C1, later) |

`Member/api/GetMemberListAsync` returns ALL members in one call (`ShallowMembers`, 64 KB, ~140 members) — the
efficient path: **one call for the whole chamber's party/district map**, then rosters just reference `MemberID`.

### 3. Member vote history — `MemberVoteSearch/api/GetMemberVoteListAsync`
Params: `memberId`, `sessionCode`. Wrapper `{MemberVoteList:[{…, VoteResult:[…]}]}`. **3,005 vote rows for one
member in one session** (512 committee, 2,222 floor). Per-vote fields:

| Field | Example | Use |
|---|---|---|
| **`ResponseCode`** | `Y` | **the member's OWN vote (Yea/Nay/etc.) — the field that makes a whip board possible** |
| **`LegislationNumber`** | `HB176` | **structural bill linkage** — filter by named bill, no text matching |
| `LegislationID` / `VoteLegislationID` | 98822 / 328338 | join keys |
| `VoteType` / `VoteTypeID` | `Committee` / 1 | **separates committee votes from floor** (whip cares about committee) |
| `CommitteeID` / `CommitteeName` | 2 / Appropriations | which committee |
| `VoteClassificationID` / `ClassificationName` | 2 / `Attendance` | **filter out quorum/attendance roll calls** — not substantive votes |
| `VoteDescription` | `Reported from Appropriations (22-Y 0-N)` | the tally (display) |
| `PassFail` | `P` | did the motion carry |
| `VoteDate` | 2026-01-21 | recency |

**→ The roster's "Vote on [named bill]" column is a structural filter**: this member's `VoteResult` where
`LegislationNumber == "SB1047"` and `ClassificationName != "Attendance"`, read `ResponseCode`. No judgment, no
text — which is exactly why the mockup names a *specific* bill and why "voted on this issue" (a judgment) was
deleted ([[design/information_display]] §P20c).

---

## The one storage finding that changes the architecture
**Member votes CANNOT live in Google Sheets.** ~140 members × ~3,000 votes/session × ~24 fields ≈ **10M cells
from votes alone** — at or past the Sheets ceiling that [[audits/fable_2026-07/codebase_longevity_audit]] (C-8)
already flags as a multi-year risk, and that's *one* session. This is not a Sheets-tab feature.

Options (owner/architecture call — do NOT default):
- **(A) Cloudflare D1** — the same store the org WRITE path already needs ([[ideas/war_room_scoping]] D2). Votes
  are relational (member × bill × committee × Y/N); D1 models them natively and the War Room reads its LIS side
  and its org side from one edge store. **Leaning here** — but it means LIS-read data and org-write data share a
  DB, so the trust partition ([[design/information_display]] §5b) must be enforced at the *table/column* level,
  not by store.
- **(B) An Azure-blob-style derived mirror** — we already treat `HISTORY.CSV`/`VOTE.CSV` as bulk blobs; member
  votes could be a periodically-rebuilt JSON/Parquet artifact the SPA reads directly (CDN-inversion pattern,
  [[audits/fable_2026-07/50_state_scaling_architecture]]). Keeps votes out of any live DB; weaker for ad-hoc
  query (the predictive lane wants query).
- Note: `VOTE.CSV` (the bulk blob we already fetch) may already carry per-member roll calls — **worth checking
  before adding per-member API calls**, since one blob beats 140 API calls (guardrail #1, fetch-less).

---

## Cadence & safety (must obey [[knowledge/lis_api_safety]])
- **Rosters are near-static within a session** — chair/membership change rarely. Fetch **once per session, then
  on a slow re-check** (a membership diff is itself a useful change-feed signal). Not per-cycle.
- **Votes accrue at meeting/floor cadence** — a member's list grows when they vote. Fetch **incrementally**,
  correlated to real activity (guardrail #5), keyed by `VoteID` so we only append new rows. Prefer the bulk
  `VOTE.CSV` blob (conditional-fetch/304, guardrail #1) over 140 per-member calls if it carries the same data.
- **Authorization:** session 20261/20251 only, via the existing `lis_authorization` gate
  ([[knowledge/lis_api_authorization]]). These endpoints returned 200 on the legacy `WebAPIKey`.
- **Request-cap:** a full roster+vote cold-start is ~1 chamber-member call + N committee calls + (ideally) 1
  vote blob — well under `LIS_REQUEST_CAP`. If we ever go per-member (140 calls), that's still bounded, but the
  blob is the right answer.

## 50-state isolation (Standard #6)
Every field above is **VA LIS-shaped** (`CommitteeRoleTitle`, `PartyCode`, `MemberVoteSearch`). The ingest must
land behind the same source-contract seam the calendar uses, so a second state swaps the *fetcher + field map*,
not the War Room. Record each new state's roster/vote endpoints as a sibling of this page (as
[[knowledge/lis_api_authorization]] §"onboarding state #2" requires).

---

## Still genuinely unknown (do not pretend otherwise)
1. **Companion-bill sourcing** (mockup's "Companion SB402"). No endpoint named for it in the inventory; may be
   derivable from patron + identical-title, or from a LegislationRelationship-type route not yet probed. **Flag,
   don't fake.**
2. **The votes store** — (A) vs (B) above is unresolved and is an owner/architecture decision.
3. **Worker placement** — does roster/vote ingest extend `calendar_worker.py` (shares the session gate + cache
   infra) or stand up as its own scheduled worker (cleaner isolation, its own cadence)? Leaning own-worker
   because its cadence (per-session, not per-meeting) differs from the calendar's.

## What this unblocks
- The War Room's entire LIS side (roster, chair, party math, past votes) — every number now has a named source
  ([[design/object_page_patterns]], the provenance table on the mockup).
- **The predictive lane** ([[ideas/predictive_lane]]) — a member × bill × Y/N matrix at 3,000 rows/member IS the
  training substrate roll-call models use. Ingest first; model second.

See also [[ideas/war_room_scoping]], [[architecture/strategic_tools_placement]], [[design/object_page_patterns]],
[[knowledge/lis_api_safety]], [[knowledge/lis_api_authorization]].
