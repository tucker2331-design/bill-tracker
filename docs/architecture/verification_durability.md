---
tags: [architecture, verification, reliability, durability, standards]
updated: 2026-06-07
status: active
---

# Verification & Durability — How Accuracy Survives the Session Boundary

Owner ask (2026-06-07): *"ensure we're shipping banking-grade software, and next
session it won't lose this level of accuracy because of new data."* You cannot
verify next session's data by hand — it doesn't exist yet. So accuracy is
protected by **three automated, session-agnostic layers** that run forever, catch
regressions themselves, and require no per-session human action (Standard #2 +
#8). All read the **active** session's output (the live sheet / the live APIs),
so 2027 is covered the moment the worker writes to it — no code change, no
re-audit.

## The three layers

| Layer | Cadence | What it guards | Trips when | Where |
|---|---|---|---|---|
| **1. In-cycle circuit breaker** | every 15 min (worker) | bad Sheet1 overwrites | `meeting_unsourced` regresses vs rolling baseline (delta) or the abs floor | `calendar_worker.py` |
| **2. Accuracy sentinel** | daily (cron) | the accuracy METRIC | Section 9 > 0, unclassified > 0, sheet collapses below the floor, or over-derivation | `tools/verification/accuracy_sentinel.py` → `🛡️ Accuracy Sentinel` |
| **3. Reconciliation tripwire** | weekly (cron) | DRIFT vs an INDEPENDENT source | committee reports stop matching the official MinutesBook (mis-attribution) above threshold | `tools/reconciliation/reconcile_votes.py` → `🔎 Reconciliation Tripwire` |

**Why three.** Layer 1 stops bad data from ever being written *this cycle*. Layer
2 re-derives the published accuracy metric from the live sheet using the **same**
`classify_action` as production (extracted from `ray2.py` at runtime, so it can
never drift) and fails if the goal (Section 9 = 0, unclassified = 0) regresses —
the answer to "did new data quietly break it?" Layer 3 is the answer to "who's to
say that's all the bugs?": it diffs our output against a source the pipeline
**never touches** (the official committee minutes), catching *unknown* drift no
internal check could.

## Why this is session-agnostic (2027-safe)
- The worker derives session code, committee maps, ministerial codes, the modal
  schedule maps, and the convene/adjourned graph from the LIS APIs **each cycle**
  — nothing is hardcoded to 2026 (the one pinned constant, the investigation
  window, raises a WARN when stale: audit #1r).
- All three guards read the **active** output, not a 2026 snapshot. The sentinel's
  only absolute is the partial-sheet floor (5000 rows) — well below any real
  session, well above a collapse.
- The cache self-prunes the prior session on rollover (audit #73), and a cold
  2027 start drains Tier A then self-heals (stress-test S1/S2).

## What "verified" means here (honest scope)
- **Section 9 = 0** and **unclassified = 0** are measured against the FULL live
  sheet every day (the goal, both halves).
- Committee reports are **99.67%** confirmed against the independent official
  minutes (weekly), plus a live-LIS-website spot-check (committee+vote+date exact
  on every bill checked).
- **Not** a row-by-row independent proof of all ~35k rows' every field — that's
  impossible to sustain and unnecessary: the three layers make any *regression*
  fail loudly, which is the bank-grade guarantee (continuous detection), not a
  one-time snapshot.

## If a layer trips
The workflow run fails → GitHub notifies. Triage: (1) read the failing
invariant + its example rows, (2) check whether it's a real regression or an
upstream LIS change (schema canary / new vocabulary), (3) the worker's breaker
has already preserved last-known-good for the in-cycle case. Never silence a
tripped guard without finding the cause — that's the #62/#72/#82 lesson.
