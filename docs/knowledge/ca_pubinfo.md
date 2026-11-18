---
tags: [knowledge, california, ca, pubinfo, source, terms, multi-state]
updated: 2026-11-18
status: active
open_loop: CA site — intake built and tested on the real 2025-26 export; owner steps before it is live (CA spreadsheet, Cloudflare Worker, the Assembly display label in the SPA). See "To go live".
---

# California — pubinfo (Legislative Counsel's bulk database)

Scoped 2026-11-18 (owner: "start working on a live page for CA the same way you did for PA and VA, scoping what we
are allowed to do legally and within terms"). Prior plan: [[audits/fable_2026-07/multistate_ingestion_ca_fl]].

## What we may use — and the rule we follow
| question | answer | source |
|---|---|---|
| Is the data copyrighted? | **No — public domain.** "the State of California retains no copyright or other proprietary interest" | Government Code §10248.5 (overrides §10248(g)) |
| May we be charged or gated? | No fee may be charged for access on the public network | Government Code §10248 |
| Bulk host terms / robots? | `downloads.leginfo.legislature.ca.gov` is a plain file index; `/robots.txt` returns 404 (no rules); the Readme tells the public to load the files into its own database | checked 2026-11-18 |
| The interactive site? | `leginfo.legislature.ca.gov` answers automated requests with a Cloudflare bot challenge (even `/robots.txt`) | checked 2026-11-18 |
| **Our rule** | **Bulk files only, never the interactive site** (the PA rule). Honest User-Agent naming the repo; one download per file per publication; a 403/429 stops the run. | |

## What pubinfo holds (schema from the source's own load scripts, `pubinfo_load.zip`)
18 tables, tab-delimited `.dat` (+ `.lob` long text). Column order is read from each `<table>.sql`
(`states/ca_pubinfo.py`), never hardcoded. Key tables: `BILL_TBL` (measure type/number, current house/status,
chapter number), `BILL_HISTORY_TBL`, `BILL_VERSION_TBL` (subject = title), `BILL_VERSION_AUTHORS_TBL` (lead author,
coauthors), `LEGISLATOR_TBL` (party, district), `COMMITTEE_HEARING_TBL` (bill × hearing date × committee),
`DAILY_FILE_TBL`, `BILL_SUMMARY_VOTE_TBL` + `BILL_DETAIL_VOTE_TBL` (per-member votes), `LOCATION_CODE_TBL`
(committee codes → names), `CODES_TBL`, `LAW_*` (the codes themselves), `VETO_MESSAGE_TBL`.

**History is structural** (measured on a daily file, 2,026 rows): every action carries `ACTION_CODE` (numeric),
`ACTION_STATUS` (Applied / Rescinded), `PRIMARY_LOCATION` (Assembly / Senate / Governor / Secretary of State),
`SECONDARY_LOCATION` (Committee / Floor / Desk / E&E / Rules), `TERNARY_LOCATION` (committee code, e.g. `CS61`) and
`END_STATUS` (In Committee Process, In Floor Process, Passed, Pending Referral, In Desk Process, Enrolled, Signed by
Governor, Chaptered, Vetoed). The adapter routes on those fields only — cleaner than PA (verbs) or VA (status flags).

## Cadence
`pubinfo_<year>.zip` (full session, 1.2 GB, rebuilt Sunday) · `pubinfo_daily_<Day>.zip` (all current-session data
except code tables, 1.1 GB, daily) · `pubinfo_<Day>.zip` (that day's changed rows, 27 KB–870 KB). **Daily by
construction**; the site says "as of" the export date and never claims faster.

## Built (2026-11-18)
- `states/ca.py` — the contract: two-year session (`20252026`), house-of-origin deadline as the crossover marker,
  Assembly shown via `CHAMBER_DISPLAY` (the contract's lower chamber is "House" — every consumer reads House/Senate).
- `states/ca_pubinfo.py` — schema-driven reader; rows with the wrong field count are counted per table.
- `states/ca_adapter.py` — pubinfo → the bill contract; END_STATUS matched exactly, unknown values counted, Rescinded
  rows never move a bill, outcomes from `CHAPTER_NUM` / `CURRENT_STATUS`; fail closed on a partial universe.
- `test_ca_intake.py` — goldens on the real export (see the measured numbers there).

## To go live (owner steps, in order)
1. Create a Google Sheet "CA · Live", share it with the service account, give me its id.
2. Cloudflare: a new Worker `bill-tracker-ca` connected to `main` (build `npm run build:ca`, deploy
   `npx wrangler deploy --config wrangler.ca.toml`), its own D1 database.
3. SPA: add the Assembly display label (21 places read "House"); then the CA site config goes in `web/src/states/`.
4. Then the scheduled job (daily, after Legislative Counsel's ~21:20 Pacific publication).
