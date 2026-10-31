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
- User-Agent: `bill-tracker-intake/0.1 (+repo URL; contact address)`. A 401/403/429 stops the intake — no retry,
  no header change (`FeedRefused`).

## Feeds
| Feed | URL | Shape |
|---|---|---|
| Data index | `/data` | HTML; lists every Bill History export (39 sessions, `1969_0` … `2025_0`) and every RSS feed. The current regular session is read from it (`current_regular_session`), never hardcoded. |
| Bill History export | `/data/file?documentType=BillHistoryData&session=YYYY_N` | **A ZIP** (content-type says `application/xml`) holding one XML; filename stamps the export time (`…-202610311932.zip`). `2025_0`: 1.7 MB zipped, 19.9 MB XML. |
| Committee schedule | `/{house,senate}/rss/committee/schedule` | RSS 2.0 + `parss:` namespace: `MeetingDate`, `MeetingTime` ("Call of Chair" = PA's to-be-announced), `Committee`, `Location`, **`Bills`** (the agenda), `InCapitol`. |
| Others (not used yet) | `/{house,senate}/rss/session/{votes,calendar,journals,members,amendments,…}`, `/rss/committee/assignments` | per publication |

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
