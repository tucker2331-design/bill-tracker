---
tags: [state, live]
updated: 2026-05-04
status: active
---

# Current Status

**Owner:** Tucker Ward
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0.
**Benchmark window:** Full 2026 VA GA session (2026-01-14 → 2026-05-01) since PR-C6 / Move 3a 2026-04-28. Crossover week (Feb 9-13) remains the historical reference but is no longer the active scope.

## Active focus
**🚀 PR-C7 STRUCTURAL PIVOT IN FLIGHT — PR #41.** Owner-mandated replacement of PR-C3.1's `MEETING_VERB_TOKENS` text-pattern gate with a cross-cycle persistent LegislationEvent cache. The pivot is bigger than just time recovery: it is the architectural answer to **why pattern-list maintenance doesn't scale to 50 states** (CLAUDE.md Standard #6). Cache uses HISTORY.CSV mutation (per-bill SHA256 hash) as the live-readiness signal so a clerk's edit triggers refresh in the next 15-min cycle. Owner mandates honored: 6h TTL safety net, 500 fetches/cycle hard cap, **explicit Tier A → B → C cold-start** (uncached drains FIRST so overflow doesn't starve, per the user's critical pushback on my "organic" recommendation), terminal-event short-circuit infrastructure (`TERMINAL_DESCRIPTION_PATTERNS` empty pending real API observation). Post-merge cold-start sized at **4 cycles ≈ 60 min** to full hydration of 2,002 unique bills (per [[#PR #40 — PR-C6.4 LegEvent sizing audit (closed)]]). **Codex P1 + Gemini critical** caught a real flaw on the original commit (Tier A overflow bills bypassed the cap into the row-loop's network-fetch path, recreating the PR-C3 hang vector); fixed in `45c72b5` by seeding `_legislation_id_cache` and `_legislation_event_cache` with negative values for every non-hydrated candidate bill. The row loop now NEVER fetches; the PR-C3 hang root cause is structurally impossible. Awaiting bot re-review on the fix commit, then merge → first cold-start cycle.

**The 994 framing was wrong.** PR-C6.3 verb-dump returned 994 "meeting bugs" but the analysis revealed the dominant mass (~80%+) are **X-Ray classifier false positives** — `Governor's Recommendation` matching the substring `"recommend"` in `MEETING_ACTION_PATTERNS`, `Bill text as passed Senate (SR###ER)` matching `"passed"`, etc. PR-C7 fixes the time-recovery side; the X-Ray classifier fix is **PR-C7.1 (deferred)** — `LegEventType` Sheet1 column + `pages/ray2.py` consumes structural EventType instead of text. Quantification of the real residue (the few rows where time recovery actually matters) lands when PR-C7 numbers stabilize.

## Open PRs
| # | Branch | State | Notes |
|---|--------|-------|-------|
| 41 | `claude/pr-c7-legevent-persistent-cache` | **Open — PR-C7 (with review fixes pushed)** | Drop verb gate + cross-cycle persistent cache (LegEvent_Bills + LegEvent_Events tabs). Diff: 558 ins / 15 del + 129 ins / 36 del review-fix commit. New telemetry: 12 counters (`legevent_cache_loaded_*`, `legevent_tier_*`, `legevent_skipped_*`, `legevent_fetched_this_cycle`, `legevent_hydration_queued`, `legevent_cache_hits/misses`, `legevent_overflow_no_fetch`). Initial worksheet allocation: 3,000 / 25,000 rows (sized to PR-C6.4 audit + headroom). Persist uses **write-then-clear-trailing** so a mid-write crash leaves OLD data, not empty sheet. Graceful degradation: every cache-touch failure has a categorized `push_system_alert` and the worker falls back to today's behavior. |

