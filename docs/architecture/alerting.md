---
tags: [architecture, alerting, observability]
updated: 2026-06-16
status: active
---

# Alerting & Bug-Notification Protocol

Where every worker/accuracy alert goes, when each tripwire fires, and what the
notification looks like. Three channels, layered by signal/urgency.

## The three channels

### 1. In-sheet `SYSTEM_ALERT` rows — the complete, pull-only log
Every categorized alert (`push_system_alert` in `calendar_worker.py`) appends a row
to Sheet1:

| Field | Value |
|-------|-------|
| `Bill` | `SYSTEM_ALERT` |
| `Committee` | `System Status` |
| `Outcome` | `[SEVERITY:CATEGORY] message` |
| `Origin` | `system_alert` |

- **Severities:** `INFO`, `WARN`, `CRITICAL`. **Categories:** `TIMING_LAG`, `PARENT_CHILD`, `COMMITTEE_DRIFT`, `API_FAILURE`, `DATA_ANOMALY`, `UNKNOWN` (CLAUDE.md Standard #4).
- **All** severities land here — it's the full record. Deduped within a cycle by `dedup_key`.
- **Pull-only:** the worker stays GREEN; you (or the X-Ray) read these. No push.

### 2. GitHub Actions failure email — the catch-all escalation
Fires whenever a workflow **step exits non-zero**. GitHub emails the repo owner automatically. Triggers:
- Worker uncaught crash.
- **Circuit breaker STUCK** — 3rd consecutive trip → `sys.exit(1)` (see below).
- Session-rollover precondition failure (archive must succeed before overwrite) → raise.
- **Any accuracy-sentinel FAIL** (the script `return 1`s → the step fails).

No setup required — this is on as long as GitHub Actions notifications are enabled for the account.

### 3. Slack ops channel — the fast, high-signal push (opt-in)
`notify_slack()` (worker) / `_notify_slack()` (sentinel) POST to a Slack Incoming
Webhook. **CRITICAL-only by design** — WARN/INFO stay in channel 1 so Slack carries
only "stop and look" events:
- Worker **CRITICAL** `push_system_alert`s (breaker trip, LIS auth failure, I1–I3 data-integrity anomalies).
- Circuit breaker **STUCK** escalation (an extra, louder ping, posted synchronously before `sys.exit`).
- **Accuracy sentinel FAIL** (names the breached invariant(s)).

**Dormant until wired:** if the `SLACK_WEBHOOK_URL` env var (a GitHub secret) is
unset, `notify_slack` is a no-op and the worker/sentinel run byte-identically.
Channels 1 and 2 are unaffected.

## The tripwires — when they go off, exactly

### Mass-violation circuit breaker (`calendar_worker.py`, before the Sheet1 write)
Trips when ANY of:
- `violation_rate > 10%` (I1–I3 invariant violations / rows appended), OR
- `invariant_violations >= 50`, OR
- `meeting_unsourced_delta > 25` vs the `Sheet1!Y2` rolling baseline (only when `last_known_good > 0`), OR
- `meeting_unsourced > 500` (absolute floor, always active).

On trip: Sheet1 overwrite is SKIPPED (last-known-good preserved), `X1`/`W1` record the
trip, a `DATA_ANOMALY/CRITICAL` alert fires (→ in-sheet **and Slack**), and `Y1` is NOT
advanced (so the next healthy cycle gap-backfills). The cycle stays GREEN on a single
trip. `T1` counts consecutive trips; on the **3rd consecutive** the run `sys.exit(1)`s →
GitHub email **and** a louder Slack "CIRCUIT BREAKER STUCK" ping.

### Accuracy sentinel (`tools/verification/accuracy_sentinel.py`)
Runs **after every worker cycle** (`workflow_run` chain) **+ daily cron backstop**.
Reads the LIVE sheet via public gviz CSV (no secrets) and FAILs on any of: Section 9
(meeting-without-time) > 0, unclassified > 0, structural coverage < 97%, router
resolution < 70%, over-derivation, a collapsed/partial sheet, or **staleness** (during
an `S1=ACTIVE` session, newest action > 2 business days old). FAIL → exit 1 → GitHub
email **and** Slack.

> Staleness gate note: `S1` is **schedule-derived** (`is_active AND now <= session_end`),
> never data-derived — otherwise it could never catch a frozen pipeline. See
> [[failures/assumptions_audit]] #90 (the IsActive-outlives-session false-fire).

## What the notifications look like
- **In-sheet:** `[CRITICAL:DATA_ANOMALY] 🚨 CIRCUIT BREAKER TRIPPED at 2026-…Z — …`
- **Slack (worker CRITICAL):** `🚨 *Mastermind Ghost Worker 2 (calendar)* [DATA_ANOMALY]\n<message>`
- **Slack (breaker stuck):** `🛑🛑 *Mastermind Ghost Worker 2 (calendar)* — CIRCUIT BREAKER STUCK\n…`
- **Slack (sentinel):** `🚨 *Accuracy Sentinel FAILED* (calendar) — N invariant(s): STALENESS: …`
- **GitHub email:** standard Actions "run failed" email linking the failed run.

## Wiring Slack (one-time, owner action)
1. Create a Slack **Incoming Webhook** (Slack → app → Incoming Webhooks → Add to a channel) and copy the webhook URL.
2. Add it as a **repo secret** named `SLACK_WEBHOOK_URL` (Settings → Secrets and variables → Actions → New repository secret).
3. Done — both workflows already pass `SLACK_WEBHOOK_URL` to the env; the next CRITICAL/sentinel-FAIL posts to the channel. No code change, no redeploy.

Until step 2, the channel is dormant and channels 1–2 carry everything.

## Related
- [[architecture/calendar_pipeline]] — circuit breaker internals, state-cell map (incl. `AA1` freshness marker).
- [[architecture/stress_test_failure_modes]] — what each guard is meant to catch.
- [[failures/assumptions_audit]] #90 — the staleness false-fire that motivated fixing `S1` before wiring Slack.
