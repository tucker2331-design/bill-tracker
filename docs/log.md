---
tags: [log, meta]
updated: 2026-04-21
---

# Project Log

Append-only, reverse-chronological (newest at top). Each entry opens with `## [YYYY-MM-DD] <kind> | <title>` so `grep "^## \[" log.md | head -20` gives a parseable timeline.

**Kinds:** `ingest` (new source/doc processed), `pr` (PR opened/merged/closed), `decision` (architectural or workflow), `lint` (wiki health-check pass), `session` (notable multi-hour working block), `post-mortem` (failure analysis).

---

## [2026-04-21] pr | PR-C1 opened — write-time chokepoint + circuit breaker + state cell + concurrency

First PR in the PR-C series. Pure scaffolding — lands the infrastructure that PR-C2+ (the actual bug fixes) depend on. Zero bug-count delta expected from C1 alone; this is a prerequisite for auditable fix-passes. Branch: `claude/pr-c1-append-event-chokepoint`.

**Five pieces shipped (diff: +265 / -9 across 2 files + 3 doc files):**

1. **Write-time chokepoint `_append_event()`** — nested closure inside `run_calendar_update()`, defined once, used at all 5 bill-row append sites (API chamber event, DOCKET row, API_Skeleton DLQ row, API_Skeleton agenda row, main CSV loop row). Enforces four invariants:
   - **I1** — schema completeness (all 11 columns). Missing keys fill with `""`, push `DATA_ANOMALY / CRITICAL` alert.
   - **I2** — `Origin` in the enumerated set `{api_schedule, convene_anchor, journal_default, floor_miss, system_alert, system_metrics}`. Out-of-enum pushes alert; row is NOT dropped (visibility beats silence).
   - **I3** — concrete-source Origins (`api_schedule` / `convene_anchor`) cannot carry a `⏱️ [NO_*]` Time string. Parity violation pushes alert.
   - **I4** — telemetry counter (no invariant): meeting-verb outcome AND Origin in `{journal_default, floor_miss}` increments `meeting_unsourced`. Feeds the circuit breaker.

2. **Mass-violation circuit breaker** — just before `worksheet.clear() + worksheet.update()`, evaluates three thresholds:
   - `violation_rate > 10%` (invariant_violations / total_processed)
   - OR `invariant_violations >= 50` absolute
   - OR `meeting_unsourced >= 50` (baseline today for crossover week: ~9)

   On trip, the worker REFUSES the Sheet1 overwrite — leaves the previous cycle's data intact as last-known-good. Banner written to `Sheet1!X1`, `DATA_ANOMALY / CRITICAL` alert pushed. Y1 is NOT advanced, so PR-C2's gap-backfill naturally covers the skipped cycle. Thresholds are intentionally generous — a safety net for regressions, not a gate on normal operation.

3. **State cell `Sheet1!Y1`** — `last_successful_cycle_end_utc`. Written with the ISO UTC timestamp after every successful overwrite. Read at cycle top (logged only in C1; C2 will consume it as the "since" cursor). Empty on first post-C1 deploy is expected and does not alert. Read/write errors emit categorized `API_FAILURE` alerts.

4. **GitHub Actions `concurrency`** on `calendar_worker.yml`: `{ group: calendar-worker, cancel-in-progress: false }`. If cycle N's runtime slips past 15 min, cycle N+1 queues rather than running in parallel. Never cancels mid-flight — half-written Sheet1 is worse than a delayed cycle.

