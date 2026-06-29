---
tags: [ideas, architecture, self-healing, classification, multi-state, parked]
updated: 2026-06-29
status: parked
scope: shared
---

# Self-Healing Classification — design (PARKED, post-VA scale unlock)

The "build & classify instead of the owner" architecture: route on structural PROOF, let LIS's own
authoritative output GRADE + correct the classification, and LEARN the corrections so curation
maintains ITSELF from the source. **Honest reframe:** it does NOT eliminate the dictionary — it makes
the dictionary auto-maintained (the reconciliation loop edits it, not a human). The payoff is **scale**
(50 states without per-state hand-curation), not a VA necessity — VA's curated sets are small + already
drift-ALERTED (status / governor codes / refid shapes / schedule types / reference types all have a
runtime validator). Sequenced AFTER VA is perfect. The VA instance of the multi-state "bulk grades the
scraper" pattern ([[ideas/multi_state_data_strategy]]).

## Status: PARKED 2026-06-29 with 3 owner corrections locked in
Owner (cross-checking with Gemini) caught a product-killing regression + two scaling vulnerabilities in
the first outline. These three corrections are NON-NEGOTIABLE for any future build:

### Correction 1 — Prove-to-HIDE, not "no proof → admin" (the 10-hour blind-spot fix)
The first outline said *"no structural proof → admin by safe default."* **That is a regression** — it
would HIDE a real meeting (clerk forgot the time) in the Ledger until the nightly Referee catches it
~10 h later; the lobbyist misses the meeting. The bug was conflating TWO decisions:
- **meeting vs admin** = the ACTION TYPE (EventCode / `route_event` verdict) — exists with or without a
  time. "Reported from Committee" is meeting-kind even timeless; "Enrolled"/"Bill text" is clerical.
- **confirmed vs unconfirmed** = the PROOF (a time / a vote / a Schedule-API match).

**The rule is Prove-to-HIDE, literally:** a row enters the hidden Ledger ONLY if a structural signal
**positively proves it admin** — a clerical EventCode, OR the batch-notice law (refid shared across ≥K
bills, 0 vote-join — [[knowledge/history_refid_namespace]]), OR a Docket ScheduleClass. **Absent
proof-of-admin it SURFACES**; a meeting-kind action with no confirmed time goes to the **visible
Suspense/Unconfirmed lane** ("time pending"), never the Ledger. The Referee later UPGRADES it (found the
time) or, rarely, DOWNGRADES it.

**Why this beats "surface ALL unproven" (the owner's flooding fear):** the Suspense lane holds only
meeting-CANDIDATES (some signal says meeting) or the genuinely-ambiguous (every signal silent). The bulk
of admin (enrolled / signed / bill-text / batch referrals) is positively proven clerical → Ledger →
never floods the calendar. We surface "everything we can't prove is junk," not "everything unconfirmed."
The residual is tiny — today ≈ the Section-9 number (~0). This is the EXISTING Ledger-collapse discipline
([[workflow/source_miss_visibility]]) made the default, with a visible Suspense lane for the residual.

### Correction 2 — Canonical-ONLY learning (the typo-immune Learned Store)
The Learned Store is **forbidden from memorizing a single character of free text**. The clerk's dropdown
selection becomes a CANONICAL structural ID (EventCode G7050…, StatusID from LIS's published list,
RefidClass) — typo-immune by construction; the hand-typed Description is the free-text part. The store
keys ONLY on canonical IDs (Standard #3, extended to the learning layer). **Guard:** an event with NO
canonical ID (cache-miss / hand-entered) is NOT learnable — it surfaces for a human, never pollutes the
store. Keeps the store mathematically pure + immune to "Recommittted to Commitee"-style garbage.

### Correction 3 — Structural-INTEGRITY breaker, NOT a quantity/delta threshold
Owner rejected a delta-on-correction-COUNT (Gemini's proposal): **quantity is not accuracy.** A HIGH
correction volume is the loop WORKING (caught many of our errors) → tripping punishes success
(over-alert). A LOW volume can be CATASTROPHIC (the Referee broke + confidently mis-corrects 2 marquee
bills) → count says "safe" (under-alert). Matches [[failures/assumptions_audit#53]] (don't gate on a raw
count whose floor depends on behavior). The breaker watches the **foundations**, not the count:
1. **Every correction must be ground-truth-CONFIRMED** — the Referee acts only when LIS's independent
   record (Schedule calendar / MinutesBook) corroborates; never "corrects" on a guess → volume is
   irrelevant to safety.
2. **Trip on STRUCTURAL-INPUT failure:** the structural-proof RATE collapses (EventCode/proof fields
   went null = schema change), OR the drift monitors (`validate_status_grouping` / `validate_reference_types`
   / etc.) fire en masse (a flood of never-seen IDs = vocabulary change), OR the two ground truths
   CONTRADICT each other (calendar says meeting, minutes say no → the answer key is untrustworthy → freeze).
3. If a rate is wanted, put it on the **structural-coverage** metric (an integrity measure), never the
   correction count; treat any cycle-stable trip as a CALIBRATION bug (audit #53), not a transient.

The "state changed their IT system" scenario surfaces as the CAUSE (proof-rate craters, vocab drifts) —
which trips the breaker — not the SYMPTOM (mass corrections). Watch the cause.

## What exists vs. what a build needs
- **Already live (the GRADING machinery):** the reconciliation tripwire (99.67% vs MinutesBook) +
  completeness tripwire (180/180 vs LIS's calendar) — independent ground truth, see [[architecture/verification_durability]].
- **Missing:** (a) flip the classifier to proof-first + the visible Suspense lane (Correction 1);
  (b) make the tripwires AUTO-CORRECT (LIS wins) instead of only alerting; (c) the canonical Learned
  Store (Correction 2); (d) the structural-integrity breaker (Correction 3).

## Hurdles (honest)
1. **Ground-truth COVERAGE is the ceiling** — the loop only auto-fixes what LIS's calendar/minutes cover
   (votes + calendared meetings today; not literally every action). Where the answer key is silent →
   safe-default + Suspense + alert.
2. **LIS's own record has quirks** (cancellations still listed, TBA placeholders — both already hit) →
   "LIS wins" needs guards so we don't import LIS's errors.
3. **Convergence** — the Learned Store must be ordering-independent + idempotent (same class as the STM
   order-invariance work) or the loop oscillates.

See also [[ideas/multi_state_data_strategy]] (bulk-grades-scraper), [[architecture/verification_durability]]
(the 5-layer guard + the sustainability-honesty note), [[ideas/product_vision]] (§7 trust layer — "allowed
not to know, never pretend").
