---
tags: [log, meta]
updated: 2026-04-19
---

# Project Log

Append-only, reverse-chronological (newest at top). Each entry opens with `## [YYYY-MM-DD] <kind> | <title>` so `grep "^## \[" log.md | head -20` gives a parseable timeline.

**Kinds:** `ingest` (new source/doc processed), `pr` (PR opened/merged/closed), `decision` (architectural or workflow), `lint` (wiki health-check pass), `session` (notable multi-hour working block), `post-mortem` (failure analysis).

---

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
