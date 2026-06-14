---
tags: [architecture, stress-test, reliability, future]
updated: 2026-06-04
status: active
---

# Stress Test — What Breaks Tomorrow, in 6 Months, in 2 Years

Owner ask (2026-06-04): *"imagine what's going to cause it to fail tomorrow when we visualize it as product, what's going to fail 6 months down the line, what's going to fail in 2 years."* This is the adversarial failure-mode audit. Severity: **HIGH** = breaks the product / silent data loss; **MED** = degraded / needs manual action; **LOW** = self-healing.

## TOMORROW — live product, current data

| # | Failure mode | Sev | Status |
|---|--------------|-----|--------|
| T1 | **Transient Google Sheets 503 on workbook open** fails the entire worker cycle (observed 2026-06-04). | MED | **FIXED (PR-C7.1s):** `open_by_key` now retries 3× with backoff. Cron also recovers next run. |
| T2 | **Concurrent X-Ray viewers** — the Streamlit X-Ray reads the live Sheet/LIS on each load; many simultaneous viewers → Google API read-rate pressure. | MED | **OPEN.** Mitigation: the X-Ray reads the Sheet (cheap) not LIS for the hot path; a shared cache / `st.cache_data` TTL would harden it. The legacy `st_autorefresh` client-poll anti-pattern is NOT present ([[failures/legacy_calendar_versions]] #4). |
| T3 | **Partial HISTORY.CSV** silently truncates the calendar. | HIGH | **FIXED earlier (#68):** Content-Length completeness + retries; empty → write-skip (last-known-good preserved). |
| T4 | **Flaky Session-API window** silently drops the early session. | HIGH | **FIXED earlier (#75):** df_past window clamped to the investigation floor. |
| T5 | **Recovery extension perf** — #1q runs the LegEvent join on every TBA `api_schedule` row (~484). | LOW | Cache-lookup only, no network; negligible per-cycle cost. |

## 6 MONTHS — the 2027 session

| # | Failure mode | Sev | Status |
|---|--------------|-----|--------|
| S1 | **Multi-session cache overflow** — the LegEvent cache is keyed `(bill, session)` and re-persisted in full; a 2027 run would load 2026's ~65k events AND hydrate 2027's ~65k → ~130k > the 120k tab cap → **silent truncation (the #62 bug, recurring annually)**. | **HIGH** | **FIXED (PR-C7.1s):** `_load_legevent_cache(active_session=...)` loads only the active session, so the tab self-prunes the prior session on rollover. |
| S2 | **Cold-start breaker trip** — Jan 2027 the LegEvent cache + `CommitteeName` start empty → blank routes / `"?"` → `meeting_unsourced` spikes for ~8 hydration cycles. If the abs floor were tight it would FREEZE the season start. | MED | **GUARDED:** `CIRCUIT_MAX_MEETING_UNSOURCED_ABS=500` is intentionally loose for exactly this ([[architecture/scalability_audit]]); the delta-vs-baseline is the adaptive guard. Watch the first 2027 cycles. |
| S3 | **Stale investigation window** — config pinned to 2026. | LOW | **FIXED (post-C8) — claim corrected 2026-06-14.** The scrape/processing window is now FULLY auto-derived from the Session API each run (`get_active_session_info` + `extract_dates`, ~L2975); `INVESTIGATION_*` survives ONLY as the offline last-resort fallback. The old manual annual bump **and its #1r staleness WARN were REMOVED** — there is no annual transition touchpoint anymore. Asserted continuously by `sustainability_audit` TEMPORAL (`window-auto-derived`). *(This row and [[verification_durability]] both described the obsolete #1r WARN — fixed.)* |
| S4 | **Forward calendar on live data** — producer/X-Ray (#80/#85) never ran on real future meetings. | LOW | Validated synthetically (the Step-4 harness, `tools/forward_calendar_test/`). |
| S5 | **New vocabulary / EventCodes** — 2027 clerks use new phrasing. | LOW | Structural router + ministerial law + EventType-reference recovery all **self-calibrate** from LIS's own data. **⚠️ CLAIM CORRECTED (2026-06-14):** the prior text here — *"the text fallback patterns are 2026-tuned but only carry blank-route rows"* — was **FALSE**. `MEETING_VERB_TOKENS` were on the meeting path (the I4 breaker signal + the Part C reconciliation) until PR-C8 hardening (#119 + Part C) migrated them to structural signals and **DELETED** the constant. The meeting path is now text-free. **This false-safe claim is exactly how the text bug hid** — and the reason the stress test is now an EXECUTABLE harness (`sustainability_audit`), not a claims ledger. |
| S6 | **Relative-time markers** (#79) depend on LIS publishing `"Senate adjourned"` markers live; a format change breaks the anchor. | LOW | Falls back to the convene time (pre-#79 behavior), never a crash. |
| S7 | **Bot reviewer gap** — Gemini Code Assist sunsets 2026-07-17, BEFORE 2027. | MED | **OPEN — decide before mid-July.** Replacement candidates in [[ideas/future_improvements]] (CodeRabbit / Qodo). Codex unaffected. |

## 2 YEARS — accumulation, scale, rot

| # | Failure mode | Sev | Status |
|---|--------------|-----|--------|
| Y1 | **Hardcoded API keys** (`API_KEY`, `LIS_PUBLIC_API_KEY`) — if LIS rotates them, total break with a 401. | MED | **OPEN.** Keys are public (from the SPA bundle) so historically stable. Harden: discover the key at runtime from `handleTitle.js`, or alert + halt on a 401 storm. |
| Y2 | **LIS API contract change** — a renamed field silently breaks routing/recovery. | HIGH | **FIXED (PR-C7.1s + #127) — status corrected 2026-06-14 (was listed OPEN long after it shipped).** `_EXPECTED_EVENT_KEYS` is asserted against the first fetched LegislationEvent every cycle → CRITICAL `legevent_schema_drift` alert on any rename/removal. Covers all 10 routing/recovery/persist fields (incl. `LegislationEventID`, added #127). `sustainability_audit` UPSTREAM continuously asserts the canary still covers every event field the code reads (so a future field-read forces the canary to grow). The architecture's former deepest single risk — closed. |
| Y3 | **50-state scale** — the text fallback patterns + any VA-specific assumption (committee naming, "Senate adjourned" marker text, the [07:00–23:00] meeting-hours heuristic of #72) are VA-tuned. | MED | The lobbyist-critical path is structural and ports; the **text fallback + a few heuristics need per-state validation** (the one standing Standard-#3 caveat, [[architecture/scalability_audit]]). |
| Y4 | **Dependency rot** — GitHub Actions Node 20 deprecation (warned in logs), `actions/checkout@v3`/`setup-python@v4`, gspread/pandas majors. | MED | **OPEN.** Pin + periodically bump; the Node-20 deprecation has a hard date (2026-09-16). |
| Y5 | **Witness / API_Cache unbounded growth** — append-only across many sessions. | **ACTIVE** | **Witness: FIXED (#126)** — the L3b nightly prune (`tools/witness_retention/prune.py`) deletes `Schedule_Witness` rows >90d, sharing the worker's concurrency group for exclusive tab access. *(It did NOT exist before #126, despite the prior "retention prune exists" claim here — the tab is 51d old so no violation had occurred yet; the prune is preventive.)* **API_Cache: OPEN — live finding (2026-06-14).** `sustainability_audit` CAPACITY caught the **workbook at 79.7% of the 10M cell cap**, with `API_Cache` = **353,811 append-only rows / no row-retention** (the dominant contributor) and a stale **`C7_1a_RawCorpus` (65,447 rows)**. The cell-ceiling guard backstops the LegEvent writes but NOT Sheet1/API_Cache appends. **Remediation pending owner decision** — see [[ideas/future_improvements]]. |

## The standing OPEN items (prioritized)
1. **Y5/API_Cache — workbook capacity** (HIGH, live): the workbook is at **79.7% of the 10M cell cap**; `API_Cache` (353,811 append-only rows) is the unbounded contributor and `C7_1a_RawCorpus` (65,447 rows) is dead. Needs a row-retention/dedup policy for API_Cache + deletion of the stale audit tabs. **Remediation pending owner decision.**
2. **S7 — bot reviewer replacement** (MED, deadline **2026-07-17** — imminent). Codex unaffected.
3. **Y4 — Node-20 / action version bumps** (MED, deadline 2026-09-16). New workflows use `checkout@v4`/`setup-python@v5`; the older one-shot audit workflows still use v3.
4. **Y1 — runtime key discovery or 401-storm halt** (MED).
5. **T2 — X-Ray read caching** for many concurrent product viewers (MED).
6. **Y3 — per-state validation of the text fallback + heuristics** when state #2 onboards.

~~Y2 (LIS field-rename canary)~~ **DONE** (PR-C7.1s + #127). ~~Witness retention~~ **DONE** (#126).

> **This page is no longer a claims ledger — it is enforced by [`tools/verification/sustainability_audit.py`](../../tools/verification/sustainability_audit.py)** ([[verification_durability]] Layer 5), which runs the five trigger classes weekly against the LIVE workbook + code and FAILS on a present danger. S5 and Y2 above had **drifted out of sync with the code in opposite directions** (S5 claimed safe-but-wasn't; Y2 claimed open-but-was-fixed) — the executable harness is the structural fix so a status here can never silently rot again. Any status claim added below should cite the harness check that enforces it, or be marked a hypothesis. See [[failures/assumptions_audit]] (audits-as-claims-rot).
