---
tags: [architecture, audit, scalability, standards]
updated: 2026-07-10
status: active
open_loop: 2 latent debts: HISTORY-vs-LegEvent date drift reconciliation; _clean_legevent_cell heals silently (no counter)
---

# Scalability & Sustainability Audit — Standards Compliance

A standing assessment of the calendar subsystem against the 8 Non-Negotiable Engineering Standards (CLAUDE.md). Re-run and date-stamp this after any architecturally-significant change. Owner's question that prompted it (2026-06-03): *"is everything scalable, sustainable, long-term, and 0-maintenance?"* Re-run 2026-06-07 at owner's request after the Section-9 → 0 work block ("make sure it checks off all of our sustainability demands").

## Verdict (2026-06-07, after Section 9 = 0 via `derived_standing` + ministerial-window + schema-migration)

**Lobbyist-critical path remains sound and self-defending. This block ADDED four NON-blocking gaps that should close before 50-state scale or the 2027 season — none corrupts current output, but each is a real Standard debt.** The new `derived_standing` feature (the flagged last-resort time) is correct and bounded but is the source of three of the four gaps.

| # | Standard | Verdict (2026-06-07) | Gap introduced this block |
|---|----------|----------------------|---------------------------|
| 1 | Zero assumptions + runtime drift-validation | ⚠️ **GAP** | New static heuristics — `MEETING_HOUR_MIN/MAX = 7/23`, `MIN_STANDING_SAMPLES = 3`, the majority rule, the `_build_standing_schedule_maps` exclusion word-list — are documented (#74/#76) but have **no runtime drift check**. Standard #1 demands "a runtime check that validates it." E.g. nothing counts meeting-routed rows whose real timestamp falls OUTSIDE [7,23] (the signal the window is too tight). **Fix G1.** |
| 2 | Bank-grade reliability (breaker + RECONCILIATION) | ⚠️ **GAP (known)** | Circuit breaker intact. But (a) **reconciliation vs LIS is still NOT built** (Standard #2's "periodically diff output against LIS") — the standing latent debt, now Phase B; (b) the breaker watches `meeting_unsourced` but has **no guard on `derived_standing` volume** — an over-derivation bug would LOWER `meeting_unsourced` (looks healthy) while emitting wrong assumed times. **Fix G2 + Phase-B tripwire.** |
| 3 | Data-driven, not text | ⚠️ **caveat (widened)** | `derived_standing` is a SECOND lobbyist-path consumer that parses LIS's published relative-time text ("15 minutes after the Senate adjourns") — same family as #79. Owner-approved, last-resort, FLAGGED (`Origin=derived_standing`, shown as ASSUMED). Honest status: the lobbyist path is structural EXCEPT the flagged derived time + the existing blank-route text classifier. |
| 4 | Self-describing errors | ✅ (mostly) | `derived_standing` counter exists; a declined derivation falls through to the visible `NO_SCHEDULE_MATCH` alert. Minor: no metric for the derivation's denominator (see #7). |
| 5 | Dynamic configuration | ✅ | Modal patterns + adjourned clocks are DERIVED from the Schedule API each cycle (`_build_standing_schedule_maps`); nothing new hardcoded except the heuristics in #1. |
| 6 | Scalability to 50 states | ⚠️ **GAP (new surface)** | `derived_standing` hardcodes VA/English specifics: chamber names "Senate"/"House", the "adjourned" marker concept, the "X minutes after [chamber] adjourns" grammar, and English exclusion words. It IS isolated to 2 functions (Standard #6 "isolated and swappable" — half-met) but **not parameterized** — it ports only with per-state tuning. New VA-specific surface area GREW this block. **Fix G3 (extract a per-state config block).** |
| 7 | No vibe coding (metric needs a DENOMINATOR) | ⚠️ **GAP** | `derived_standing = 1` is a bare numerator. The owner's own rule: a metric needs a denominator. Missing: "of N committee-report rows unsourced by any real source, M were derived, K stayed timeless." Without it we can't see if derivation is over/under-firing. **Fix G4.** |
| 8 | Zero routine maintenance | ✅ (with #6) | Self-calibrating across VA sessions (modal re-derives from each session's Schedule API). The per-state tuning of #6 is a one-time onboarding cost, not routine. The Phase-B tripwire would further reduce the "human watches the count" residue. |

### Actionable fixes from this audit (small, batched as one PR after #100 merges)
- **G1 — out-of-window drift counter:** count meeting-routed rows whose real timestamp is outside `[MEETING_HOUR_MIN, MEETING_HOUR_MAX]`; surface in `SYSTEM_METRICS` so a too-tight window is visible (Standard #1/#4). Cheap.
- **G2 — `derived_standing` volume guard:** it is a LAST resort and should be rare; alert (WARN) if it exceeds a small absolute count in a cycle (signal of over-derivation / a modal-map bug). Standard #2/#4.
- **G3 — isolate the VA-specifics:** lift chamber names + the adjourned-grammar tokens + exclusion words into a clearly-labeled per-state config block (Standard #6) so state #2 swaps a table, not code.
- **G4 — derivation denominator:** emit `derived_eligible` (committee-report rows unsourced by a real source) alongside `derived_standing` and `derived_declined`, so the metric has a denominator (Standard #7).

*(G1/G2/G4 are quick; G3 is a refactor. None blocks current correctness — `derived_standing=1` and bounded. Held until #100 merges to avoid `calendar_worker.py` conflicts.)*

---

## Verdict (2026-06-03, after Section 9 = 1,072 → 25) — superseded, kept for history

## Verdict (2026-06-03, after Section 9 = 1,072 → 25)

**Mostly YES — the architecture is scalable, sustainable, and self-defending — with ONE honest caveat (text-classifier fallback) and a few tiny upstream-limited residue items. No standard is violated on the lobbyist-critical path.**

## Standard-by-standard

| # | Standard | Verdict | Evidence |
|---|----------|---------|----------|
| 1 | Zero assumptions | ✅ | Fixes #71/#72 derive everything from LIS fields. `_clean_legevent_cell` assumes only that `"None"/"null"/"nan"` are never legitimate LIS structural-field values — true by construction. |
| 2 | Bank-grade reliability | ✅ | Real **circuit breaker** (`calendar_worker.py` ~4606): on a `meeting_unsourced` regression (delta vs rolling Y2 baseline) it **refuses the Sheet1 overwrite to preserve last-known-good** rather than writing bad data. |
| 3 | Data-driven, not text | ⚠️ **caveat** | Lobbyist-CRITICAL path (meeting + needs-time) is ~99.9% structural (25 residue of ~17.6k meeting rows). BUT the X-Ray text classifier is still the **fallback for ~16% of rows** whose `LegEventRoute` is blank. See *The one real caveat* below. |
| 4 | Self-describing errors | ✅ | Breaker emits a categorized alert; `SYSTEM_METRICS` counters carry denominators; drift values fall through to text + a CRITICAL drift alert (never a silent break). |
| 5 | Dynamic configuration | ✅ | Session code DERIVED from `Session/api/GetSessionListAsync` at runtime (`_normalize_session_code_5d`); committee maps from the Committee API. Only API keys + a single session-code fallback are static. |
| 6 | Scalability to 50 states | ✅ | #71 (sibling-time inheritance) and #72 (null-cell normalization) carry **zero vocabulary, zero per-state config** — they port unchanged. The structural router consumes LIS's own published fields. |
| 7 | No vibe coding | ✅ | Every fix measured with before/after + denominator (114→3, 69→1, 1,072→25). |
| 8 | Zero routine maintenance | ✅ (with #3 caveat) | The breaker is the autonomous guardian — no human needs to watch the count; a regression auto-trips and preserves last-known-good. The per-state-maintenance risk is the text fallback (#3). |

## The one real caveat — text-classifier fallback (Standard #3)

- **What:** when `_route_for_row` can't match a Sheet1 row to a cached LegislationEvent, `LegEventRoute` is blank and the X-Ray's `classify_action` falls back to VA-tuned English text patterns (`ADMINISTRATIVE_PATTERNS` / `MEETING_ACTION_PATTERNS`).
- **Magnitude (measured 2026-06-03):** 5,837 / 35,486 rows blank-route (16.4%). Of those: **5,832 text→administrative, 3 → meeting, 2 unclassified.**
- **Why it is mostly benign:** the blank rows are dominated by `api_schedule` (3,036 — already STRUCTURALLY resolved via the Schedule API; they carry real times, blank route just means the route column wasn't the resolver) and genuinely event-less administrative HISTORY rows (referrals, printings) that have NO LegislationEvent to match. The text patterns are shared English legislative verbs ("referred", "reported", "passed") that are **likely** portable across states — but this is **not yet validated per-state.**
- **The honest risk for 50 states:** a new state whose clerks use different administrative phrasing could mis-classify some blank-route admin rows. It would NOT silently corrupt the lobbyist-critical meeting-time path (that's structural), but it could mis-file an admin row. **Mitigation path (if/when it matters):** extend structural route coverage so blank-route → near-0 (then text is a true rare fallback), OR derive an EventType→category reference from LIS at runtime (Standard #5). Not built; tracked here.

## Things that LOOK like debt but are justified (do not "fix")

- **Circuit-breaker absolute floor `CIRCUIT_MAX_MEETING_UNSOURCED_ABS = 500`** vs the current steady state of `meeting_unsourced = 4` looks ~125× too loose (audit point #14). **It is justified:** the 2027 cold-start transiently spikes `meeting_unsourced` into the thousands before the ~8-cycle hydration fills the cache; a tight absolute floor would trip the breaker and freeze the 2027 season start. The **delta-vs-rolling-baseline (25)** is the real adaptive guard; the absolute floor is only the baseline-absent catastrophic backstop. **No change** — revisit only with 2027 cold-start telemetry.

## Remaining Section-9 residue is upstream-limited, not architectural

The 25 residue is dominated by cases where the structural sources genuinely lack the answer: 15 empty-status admin (LIS encodes them identically to floor reads; only a per-state EventCode dictionary separates them), 2 LIS-published `Time TBA`, 3 HISTORY-vs-LegEvent date drift, 1 #71 conservative non-guess, and even the "fixable-looking" SJ209 P&E vote is **not in DOCKET.CSV** (confirmed 2026-06-03) — so its time isn't in our structural sources either. **The pipeline has extracted essentially everything the upstream data allows without a probabilistic guess.**

## Latent debts worth a future look (small, non-blocking)

1. **HISTORY-vs-LegEvent date drift** — the calendar places a row by HISTORY date, which can be 1–2 days off LIS's authoritative LegEvent date (cause of the 3 residual governor rows). A reconciliation that prefers the LegEvent (gold-standard) date for placement would fix both the Section-9 rows and a latent calendar-accuracy issue. Carries match-care (do it only for unambiguous single-occurrence events).
2. **No `_clean_legevent_cell` normalization counter** — the heal is silent; a flood of normalized cells (signal of an upstream schema change) wouldn't surface. Trivial Standard-#4/#9 visibility add.

## Curation-debt inventory — the "what else is hiding?" sweep (owner 2026-06-28)
Owner: the curated-dictionary / detect-vs-fix concern only surfaced because they watched — *"makes me
concerned for what else might be hiding."* So a SYSTEMATIC sweep of `structural_router`'s curated domain
values, graded by whether each has the paired runtime DRIFT-ALERT its siblings have (Standard #1).
**Re-run this whenever a change adds or grows a curated set** (the new CodeRabbit sustainability lens, PR #179,
now also flags it on any future addition).

| Curated value | Drift-alert? | Note |
|---|---|---|
| `ADMIN_PIPELINE_STATUSES` / `MEETING_INSESSION_STATUSES` | ✅ `validate_status_grouping` | the gold-standard pattern |
| `KNOWN_GOVERNOR_EVENTCODES` | ✅ `validate_governor_eventcodes` | |
| refid grammars + `KNOWN_REFID_SHAPES` | ✅ `validate_refid_shapes` (#178) | |
| **`DOCUMENT_REFTYPES` / `REFERRAL_REFTYPES`** | ✅ **FIXED 2026-06-28** | `validate_reference_types` + `KNOWN_REFERENCE_TYPES` (seeded from the MEASURED live LegEvent_Events vocab: Vote/LegislationText/LegislationFile/Committee/Subcommittee/Legislation/Minutes/Calendar) wired into the worker post-loop over the cache's ReferenceTypes — a new value now alerts instead of riding the vote/time/else fallback silently. Golden-tested; silent today (no first-run noise). |
| **`_SCHEDULE_TYPE_MAP`** (ScheduleTypeID→label) | ✅ **FIXED 2026-06-28** | `validate_schedule_types` (mirrors `validate_status_grouping`) wired into the worker post-loop over the live `_schedule_typeid_by_key` values — a new ScheduleTypeID now alerts `WARN/DATA_ANOMALY` instead of silently bucketing to `SCHED_OTHER`. Golden-tested. |
| `MEETING_HOUR_MIN/MAX`, `_VOTE_ID_MIN_LEN` | ❌ none | measured physical/structural constants (legislative hours; the len≥7 vote-id boundary). Lower drift-risk; document the measurement + a periodic re-measure, not a per-cycle alert. |

**The 3 ❌ rows WERE the answer to "what's hiding" — same class as the status grouping, minus the drift-alert.**
Each failed safe (an unrecognized value routes by a later rule / surfaces as `SCHED_OTHER`) but would
silently rot on an upstream change. **✅ BOTH classification-set gaps are now CLOSED (PR #180, 2026-06-28):**
`validate_schedule_types` (the ScheduleType map) + `validate_reference_types` (the ReferenceType vocab,
seeded from a measured LegEvent_Events probe — no noisy first run). Both wired into the worker post-loop
alongside the refid-shape monitor, each with the surface-don't-just-print except (audit #48). The remaining
`MEETING_HOUR`/`_VOTE_ID_MIN_LEN` are physical/structural CONSTANTS (legislative hours; the len≥7 vote-id
boundary), not classification sets — lower drift-risk, kept as documented-measurement + periodic re-measure
rather than a per-cycle alert. So the "curated value without a drift-alert" class is now empty for the
classification maps. See [[architecture/verification_durability#Sustainability honesty — the curation inventory + the path past "detect + ping" (owner 2026-06-28)]].
