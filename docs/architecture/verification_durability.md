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

## The five layers

| Layer | Cadence | What it guards | Trips when | Where |
|---|---|---|---|---|
| **1. In-cycle circuit breaker** | every cycle (worker) | bad Sheet1 overwrites | `meeting_unsourced` regresses vs rolling baseline (delta) or the abs floor | `calendar_worker.py` |
| **2. Accuracy sentinel** | daily (cron) | the accuracy METRIC | Section 9 > 0, unclassified > 0, **unconfirmed > budget**, sheet collapse, over-derivation, **structural coverage < floor** | `tools/verification/accuracy_sentinel.py` → `🛡️ Accuracy Sentinel` |
| **3. Reconciliation tripwire** | weekly (cron) | DRIFT vs an INDEPENDENT source | committee reports stop matching the official MinutesBook (mis-attribution) above threshold | `tools/reconciliation/reconcile_votes.py` → `🔎 Reconciliation Tripwire` |
| **4. Completeness tripwire** | weekly (cron) | a HIDDEN meeting (the catastrophic failure) | a committee meeting on the LIS Schedule calendar is ABSENT from Sheet1 (join by committee CODE) | `tools/verification/completeness_tripwire.py` → `🗓️ Completeness Tripwire` |
| **5. Sustainability audit** | weekly (cron) | LATENT / future "time-bomb" failures the other four can't see — five enumerable triggers: temporal, capacity, upstream-schema, state-wedge, determinism | a PRESENT danger (over cell-cap, broken retention, an unguarded consumed field, a live dedup collision, a stale wedge marker); trajectory risks WARN, never silently skip | `tools/verification/sustainability_audit.py` → `🧭 Sustainability Audit` |

Layer 5 (added 2026-06-14) is the answer to *"who's to say that's all the bugs, and how do I find them when I step away?"* The other four guard against REGRESSION of known-good state; Layer 5 guards against latent failures wired to a trigger that hasn't fired yet (a year rollover, the workbook filling, an LIS field rename, a wedged baseline, a nondeterministic dedup). It is **convention-driven** — it walks the workbook's ACTUAL tabs and the code's ACTUAL event-field reads — so a future DB addition is auto-covered or auto-flagged. Crucially, it makes [[stress_test_failure_modes]] **executable**: that page had silently rotted (a status claim drifted out of sync with the code, which is how the 2026 text bug hid), and an un-run claim is indistinguishable from a lie once enough time passes. On its first live run it caught a real, unknown finding: the workbook at **79.7% of the 10M cell cap**.

**Why four.** Layer 1 stops bad data from ever being written *this cycle*. Layer
2 re-derives the published accuracy metric from the live sheet using the **same**
`classify_action` as production (now **IMPORTED from `structural_router.py`** — the
single centralized source, post-C8.4c; it was formerly AST-extracted from `ray2.py`,
which this page described until corrected 2026-06-14) and fails if the goal (Section
9 = 0, unclassified = 0) regresses —
the answer to "did new data quietly break it?" Layer 3 is the answer to "who's to
say that's all the bugs?": it diffs our output against a source the pipeline
**never touches** (the official committee minutes), catching *unknown* drift no
internal check could. Layer 4 (PR-C8.3) is the verifiable **no-hidden-meeting**
guarantee — every committee meeting LIS itself calendars must appear in our data
(180/180 = 100% at baseline); a dead Schedule source → `EXTERNAL SOURCE CHANGE`
(exit 2), never a false PASS.

**Two structural-health metrics (sentinel, post-PR-C8).** The classification is now
fully structural (no text patterns). The sentinel reports BOTH: **ROUTER RESOLUTION**
(LegEventRoute / rows, ~83.8% — the original router's reach, the mass-degradation
floor) and **STRUCTURAL COVERAGE** (1 − unconfirmed/rows, ~99.8% — how much is
classified by *any* structural signal: route + RefidClass + ScheduleClass + skeleton).
Coverage is the honest "the 16% is structural now, not text" headline; only the
surfaced `unconfirmed` fail-safe lane is uncovered, and it is never hidden.

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

## Sustainability honesty — the curation inventory + the path past "detect + ping" (owner 2026-06-28)
Owner pushed hard: *"most of the system relies on dictionaries and our great solution was just pinging me
to fix it instead of building it to a groundbreakingly sustainable level."* Straight accounting:
- **STRUCTURAL / dynamic (zero curation, runtime-derived):** committee maps (Committee API), session +
  date windows (Session API), ministerial codes; vote evidence (VoteTally + VOTE.CSV join), meeting times
  (Schedule API + convene graph), outcomes (BILLS.CSV flags). **The bulk of the pipeline.**
- **CURATED (drift-ALERT, not drift-FIX):** `route_event` status groupings (the 52-status admin/meeting
  split), the ReferenceType sets, the 7–23 business-hours window, the `classify_refid` grammars. These are
  FALLBACKS/refinements, each **empirically justified** (e.g. the 05:00 document-batch-time fix that faked
  meeting times — [[failures/assumptions_audit#74]]), each with drift DETECTION — but a genuinely-new
  category still needs human judgment. The refid shape-drift monitor (#178) is more "detect + ping"
  (sanctioned by Standard #8 for structurally-unprecedented variation — but not the ceiling).
- **THE PATH to groundbreaking sustainability (NOT more groupings):** (1) **meeting = PROVEN** (a vote, an
  in-hours wall-clock time, a Schedule match, or a committee-vote refid), never assumed; (2) everything
  else = **admin by SAFE DEFAULT** — a brand-new category can't fabricate a meeting, so no grouping is
  needed; (3) the **5-layer guard as the SELF-CORRECTING backstop** (esp. reconciliation vs the MinutesBook
  + completeness vs LIS's own calendar — independent ground truth), which lets the curated groupings shrink
  toward zero because the loop catches what they miss. **TWO real gaps drive the low confidence:** (a) the
  guard is **INVISIBLE** — it runs in CI and alerts to the sheet, so the owner never SEES 180/180 or 99.67%
  → **surface it (Health tab #6)**; (b) it **ALERTS, doesn't AUTO-CORRECT** → make LIS's calendar AUTO-WIN
  (the multi-state "bulk grades the scraper" pattern, applied to VA classification). **Sequence:** surface
  first (visibility = confidence), then reconciliation→auto-correct, then shrink the curated groupings
  against the loop. This is the real sustainability track, logged so it isn't lost. See [[ideas/multi_state_data_strategy]].
