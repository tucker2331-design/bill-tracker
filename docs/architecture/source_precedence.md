---
tags: [architecture, trust, provenance, precedence, standards]
updated: 2026-07-25
status: active
---

# Choosing between disagreeing sources — the precedence ladder (house rule)

> **Owner, 2026-07-25:** *"How are you choosing the authoritative source — the one you're going to trust over
> the other — and how is the code going to do that in EVERY scenario?"*

**Short answer: we already have the right pattern, it is proven in the calendar subsystem, and the bill path
never inherited it.** This page generalizes it into a house rule so the answer is the same everywhere.
*(Written under [[workflow/design_proposal_protocol]] — existing machinery checked first, alternatives audited.)*

## What already exists (the prior art is ours)
[[architecture/calendar_pipeline]] documents two working ladders:
- **Committee resolution:** `History_refid` (structural PK) → `LOCAL_LEXICON` (text) → `bill_locations` memory.
- **Time resolution:** 7 rungs, exact schedule match → parent inheritance → hints → substring → convene anchor
  → LegislationEvent → **explicit terminal `NO_SCHEDULE_MATCH`**.
And critically, four properties that make them trustworthy rather than merely opinionated:
1. **Every row carries `Origin`** — the rung that produced its value (49 usages in `calendar_worker.py`).
2. **An explicit terminal rung** (`NO_SCHEDULE_MATCH` / `journal_default`) — an honest "we don't know",
   never a silent guess ([[workflow/source_miss_visibility]]).
3. **A stated principle, not a preference:** *"A concrete `ScheduleTime` always wins… the resolver never
   re-derives a time LIS published."*
4. **Measured, not asserted:** *"0 of 2,889 published-clock keys resolve to a derived time"*
   (`validate_relative_chains.py`), plus per-rung counters (`ANCHOR_RUNG_COUNTS`) so drift is visible.

## The four principles (why a source wins — derived, never a name-based table)
Precedence must fall out of a **property of the value**, knowable at runtime, never a hardcoded ranking of
source names (Standard #1 forbids hardcoding what's derivable; Standard #8 forbids maintenance tables):
1. **Published beats derived.** Never re-derive what the source explicitly stated.
2. **Structural beats text.** A code/flag/refid beats prose (Standard #3).
3. **System-of-record-for-this-field beats an incidental mention.** The Schedule API owns meeting times;
   `History_refid` owns committee identity; BILLS.CSV flags own terminal outcome; MinutesBook owns what
   happened in a committee meeting.
4. **Corroboration raises confidence but never creates authority.** Two mirrors of one upstream agreeing is
   not evidence — correlated error. (This is why majority-vote was rejected below.)

## "…in EVERY scenario?" — the honest answer: the ladder does NOT need a winner for every pair
It needs a **default for the pairs it cannot justify**. When no principle above applies — e.g. two *published,
structural, equally-system-of-record* sources disagree — the code **does not invent a winner**. It falls to the
**terminal rung: `unresolved` → the value is UNVERIFIED → red** (fail-closed, Standard #2), and **both values
are shown**. That is the same shape as the calendar's `NO_SCHEDULE_MATCH`, and it is what makes the answer
general: novel disagreements degrade into visible honesty instead of a coin flip wearing a rule's clothing.

## A rung may only exist if it is MEASURED (Standard #1)
A precedence rung ships with evidence from the archive that it actually holds — the calendar's *"0 of 2,889"*
is the model — and it is **re-measured continuously**, alerting if it degrades. A rung with no measurement is
provisional: its rows resolve, but they are marked unverified until the measurement exists. **We do not assert
which source is more trustworthy; we measure it and publish the track record.** (This is also the archive moat
pointed inward — [[ideas/moat_and_competition]].)

## Alternatives audited (and the rule that killed each)
| Design | Verdict |
|---|---|
| **Static precedence table per source pair** | ❌ Standard #1 (hardcoding what's derivable) + Standard #8 (a table a human must extend); silently has no answer for a new pair. |
| **Newest-wins / recency** | ❌ Recency ≠ authority. A late upstream typo would beat an earlier truth; 2026-07-25's stale string was not "older" in any usable sense. |
| **Majority vote across sources** | ❌ Needs ≥3 sources (we usually have 2), and our sources are mirrors of one upstream — correlated errors mean a wrong value published three times "wins". Violates principle 4. |
| **Never choose; publish every disagreement as unverified** | ⚠️ Honest but discards justified knowledge (structural-over-text is a *good, measurable* rule) and would have marked 443 rows unverified on 2026-07-25. **Correct as the DEFAULT, wrong as the only rule** — it survives as the terminal rung. |
| **Property-derived ladder + honest terminal + measured rungs** | ✅ **Adopted** — generalizes the calendar's proven pattern; degrades safely on the unanticipated case. |

## The concrete gap this exposes — the bill path is a generation behind
| | Calendar path | Bill/outcome path |
|---|---|---|
| Ladder | 7 documented rungs | implicit 2 rungs (`flags` → `keyword`), undocumented |
| Provenance | **`Origin` per row** (49 usages) | **`source` = the literal constant `"LIS"`** — never varies |
| Terminal rung | `NO_SCHEDULE_MATCH` (honest) | none — a keyword guess is published looking identical to an oracle-confirmed value |
| Measured | yes (0 of 2,889; rung counters) | no |

**`source: "LIS"` is provenance in name only.** By our own doctrine — *"a signal that never varies is not a
signal"* (`tools/open_loops.py`, on `status: active`) — it carries zero information. **This single gap is the
root cause of 2026-07-25**: with no `Origin` on the outcome, the adjudication verdict had nowhere to live, so
it was discarded and only a bare mismatch rate survived ([[architecture/incident_counter]] §3c).

**The fix is one field, not a subsystem:** `outcome_origin ∈ {structural_flag, keyword_fallback, unresolved}`.
It simultaneously (a) makes `published_output_impeached` derivable downstream for free, (b) makes the 12
oracle-less bills visibly unverified instead of invisible, (c) puts the bill path on the same pattern as the
calendar. Folded into W0c.

See also [[architecture/calendar_pipeline]] (the ladders), [[architecture/incident_counter]] (what consumes
the verdict), [[workflow/source_miss_visibility]], [[design/information_display]] P25a/P25c.
