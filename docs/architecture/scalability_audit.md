---
tags: [architecture, audit, scalability, standards]
updated: 2026-06-03
status: active
---

# Scalability & Sustainability Audit — Standards Compliance

A standing assessment of the calendar subsystem against the 8 Non-Negotiable Engineering Standards (CLAUDE.md). Re-run and date-stamp this after any architecturally-significant change. Owner's question that prompted it (2026-06-03): *"is everything scalable, sustainable, long-term, and 0-maintenance?"*

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