## Recently closed (this session, 2026-04-28 → 2026-05-04)
- **PR#40** `claude/pr-c6.4-legevent-sizing-audit` — merged 2026-05-01 at `3039123`. **PR-C6.4** read-only audit that returned the data PR-C7 ships against: cold-start surface = **2,002 unique bills**, today's `MEETING_VERB_TOKENS` gate covers only **0.1%** of `journal_default` rows (3 of 4,893), top-20 distribution is flat (10 rows max per bill, 7 typical), 4 cycles to full hydration at 500/cycle. Gemini high review folded in mid-flight: `pd.to_datetime` for date parsing instead of `strptime` (defends against Sheet column format drift).
- **PR#39** `claude/pr-c6.3.1-get-all-values-fix` — merged 2026-05-01 at `1941ec7`. **PR-C6.3.1 hotfix** for the verb-dump tool that crashed on first prod run with `gspread.exceptions.GSpreadException: header row contains duplicates: ['']` — Sheet1 has 26 allocated cols but only ~12 schema cols, so the 14+ trailing empty header cells parsed as identical `''` keys. Switched from `get_all_records()` to `get_all_values()` + `list.index()` for column lookup. Gemini medium review folded in: pre-calc column indices in locals + drop `_cell()` helper (matches the existing strptime pre-parse hygiene in the same file).
- **PR#38** `claude/pr-c6.3-meeting-verb-dump` — merged 2026-05-01 at `1941ec7`. **PR-C6.3** read-only triage that surfaced the misclassification finding: top bug rows are `Governor's Recommendation` (76+41+5), `[Memory Anchor] X Failed to Pass from conference` (14), `Bill text as passed Senate (SRxxxER)` family (~46 unique outcomes). Owner rejected the New-Verb Canary proposal as a band-aid; mandated the structural pivot (PR-C7). Codex P1 review folded in (Committee filter `"📋 Ledger Updates"` matches the worker's actual write at `calendar_worker.py:2772`, not the unprefixed string). Gemini medium folded in (date pre-parse, tag-stripping in `extract_verb_prefix`).
- **PR#37** `claude/pr-c6.2-trim-api-cache-cols` — merged 2026-04-28 at `18134b5`. **PR-C6.2** trimmed `API_Cache` from 26 cols to 6 (the actual schema: `Date, Committee, Time, SortTime, Status, Location`). Reclaimed **7,076,220 cells** = 70.8% of the 10M cap. Workbook total: 9,996,623 → 2,920,403 cells (99.97% → 29.2%). Headroom: 3,377 → 7,079,597 cells. Three-layer safety: schema match check, all-empty G:Z check (50k-row chunked read per Gemini high), workflow_dispatch dry-run gate. Codex P2 + Gemini medium folded in (drop `rows=` from resize so concurrent worker appends aren't truncated).
- **PR#36** `claude/pr-c6.1-cell-count-audit` — merged 2026-04-28. **PR-C6.1** read-only cell-count audit. Returned the unambiguous diagnosis: API_Cache = 9,199,086 cells = **92.0% of workbook**, dominating Sheet1 by 12×. Codex P2 review fixed inline (recommendation must reference the dominant sheet by name, not hardcode "Sheet1").
- **PR#35** `claude/pr-c6-full-session-stress-test` — merged 2026-04-28 at `214104b`. **PR-C6 / Move 3a** widened `investigation_config.py` from `2026-02-09 → 2026-02-13` to `2026-01-14 → 2026-05-01`. First worker run on the wider window crashed at `calendar_worker.py:2972` with `gspread.exceptions.APIError: [400]: This action would increase the number of cells in the workbook above the limit of 10000000 cells.` — Google Sheets per-workbook cap. Diagnosed and fixed across PR-C6.1 → PR-C6.2.
- **PR#34** `claude/pr-c5.1-sb584-outlier-and-writeback` — merged 2026-04-27. **PR-C5.1** SB584 malformed-row guard + post-milestone writeback. Closed the final UNKNOWN_ACTION counter. See [[failures/assumptions_audit]] #45 (missing-pattern vs malformed-row) and #46 (post-normalization predicate rule — bot-caught silent-pass).

## Known bug count (as of last X-Ray run on 2026-04-28, full session window)
**The 994 number is a misclassification artifact, not a real bug count.** PR-C6.3 dump revealed the dominant mass is admin actions matching meeting-substring patterns (`recommend`, `passed`, `failed`, `concurred`). Real meeting time bugs are estimated at < 20.
- **Meeting actions without times (X-Ray reported): 997** (full session) — primarily false positives; PR-C7 will collapse via time recovery, real residue measurable only post-PR-C7
- **Unclassified (X-Ray reported): 8** — 2 are System rows (own observability rows mis-flagged by X-Ray), 6 are real `Substitute / Amendment` rows
- **Worker UNKNOWN_ACTION counter: 6** (full session)
- **Section 7 (Sheet vs LIS time parity): 0** ✓ — perfect parity on resolvable cases
- **Source-bucket math (post PR-C6.2 + Move 3a):** `processed=64,891`, `sourced_api=12,314 + sourced_convene=32,433 + unsourced_journal=6,546 + unsourced_anchor=4,642 + dropped_noise=6,838 + floor_anchor_miss=6,578` (note: bucket sum > total_processed because some buckets overlap intentionally — see source-miss visibility framework)
- **Workbook capacity: 29.2% of 10M cap** (post PR-C6.2 trim) — comfortable headroom for PR-C7's new `LegEvent_Bills` + `LegEvent_Events` tabs (~170k cells initial)

