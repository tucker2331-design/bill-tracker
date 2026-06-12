---
tags: [architecture, plan, hardening, post-c8, standards]
updated: 2026-06-12
status: active
---

# Post-C8.4 Hardening — three grounded, to-standard solutions

The three items deferred at the end of PR-C8.4 ([[state/current_status]]). Each is designed to
meet the [[../CLAUDE|engineering standards]] (zero-assumptions, structural-determinism, self-
describing errors, zero-routine-maintenance, scalable-to-50-states) and is GROUNDED in an existing
in-codebase precedent — no new pattern invented. Implement in the order below (cleanest first).

---

## Solution 3 (do FIRST — cleanest, additive, zero behavior change): G-code drift alert

**Problem (the one fail-UNSAFE gap in C8.4b).** `route_event`'s executive split uses the prefix
families `("G72","G73","G79")` (veto + recommendation). A prefix is fail-SAFE *within* those
families (a new variant over-surfaces). But a brand-new action-required governor family with a
DIFFERENT prefix (say a future `G81xx`) would fall through to the milestone `admin` branch →
buried in the Ledger. Today that gap is silent.

**Standard it must meet:** #1 (static values need a runtime drift check), #4 (self-describing
errors → categorize + route), #8 (humans pinged only for genuine anomalies — a brand-new LIS
EventCode family IS one).

**Grounded design (mirror `validate_status_grouping`, structural_router.py:501).** That function
already does exactly this for LIS Status names: compare the live published vocabulary against our
classified set, return the unclassified ones, caller raises a categorized DRIFT alert. Mirror it
for governor EventCodes:

1. `structural_router.py`: a named set `KNOWN_GOVERNOR_EVENTCODES` = the G-codes we have
   classified (measured 2026-06-11: `G4000, G7010, G7050, G7210, G7220, G7320, G7321, G7322,
   G7324, G7900, G7910, G9998, G9999`), each tagged executive vs milestone in a comment. Plus a
   pure `validate_governor_eventcodes(live_g_codes) -> list[str]` returning observed `G*` codes
   NOT in the set. Pure, never raises, golden-tested (known set → `[]`; a synthetic `G8100` →
   `["G8100"]`).
2. `calendar_worker.py`: while iterating the hydrated LegEvent cache (it already walks every
   event), collect the distinct `G`-prefix EventCodes, then once per cycle call
   `validate_governor_eventcodes(...)`. Non-empty → `push_system_alert(..., category="DATA_ANOMALY",
   severity="CRITICAL", dedup_key="governor_eventcode_drift::"+",".join(new))` — exactly the
   `_validate_status_grouping` call site (calendar_worker.py:3979) does.

**Risk:** none — additive observability; does NOT change routing. **Fail direction:** an unknown
G-code still routes admin (unchanged) BUT now SHOUTS, so the owner classifies it before it can
silently bury a veto twice. **Verification:** golden test + grep the live LegEvent G-codes against
the set (expect `[]` today).

---

## Solution 2 (do SECOND — sharpens the breaker AND removes text): structural `meeting_unsourced`

**Problem.** I4 (the write-time chokepoint, calendar_worker.py:2880) computes the breaker's
`meeting_unsourced` signal by testing the row's Outcome against `MEETING_VERB_TOKENS` — a VA-English
verb list (calendar_worker.py:462). Internal telemetry only (Standard #3's permitted carve-out, NOT
lobbyist-facing) but a text dependency that will not scale to 50 states, and a high-recall PROXY
for the real thing.

**Standard it must meet:** #3 (structural, not text — even for internal diagnostics where feasible),
#6 (no VA-English assumption), #7 (the metric must mean what it says).

**Grounded design.** The thing I4 is trying to detect is *"a row that IS a meeting but has no
time"* — i.e. the Section-9-bug shape. That is **already a structural fact on the row**: the
worker stamps `LegEventRoute` (the `route_event` verdict) before append. So:

