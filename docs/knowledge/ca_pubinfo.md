---
tags: [knowledge, california, ca, pubinfo, source, terms, multi-state]
updated: 2026-11-18
status: active
open_loop: CA site — merged and writing its sheet daily (first run 2026-11-18: 5,040 bills); owner step left before it is live (the Cloudflare Worker bill-tracker-ca). See "To go live".
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

**The job reads the newest `pubinfo_daily_<Day>.zip`** (by the index's Last-modified column), not the yearly file —
the yearly file is rebuilt only on Sunday, so reading it would miss Monday–Saturday (Codex #274, case law #162).
Verified 2026-11-18 by reading the daily zip's directory with one range request: it carries every table the contract
reads (BILL, BILL_HISTORY, BILL_VERSION, BILL_VERSION_AUTHORS, LEGISLATOR, BILL_SUMMARY_VOTE, COMMITTEE_HEARING,
LOCATION_CODE, + analysis/motion/daily-file/agenda/veto); only CODES_TBL and the LAW_* tables are absent. Records are
stamped with the file's own HTTP `Last-Modified` (`source_published_utc`), never our clock. The CI fetch cache is
pruned to the files a run used.

## Built (2026-11-18)
- `states/ca.py` — the contract: two-year session (`20252026`), house-of-origin deadline as the crossover marker,
  Assembly shown via `CHAMBER_DISPLAY` (the contract's lower chamber is "House" — every consumer reads House/Senate).
- `states/ca_pubinfo.py` — schema-driven reader; rows with the wrong field count are counted per table.
- `states/ca_adapter.py` — pubinfo → the bill contract; END_STATUS matched exactly, unknown values counted, Rescinded
  rows never move a bill, outcomes from `CHAPTER_NUM` / `CURRENT_STATUS`; fail closed on a partial universe.
- `states/ca_fetch.py` — bulk host only (the interactive site is refused before any request), streamed to disk,
  20 h per-URL cap, stop on 401/403/429.
- `test_ca_intake.py` (in CI) — 23 checks on 240 real bills cut by `tools/historical_cache/ca/make_sample.py`.
- `ca_bill_tracker.py` — the job (`--dry-run` builds and prints the completeness payload; write needs the sheet).
- Site: `web/src/states/ca.ts` (+ `chamberLabels` → "Assembly" on the subway legend and Search chips),
  `npm run build:ca`, `wrangler.ca.toml` (placeholders), `.github/workflows/ca_bill_tracker.yml` (manual only).

**Measured on the full 2025-26 export (2026-11-18):** 5,040 measures built (2,796 AB · 1,447 SB · 797 resolutions
and amendments), 1 GRP counted outside both houses, 88,823 actions, 36 rescinded, 28 with a blank status (history
only), **0 unclassified**, 0 malformed rows; outcomes (after the #274 fold-in): 1,830 signed (AB/SB with a chapter
number) · 686 adopted (419 chaptered resolutions and ACAs + 267 HR/SR passed — none is "signed": the Governor never acts
on them) · 771 died · 243 vetoed (212 with status Vetoed + 31 with a veto override pending) · 0 awaiting the Governor
· 1,510 in progress (session ends 30 Nov); 3 stray history ids with no text (SB2510–2512) counted as
`history_only_no_text`;
281 House/Senate Resolutions have no subject line in the source (counted as `titles_blank`); co-author party joined
for 31,468 of 31,472. Dry run: 1 request (the index) when the session file is cached.

## To go live (owner steps, in order)
1. ✅ 2026-11-18: "CA · Live" created and shared; id in `wrangler.ca.toml` (the job reads it there — no repo secret).
   The job is scheduled daily (06:41 UTC) once merged.
   ✅ 2026-11-18: D1 `bill-tracker-ca-db` created (id in `wrangler.ca.toml`); tables from `tools/d1/console_setup.sql`
   (one paste, proven identical to migrations 0001–0003 in SQLite, and recorded as applied).
2. Cloudflare: a new Worker `bill-tracker-ca` connected to `main` (build `npm run build:ca`, deploy
   `npx wrangler deploy --config wrangler.ca.toml`), its own D1 database.
3. ✅ 2026-11-18: merged (#274) — the daily schedule (06:41 UTC) is live, no repo secret needed (the sheet id is read
   from `wrangler.ca.toml`). **First write run** (dispatched by hand, run 44423770882): 5,040 bills written to
   "CA · Live" from `pubinfo_daily_Wed.zip` (published 2026-11-18T12:23:47Z — so the index's Last-modified column is
   Pacific time), 0 unclassified, 0 malformed rows, 3 requests, 3 m 16 s. Saved fetch cache: 1.16 GB (one day's file;
   GitHub evicts the unused older entries, oldest-accessed first, after 7 days).
Residual (engineering, not owner): CA committee rosters and hearings calendar (`COMMITTEE_HEARING_TBL`,
`DAILY_FILE_TBL`) for the War Room and Calendar screens — off in `ca.ts` until built.
