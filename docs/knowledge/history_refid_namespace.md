---
tags: [knowledge, api, structural, refid, lis]
updated: 2026-06-09
status: active
---

# HISTORY.CSV refid namespace — the structural identity layer (PR-C8 investigation)

`History_refid` is a TYPED structural namespace, not an opaque string. Census over 65,366
rows (session 20261):

| Shape | Count | Meaning | Structural use |
|---|---|---|---|
| `H14`/`S04` (committee code) | 4,353 | acting committee | committee attribution (already used) |
| `H14V2610034` (vote id) | 5,657 | roll-call vote id | **JOIN to VOTE.CSV** = structural "a recorded vote happened on this row" — replaces any text tally-regex |
| numeric, shared across bills same-date | most of 8,231 | **batch document id** (one agenda/assignment notice fanning across 4–63 bills) | **batch-notice law** (below) |
| numeric, singleton | ~1,568 | per-bill document id (e.g. governor's substitute print) | residual → surface |
| `HB1000F122` (impact-stmt doc) | 4,299 | bill **impact-statement** filing (`[HS]B\d+…F\d+`): Fiscal (4,293) + Racial-and-Ethnic (6) | **DOCUMENT → admin** (2026-06-27): 0 vote-join, fan-out=1, **0 live Sheet1 rows (noise-filtered)** → `classify_refid` `_IMPACT_DOC_REFID_RE` |
| empty | 27,332 | floor readings/clerical | other signals |

**Impact-statement caveat (2026-06-27, route-cross-checked):** the `…F###` shape was classified DOCUMENT
only AFTER confirming via the live route that it never surfaces (0 Sheet1 rows). The sibling unknown shapes
do the OPPOSITE — `\d+D_H####` "(sub)committee offered" compounds and `HB####/SB####` "incorporated" bill-refs
**route `LegEventRoute=meeting`** (real committee times from the schedule match, not the refid), so they must
NOT get an admin refid label and stay UNKNOWN/surface until a dedicated *non-decisive* class lands. Lesson: a
refid's identity ≠ its row's route; the refid class must never override a positive meeting route to admin.
See [[testing/va_data_quality_audit]] edge #3.

**VOTE.CSV** (never opened before 2026-06-09): per-member roll calls, first column = vote id
(`26110000`-style) matching the V-refid suffix. 1,606 roll-calls in 20261. This is the
structural deliberative-evidence source.

**BILLS.CSV**: per-bill `Last_*_actid` fields (`H7010`, `S7300`, `G9998`) — confirms the
EventCode namespace is LIS's complete published action taxonomy.

## The batch-notice law (text-free classification of HISTORY-only rows)
A HISTORY row whose refid is (a) shared by ≥K bills on the same date (batch document),
(b) has no VOTE.CSV join, and (c) has no LegislationEvent instance, is a clerk's batch
notice → ledger. Measured (20261, K=4, crude sheet-side reverse-join): **2,675/2,765
(96.7%)** of blank-route journal rows proven; **0** batch documents contain a vote join
(rule of three: p < 0.11%). Deliberation is per-bill (votes recorded per bill+member);
batch paperwork fanning across dozens of bills with zero votes is administrative BY
STRUCTURE. No decision reads the description text — typos and re-wordings cannot misroute.

## Negative results (4× confirmed: House agenda data is NOT in the API surface)
DOCKET.CSV = Senate-only; Schedule API `Docket` type = Senate-only; no `Docket` controller
exists; Calendar API = floor calendars only (its blob `.JSON` file 404s).

## ⚠️ SPA-shell false-200 lesson
`lis.virginia.gov/<AnyController>/api/<anything>` returns **HTTP 200 with the React SPA
shell HTML** for nonexistent routes. A 200 does NOT mean an endpoint exists — require
`application/json` content-type + parseable body before believing a probe.

## REFINEMENT from PR-C8.1 native measurement (2026-06-09)
The original "numeric refid = batch document" was too coarse. Measured segmentation of the
numeric refid space (session 20261):

| refid len | distinct | VOTE.CSV join | role |
|---|---|---|---|
| 3 | 7 | 0% | subcommittee-assignment batch |
| 4 | 315 | 0% | agenda-notice batch |
| 6 | 30 | 0% | singleton per-bill doc |
| 7 | 182 | **100%** | floor roll-call vote-id |
| 8 | 1,380 | **100%** | floor roll-call vote-id |

Consequences for the decision chain:
- **Vote evidence has TWO structural forms** (either ⇒ meeting): (a) refid matches the V-grammar
  `^[HS]\d{1,2}(?:\d{3})?V\d+$` (committee vote record — these NEVER appear in VOTE.CSV, which is
  floor-only; 0% join is EXPECTED, not a miss); (b) a bare-numeric refid that IS a key in VOTE.CSV
  (floor roll-call). The earlier spec idea of "VOTE_REF_UNMATCHED → surface" was WRONG for V-grammar
  refids — a V-refid is itself the vote record.
- **Batch-notice = a NON-vote numeric refid (not a VOTE.CSV key) shared by ≥K same-date bills.** The
  len-3/4 batch refids are 0% vote-join at every fan level, so the law is safe; K is small.
- **Per-row purity (critical):** classify each row by ITS OWN refid. A bill assigned to a
  subcommittee (batch, admin) AND voted (separate row, meeting) on the same day is TWO rows, each
  correct. A "bill voted that day" test is NOT a valid batch counterexample (it produced 587 false
  positives at K=2). The only valid counterexample is the batch ROW's own refid joining VOTE.CSV (=0).
- **K is finalized from the NATIVE shadow run** (C8.1), not this reverse-join (which has ~654
  bill+date join-miss artifacts that vanish when the worker builds rows from HISTORY directly).

## Refid SHAPE drift monitor — the sustainable answer to UNKNOWN_REFID (2026-06-27)
`classify_refid` recognizes a fixed grammar; an unrecognized shape silently becomes `UNKNOWN_REFID`,
with no signal that LIS introduced a new namespace. Hand-adding a grammar per shape (e.g. the
impact-statement family) is a maintenance treadmill — the refid layer's least-sustainable corner — and
the layer is only a SECONDARY/shadow cross-check anyway (`route_event` on EventCode/ReferenceType/Status
is the primary structural router and already routes these rows; an `UNKNOWN_REFID` is a *measurement*
gap, not a misrouting). So instead of pre-coding every shape, `structural_router.validate_refid_shapes`
mirrors `validate_status_grouping`: a baseline of acknowledged shapes (`KNOWN_REFID_SHAPES`, 22 census
signatures) + a runtime diff that **alerts** (`WARN/DATA_ANOMALY`) when a NOVEL shape appears
`≥ REFID_SHAPE_MIN_VOLUME` (25) times in a session → human review. Static-value-WITH-runtime-drift-alert
(Standard #1), `UNKNOWN`→human (Standard #4), ping-only-on-anomaly (Standard #8). Signature = the shape
skeleton (each digit-run → `#`; `HB1000F122`→`HB#F#`). The worker runs it post-loop off the refid column
(`UNKNOWN_REFID` is fanout/vote-independent). A human then classifies a genuinely-new shape ONCE, rather
than us pre-coding every one. **GENERALIZABLE** → every state's worker gets the same shape-drift monitor.
See `test_refid_shape_drift.py`, [[testing/va_data_quality_audit]] edge #3.
