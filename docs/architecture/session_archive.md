---
tags: [architecture, capacity, archive, trends]
updated: 2026-07-31
status: active
---

# Session Archive — preserve every session's output for trend analysis

The [[verification_durability|sustainability audit]] CAPACITY check found the live
workbook ("Test Mastermind") at ~79.7% of Google Sheets' **10M-cell-per-workbook**
cap. The resolution is **separation, not deletion**: each kind of data gets the right
home, and every session is kept (owner requirement, 2026-06-14).

## The two kinds of data (opposite needs)
- **Working / regenerable scratch** — `API_Cache`, the LegEvent cache, `Schedule_Witness`.
  Re-derivable from LIS/HISTORY. Goal: keep **bounded** (session-prune), not preserve.
  This is what actually fills the cap. *(`API_Cache` row-retention is the owner's parked
  "bigger conversation" — see [[ideas/future_improvements]].)*
- **Product output / trend data** — `Sheet1` (the calendar) + structural vote/committee
  records. Goal: **keep every session, forever**, for cross-session trends.

## The archive
- A SEPARATE workbook, **"Mastermind Archive"** (id `1AA-dCUD…`; canonical = `ARCHIVE_ID`
  in `tools/session_archive/archive.py` — the single source of truth), owner-created and
  shared with the worker's service account as Editor. Its own 10M-cell
  budget → **8 sessions ≈ 4 years**, after which the chain rolls automatically (see Capacity below).
- One clearly-named tab per session: `Session_<code>` (e.g. `Session_20261`).
- The one-time PR-C7.1a audit corpus (`C7_1a_*`) also lives here (moved out of the live book).

## Tooling — `tools/session_archive/archive.py` (`🗄️ Session Archive` workflow_dispatch)
| Mode | Effect |
|---|---|
| `verify` | open BOTH workbooks, list archive tabs — confirms the share. Read-only. |
| `snapshot-session` | copy live `Sheet1` → archive `Session_<SESSION_CODE>` (idempotent). |
| `migrate-c7` | copy `C7_1a_*` → archive (preserve), verify present, then ONLY on `CONFIRM=delete` remove from live. |

`_copy_tab` = `copy_to` + a single atomic `batch_update` (delete-old-then-rename by raw
`sheetId`) — no in-loop full-list fetch, no reliance on the gspread `Worksheet`
constructor / `get_worksheet_by_id` typing (version-robust, 6 Gemini rounds). Shares the
`calendar-worker` concurrency group → never races a worker write.

## Done 2026-06-14 (PR #131)
- `verify` ✅ (share correct) → `snapshot-session 20261` ✅ (`Session_20261`, 37,542 rows) →
  `migrate-c7` copy ✅ (4 tabs, 75,374 rows preserved) → `migrate-c7 CONFIRM=delete` ✅.
- Live workbook **79.7% → 75.3%** of cap (freed ~436k cells; 17→13 tabs).

## Capacity — the archive is a CHAIN, not a workbook (2026-07-31)

Owner: *"is there any way to automate the creation and switching to a new google sheet to make the
archiving last forever?"* **Yes, and it is built.**

**Measured.** Sheet1 is 29 columns; `Session_20261` is 37,837 rows (this page's older PR-#131 figure of
37,542 gives the same answers) = **1,097,273 cells**. Raw division says 9 sessions per workbook; the
250k safety margin costs exactly one, so the number the code acts on is **8** — 8 × 1,097,273 + 250,000 =
9,028,184 fits, a 9th would need 10,125,457. At ~2 sessions/year that is **~4 years**, so the first roll
lands around **2030**. *(This page previously said "scales for years" without a number. It does — 4 of
them.)*

**The roll decision is not a percentage.** "Roll at 80% full" is another magic number and is wrong both
ways: 80% of 10M leaves 2 sessions unused, while a session bigger than the remaining 20% still fails. The
code asks the question the failure actually asks — *does the incoming session fit?* — which is arithmetic
on two measured quantities and needs no constant. `tools/session_archive/capacity.py`, 23 tests.

**The registry is the load-bearing piece, not the creation.** Creating a workbook is one API call; knowing
*which* workbook holds `Session_20351` is the hard part. `Archive_Registry` (a tab in **VA·Ops** — it
cannot live in the archives it indexes, or the index rolls away with them) maps
`Jurisdiction | SessionCode | WorkbookId | WorkbookTitle | ArchivedUTC | Rows | Cols`. **Jurisdiction is
first and is not decoration** (Standard #6): NY archives through the same registry with no per-state code
path. `tools/session_archive/registry.py`, 30 tests.

**Fail-closed everywhere.** `resolve_active` returns `None`, never a default workbook id — a silent
fallback is how session N+1 gets written into a full or wrong book. The genesis id seeds an **empty**
registry only; once any row exists the registry is the sole authority. The registry row is written *after*
`_copy_tab` verifies, so a failed copy never leaves a pointer to a tab that does not exist.

**The worker refuses rather than fails mid-copy.** `_archive_capacity_check` runs *before*
`_archive_completed_session` copies. If the session will not fit it raises, so the session marker does not
advance and nothing is lost — instead of the 2026-04-28 production failure (`APIError [400] … above the
limit of 10000000 cells`) thrown after the whole pipeline had run. At one session of headroom it warns,
giving ~6 months of lead time.

**One step is UNVERIFIED and says so in the code:** `gc.create()` has never been executed here (no
credentials in the dev environment). If a service account cannot own Drive files, creation fails — and the
tool treats that as a hard stop with the exact manual remedy, never as "carry on with the full workbook".
`ARCHIVE_SHARE_WITH` is **required** for a roll: a workbook created by the service account is invisible to
a human until shared, and an archive nobody can open is not an archive.

## Next (not yet built) — the auto-rollover hook
The "automatic" half: a worker hook that calls `snapshot-session` when it detects the
active session has changed from the last-archived one (the worker already detects rollover
for the cache prune — same trigger). Fires first at the 2027 session open. Tracked in
[[ideas/future_improvements]]. The **trend-analytics layer** (per-committee survival rates
across sessions) READS this archive and is a separate, later project — explicitly out of
scope for the maintenance work.
