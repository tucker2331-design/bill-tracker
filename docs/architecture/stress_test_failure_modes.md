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
| S3 | **Stale investigation window** — config pinned to 2026; viewport/metrics anchor to the old window. | MED | **GUARDED (#1r):** runtime WARN when the active session starts after `INVESTIGATION_END`; `blob_code` is already session-derived and the #75 clamp keeps it functioning. Operator updates `investigation_config.py` once (deliberate annual transition, not routine). |
| S4 | **Forward calendar on live data** — producer/X-Ray (#80/#85) never ran on real future meetings. | LOW | Validated synthetically (the Step-4 harness, `tools/forward_calendar_test/`). |
| S5 | **New vocabulary / EventCodes** — 2027 clerks use new phrasing. | LOW | Structural router + ministerial law + EventType-reference recovery all **self-calibrate** from LIS's own data. The text fallback patterns are 2026-tuned but only carry blank-route rows. |
| S6 | **Relative-time markers** (#79) depend on LIS publishing `"Senate adjourned"` markers live; a format change breaks the anchor. | LOW | Falls back to the convene time (pre-#79 behavior), never a crash. |
| S7 | **Bot reviewer gap** — Gemini Code Assist sunsets 2026-07-17, BEFORE 2027. | MED | **OPEN — decide before mid-July.** Replacement candidates in [[ideas/future_improvements]] (CodeRabbit / Qodo). Codex unaffected. |

## 2 YEARS — accumulation, scale, rot

| # | Failure mode | Sev | Status |
|---|--------------|-----|--------|
| Y1 | **Hardcoded API keys** (`API_KEY`, `LIS_PUBLIC_API_KEY`) — if LIS rotates them, total break with a 401. | MED | **OPEN.** Keys are public (from the SPA bundle) so historically stable. Harden: discover the key at runtime from `handleTitle.js`, or alert + halt on a 401 storm. |
| Y2 | **LIS API contract change** — a renamed field (`CommitteeName`, `VoteTally`, `ReferenceType`) silently breaks routing/recovery. | HIGH | **PARTIAL.** `validate_status_grouping` alerts on new Status values; there is NO equivalent canary for renamed/removed FIELDS. Add a per-cycle schema assertion on the first fetched event ([[ideas/future_improvements]]). |
| Y3 | **50-state scale** — the text fallback patterns + any VA-specific assumption (committee naming, "Senate adjourned" marker text, the [07:00–23:00] meeting-hours heuristic of #72) are VA-tuned. | MED | The lobbyist-critical path is structural and ports; the **text fallback + a few heuristics need per-state validation** (the one standing Standard-#3 caveat, [[architecture/scalability_audit]]). |
| Y4 | **Dependency rot** — GitHub Actions Node 20 deprecation (warned in logs), `actions/checkout@v3`/`setup-python@v4`, gspread/pandas majors. | MED | **OPEN.** Pin + periodically bump; the Node-20 deprecation has a hard date (2026-09-16). |
| Y5 | **Witness / API_Cache unbounded growth** — append-only logs across many sessions. | MED | Retention prune exists for the witness; the cell-ceiling headroom guard (`LEGEVENT_WORKBOOK_CELL_CEILING`) + grow-or-alert (#61) backstop the workbook. S1's session-prune removes the largest contributor. |

## The standing OPEN items (prioritized)
1. **Y2 — LIS field-rename canary** (HIGH, cheap): assert the expected keys on the first fetched event each cycle; alert on drift. The structural architecture's single point of failure.
2. **S7 — bot reviewer replacement** (MED, deadline mid-July 2026).
3. **Y4 — Node-20 / action version bumps** (MED, deadline 2026-09-16).
4. **Y1 — runtime key discovery or 401-storm halt** (MED).
5. **T2 — X-Ray read caching** for many concurrent product viewers (MED).
6. **Y3 — per-state validation of the text fallback + heuristics** when state #2 onboards.

Everything marked FIXED above was closed in this session's stress pass (PR-C7.1s) or earlier (#61/#62/#68/#75). The architecture's deepest single risk is **Y2 (a silent LIS field rename)** — worth the canary next.
