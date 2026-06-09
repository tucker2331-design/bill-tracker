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
| empty | 27,332 | floor readings/clerical | other signals |

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
