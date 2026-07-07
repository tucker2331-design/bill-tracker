---
tags: [audit, fable, sweep, security, ci]
updated: 2026-07-04
status: active
---

# FABLE 4 — Personal sweep: everything else worth flagging

Smaller findings from the audit passes that fit none of the other three pages. Same format: evidence →
fix → validation. None are urgent-today; S-1 and S-2 should ride the next convenient PRs.

## S-1 · LIS WebAPIKey committed in plaintext in 10 files
> **STATUS 2026-07-06: SHIPPED (PR #203).** `lis_authorization.py` now exports the single env-first source
> `LIS_API_KEY` + `LIS_PUBLIC_API_KEY` (`os.environ.get("LIS_API_KEY", "<current>")`) — **rotation = set ONE
> GitHub secret, zero code edits.** All runnable production + tool code imports it (both workers; the 4 active
> tools + backend_worker extend their existing `lis_authorization` import). `grep 81D70A54` in running code == 1.
> Intentionally left (documented in the PR): deprecated `xray.py`, frozen `backend_worker_3col_backup.py`, and
> the X-Ray UI-default pair (`pages/ray2.py`+`calendar_xray.py`, user-overridable password fields). Rotation
> note added to [[knowledge/lis_api_authorization]].
- **Evidence:** `grep -rn "81D70A54" --include="*.py" .` → calendar_worker.py, bill_tracker (via import),
  pages/ray2.py, calendar_xray.py, xray.py, backend_worker.py (+backup), and three tools/ scripts.
- **Risk:** not secrecy (it appears to be the public/SPA-class key; LIS 401-handling already exists and
  `auth_failed` is detected as a rotation signal) — the risk is **rotation brittleness**: if LIS rotates
  the key, ten hardcoded copies must be found and changed under time pressure, and history keeps the old
  one forever.
- **Fix:** single source: `lis_authorization.py` exports `LIS_API_KEY = os.environ.get("LIS_API_KEY",
  "<current value>")` (env-first, current value as fallback so nothing breaks); all ten files import it.
  Add a line to the session-rollover runbook: "verify key validity annually; rotation = change ONE line
  or set ONE secret." Do NOT scrub git history (public-class key; not worth a rewrite).
- **Validation:** `grep -rn "81D70A54" --include="*.py" | wc -l` == 1. Effort: ~1 h.

## S-2 · CI blind spot: the 9 worker golden-test files never run in CI
> **STATUS 2026-07-06: SHIPPED (PR #204).** New paths-filtered `golden_tests.yml` job installs the worker
> deps and runs the offline golden + pure-logic tests (compute_effective_scrape_end, pr_c3_helper_v2,
> refid_shape_drift, cadence, lis_authorization, session_rollover) on any PR/push touching worker logic or a
> test file. Stdlib `structural_tests.yml` stays the always-on fast lane. A broken worker helper / cadence
> floor now fails CI without a bot. (NY tests deliberately excluded for now — separate subsystem, possible
> network; a follow-up can add an offline NY job.)
- **Evidence:** `structural_tests.yml` is deliberately stdlib-only (AST-extraction, no pip, seconds).
  The full golden suites (test_compute_effective_scrape_end, test_classify_*, test_route_event,
  test_pr_c3_helper_v2 …) import calendar_worker → need pandas/gspread → run only when a session
  remembers to run them locally. Every worker PR this block ran them manually; that's discipline, not
  enforcement.
- **Fix:** add a second job `golden-tests` to structural_tests.yml: `pip install pandas requests gspread
  google-auth pytz beautifulsoup4 pdfplumber` (cache the wheel dir), run the 9 files, triggered on PRs
  whose diff touches `calendar_worker.py`/`bill_tracker.py` (paths filter). Keep the stdlib job as the
  always-on fast lane. ~2 min added CI time, only on worker PRs.
- **Validation:** a PR that breaks `parse_24h_time` fails CI without any bot's help. Effort: ~1 h.

## S-3 · Repo-root cruft misleads readers (human and model)
- **Evidence:** `backend_worker.py` (+ `backend_worker_3col_backup.py`), `xray.py` live at root beside
  the real system; all carry the plaintext key; CLAUDE.md must keep explaining what's deprecated.
- **Fix:** `git mv` the deprecated set into `attic/` with a one-line README ("kept for reference;
  nothing here runs — see CLAUDE.md file map"). Update CLAUDE.md's file map (it gets SHORTER — the
  explanation becomes one line). Confirm `update_database.yml` (paused) points at nothing that moved, or
  move the workflow to attic too (it's schedule-commented; manual dispatch would break → acceptable,
  it's deprecated — note it in the PR).
- **Validation:** repo root lists only living code. Effort: ~30 min.

## S-4 · Measurement caveat from this audit (recorded so nobody re-trips it)
- gviz `count(A)` per-tab probes silently FALL BACK to the first sheet when a tab name doesn't resolve
  (my LegEvent_Cache probe returned Sheet1's count). For capacity work (C-2), use the Sheets API-based
  `tools/cell_count_audit` (authoritative), never gviz tab queries.

## S-5 · Self-healing items verified — no action, recorded to prevent false alarms
- **Metrics_History ≈ 72k rows** is flood-era backlog (#190's per-row alerts); the 45-day prune (daily,
  green) ages it out by ~mid-August 2026; post-#190 append rate is ~2 rows/cycle. Do NOT build anything.
- **`.lis_blob_cache` on Actions cache** can be evicted (7-day idle / repo 10 GB) → next run is a full
  re-download by design (guardrail #1's fail-safe). Cold cycles are slower, never wrong.
- **Stale vite HMR errors** in the preview console during this session were branch-switch artifacts;
  main builds clean (`tsc` + `vite build` verified post-merge).

## S-6 · docs/state/next_session.md is a second, stale "what's next"
> **STATUS 2026-07-06: SHIPPED** (with B-1). `next_session.md` archived (status: archived, stub banner →
> current_status); index "START HERE" repointed to [[state/current_status]] as the ONE live source.
Covered as brain-audit B-6; flagged here because it bit ME this session: current_status pointed to it as
authoritative and its queue was three weeks old. One source of NEXT (current_status after B-1); archive
the page.

See also [[audits/fable_2026-07/README]] for the priority queue.