## Next PRs (post PR-C7 merge)
- **PR-C7.1 — Sheet1 schema migration + X-Ray classifier rewrite (deferred from PR-C7).** Add `LegEventType` column to Sheet1 (idempotent, written by worker for cache-hit rows); update `pages/ray2.py` `classify_action()` to consult LegEventType FIRST and fall back to text patterns only when EventType is absent. This eliminates the X-Ray's substring-precedence bug class (`Governor's Recommendation` matching `recommend` etc.). Gated on PR-C7's cache being observed populated and stable across 2-3 cycles.
- **PR-C7.2 (TBD) — populate `TERMINAL_DESCRIPTION_PATTERNS`.** Currently empty pending observation of actual LegEvent API response shapes. After PR-C7's first cold-start completes, sample `LegEvent_Events` to identify recurring terminal-state descriptions (`Approved by Governor`, `Vetoed by Governor`, `Stricken from docket`, etc.). Add to the constant. Reduces steady-state refresh load.
- **PR-D — `lexicons/va.py` extraction.** Move all VA-specific pattern lists (`KNOWN_NOISE_PATTERNS`, `KNOWN_EVENT_PATTERNS`, `MEETING_VERB_TOKENS`, `MEETING_ACTION_PATTERNS`, `ADMINISTRATIVE_PATTERNS`, `ADMIN_OVERRIDE_PATTERNS`) into a single module. Eliminates the worker-vs-X-Ray drift class. Names CLAUDE.md Standard #6 for the 50-state vector. Deferred until PR-C7 / PR-C7.1 stabilize the verb set.
- **v2_shadow_test integration (deferred — owner direction).** v2_shadow_test fills a different role (front-end bill page); calendar subsystem we built has more advanced material. v2 needs to be reworked to match calendar_worker before merger. Gated on PR-C7 / PR-C7.1 closing.
- **Forward calendar (upcoming weeks, not just history) — owner-flagged hardest future challenge.** All work to date is HISTORY.CSV-backed (past actions). Showing upcoming committee meetings before they happen requires a different signal source (Schedule API for the future window, plus reconciliation against actual outcomes as days pass). Scope and approach TBD.

## Active architecture
Two parallel Streamlit apps and two scheduled workers. Full description in [[architecture/calendar_pipeline]].
- `backend_worker.py` — main product worker ("Mastermind Ghost Worker") — front-end bill page; **needs rework to match calendar_worker advanced material before any subsystem merger** (owner-flagged 2026-04-27)
- `calendar_worker.py` — calendar subsystem worker ("Mastermind Ghost Worker 2"); **PR-C7 in flight** adds cross-cycle persistent LegEvent cache + drops `MEETING_VERB_TOKENS` gate
- `pages/ray2.py` — X-Ray diagnostic (Streamlit-served); still uses text classifier (`MEETING_ACTION_PATTERNS` + `ADMINISTRATIVE_PATTERNS` + `ADMIN_OVERRIDE_PATTERNS`); deferred update to consume LegEventType in **PR-C7.1**
- `calendar_xray.py` — diff-identical backup of `pages/ray2.py`

## Active diagnostic tooling (read-only, workflow_dispatch only)
| Workflow | Purpose | Result |
|---|---|---|
| 🔍 Cell Count Audit (Mastermind DB) | Per-worksheet cell distribution + 10M-cap headroom | API_Cache 92% pre-trim → 21.2% post-trim |
| ✂️ Trim API_Cache Columns | One-shot 26→6 col trim with three-layer safety | One-shot complete (PR-C6.2 cycle) |
| 🩺 Dump Unrecovered Meeting Outcomes | Pre/post-PR-C7 verification: meeting-bug distribution + verb-coverage analysis | Pre-PR-C7 baseline captured 2026-05-01 |
| 📐 LegEvent Sizing Audit | Cold-start fetch sizing vs LIS WAF budget | 2,002 bills → 4 cycles at 500/cycle |

## What changes this page
Anything that changes the answer to "what is Tucker working on right now?" — opening/closing a PR, changing the active bug count, shifting the goal, pausing/resuming a thread. The LLM updates this page on every session conclusion.
