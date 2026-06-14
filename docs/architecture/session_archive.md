---
tags: [architecture, capacity, archive, trends]
updated: 2026-06-14
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
  budget → scales for years; the 50-session trend vision spans archive workbooks if needed.
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

## Next (not yet built) — the auto-rollover hook
The "automatic" half: a worker hook that calls `snapshot-session` when it detects the
active session has changed from the last-archived one (the worker already detects rollover
for the cache prune — same trigger). Fires first at the 2027 session open. Tracked in
[[ideas/future_improvements]]. The **trend-analytics layer** (per-committee survival rates
across sessions) READS this archive and is a separate, later project — explicitly out of
scope for the maintenance work.
