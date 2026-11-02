---
tags: [knowledge, pennsylvania, multistate, source-contract, xml, rss]
updated: 2026-10-31
status: active
open_loop: The next-meeting join reads the committee-schedule RSS's own Bills field, but on the 2026-10-31 sample all 7 meetings list no bills (session winding down), so the populated join is unproven on real data — capture an in-session schedule sample (January 2027) and add it to the PA goldens.
---

# Pennsylvania bulk feeds — the source contract (measured 2026-10-31)

Measured on REAL downloads, committed with a manifest at `tools/historical_cache/pa/2025_0/` (URLs, sizes, SHA-256).
Adapter: `states/pa_adapter.py`; fetcher: `states/pa_fetch.py`; config: `states/pa.py`; goldens: `test_pa_intake.py`.

## Access rules (owner, 2026-10-31)
- **robots.txt** (fetched, 284 bytes, Last-Modified 2024-03-06): one group only, for the *UserWay ADA scanner*
  user-agent. No `User-agent: *` group, so nothing applies to us. That group protects `/legislation/bills/*` and
  `/cfdocs/`, and we respect the spirit: **bulk feeds only, never a per-bill page.**
- Terms (owner checked 2026-10-29): no use restriction, AS-IS disclaimer only.
- **All feeds live on `www.palegis.us`** — the export is served from there directly (no redirect, no CDN host).
- **No conditional GET:** none of the responses carried `ETag` or `Last-Modified`. The fetcher therefore caps
  each URL at one request per hour (the export's own cadence) and serves the cache otherwise.
- User-Agent: `bill-tracker-intake/0.1 (+https://github.com/tucker2331-design/bill-tracker)` — the repo is the contact
  (owner 2026-11-01; the first fetches on 2026-10-31 also carried an email). A 401/403/429 stops the intake — no retry,
  no header change (`FeedRefused`).

## Feeds
| Feed | URL | Shape |
|---|---|---|
| Data index | `/data` | HTML; lists every Bill History export (39 sessions, `1969_0` … `2025_0`) and every RSS feed. The current regular session is read from it (`current_regular_session`), never hardcoded. |
| Bill History export | `/data/file?documentType=BillHistoryData&session=YYYY_N` | **A ZIP** (content-type says `application/xml`) holding one XML; filename stamps the export time (`…-202610311932.zip`). `2025_0`: 1.7 MB zipped, 19.9 MB XML. |
| Committee schedule | `/{house,senate}/rss/committee/schedule` | RSS 2.0 + `parss:` namespace: `MeetingDate`, `MeetingTime` ("Call of Chair" = PA's to-be-announced), `Committee`, `Location`, **`Bills`** (the agenda), `InCapitol`. |
| Committee assignments (rosters) | `/{house,senate}/rss/committee/assignments` | RSS, one `<item>` per MEMBER (House 201, Senate 49 on 2026-11-01): `<link>` carries the structural `memberId`; `<parss:Committee position="Chair\|Vice Chair\|Secretary\|">` per standing committee; `<parss:Subcommittee committee=…>`; `<parss:District>`. **No committee id** — committees are named, "&" spelled out. House labels BOTH the majority and the minority chair "Chair" (Education: Cutler R + Schweyer D); shown as the feed says. Read by `states/pa_roster.py`. |
| Members | `/{house,senate}/rss/session/members` | RSS, one `<item>` per member, same `memberId` in `<link>`, `<parss:Party>` (D/R), addresses. Party joins on memberId (all 250 agree with the assignments title, checked in `test_pa_roster.py`). |
| Others (not used yet) | `/{house,senate}/rss/session/{votes,calendar,journals,amendments,…}` | per publication |

## Why 0 of the 7 scheduled meetings list bills (diagnosed 2026-11-01)
Checked by hand, once: the Senate meeting-schedule page (`/senate/committees/meeting-schedule`, the RSS items' own
`<link>`; 1 request, honest UA) — the same meetings, with descriptions the RSS does not carry. The 7 RSS entries are:
- **2 × House Appropriations, "Call of Chair"** (9 and 10 Nov) — PA's to-be-announced slot; no agenda posted yet.
- **1 × Senate Transportation, 13 Nov, at an airport boardroom** — the page calls it a *"public hearing on aviation
  investment and reform"*: a hearing takes testimony and votes on no bills.
- **4 × legislative AGENCIES, each listed in BOTH chambers' feeds** — IRRC (19 Nov; its agenda is *regulations*, not
  bills) and the Center for Rural Pennsylvania board (17 Dec). The page files them under "Meetings of legislative
  agencies"; they never carry bills.

**Verdict:** not a broken feed and not "agenda not posted" across the board — the list is all hearings, agency meetings
and two unannounced Appropriations slots, in the post-election lull (election 3 Nov 2026). Whether the `Bills` field is
populated for a voting meeting is still UNPROVEN (no populated example seen; archive.org is outside this
environment's network policy) — capture an in-session schedule in January 2027 (open loop above).
**No future session days are published as a feed:** the data page lists none, and the session-calendar RSS
(`/{house,senate}/rss/session/calendar`, fetched once 2026-11-01: 36 / 37 items) lists the bills for "the next session
day" without that day's date. So the PA calendar shows session days once the export records floor business.

## The 22 "Undefined Action" rows (investigated 2026-11-01)
PA's own `<verb>Undefined Action</verb>` labels real parliamentary motions it has not coded. On 2025_0: motion to
reconsider final passage (3: HB1099, HB1859, HB1866, each after a defeat; the export never records the motion's
result), first consideration rescinded (3), "Reconsider the vote by which the House accepted the report…" (4: SB146 ×2,
HB2359, HB2460 — each followed by a coded re-report), referred to House/Session Calendar (5), removed from uncontested
calendar (2), motion to report defeated (1: HB1200, 3-7 — a committee kill, text only), amended / bill gone over (1),
originated in Committee on Rules (1), revert to prior printer's no. (1), amended on concurrence (1).
**None moves a bill wrongly** (they never route — Standard #3); the only status they could change is the 3 House
reconsideration motions, whose outcome the export does not carry. They show in history and in What's new as the
source's own text (Codex #260).

## Committee roster join (2026-11-01)
The export's `<committee>` ("AGING AND OLDER ADULT SERVICES") and the roster feed ("Aging & Older Adult Services") name
the same room. PA publishes no committee id, so `committee_key` = exact equality after ONE fixed mapping (upper case,
"&" → "AND"). Measured on the real samples: 54 roster committees; **every one of the 5,184 bills that name a current
committee finds its roster (0 missing)**. Runtime check: `bills_committee_without_roster` on PA Health, limit 0 — a
rename on one side shows up red, never as an empty list. 4 requests (fetched once, committed with the manifest).

## Bill History XML (2025_0)
`<historyExport exportDate totalDocuments=5269>` → `<session year=2025 session=0>` → 5,269 `<bill id="20250HB0017"
lastUpdate>` (2,757 HB · 1,427 SB · 673 HR · 412 SR). Per bill: `body` (H/S), `type` (B/R + description),
`number`, `shortTitle`, `cosponsorshipMemo@memoUrl`, `sponsors/sponsor` (71,213: `sequenceNumber`, `party`,
`body`, `districtNumber`; surname text, **no member id**), `printersNumberHistory/number@billTextPdfUrl` (6,198),
`actionHistory/action` (19,915), `amendments/amendment` (1,253), `supportingDocuments` (fiscal notes).

**Each `<action>` is structured:** `@actionChamber` (H / S / **E** = the Governor), `<verb>`, `<committee>`,
`<date>` (MM/DD/YY), `<printersNumber>`, `<rollCallVote>` (`(195-8)`), `<fullAction>` (the prose line).

- **`<verb>` is a closed vocabulary — 59 values on 2025_0**, mapped one-to-one in `VERB_CLASS`; an unseen verb is
  counted (`verbs_unclassified`) and never moves a bill. PA's own `Undefined Action` label: 22 rows, counted.
- **No veto verb exists in this export**, so none is mapped (no guessing); 200 bills became law, matching the
  200 `Act No.` actions exactly.
- **Journal-remarks rows** (`(Remarks see House/Senate Journal Page`, 1,450 rows) carry the FILING date, not the
  event date (HB1099: a 2025-09-30 vote filed 2026-05-13) — kept in history, never used as status.
- **Reconsideration voids a result:** three verbs reconsider a vote (SB49: defeated 10 Jun 2026, reconsidered
  16 Jun; SR1: adopted, reconsidered, adopted again). The earlier floor result is cleared until a new vote.
- **`<subType>` matters for resolutions:** R = simple (1,073), **C = concurrent (12)** — a concurrent resolution
  needs BOTH chambers (HR25 was adopted by the House only and is not final). Bills: B 4,035 · A 81 · J 68.
- **Sponsor `sequenceNumber` runs past 99** (5 values 100-104, HR561 has 104 sponsors) — sort numerically.
- **Concurrence rounds are real and common:** after both floors pass, an amended bill is referred back to the
  origin chamber's RULES committee (HB257, HB559, HB1042, HB1667, …) — a referral that is NOT a new first committee.

## Modelled honestly (no VA shapes forced)
Two-year session; **no crossover stage**; stages `introduced → committee1 → floor1 → committee2 → floor2 →
concurrence → governor → law`, plus `adopted` for a simple resolution. Stages only move forward. Nothing is
declared dead or carried over inside an open session. Measured: committee1 3,503 · floor1 634 · committee2 457 ·
adopted 384 · law 200 · floor2 74 · concurrence 11 · introduced 6.
