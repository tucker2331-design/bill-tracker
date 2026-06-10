---
tags: [architecture, plan, structural, classification, pr-c8]
updated: 2026-06-09
status: active
---

# PR-C8 Execution Spec — Close the 16% Structurally (NO TEXT ON THE LOBBYIST PATH)

**Audience: the implementing model.** This spec was produced by an extended deep-reasoning
session (2026-06-09) after several wrong turns. Your job is to EXECUTE it, not re-design it.
Where this page and your instinct disagree, this page wins. Where reality and this page
disagree (a measurement fails a gate), you STOP and escalate — you do not improvise.
Background knowledge: [[knowledge/history_refid_namespace]] (the discovery this is built on),
[[architecture/verification_durability]], [[knowledge/lis_api_authorization]].

## Mission

Replace the hand-built text-pattern classification of blank-route rows (the "16%") with a
fully structural decision chain, keeping Section 9 = 0 and unclassified = 0, via three PRs:
C8.1 (shadow), C8.2 (flip), C8.3 (guards). Definition of done is at the bottom.

---

## HARD RULES (violating any of these = stop and revert)

1. **NO PROSE ON THE DECISION PATH.** A row's classification may consume ONLY:
   `LegEventRoute` (EventCode-derived), `ScheduleTypeID`, `History_refid` (its typed grammar
   + joins), VOTE.CSV join results, LegislationEvent presence/absence, dates, bill IDs,
   committee CODES (H01–H24/S01–S13). **FORBIDDEN inputs:** `History_description`, `Outcome`
   text, `OwnerName` text, any regex/substring/keyword test on prose.
   - *Litmus test:* "If LIS replaced every description with random UUIDs tomorrow, would any
     row's classification change?" The answer must be NO.
   - Parsing the refid's grammar (`H14V2610034` → committee H14, vote 2610034) is **allowed**
     — refid is a typed identifier, like an EventCode. Reading sentence text is not.
   - The existing exact-match empty-outcome guard (`"" / "none" / "nan"` → skeleton row) is a
     **null check**, not prose parsing. Keep it.
   - Text MAY appear in diagnostics/telemetry/audits that never change a row's class
     (Standard #3 carve-out). `MEETING_VERB_TOKENS` in the worker is telemetry-only today;
     it must never gate a classification. Do not repurpose it.
2. **FAIL-SAFE DIRECTION.** No structural proof → the row SURFACES (visible, flagged
   "unconfirmed"). Hiding (ledger) requires positive structural proof. Never invert this.
3. **LIS AUTHORIZATION.** Only sessions in `lis_authorization.LIS_API_AUTHORIZED_SESSIONS`
   (2025/2026 until LIS notifies). Never remove or bypass the existing gates. Never add a
   pre-2025 call. An API ban ends the product.
4. **`pages/ray2.py` and `calendar_xray.py` stay diff-identical.** Every edit to one is
   applied verbatim to the other; verify with `diff -q` before commit (pre-push audit #4).
5. **PROCESS:** branch → PR → request Gemini review → fold in ALL real findings → verify
   "stale" re-emissions against the actual code lines before dismissing them → dispatch a
   branch worker run → sentinel all-green → merge. Never merge before the review lands.
   Always push after committing. Log every PR in [[log]].
6. **SHADOW BEFORE FLIP.** C8.1 must cause zero visible change (new telemetry column only).
   C8.2 flips only after C8.1's gates pass on live production data.
7. **ZERO-UNEXPLAINED-DIFF GATE.** Before merging C8.2, enumerate every row whose class
   changes vs the pre-flip sheet. Each diff is either (a) individually explained and listed
   in the PR body, or (b) you STOP. "Close enough" does not exist.
8. **NEVER TUNE A THRESHOLD TO MAKE A GATE PASS.** If a gate fails (e.g., a batch document
   turns out to contain a vote join), that is a DISCOVERY: write it to
   `docs/failures/assumptions_audit.md`, update [[state/current_status]], and stop for the
   owner. Adjusting K or a budget until the number goes green is forbidden (audit #78:
   homework-grading).
9. **SPA-SHELL FALSE 200s.** Any `lis.virginia.gov` probe returning 200 with HTML (the React
   shell) is a NONEXISTENT endpoint. Require `application/json` + parseable body. (See
   [[knowledge/history_refid_namespace]] §lesson.)
10. **Do not touch the circuit breaker's trip logic** (calibration risk, audit #53), and do
    not modify `lis_authorization.py` except to add a newly-authorized session code.
11. **Raw-CSV semantics for the live sheet** in any verifier: use Python's `csv` module, not
    pandas (pandas NaN-converts `"None"` — prior bug class).
12. **Session-agnosticism:** no `20261` literals in new logic; derive session/blob_code as
    the worker already does. All new constants named, documented, and session-independent.

---

## The structural decision chain (target state after C8.2)

For every row, in order; first hit wins:

| # | Signal (structural only) | Class |
|---|---|---|
| 1 | `LegEventRoute == "meeting"` | meeting |
| 2 | `LegEventRoute == "admin"` | administrative |
| 3 | Skeleton row (empty/none/nan Outcome; Schedule-origin) | administrative (calendar entry carries its own time) |
| 4 | Vote-refid with confirmed VOTE.CSV join | meeting |
| 5 | **Batch-notice law**: numeric refid shared by ≥K same-date bills AND no vote join AND no LegislationEvent instance | administrative (ledger) |
| 6 | Committee-code refid (`H14`/`S04`) with no other signal | administrative |
| 7 | Anything else | **unconfirmed → SURFACES visible+flagged** |

The batch-notice law's justification (do not re-litigate): deliberation is recorded per bill
(votes per bill+member in VOTE.CSV); a clerk document fanning across dozens of bills with
zero votes is administrative BY STRUCTURE. Measured 2026-06-09: 2,675/2,765 blank-route
journal rows (96.7%) at K=4 with **0 counterexamples** (rule of three: p < 0.11%).

---

## PR-C8.1 — Structural evidence layer (SHADOW MODE)

**Goal:** worker stamps a telemetry column; nothing visible changes.

1. **Pure function** in `structural_router.py`:
   `classify_refid(refid, *, fanout, has_vote_join, has_legevent) -> str` returning one of
   `VOTE_JOIN | VOTE_REF_UNMATCHED | BATCH_NOTICE | SINGLETON_DOC | COMMITTEE_REF | EMPTY`.
   Pure, no I/O, full docstring, golden tests in the PR body (cases below).
2. **Per-cycle indexes** in `calendar_worker.py` (build once, like the committee maps):
   - VOTE.CSV via `safe_fetch_csv` on the session blob. Vote id = first column of each row
     (digit-string like `26110000`). **Beware:** the header row is junk (`'10458X'`); skip
     non-digit first columns. Sanity: in-session count should be hundreds (1,606 in 20261).
     If the file is empty/missing → categorized WARN (`API_FAILURE`), vote-join treated as
     unavailable, rows fall through toward SURFACE (fail-safe), cycle continues.
   - Fan-out index from the HISTORY iteration the worker already does:
     `(numeric_refid, date) -> set(bills)`.
3. **OPEN ITEM you must resolve empirically (do NOT assume):** the V-refid suffix ↔ VOTE.CSV
   id correspondence. `H14V2610034` suffix is 7 digits; VOTE.CSV ids seen are 8 digits
   (`26110000`). Measure the join across ALL ~5,657 V-refid rows; report the match rate in
   the PR. ≥99% → use the join. Below → classify those rows `VOTE_REF_UNMATCHED` (which
   SURFACES, fail-safe) and record the finding in assumptions_audit. Never fabricate a
   mapping rule you didn't measure.
4. **Choose K empirically from the native side:** measure K=2,3,4 fan-out distributions and
   counterexample counts (batch candidates that DO have a vote join or LegislationEvent).
   Pick the smallest K with zero counterexamples; document the choice + the rule-of-three
   bound in the PR and in this page. (Expectation from the sheet-side measurement: K=2 or 3;
   small committees post 2–3-bill agendas.)
5. Worker writes `RefidClass` to every row (new column, additive; follow the PR-C7.1b-1
   pattern used when `LegEventRoute` was added). Telemetry counters `refidclass_*` in
   `source_miss_counts` + one metrics print line.
6. **Gates to merge C8.1:** parse-clean; import-clean from `pages/` (audit #8); branch worker
   run success with processed-count unchanged (±normal drift); sentinel all-green; from the
   post-run sheet: ≥96% of blank-route journal rows are `BATCH_NOTICE`, `BATCH_NOTICE ∩
   vote-evidence = 0`, residual (`SINGLETON_DOC`+`VOTE_REF_UNMATCHED`+unmatched) dumped in
   the PR body and ≤ ~120 rows. Any gate fails → Hard Rule 8.

**Golden tests (encode verbatim):**
- `("H14V2610034", fanout=0, vote_join=True, legevent=False)` → `VOTE_JOIN`
- same with `vote_join=False` → `VOTE_REF_UNMATCHED`
- `("5354", fanout=63, vote_join=False, legevent=False)` → `BATCH_NOTICE`
- `("5141", fanout=1, ...)` → `SINGLETON_DOC`
- `("H14", ...)` → `COMMITTEE_REF`;  `("", ...)` → `EMPTY`
- `("5354", fanout=63, vote_join=True, ...)` → must NOT be `BATCH_NOTICE` (law violated →
  classify `VOTE_JOIN`, and the cycle-level counterexample counter increments)

## PR-C8.2 — The flip (text leaves the lobbyist path)

1. `classify_action` (in BOTH ray2 and calendar_xray, identically) becomes the chain in the
   table above, consuming `(legevent_route, refid_class, outcome_for_null_check_only)`. The
   three pattern lists (`MEETING_ACTION_PATTERNS`, `ADMINISTRATIVE_PATTERNS`,
   `ADMIN_OVERRIDE_PATTERNS`) are DELETED from both files. If any X-Ray diagnostic section
   still wants them for display, it moves to a clearly-marked diagnostics block that
   `classify_action` cannot reach; prefer deletion.
2. New class `unconfirmed` is **not** `unclassified`. It is the deliberate fail-safe lane:
   visible on the calendar day, flagged, no time expectation, full provenance. The X-Ray
   gets a section listing them; the sentinel (see below) budgets them.
3. **Sentinel updates** (`tools/verification/accuracy_sentinel.py`): add `RefidClass` to
   `REQUIRED_COLUMNS`; AST-extraction keeps working against the new `classify_action`;
   invariants become: SECTION 9 == 0, UNCLASSIFIED == 0 (the category should now be
   structurally impossible — keep the gate at 0), **UNCONFIRMED ≤ 150** (initial budget;
   revisit in C8.3), FLOOR, DERIVED ≤ 25, STRUCTURAL RESOLUTION ≥ 0.70.
4. **Zero-unexplained-diff gate (Hard Rule 7):** comparison script old-class vs new-class for
   all ~37k rows. Expected diffs ONLY: (a) residual rows admin→unconfirmed (the fail-safe
   lane becoming honest), (b) individually-listed rows gaining `meeting` via a verified
   VOTE_JOIN. Anything else → stop.
5. **Grep gate** before merge: `grep -n "MEETING_ACTION_PATTERNS\|ADMINISTRATIVE_PATTERNS\|ADMIN_OVERRIDE_PATTERNS" pages/ray2.py calendar_xray.py`
   returns nothing (or only the marked diagnostics block). Add this as a permanent check in
   the PR body.
6. assumptions_audit entry (numbered) + update [[architecture/calendar_pipeline]] with the
   new chain + log entry.

## PR-C8.3 — Guards

1. **Completeness tripwire** (productionize the 2026-06-09 PoC, which measured 180/180):
   `tools/verification/completeness_tripwire.py` — Schedule API committee meetings
   (active-session window, concrete times) joined against our sheet coverage.
   **Join key = committee CODE** (resolve both sides through the existing
   `NORM_TO_CODE`/`COMMITTEE_CODE_MAP` structural maps), NOT name text. Any LIS-calendar
   meeting absent from our data = FAIL (exit 1) listing the gaps. Empty/tiny schedule list →
   `EXTERNAL SOURCE CHANGE` (exit 2, mirroring `reconcile_votes.py`'s guard — a dead source
   never PASSes). Weekly workflow + manual dispatch.
2. **Unconfirmed budget alert:** sentinel budget stays fixed (150) until two weeks of green
   runs, then add the delta-vs-rolling-baseline form (audit #53 philosophy: prefer deltas;
   any cycle-stable trip is a calibration bug, not a transient).
3. Update [[architecture/verification_durability]] with the new layer + this chain.

---

## Stop-and-escalate protocol (for the implementing model)

STOP, write findings to [[state/current_status]], and wait for the owner when:
- A batch-notice counterexample appears (gate 8) — at ANY point, including post-merge cycles.
- The V-refid↔VOTE.CSV match rate is materially below 99% and the cause isn't obvious.
- The residual/unconfirmed lane exceeds its budget on a healthy cycle.
- Any measurement contradicts a number in this spec by more than noise.
- You feel the need to read description text to make a decision. (That feeling is the bug.)

## Definition of done (whole C8 block)
- [ ] Text pattern lists absent from the lobbyist path (grep gate clean in both X-Ray files).
- [ ] Section 9 = 0 and unclassified = 0 on live production data, post-flip.
- [ ] Unconfirmed lane ≤ budget, listed and visible in the X-Ray.
- [ ] Structural resolution ≥ floor; sentinel + reconcile + completeness all green in CI.
- [ ] All three PRs merged with Gemini review folded + branch worker validation.
- [ ] assumptions_audit, calendar_pipeline, verification_durability, log, current_status updated.

---

## PR-C8.1b — ScheduleType companion (added after the C8.1 native measurement)

C8.1's RefidClass only covers HISTORY-loop rows. The C8.1 shadow run showed the remaining
blank-route rows are ALL `api_schedule` origin: ~1,452 skeleton (already admin via the
empty-outcome rule) + ~964 text rows ("Scheduled" commission/board meetings + Schedule-API
"Placed on X Agenda" links). Their structural signal is the Schedule API's **`ScheduleTypeID`**
(measured inventory, 20261): `1`=Committee (940), `2`=Chamber (1), `4`=Caucus (457),
`5`=Other/commission (1869), `6`=Docket (209).

**Wiring (the schema-migration part — follow the CommitteeName `"?"` migration precedent):**
1. When the worker fetches the Schedule API, capture `ScheduleTypeID` per entry.
2. Add `ScheduleTypeID` to the **API_Cache** schema (new column; migration-burst guard handles
   pre-migration rows returning "" — same pattern as the `Location`/`CommitteeName` columns).
3. Carry it into `api_schedule_map[k]` (currently stores Time/SortTime/Status/Location at L3311).
4. Stamp a `ScheduleClass` column on api_schedule rows (SHADOW, additive telemetry), via a new
   pure `classify_schedule_type(schedule_type_id) -> MEETING_EVENT|FLOOR|CAUCUS|DOCKET|OTHER`
   in structural_router (golden-tested). NO text — keyed on the integer id only.
5. Gate: shadow run, sentinel green, distribution dumped in the PR; ≥ ~95% of api_schedule
   text rows get a non-OTHER ScheduleClass.

**Open items to MEASURE (don't assume):**
- Whether the `api_schedule` "Placed on X Agenda" rows DUPLICATE the HISTORY journal_default
  "Placed on Agenda" rows (possible double-count on the sheet) — characterize before C8.2.
- Whether the "Scheduled" commission rows (interim, dated pre-session e.g. 2025-11) should be
  in the session window at all, or are window-filter leakage (orthogonal to classification).

Then **C8.2** flips classify_action onto BOTH signals (RefidClass + ScheduleClass) and deletes
the text patterns.
