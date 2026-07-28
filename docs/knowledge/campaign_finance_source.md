---
tags: [knowledge, api, campaign-finance, money, sources, compliance]
updated: 2026-07-27
status: active
---

# Campaign finance — go to the source, not the aggregator (queue item P3)

> Owner, 2026-07-27: *"VPAP prohibits sub-leasing with their info. My question is, where do they get it? There
> has to be a public open source one they are sourcing from we can find."*

**Correct, and found. VPAP is an aggregator; the Commonwealth publishes the underlying filings itself.**

## The primary source

```
https://apps.elections.virginia.gov/SBE_CSV/CF/<YYYY_MM>/
```

Virginia **Department of Elections (ELECT)** — the agency candidates and committees actually file with.
Verified live 2026-07-27:

- **Monthly directories from `1999` through `2026_07`** — the current month, stamped 7/1/2026. Live and
  maintained, not an archive dump.
- **10 CSVs per month.** `Report.csv` (2.1 MB) is the filing metadata; `ScheduleA.csv` (3.8 MB) contributions;
  `ScheduleD.csv` (5.4 MB) expenditures; Schedules B/C/E/F/G/H/I cover in-kind, loans, and the rest.
- **No key, no registration, no attestation.** Plain HTTP directory listing over IIS.
- ELECT states submitted reports and data feeds refresh **daily at ~5:15 PM and ~12:05 AM**.

## Why this matters beyond convenience

**The restriction that blocked VPAP does not apply to us, because we are not using VPAP's data.** Their terms
govern *their* compilation. The underlying filings are Virginia public records published by the state agency
of record — we take the same input they take.

This is also **strictly better sourcing**, not merely a workaround:
- **Standard #3 (structural, not derived).** ELECT's CSVs are the filings. An aggregator's tables are a
  derived product — someone else's normalisation choices, which we cannot audit and which can drift.
- **No intermediary to fail.** One fewer party who can change terms, rate-limit us, or go dark.
- **Deeper history.** 1999→present, well beyond the LIS 2025/26 API window
  ([[knowledge/lis_api_authorization]]) — money history is not bounded by that rule at all, because it is a
  different agency and a different publication.

## The generalisable rule (Standard #6)

**When a data aggregator's terms block us, find the agency they file with.** Aggregators exist because the
primary source is inconvenient, not because it is closed. Every state has a campaign-finance disclosure
agency publishing filings as public record; the pattern ports even though the URL does not. Same reasoning
retired LegiScan ([[knowledge/legiscan_terms]]) and it is now a standing move, not a one-off.

## Status
- **P3 RESOLVED — VPAP is no longer needed.** The money overlay (ideation C1) can be built on ELECT.
- **Still open before ingest:** confirm ELECT publishes no separate reuse restriction (the download page
  states none), and settle the **name→legislator join**, which is the real engineering work — filer names are
  free text and must be matched to `MemberID` structurally, never by fuzzy string alone (Standard #3).
- **Gift / economic-interest disclosures are a SEPARATE source** — the Virginia Conflict of Interest and
  Ethics Advisory Council, not ELECT. Not yet probed.