5. **Counter schema additions** in `source_miss_counts`: `invariant_violations` (rows that failed I1/I2/I3 at append time) and `meeting_unsourced` (meeting-verb outcome + unsourced Origin). Both overlap the existing denominator buckets by design — orthogonal-tag pattern, same as `unsourced_anchor` and `dropped_ephemeral` (see [[failures/gemini_review_patterns]] #31).

**Module-level constant added:** `MEETING_VERB_TOKENS` (high-recall list mirroring `tools/crossover_audit/diff_sheet1.py` MEETING_VERBS — the two lists should stay in sync). False positives only elevate the telemetry counter, never drop or reclassify rows.

**Self-audit against 9-point pre-push checklist:** pass.
- (1) Verb forms — MEETING_VERB_TOKENS covers base/past/present as the crossover-audit pair does; no new conjugation lists.
- (2) Function scope — `_append_event` defined once, nested in `run_calendar_update`, before all call sites.
- (3) Doc version sync — architecture doc updated in same PR.
- (4) Duplicate file check — no `pages/ray2.py` / `calendar_xray.py` drift (PR doesn't touch X-Ray).
- (5) Architecture conformance — [[architecture/calendar_pipeline]] now has "Write-Time Safety Rails (PR-C1)" section.
- (6) Zero-trust data — all four invariants emit categorized alerts; no silent paths introduced.
- (7) Cross-list validation — MEETING_VERB_TOKENS overlaps with ABSOLUTE_FLOOR_VERBS, DYNAMIC_VERBS, KNOWN_EVENT_PATTERNS by design (orthogonal tagging, not classification).
- (8) Import resolution — no new top-level imports touched.
- (9) Source-miss visibility — grep on diff is empty; no new `continue` / `except: pass` / `"Time TBA"` sites.

**Writing back to:** [[architecture/calendar_pipeline]] (Write-Time Safety Rails section), [[state/current_status]] (PR-C1 added to Open PRs, Active focus updated), this entry.

**After Gemini review:** merge → PR-C2 (gap-backfill consuming Y1) → PR-C3 (LegislationEvent secondary time source, collapses Class 1) → PR-C4 (subcommittee attribution, collapses Class 2).

## [2026-04-20] pr | PR #27 review fixes — encoding, portability, phantom_row coverage

Six review comments from Gemini + Codex on the crossover-audit tooling addressed in one commit on branch `claude/crossover-audit`.

**Medium (Gemini):**
- `build_universe.py`, `diff_sheet1.py`: open HISTORY.CSV as `iso-8859-1` (per [[knowledge/lis_api_reference]]). Defensive — current snapshot happens to be pure ASCII, but that won't hold forever.
- `extract_truth.py`: `html.unescape()` added to `strip_tags` so LIS-emitted `&amp;` / `&nbsp;` / numeric refs don't desync downstream string compares against API-sourced text.
- `fetch_bills.sh`: `CHROME` path via env-var override with executable-bit check, so the script runs on Linux/CI without editing.

**Codex:**
- `fetch_bills.sh` (P2): capture Chrome exit status; report `FAIL` distinctly from `UNDERSIZED`. Previous version masked non-zero rc by redirecting stderr.
- `diff_sheet1.py` (P1): iterate `universe | sheet_bills` (union, not intersection) so phantom-row checks also cover the 19 bills in Sheet1 with no Feb 9-13 HISTORY activity. Re-ran: `phantom_row: 0` still holds — all 19 are correctly-classified `Outcome: Scheduled` placeholders (non-action).

**Extra fix caught during verification:**
- `diff_sheet1.py`: `sorted(all_dates)` before iteration so `crossover_audit_findings.json` is deterministic across runs. Python set iteration is hash-randomized; findings.json was churning on every re-run and cluttering diffs.

**Findings summary unchanged:** `meeting_in_ledger: 9`, `phantom_row: 0`, `subcommittee_miss: 0`. See [[testing/crossover_audit]].

**PR-C direction (decided this session, not yet coded):** LegislationEvent API (`GET /LegislationEvent/api/GetLegislationEventByLegislationIDAsync?legislationID=<int>`) is the bank-grade source. Per-bill event dump carries ISO `EventDate`, `CommitteeName`, `ParentCommitteeName`, `EventCode`, `VoteTally`. Requires a pre-built bill→integer-ID map (AdvLegSearch + sequential sweep covers all 3,634 session 20261 bills; the published `GetLegislationIdsListAsync` returns only 2,831). Coverage on the 9 known bugs: 6 fully rescued; 3 are LIS-side data holes (HB24 has no meeting-verb event; SB494 Feb 12 and SB555 Feb 12 × 2 carry `00:00` midnight-stub timestamps). New quirk logged to [[knowledge/lis_api_reference]] as follow-up.

**Fallback chain order** (to be implemented in PR-C):
1. `LegislationEvent` API, join-by-(bill, date) so fields merge across multiple events on the same day
2. `Schedule` API by (committee, date) for bills where LegislationEvent is committee-only or blank
3. `HISTORY.CSV` refid parsing (H18001 → parent H18) as last-resort committee attribution
4. `SOURCE_GAP` alert — never silent-fallback to `Time TBA` or `12:00`

## [2026-04-19] session | Crossover Week full-universe audit completed — X-Ray Section 9 bug count confirmed at 9

Ran tier-A ground-truth audit: 1,544 bills × 6,885 LIS actions vs 4,473 Sheet1 rows, Feb 9-13 2026 window. Pipeline: `tools/crossover_audit/{build_universe.py, fetch_bills.sh, extract_truth.py, diff_sheet1.py}`. Raw DOM via headless Chrome (see [[knowledge/lis_dom_scraping]]).

**Headline:** the X-Ray Section 9 bug count of **9 is the actual, full-window crossover-week bug count.** Confirmed zero hidden meeting-misrouted rows, zero phantom rows, zero silent bill-drops. The 51 bills in HISTORY-but-not-in-Sheet1 are all Fiscal-Impact-Statement-only entries correctly filtered as noise. See [[testing/crossover_audit]] for full findings table, 9-bug exemplars with LIS committee attributions, and class distribution.

**Class distribution:**
- **Class 1 (Schedule API gap at full committee):** 4 bugs — HB111/HB505/HB972 (Feb 12 H-P&E meeting), HB609 (Feb 12 H-Finance). Two upstream API gaps = 4 of 9 bugs. Fixing the secondary time source collapses Class 1 entirely.
- **Class 2 (Subcommittee attribution miss):** 5 bugs — HB24, HB1266, HB1372, SB494, SB555. State-machine / attribution bugs in worker's subcommittee resolution path.

**Instrumentation observation (not a bug, but worth noting):** 423 admin-verb rows are tagged `⏱️ [NO_SCHEDULE_MATCH]` because the worker runs the schedule lookup on every row regardless of verb class. Consider narrowing the tag to rows whose verb class implied a meeting was expected. Logged to [[state/open_anti_patterns]] as item #8.

**Artifacts checked in:**
- `docs/testing/crossover_lis_truth.json` — 1.3 MB, 6,885 actions structured per-bill
- `docs/testing/crossover_audit_findings.json` — 180 KB, categorized discrepancies
- `tools/crossover_audit/` — reproducible pipeline

**Lesson learned (scraping):** LIS bill-details DOM uses nested `<span>` tags in descriptions. A naive regex over the history-event-row block over-captures across row boundaries. The fix (row-split BEFORE parsing) is now documented in [[knowledge/lis_dom_scraping]] so the next scraping task doesn't repeat the mistake. Caught during audit dry-run by noticing empty LIS truth on bills that clearly had HISTORY activity — investigating revealed the regex bug rather than accepting "LIS is missing rows."

Next: PR-C scoping. Two-track fix — secondary time source for Class 1 (4 bugs) + subcommittee resolution fix for Class 2 (5 bugs). No code written until audit is reviewed.

## [2026-04-16] pr | PR-B opened — metrics visibility + source-miss diagnostic hint

Branch: `claude/pr-b-metrics-visibility-diagnostic` from `origin/main` post-PR#25-merge. Two focused fixes cashing in on real-world behavior of PR-A:

1. **Viewport slice was filtering out the `SYSTEM_METRICS` row.** PR-A stamped the metrics row with `Date=today` (run timestamp) so it'd write on every cycle. The end-of-pipeline viewport slice then filtered `final_df` to `scrape_start <= Date <= scrape_end` (= Feb 9-13, 2026), silently dropping the `Date=2026-04-16` metrics row before Sheet1. X-Ray Section 0 rendered blank even though upstream counters were correct. Fix: exempt `Origin in {system_alert, system_metrics}` from the window mask (`final_df = final_df[in_window | is_system]`). Logged as [[failures/gemini_review_patterns]] #36.
2. **NO_SCHEDULE_MATCH rows now carry a `DiagnosticHint` column.** New pre-loop dict `api_schedule_by_date` indexes `api_schedule_map` by date. `_build_diagnostic_hint()` produces `loc='<bill_locations[bill]>'; api_<date>=[<committee>@<time>; ...]` (nearest-3 same-chamber candidates). Populated in both `journal_default` and `floor_miss` branches; empty string for sourced rows. Added to all 9 `master_events.append` sites (4 API-sourced = `""`, 1 CSV branch = populated, plus push_system_alert / SYSTEM_METRICS / cache_alert meta sites). X-Ray Sections 4d, 9 sample rows, and the Ledger Health Check "meeting actions in Ledger" expander now surface the column when present. Sheet1 schema: 10 → 11 columns. Logged as [[failures/gemini_review_patterns]] #37.

Also re-synced `calendar_xray.py` with `pages/ray2.py` and updated [[architecture/calendar_pipeline]] schema section.

## [2026-04-16] pr | PR#25 merged — worker source-miss visibility instrumentation (PR-A)

Merged into `main` after Gemini review follow-up commits. Worker ran successfully with the new counters (mutual-exclusive denominator = 63,081). The `SYSTEM_METRICS` row never reached Sheet1 because of the viewport-slice bug documented in PR-B's entry above.

## [2026-04-16] pr | PR#25 updated — Gemini review follow-up for PR-A

Five issues from Gemini review of PR#25, logged as [[failures/gemini_review_patterns]] #31-#35:

1. **#31 Counter double-counting.** `source_miss_counts` split into mutually-exclusive denominator buckets (`sourced_api`, `sourced_convene`, `unsourced_journal`, `floor_anchor_miss`, `dropped_noise` — sum to `total_processed`) and orthogonal tag counters (`unsourced_anchor`, `dropped_ephemeral` — overlap intentional). `unsourced_anchor` now fires on every Memory-Anchor row regardless of time resolution.
2. **#32 Origin/metric parity.** Floor transitions from `api_schedule` to `convene_anchor` now decrement `sourced_api` and increment `sourced_convene`, so row Origin matches the counter.
3. **#33 Dedup-key scope.** `no_match` alert key now includes `bill_num` per [[workflow/source_miss_visibility]].
4. **#34 Redundant import.** Removed local `import json as _json`; use module-level `json`.
5. **#35 Origin field parity.** Added `Origin="api_schedule"` to 4 `master_events.append` sites in the Schedule API branch.

X-Ray Section 0 rewritten to visually separate denominator buckets (with sum-check warning on drift) from orthogonal tag counters.

## [2026-04-16] pr | PR-A opened — worker source-miss visibility instrumentation

Branch: `claude/worker-source-miss-visibility`. Instrumentation-only PR that cashes in all five items from [[state/open_anti_patterns]]:

1. `calendar_worker.py` L756 — `except: print` cache fallback now also calls `push_system_alert(..., category="API_FAILURE", severity="WARN")`.
2. L~1201 Memory Anchor path now tags both admin and dynamic verbs (`📝 [Memory Anchor: admin]` vs `⚙️ [Memory Anchor]`).
3. L~1181 silent `"Journal Entry"` default replaced with `"⏱️ [NO_SCHEDULE_MATCH]"` tag + deduped `push_system_alert` (category `TIMING_LAG`, severity `WARN`).
4. L~1340 ephemeral-filter silent `continue` replaced with counter + deduped alert (category `DATA_ANOMALY`, severity `INFO`).
5. Ledger-Updates rename (L~1363) now gates off a new `Origin` column (`journal_default` / `floor_miss` / `api_schedule` / `convene_anchor` / `system_alert`) instead of the renamed Time string, so provenance survives.

Also: `push_system_alert` extended to accept `category`, `severity`, and `dedup_key`; a JSON-encoded `SYSTEM_METRICS` row is written to Sheet1 per run. X-Ray `pages/ray2.py` gains Section 0 rendering the denominator (total / sourced / unsourced / dropped). `calendar_xray.py` re-synced.

Expected effect: bug count goes *up* short-term because previously-silent rows now surface with visible tags. That is the point — per [[failures/pr22_post_mortem]], the old metric was rewarding silencing.

## [2026-04-16] pr | PR#24 opened — Gemini review follow-up for the brain PR

Four doc fixes flagged by Gemini on PR#23: (1) removed placeholder `[LLM-Wiki](https://github.com/)` link in `docs/README.md`; (2) aligned severity labels in `docs/state/open_anti_patterns.md` to CLAUDE.md Standard #4 (`INFO`/`WARN`/`CRITICAL`); (3) `<mod>` → `<module>` in CLAUDE.md pre-push audit point 8 for consistency with [[workflow/three_phase_protocol]]; (4) corrected the log entry below to cite the actual migrated files (`feedback_always_push.md`, `project_tba_discovery.md`) instead of just the `MEMORY.md` index. Also untangled stale "PR#23" references in [[state/current_status]] and [[state/open_anti_patterns]] that referred to the instrumentation PR before PR#23 was assigned to the brain PR.

## [2026-04-16] pr | PR#23 merged — Obsidian brain consolidation

Vault is live on `main`. Primary checkout now carries `docs/` as the project brain. Follow-up fixes in PR#24 address Gemini review.

## [2026-04-16] decision | Consolidated brain into Obsidian-compatible wiki

Restructured `docs/` as an Obsidian vault. Created `index.md`, `log.md`, `state/`, and `workflow/` subtrees. Migrated the two entries from global `~/.claude/.../memory/` (`feedback_always_push.md` and `project_tba_discovery.md`, both indexed by `MEMORY.md`) into `[[workflow/push_and_pr]]` and `[[knowledge/tba_times]]`. Updated [[README]] as the vault entry point. CLAUDE.md now routes all persistent memory writes here, not to global memory.

Trigger: user reported scattered knowledge between `docs/` and hidden `~/.claude/` memory folder; adopting the LLM-Wiki pattern with Obsidian as visual interface.

## [2026-04-16] post-mortem | PR#22 framework failure — "only measuring the bugs we wanted"

See [[failures/pr22_post_mortem]] and [[state/open_anti_patterns]]. User invalidated PR#22's reclassification premise (members really do offer amendments in committee). Audit of `calendar_worker.py` found the anti-pattern PR#22 inherited is still live in four places: line ~1181 (silent "Journal Entry" default), lines ~1248-1261 (ephemeral `continue`), lines ~1158-1167 (selective Memory Anchor tag), lines ~1269-1275 (Journal → Ledger rename without provenance). Section 9 bug metric was measuring symptoms, not source-miss rate.

New workflow rule created: [[workflow/source_miss_visibility]]. PR#22 to be closed unmerged by user.

## [2026-04-15] pr | PR#22 opened — `[chamber] (sub)committee offered` as admin override

Reclassified 8 crossover-week "offered" rows as administrative via `ADMIN_OVERRIDE_PATTERNS`. Premise later invalidated by user pushback. Logged as [[failures/assumptions_audit]] entry #41. To be closed.

## [2026-04-14] pr | PR#21 merged — `_REPO_ROOT` file-probe replaces dir-name check

Gemini PR#20 review flagged brittle `_HERE.name == "pages"` check. Replaced with `(_HERE / "investigation_config.py").exists()` probe. Logged as [[failures/gemini_review_patterns]] pattern #30.

## [2026-04-13] pr | PR#20 merged — sys.path prelude fix for `pages/ray2.py`

Streamlit subpage threw `ModuleNotFoundError: investigation_config` on deploy after PR#19. Added sys.path prelude. Logged as [[failures/assumptions_audit]] #39.

## [2026-04-12] pr | PR#19 merged — window alignment via `investigation_config.py`

Rolling `scrape_end = now + timedelta(days=7)` was expanding the bug count mechanically every run. PR#14-18 metrics were polluted. Pinned to `INVESTIGATION_START/END = Feb 9-13` in a single module, imported by worker + X-Ray. Logged as [[failures/assumptions_audit]] #38.

## [2026-04-11] pr | PR#18 merged — "prefiled and ordered printed" → admin override

2,042 prefiled rows were misclassifying as meetings due to substring "offered". Added to `ADMIN_OVERRIDE_PATTERNS`. Logged as [[failures/assumptions_audit]] #37. (Note: #37's call about bare "committee offered" being a meeting was later invalidated by #41.)

## [2026-04-10] pr | PR#17 merged — subcommittee vote refid regex fix

`resolve_committee_from_refid()` regex missed H14003V... format (parent + 3-digit subcommittee + V + vote ID). 1,637 subcommittee refids were unlocked. Logged as [[failures/assumptions_audit]] #36.

## [2026-04-09] pr | PR#16 merged — sub-panel schedule matching + overwrite protection

Added Strategy B in `find_api_schedule_match` for hyphen-suffixed sub-panels (HCJ-Civil, etc.) that aren't in Committee API. Added map overwrite protection so "Time TBA" can't clobber concrete times. Logged as [[failures/assumptions_audit]] #34, #35.

## [2026-04-08] pr | PR#15 merged — whitespace normalization + session marker fallback

Session marker fallback now overwrites non-concrete placeholder times. `_is_non_concrete_time` hoisted to module level. Logged as [[failures/assumptions_audit]] #32, #33.

## Earlier entries

Pre-2026-04-08 PR history is captured in the [[testing/crossover_week_baseline]] progress tracker table and in numbered entries in [[failures/assumptions_audit]]. This log was backfilled starting 2026-04-16 and is append-only from that date forward.
