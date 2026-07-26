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

## How often does the "equal competing sources" tie actually happen? — MEASURED, 2026-07-25
> **Owner:** *"How often do you expect that equal-competing-data scenario to play out? Because that would reset
> our counter, and if it's a chronic condition that would make it unlivable."* Correct worry, and our own rules
> say measure it, don't estimate it (Standard #7; pre-push #14 — *"grep every threshold against the new
> steady-state and flag any that would trip on healthy operation"*). Live product data, **37,832 calendar rows**:

| Origin (which rung produced the value) | Rows | Share |
|---|---|---|
| `convene_anchor` | 17,137 | 45.30 % |
| `api_schedule` | 11,798 | 31.19 % |
| `legislation_event` + `scheduled_future` + `derived_standing` | 673 | 1.78 % |
| `admin_default` + `executive_default` (**no time expected** by design) | 2,052 | 5.42 % |
| `floor_miss` + `journal_default` (**terminal rung — nobody had a value**) | 6,170 | 16.31 % |

**The decisive finding: there is no "conflict" or "tie" Origin at all — zero rows in 37,832.** That is
structural, not luck, and it separates two things I had been blurring:
- **Ladders resolve SCARCITY** — *which source has the value*. Their terminal rung means **"nobody published
  one"** → the value is **ABSENT**, not disputed.
- **Adjudication resolves CONFLICT** — *two sources have it and differ*. That is Friday's case, and it was
  **resolved by a principle** (structural>text), not a tie.

**True ties observed to date: zero.** Not in 37,832 calendar rows; not in the 3,645-bill outcome path (443
conflicts, **all** discriminated by a principle). The reason is structural: our sources are **asymmetric** —
one is always more structural, or the system of record for that field. A genuine tie needs two *equally*
authoritative *structural* sources for the *same* field, which is a rare shape. **So the tie case is not the
chronic risk.**

**The real chronic population is ABSENCE, and it is large** — 16.31 % terminal-rung + the 12 flagless bills.
A naive "any unresolved → break the streak" rule would indeed be unlivable, exactly as the owner predicted.
**The resolution is a distinction we already enforce elsewhere** — §9 (the project's own accuracy metric)
counts *meeting* actions without times as bugs while administrative actions legitimately have none, and it
sits at **0** even with 16.31 % of rows on terminal rungs. Generalized:
| State | Meaning | Counts against the ledger? |
|---|---|---|
| **Absent** | no source published a value; **we published nothing** | ❌ no — disclosed with its denominator |
| **Unverified** | **we published a value** no oracle confirms (the 12 flagless bills) | ⚠️ yes — but see baseline rule |
| **Conflict-unresolved** | two sources differ, no principle discriminates | ✅ yes (zero observed) |
| **Impeached** | published value verifiably wrong | ✅ yes — red |

**The livability guarantee (pre-push #14's own rule): a known, explained, BOUNDED unverified population is a
disclosed limitation shown with its denominator; the incident fires on DEVIATION FROM BASELINE, not on
existence.** *"Prefer delta-vs-rolling-baseline thresholds for metrics whose floor depends on system
behavior."* This does not soften the owner's rule — the client is told the exact scope ("12 of 3,645 carry a
text-derived outcome LIS hasn't structurally confirmed"), which is the opposite of assuming it's fine.
**And a chronic TIE would be a bug, not a condition to live with:** recurring ties mean the ladder is missing a
principle for that pair, and breaking the streak is precisely the pressure that forces us to add and measure
one.

**Open calibration item (honest gap):** §9 = 0 proves the accuracy-critical population is fully resolved, but I
have **not** cross-tabulated Origin against the meeting-action classifier to prove all 6,170 terminal-rung rows
fall outside it. That cross-tab is the first calibration step of W0c — measure before setting any threshold.

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