1. I4: increment `meeting_unsourced` when `event.get("LegEventRoute") == "meeting"` AND
   `origin in _UNSOURCED_ORIGINS_FOR_METRICS` (journal_default / floor_miss). Delete the
   `MEETING_VERB_TOKENS` test from I4. The signal becomes the TRUE Section-9-bug shape (router
   says meeting, worker couldn't source a time), not a verb proxy.
2. This **sharpens the circuit breaker**: steady-state `meeting_unsourced` collapses from ~150
   (verb-recall noise) toward ~0 (Section 9 = 0 in production), so the Y2 delta-breaker becomes a
   true Section-9-regression detector. The Y2 baseline ratchets down automatically (presence-flag
   grace on the first post-deploy cycle, exactly as PR-C7.0.4 handled the last recalibration).
3. `MEETING_VERB_TOKENS`: the worker no longer references it. Keep the constant ONLY if
   `tools/crossover_audit/diff_sheet1.py` still mirrors it (separate OFFLINE audit tool); migrating
   that tool is out of scope here and tracked separately.

**Risk / guard:** during cold-start cache hydration, blank-route meeting rows (`route==""`) aren't
counted — but the breaker watches the DELTA (a regression), and a hydration transient is not a
regression; steady-state (warm cache) the route is set. Document this. The breaker baseline reset
is automatic (the ratchet). **Verification:** an I4 unit test — `route=="meeting"`+unsourced
origin → counts; `route` in {admin, executive} or a meeting-WITH-time → does not; confirm the live
`meeting_unsourced` drops to its structural floor on the next run; the breaker does not trip
(first-cycle grace) and Y2 ratchets.

---

## Solution 1 (do LAST — largest; includes a beneficial refactor): unconfirmed ROLLING baseline

**Problem.** The accuracy sentinel gates `unconfirmed` against an ABSOLUTE `--unconfirmed-max 150`.
Audit #53's lesson: an absolute threshold whose floor depends on system behavior is a calibration
bug waiting to happen; prefer delta-vs-rolling-baseline; any cycle-stable trip is a bug, not a
transient. The honest floor today is 31 (the irreducible residual); a fixed 150 is both too loose
(won't catch a 31→140 structural drift) and the wrong shape.

**Standard it must meet:** #1, #5 (dynamic config — self-calibrating), #7 (measurable),
audit #53 (delta-vs-rolling-baseline) and #15 (sentinel-value-collision: track presence separately).

**Grounded design (mirror the Y2 / PR-C7.0.4 circuit breaker, calendar_worker.py:5502).** The
rolling-baseline mechanism already exists for `meeting_unsourced` (state cell `Sheet1!Y2`, presence
flag, `delta = max(0, current - baseline)`, ratchet on success, catastrophic absolute floor). The
owner of a rolling baseline MUST be the WORKER (it sees consecutive cycles; the sentinel reads one
snapshot, so sentinel-current ≈ any worker-written baseline from the same cycle → no signal). So:

1. **Beneficial refactor — centralize `classify_action`.** Today it lives in `pages/ray2.py`,
   is duplicated verbatim in `calendar_xray.py` (diff-identical burden), and is AST-extracted by
   the sentinel — three copies of one truth, exactly the "duplicated copy that can drift" the
   structural_router header warns against. Move `classify_action` into `structural_router.py`
   (dependency-free) and have ray2 / calendar_xray / sentinel / **worker** all import it. This
   removes the AST hack and the diff-identical maintenance, and lets the WORKER compute the
   `unconfirmed` count authoritatively from one source. (All existing golden tests stay; add a
   classify_action golden suite.)
2. **Worker:** compute the per-cycle `unconfirmed` count (shared `classify_action` over its rows);
   add an `unconfirmed`-delta ARM to the existing circuit breaker, reading last-known-good from a
   NEW state cell `Sheet1!Y3` with a separate `y3_baseline_present` flag (audit #15). Trip when
   `unconfirmed_delta > K` (a SPIKE = new LIS structure the classifier doesn't cover yet) OR an
   absolute catastrophic floor; improvements ratchet Y3 down; first cycle / cleared / malformed
   Y3 → delta-check inactive (floor still applies). On trip → refuse the Sheet1 overwrite (keep
   last-known-good) — a sudden mass of unclassifiable rows means an LIS schema break, and bank-
   grade behavior is to NOT publish the degraded sheet.
3. **Sentinel:** replace the absolute `--unconfirmed-max` with delta-vs-Y3 (read Y3 from the
   sheet) + keep a generous absolute backstop (mirrors the breaker's catastrophic floor). Now
   self-calibrating.

**Risk / guard:** presence-flag (no zero-collision, audit #15); first-cycle grace; catastrophic
floor backstop; delta only on increases (improvements never trip); the refactor is covered by the
existing + new golden suites and the zero-unexplained-diff gate (classification output must be
byte-identical before/after the move). **Verification:** the move is output-identical (golden +
live-sheet re-classify diff = 0); the breaker arm unit-tested; Y3 ratchets on a green run.

**Why this order:** #3 is additive/zero-risk and closes a fail-unsafe gap immediately; #2 is a
contained I4 swap that also sharpens #1's future signal; #1 is largest (refactor + breaker arm +
sentinel) so it goes last, on the cleaned-up `classify_action` foundation.

Each ships as its own PR through the full Gemini re-audit loop ([[workflow/bot_review_fold_in]]),
with assumptions_audit + log + current_status write-back.
