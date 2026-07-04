---
tags: [audit, fable, multistate, california, florida, architecture, ingestion]
updated: 2026-07-04
status: active
---

# FABLE 3b — California & Florida: sources, structure, and the 10–15 minute target

Same method as [[audits/fable_2026-07/multistate_ingestion_pa]] (research the actual delivery, find the
structural math, no text dictionaries, no third parties), aimed at the owner's freshness target:
**data as fast as 10–15 minute intervals.** Everything marked VERIFIED was inspected live on 2026-07-04;
everything marked TO-VERIFY is a Phase-0 task with the exact check written down.

---

## CALIFORNIA — the most structural state yet; the batch layer is a literal database

### What CA publishes (VERIFIED from the official pubinfo Readme, downloads.leginfo.legislature.ca.gov)

The **pubinfo export** is a full relational database (they even ship the MySQL DDL — `capublic.sql`):
tab-delimited `.dat` tables + `.lob` blobs for long text. Tables include: `BILL_TBL`,
`BILL_HISTORY_TBL`, **`BILL_DETAIL_VOTE_TBL`** (per-legislator votes!), `BILL_SUMMARY_VOTE_TBL`,
`BILL_MOTION_TBL`, `BILL_VERSION_TBL` (+ authors), **`COMMITTEE_HEARING_TBL`**,
**`COMMITTEE_AGENDA_TBL`**, **`DAILY_FILE_TBL`** (the floor/hearing agenda as a table),
`LOCATION_CODE_TBL` (committee/floor location codes), `LEGISLATOR_TBL`, **`CODES_TBL`** (coded
vocabularies), `VETO_MESSAGE_TBL`, `LAW_*`. Sessions back to 1989 as `pubinfo_YYYY.zip`.

**This is Challenge-1 heaven: votes, hearings, agendas, daily files, and code tables arrive as KEYED
RELATIONAL ROWS.** No prose routing anywhere in the batch layer — CA is structurally cleaner than VA.
The `bill_history_tbl` action lines are prose *display* strings, but the events that matter (votes,
hearings, versions, vetoes) all have dedicated coded tables to JOIN — the PA Prove-to-Hide router
applies with even less residue.

