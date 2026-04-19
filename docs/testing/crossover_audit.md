---
tags: [testing, audit, crossover, ground-truth]
updated: 2026-04-19
status: complete
---

# Crossover Week Audit — Full-Window Ground Truth Pass

> **Status: complete (2026-04-19).** Full-universe scan of 1,544 bills × 6,885 LIS actions vs 4,473 Sheet1 rows. Crossover week (Feb 9-13, 2026) is frozen data — this page is the canonical, don't-re-run record. Rerun only needed if the worker changes materially.

## Purpose

Answer the question [[failures/pr22_post_mortem]] left open: **how many bugs does Sheet1 actually have for crossover week, and what are they?**

The [[testing/crossover_week_baseline]] bug count (9, as of post-PR#21) is the X-Ray Section 9 metric, which only counts **meeting actions the worker *itself* flagged as time-unresolvable**. That metric is honest but narrow — it can't see:
- **Wrong times** (row resolved to an incorrect time)
- **Wrong committees** (row attributed to the wrong committee)
- **Misclassified rows** (meeting actions silently routed to Ledger Updates)
- **Missing rows entirely** (actions dropped by noise filter without a trace)
- **Extra/phantom rows** (Sheet1 has rows LIS does not)

This audit measures all of those against the authoritative source: the LIS website itself.

## Scope

**Window:** Feb 9-13, 2026 (crossover week).

**Universe:** Every bill with at least one HISTORY.CSV entry dated Feb 9-13, 2026 — derived from the raw `HISTORY.CSV` blob, not from Sheet1. Sheet1-derived scoping would silently miss bills the worker dropped entirely (see [[state/open_anti_patterns]] family).

Expected size: ~1,800-2,000 bills.

**Ground truth:** `lis.virginia.gov/bill-details/20261/<BILL>` rendered via headless Chrome — see [[knowledge/lis_dom_scraping]].

**Complementary source (for time verification):** cached Schedule API snapshot (`/tmp/lis_audit/sched.json`). LIS bill pages show committee + date but not meeting time; Schedule API fills the time dimension.

## Why now

1. Crossover week is **frozen data** — the underlying LIS history will not change. Running this audit once and persisting the truth JSON means no re-scrape needed for future verification.
2. [[failures/pr22_post_mortem]] established that metric-without-denominator is fatal. This audit *is* the denominator for any future accuracy claim.
3. PR-A + PR-B instrumented the pipeline for source-miss visibility, but visibility ≠ accuracy. A row with a resolved time might still be *wrong*. The audit catches that.

## Methodology

See `tools/crossover_audit/README.md` for the runnable pipeline. Summary:

1. **Build universe** — `tools/crossover_audit/build_universe.py` filters HISTORY.CSV → list of unique bill IDs with Feb 9-13 activity.
2. **Fetch** — `tools/crossover_audit/fetch_bills.sh` renders each bill page via headless Chrome (8x parallel, ~20 min total).
3. **Extract** — `tools/crossover_audit/extract_truth.py` parses `history-event-row` blocks → structured JSON `{date, chamber, committee_code, committee_name, action, refid}` per bill.
4. **Diff** — `tools/crossover_audit/diff_sheet1.py` joins Sheet1 rows against LIS truth per `(Bill, Date)`, cross-references Schedule API for time accuracy, emits categorized discrepancy list.

## Error class taxonomy

Derived from the 9 known X-Ray Section 9 bugs (see [Error class seed](#error-class-seed) below). Expected to cover most full-scan discrepancies; full scan may surface new classes, in which case this table expands.

| Class | Signature | Semantics |
|---|---|---|
| **1. Schedule API gap (full committee)** | LIS shows committee X action on date D; Schedule API has no X entry on D; worker correctly resolved committee but had no time. | Upstream source incompleteness. Worker attribution correct; fix requires either a secondary time source or an inferred fallback. |
| **2. Subcommittee attribution miss** | LIS shows subcommittee Y of parent X; worker resolves to X; Schedule API has no Y on D. | State-machine / bill-location resolves to parent instead of subcommittee. |
| **3. State-machine drift (missed re-referral)** | Bill was reassigned to a new committee Z; worker still tracks old committee. | Referral-tracking bug in `bill_locations`. |
| **4. Admin/meeting misclassification** | Meeting action (vote, substitute offered, subcommittee recommendation) classified as admin → routed to Ledger Updates. | Action classifier treats the verb pattern as admin when it should be meeting. Example: `[Memory Anchor: admin] House committee offered` tagged as admin but is actually a committee vote. |
| **5. Date-skewed action** | HISTORY.CSV action dated D₁ but the actual meeting was D₀; Sheet1 attempts time resolution on D₁ where no meeting occurred. | HISTORY lag between when the meeting happened and when the admin action was logged. |
| **6. Wrong time** | Worker resolved committee correctly but Sheet1 Time disagrees with Schedule API. | Resolution priority mis-ordered, or map overwrite regression. |
| **7. Missing row** | LIS has action for (Bill, Date, Committee) but Sheet1 has no corresponding row. | Noise filter or dedup silently dropped the row. |
| **8. Phantom row** | Sheet1 has a row for (Bill, Date, Committee) but LIS has no matching action. | Incorrect memory-anchor attribution; worker synthesized a row LIS doesn't recognize. |

### Error class seed

Pre-audit classification of the 9 known bugs (X-Ray Section 9):

Seed pre-audit (now superseded by [Findings](#findings) below, which contains the audit-verified class assignments). Kept for trace of what was predicted pre-scan.

| Bug # | Bill | Date | Pre-audit class | Audit-verified class |
|---|---|---|---|---|
| 1 | HB24 | 2026-02-10 | 2 | **2** ✓ |
| 2 | HB1266 | 2026-02-10 | 2 | **2** ✓ |
| 3 | SB494 | 2026-02-11 | 1 or 2 | **2** |
| 4 | SB555 | 2026-02-11 | 2 | **2** ✓ |
| 5 | HB111 | 2026-02-12 | 1 | **1** ✓ |
| 6 | HB505 | 2026-02-12 | 1 | **1** ✓ |
| 7 | HB609 | 2026-02-12 | 1 | **1** ✓ |
| 8 | HB972 | 2026-02-12 | 1 | **1** ✓ |
| 9 | HB1372 | 2026-02-13 | 1 or 2 | **2** |

Three bills (HB111, HB505, HB972) share the same failure: Feb 12 P&E committee meeting missing from Schedule API. **One upstream source gap = three visible bugs.** HB609 adds a fourth (Feb 12 H-Finance). See [Findings](#findings) for leverage math.

### 432 Ledger-routed rows breakdown (pre-full-scan)

Of the 432 rows with `Origin=journal_default` currently collapsed into `📋 Ledger Updates`:

| Outcome classification | Count | Status |
|---|---:|---|
| Legitimate admin (Placed on Agenda, Assigned sub, Referred to, etc.) | 418 | Correct — admin actions don't need times |
| Meeting action wrongly classified as admin | 9 | **Bugs** — the known 9 |
| Borderline (Committee substitute printed) | 5 | Ambiguous — printing is admin but coincident with committee meeting |

This validates the 9-count as honest (the admin-text-based misclassification isn't pulling in more hidden meeting actions than we thought). The full-scan may surface additional misclassifications in the api_schedule and convene_anchor strata, not here.

## Findings

### Scale

| Metric | Count |
|---|---:|
| Bills in universe (HISTORY Feb 9-13 activity) | 1,544 |
| Bills with ≥1 LIS Feb 9-13 action | 1,533 |
| Bills in Sheet1 with ≥1 Feb 9-13 row | 1,551 |
| Overlap (universe ∩ Sheet1) | 1,493 |
| Bills in HISTORY universe but not in Sheet1 | 51 |
| LIS actions in window (ground truth denominator) | 6,885 |
| Sheet1 rows in window | 4,473 |
| Sheet1 Ledger-Updates rows in window | 432 |

### Discrepancies by category

| Category | Count | Semantics |
|---|---:|---|
| `missing_bill` — bill has HISTORY meeting activity but Sheet1 has no rows for this bill | **0** | All 51 "absent" bills are FIS-only (Fiscal Impact Statement), correctly filtered as noise. |
| `meeting_in_ledger` — Sheet1 row in Ledger Updates but action contains a meeting verb | **9** | The known X-Ray Section 9 bugs, all accounted for. |
| `no_schedule_match_meeting` — Sheet1 row tagged NO_SCHEDULE_MATCH AND outcome has a meeting verb (excluding those already in `meeting_in_ledger`) | **0** | No additional hidden meeting-verb bugs outside the 9. |
| `no_schedule_match_admin` — Sheet1 row tagged NO_SCHEDULE_MATCH on an admin verb | **423** | Instrumentation chatter, not bugs. Worker correctly tags all rows it tried to resolve; admin rows like "Placed on Finance Agenda" never have an API match. Not a correctness bug but surfaces an instrumentation-scope question — see _Instrumentation observations_ below. |
| `phantom_row` — Sheet1 has row but LIS + HISTORY have nothing for (bill, date) | **0** | No synthesized rows. |
| `action_count_drift` — LIS shows ≥1 meeting action on (bill, date) but Sheet1 has zero rows for that bill/date | **0** | No bills silently dropped; every LIS meeting action has at least one Sheet1 counterpart. |
| `subcommittee_miss` — structural subcommittee-vs-parent drift | **0** | Captured inside `meeting_in_ledger` for the known 9; no orthogonal cases surfaced. |

### The headline

**The X-Ray Section 9 bug count of 9 is the actual, full-window crossover-week bug count.** No hidden meeting actions misrouted elsewhere in Sheet1. No missing bills beyond the fiscally-filtered noise. No phantom rows. The instrumentation lands correctly on every meeting-verb action that the worker itself flagged.

This was not a foregone conclusion — the [[failures/pr22_post_mortem]] caution was that Section 9 metric only counts rows **the worker itself** flagged unresolvable, so it could structurally miss misclassifications, silent drops, and phantom rows. This audit verified those three failure modes are at **zero** for crossover week.

### The 9 bugs — full exemplars with LIS committee attribution

From `docs/testing/crossover_audit_findings.json` (meeting_in_ledger):

| # | Bill | Date | LIS committee attribution | Sheet1 outcome | Class |
|---|---|---|---|---|---|
| 1 | HB24 | 2026-02-10 | Firearms (H15001) — subcommittee of H-Public Safety | 📝 [Memory Anchor: admin] H House subcommittee offered | **2** — subcommittee miss |
| 2 | HB1266 | 2026-02-10 | Natural Resources — subcommittee of HACNR (no anchor in LIS row) | 📝 [Memory Anchor: admin] H House subcommittee offered | **2** — subcommittee miss |
| 3 | HB1372 | 2026-02-13 | Commerce Agriculture & Natural Resources — subcommittee of HAPP (no anchor) | ⚙️ [Memory Anchor] H Subcommittee recommends continuing to (Voice Vote) | **2** — subcommittee miss |
| 4 | HB111 | 2026-02-12 | H-Privileges and Elections (H18) — parent committee | 📝 [Memory Anchor: admin] H House committee offered | **1** — Schedule API gap |
| 5 | HB505 | 2026-02-12 | H-Privileges and Elections (H18) — parent committee | 📝 [Memory Anchor: admin] H House committee offered | **1** — Schedule API gap |
| 6 | HB972 | 2026-02-12 | H-Privileges and Elections (H18) — parent committee | 📝 [Memory Anchor: admin] H House committee offered | **1** — Schedule API gap |
| 7 | HB609 | 2026-02-12 | H-Finance (H10) — parent committee | 📝 [Memory Anchor: admin] H House committee offered | **1** — Schedule API gap |
| 8 | SB494 | 2026-02-11 | Senate subcommittee (no committee anchor in LIS row) | 📝 [Memory Anchor: admin] S Senate subcommittee offered | **2** — subcommittee miss |
| 9 | SB555 | 2026-02-11 | Health Professions — subcommittee of S-Ed&H (no anchor) | 📝 [Memory Anchor: admin] S Senate subcommittee offered | **2** — subcommittee miss |

Revised class distribution:
- **Class 1 (Schedule API gap at full committee):** 4 bugs (HB111, HB505, HB972, HB609). HB111/505/972 share the Feb 12 H-P&E meeting — one upstream API gap = three visible bugs. HB609 is the Feb 12 H-Finance meeting — also missing from Schedule API.
- **Class 2 (Subcommittee attribution miss):** 5 bugs (HB24, HB1266, HB1372, SB494, SB555). Worker resolved to parent or "Memory Anchor" default when LIS shows subcommittee.

Leverage math: **two upstream Schedule-API gaps (Feb 12 H-P&E, Feb 12 H-Finance) account for 4 of 9 bugs** — fixing the secondary time source there collapses Class 1 entirely. The remaining 5 are state-machine / attribution bugs in the worker's subcommittee resolution path.

### Instrumentation observations (not bugs, but worth a note)

1. **423 admin-verb rows are tagged `⏱️ [NO_SCHEDULE_MATCH]`** (Origin=journal_default, Committee=Ledger Updates). These are correct placements (admin actions don't need times), but the visible NO_SCHEDULE_MATCH tag is noise for actions like "Placed on Finance Agenda" that were never supposed to find an API match. The worker instrumentation from PR-A tags any row that ran the schedule lookup and missed — which includes admin rows. Consider tightening the tag to only fire on rows whose verb class implied a meeting was expected. Low priority; no data integrity impact.
2. **12 bills empty in LIS truth within window, have HISTORY Feb 9-13 activity.** All 12 have only "Placed on X Agenda" or similar pre-meeting scheduling entries in HISTORY. The LIS bill-details page does not render those as history rows — LIS treats them as internal scheduling artifacts, not public history. Confirms the worker's correct policy: HISTORY > LIS website for admin entries.

### What this audit cost (and why it will not be rerun)

| Artifact | Size |
|---|---:|
| `/tmp/lis_audit/*.html` (raw DOM dumps) | ~20 MB (1,545 bills × ~13 KB avg; regenerable via `fetch_bills.sh`) |
| `docs/testing/crossover_lis_truth.json` | ~1.3 MB (checked in — canonical) |
| `docs/testing/crossover_audit_findings.json` | ~180 KB (checked in — input to PR-C) |
| Wall time | ~35 min fetch + ~1 min pipeline |

Crossover-week ground truth is frozen. Cross-reference future worker changes against these JSON artifacts rather than re-scraping.

## Artifacts

- **`docs/testing/crossover_lis_truth.json`** — structured truth for every bill in the universe. Canonical; checked in.
- **`docs/testing/crossover_audit_findings.json`** — categorized discrepancy list. Checked in; input to future PR-C fix work.
- **`/tmp/lis_audit/*.html`** — raw DOM dumps. Not checked in (size); regenerable via `fetch_bills.sh`.
- **`tools/crossover_audit/`** — scripts. Checked in.

## Relationship to PR-C

This audit defines the scope of PR-C (and likely PR-C.1, C.2, C.3 — one per error class, per the [[failures/pr22_post_mortem]] lesson). No PR-C code is written until this page's Findings section is complete and [[state/current_status]] reflects the shipped audit.

## See also

- [[failures/pr22_post_mortem]] — the framework lesson that forced this audit
- [[workflow/source_miss_visibility]] — governing rule
- [[knowledge/lis_dom_scraping]] — the technique used for fetching
- [[testing/crossover_week_baseline]] — historical bug-count tracker (pre-audit baseline)
