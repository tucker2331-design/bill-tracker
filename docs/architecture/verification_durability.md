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

## Anti-"homework-grading" invariants (Gemini architectural review, audit #78)

A guard that only watches BAD outcomes is defeated by **graceful degradation**:
if 2027 LIS breaks its schema, the worker cleanly routes everything to the
fallback/Ledger, `meeting_unsourced` / Section 9 stay 0, and a bad-outcome
ceiling reports PASS over a silent catastrophe. So the guards include **positive
invariants** and **dead-source detection**:

- **Structural-resolution FLOOR (sentinel):** non-blank `LegEventRoute` /
  legislative rows must stay ≥ 70% (baseline ~83.6%). Mass degradation
  *collapses* this — that IS the failure being measured, so it can't be gamed by
  the worker "handling" the break. The positive-health complement to the
  breaker's single negative signal.
- **EXTERNAL SOURCE CHANGE (tripwire):** the reconciliation depends on the LIS
  **MinutesBook JSON API** (not HTML/PDF scraping — more stable, but still
  external and versionable). If it returns too few books or the fetch throws, the
  tripwire raises a distinct `EXTERNAL SOURCE CHANGE` failure (exit 2) — an empty
  independent source verifies nothing and must never read as "0 drift / PASS."
- **Structural, not text, identity:** the worker's own diagnostic rows are
  excluded by the structural `Source == "SYSTEM"` flag, never the "System Status"
  committee text (Standard #3).

**Known proliferation (acknowledged, not "fixed"):** the in-cycle **circuit
breaker** watches `meeting_unsourced`, which graceful mass-degradation also drives
to 0 — the same blind spot. Its trip logic is left unchanged on purpose (it is
delicately calibrated; a new input risks freezing the 2027 cold start — audit
#53). The sentinel's structural-resolution floor is its deliberate macro-degradation
complement: the breaker guards per-cycle on its calibrated signal; the sentinel
(daily, non-gating) catches the mass-degradation a single signal can't.

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

## Is it TRULY session-agnostic? (the honest confirmation)

**YES for all logic and all three guardrails — with ONE deliberate, self-alerting
annual transition point, not routine maintenance.**

Session-agnostic by construction:
- The worker derives session code, committee maps, ministerial EventCodes, the
  modal schedule maps, and the convene/adjourned graph from the LIS APIs **every
  cycle** — re-calibrated from 2027's own data, no 2026 constants in the logic.
- All three guards read the **active** session's live output/APIs, never a 2026
  snapshot, and their thresholds are session-stable invariants (resolution ≥ 70%
  vs ~83.6% baseline; drift ≤ 1%; derived ≤ 25; ≥ 50 minutes books).
- New features degrade safely on a cold 2027 cache (DR1 dry-run: empty maps →
  no derivation, all-Tier-A hydration, no spurious back-fill).
- The cache self-prunes the prior session on rollover (#73); the breaker
  preserves last-known-good through the cold-start spike (#75 clamp + S2).

The one NON-automatic touchpoint (deliberate, self-alerting — Standard #8's
"deliberate annual transition," not "routine maintenance"):
- **`investigation_config.py` window** is pinned (`INVESTIGATION_END=2026-05-01`).
  When the 2027 session starts, the worker raises a WARN that the window is stale
  (#1r); the operator updates it **once** (~5 min). Until then the worker still
  functions on the #75-clamped window.

One session-START watch item (first ~1-2 weeks of a new session only): the
sentinel's absolute row-floor (5000) and resolution-floor assume a populated
sheet. Early in a fresh session the sheet is still ramping; the breaker's
last-known-good preservation covers most of this (the sheet shows carried-forward
data until 2027's cache warms), but confirm the sentinel isn't tripping on a
legitimate early-session ramp before treating it as a regression.

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