**Cadence (VERIFIED):** per-weekday incremental zips (`pubinfo_Mon.zip` … `pubinfo_Sat.zip` — "the day's
new records since last extract") + full current-session zip; Sunday = full reload. **The batch layer is
DAILY.** It cannot meet 10–15 min on its own.

### The 10–15 minute path (the speed layer CA needs)

| Candidate surface | What it carries | Verdict |
|---|---|---|
| **Assembly Daily File site** (dailyfile.assembly.ca.gov) | committee hearing agendas, floor file, file-item status — a dynamic web app | TO-VERIFY (Tier-2 endpoint hunt): modern app ⇒ likely JSON/XHR-backed; the hearing-schedule analog of PA's `parss:` |
| **Senate Daily File / committee pages** (senate.ca.gov) | same for the Senate | TO-VERIFY (same protocol) |
| **leginfo bill pages** (JSF app: `billStatusClient.xhtml` etc.) | status/history/votes | TO-VERIFY **empirically**: the site may refresh intra-day even though bulk is nightly — nobody documents it, so MEASURE it |
| Floor session video/streams | live floor state | context only; not structured — ignore |

**Phase-0 CA experiment (the honest core of this plan):** on 2–3 active session days, poll (5-min
cadence, conditional GET) a set of moving bills' leginfo pages + both Daily File surfaces, timestamp
every observed change, and compare against the floor/committee stream timestamps. Output: a **measured
publication-lag table per event class** (hearing schedule change, floor file movement, vote posted,
action line posted). Rule: the speed layer is built ONLY on surfaces whose measured lag ≤ the target;
classes that measure slower are served honestly at their real cadence ("as of" labeling — never
manufactured freshness).

**Expected outcome (stated as a falsifiable prediction, not a promise):** schedule/agenda/file classes
will meet 10–15 min via the Daily File apps; votes/actions may prove intra-day-but-not-15-min on
leginfo. If so, CA ships with fast meetings + honest same-day votes — and the measured-lag table is the
evidence the product story stands on.

### CA lambda mapping
Batch = daily pubinfo relational load (idempotent; the Sunday full reload is a free weekly
self-reconciliation). Speed = whichever Daily-File/leginfo endpoints pass the lag experiment,
provisional-stamped. Reconciler = next pubinfo increment confirms/corrects; per-legislator vote rows
(`BILL_DETAIL_VOTE_TBL`) make vote verification exact. Verification oracle = first-party redundancy
(Daily File vs COMMITTEE_HEARING/AGENDA_TBL vs DAILY_FILE_TBL — three internal surfaces for the same
facts).

---

## FLORIDA — no official bulk dump; TWO first-party site systems = a built-in dual oracle

### What FL publishes (researched 2026-07-04)

- **flsenate.gov** — the Senate's system, carrying BOTH chambers' bills. Clean, ID-keyed URL grammar
  (`/Session/Bill/<year>/<number>` + tabs for history/votes/related). Official RSS is thin (VERIFIED:
  only Daily Senate Calendar + two video feeds at `/tracker/rss`), but the site notes RSS icons
  "throughout the site" — per-context feeds TO-VERIFY. Site includes a Tracker product (email alerts —
  potential exotic push tier).
- **flhouse.gov / MyFloridaHouse** — the House's system. **VERIFIED: a live `/api/` surface exists** —
  `flhouse.gov/api/document/apr?sessionid=113&id=1056` surfaced in the public index (session-ID-keyed
  document API). Where there is one documented-by-existence endpoint there is a family; the House site's
  bill/committee/calendar pages almost certainly ride the same API (Tier-2 hunt, highest FL priority).
- **No official bulk export found** for either chamber (unlike PA's XML or CA's pubinfo). FL is a
  **site-API state**: the structural channel IS the sites' own endpoints.

### The 10–15 minute path

FL's working sites are the chambers' operational systems — during session they publish actions,
committee notices (rule-governed formal notices), calendars, and votes on the sites in near-real-time.
The plan:

1. **Phase 0 endpoint enumeration (both sites, 1–2 h each):** DevTools over a bill page, committee page,
   calendar page, vote page. Catalog every XHR/JSON endpoint, its keys (sessionid, bill number,
   committee id), auth (expect none), and response shape. The flhouse `/api/` family is confirmed to
   exist; flsenate's clean URL grammar suggests either JSON endpoints or highly stable server-rendered
   IDs (if truly no JSON: flsenate pages are ID-keyed enough that a structured-attribute extraction —
   table cells with stable ids, NOT prose classification — may qualify; decide only on evidence).
2. **Speed layer:** poll the enumerated endpoints for tracked entities at 5–10 min on session days
   (conditional GET, jitter, activity-correlated cadence — the charter verbatim). Committee notices +
   calendars via the official publication surfaces; votes via the vote endpoints.
3. **Batch layer (self-built, since FL doesn't ship one):** a nightly full sweep of the same endpoints
   snapshotted to versioned storage — OUR pubinfo-equivalent, giving replayability, diffability, and the
   reconciliation baseline. Cadence-bounded and conditional so it's lighter than one LegiScan crawl.
4. **The built-in oracle (FL's structural gift):** flsenate and flhouse are **two independent
   first-party systems describing the same legislature**. Cross-checking them IS the dual-pipeline
   verification — divergence alerts with denominators, no third party anywhere.

**Verdict:** 10–15 min is PROBABLE for FL across all lobbyist-critical classes, contingent on Phase-0
endpoint enumeration — with the same honest fallback: any class that measures slower ships at its real
cadence with "as of" labeling.

---

## The emerging state taxonomy (for the 50-state contract)

| Tier | Delivery | States so far | Batch layer | Speed layer |
|---|---|---|---|---|
| A | Real API | NY (OpenLeg) | API paging | API deltas |
| A′ | Relational export | **CA** | daily .dat load | site/daily-file endpoints (measured) |
| B | Bulk file + feeds | VA (blobs+API), **PA** (XML+RSS) | blob/XML re-derive | API / RSS polling |
| C | Site-API only | **FL** | self-built nightly snapshot | site endpoints |

All four tiers implement the SAME [[audits/fable_2026-07/multistate_ingestion_pa]] lambda contract
(batch-authoritative / speed-provisional / reconciler / first-party verification) — the per-state
manifest just binds different sources to the same slots ([[ideas/multi_state_data_strategy]] confirmed).

## Phase plan for Opus (per state, when green-lit)
- **CA:** P0 = pubinfo schema page (download `pubinfo_2025.zip`, document every table/column from the
  shipped DDL) + the measured-lag experiment (design above). P1 = batch loader (mirror ny/pa shape;
  the DDL is given — this is the easiest loader of any state). P2 = speed pollers for surfaces that
  passed the lag gate. Gates: full-session replay loads clean; vote rows reconcile
  DETAIL↔SUMMARY↔history 100%; speed_wrong_rate < 1% over a week.
- **FL:** P0 = endpoint enumeration (both sites) + notice-rules page (FL publishes committee notices on
  formal rule deadlines — encode them as expectations the completeness tripwire checks). P1 = self-built
  nightly snapshot + batch derive. P2 = speed pollers. Gates: cross-site (House↔Senate systems)
  divergence ≈ 0 on a sample week; snapshot replay stability; speed_wrong_rate < 1%.

Sources: [pubinfo Readme (official)](https://downloads.leginfo.legislature.ca.gov/pubinfo_Readme.pdf) ·
[downloads.leginfo index](https://downloads.leginfo.legislature.ca.gov/) ·
[FL Senate RSS](https://www.flsenate.gov/tracker/rss) · [flhouse.gov](https://www.flhouse.gov/) (live
`/api/document/` endpoint observed) · [leginfo.legislature.ca.gov](https://leginfo.legislature.ca.gov/)
