---
tags: [testing, calibration, method, plan, war-room]
updated: 2026-08-02
status: active
---

# Calibration v2 — the plan, before any data is touched

**Why there is a plan this time.** Round 1 produced four method bugs, two withdrawn conclusions, and a
headline finding that had to be corrected twice. None of that was bad luck. It was the predictable result
of **running tests first and deciding what they meant afterwards** — every result invited a new question,
each new question got a fresh hand-rolled script, and each script had its own bugs.

**The fix is not "be more careful." It is to decide the questions, the measures, and the pass marks BEFORE
looking at the data**, and to run everything through one tested harness instead of twenty ad-hoc scripts.

---

## 1 · The question Round 1 never asked itself

The owner's question, and it is the crux: *"are we looking for how well it predicts the outcome in the
following session, or historical, or which one actually makes the difference and gives insight?"*

**Round 1 only ever measured prediction, and then treated failure-to-predict as failure-to-be-useful.**
That was a category error. There are **three different questions**, they need different tests, and a stat
can pass one while failing another.

| | question | test | what it decides |
|---|---|---|---|
| **Q1 · STABILITY** | Is this number a durable property, or does it swing session to session? | spread and rank-correlation across 20 sessions | **whether we may SHOW it** |
| **Q2 · SEPARATION** | Does knowing it change the outcome, and by how much? | difference in rates between buckets, with denominators | **whether it is worth showing** |
| **Q3 · TRANSFER** | Does last session's value tell you this session's? | fit on earlier sessions, test on a later one | **whether we may imply "expect similar"** |

**A stat that passes Q1 and Q2 but fails Q3 is still worth showing — as history, not as a forecast.**
That is exactly the case for committee pass rates, and Round 1 wrongly discarded them on Q3 alone.

**Every stat gets all three scores. No stat gets a single verdict.** That is the answer to "stop checking
things off binary."

---

## 2 · What is being tested — the outcomes

Round 1 got this wrong and it invalidated a headline
([[testing/calibration_correction_committee_outcome]]). Both outcomes are now defined structurally and
**cross-validated against Open States before use**:

| outcome | definition | validation status |
|---|---|---|
| **Passed its chamber of origin** | LIS `Passed_house`/`Passed_senate` | **100.0% agreement** with Open States, 2,062/2,062 (2023) |
| **Got out of committee** | last action code NOT in the 8 terminal suffixes `{40, 81, 90, 92, 93, 94, 97, 98}` | corrected 2026-08-02; the old 1-suffix rule missed 96% of Senate committee deaths |

**A third outcome is worth adding and was never considered:** *how far did it get* — an ordinal stage
(died in committee, passed origin chamber, passed both, signed). A binary outcome throws away the
difference between a bill that died on day 3 and one that died at the Governor's desk.

---

## 3 · The stats to test, organised by what they describe

Round 1 tested 47 things in a flat list. Grouping them by **object** makes the coverage gaps visible —
and matches the entity-statistics frame the vault already settled on ([[ideas/predictive_lane]]).

**BILL** — class (resolution vs legislation) · subject · number of subjects · emergency clause · filing
timing · companion presence · bill number band

**PATRON** — majority standing *(the surviving Round-1 finding)* · party · bill volume · prior-session
success · success in this committee · success on this subject · seniority · chairs a committee

**CO-PATRONS** — count · share in the majority *(survived Round 1)* · cross-party presence · whether any
sits on the deciding committee · chief-co-patron presence

**COMMITTEE** — pass rate overall · pass rate by subject · pass rate by patron party · load that session ·
size · money committee · chair identity

**SESSION / CONTEXT** — chamber · party control regime · which party holds the other chamber · Governor's
party · election-year vs off-year · session length

**The last group is entirely new and is the one 20 sessions unlocks.** With 2 sessions it could not be
tested at all.

---

## 4 · Party control — the stratification, and the reason it now works

**With 2 sessions we had one observation per House control regime. With 20 we have several.** Virginia
changed hands more than once in 2017–2027, so the same test can be run **within each regime** and compared.

**This settles the Don Scott question properly.** If the majority-standing gap appears under every
Speaker and every majority, it is institutional. If it tracks particular people, that will show as a gap
that varies by regime rather than by chamber.

Every stat is therefore scored **three ways**: pooled, split by chamber, and split by control regime.
Where a stat only works in one regime, that is a finding, not a nuisance.

---

## 5 · How many combinations, and where it stops

Round 1's combination work was hand-picked, then a 528-pair sweep. The rule this time, fixed in advance:

1. **All singles.**
2. **All pairs** among stats that clear a minimum sample.
3. **Triples ONLY for pairs that already beat their parts**, and only where every cell keeps a real sample.
4. **Nothing beyond triples.** Round 1 measured the cliff: 4 variables left 63% of test bills with no
   match in training, 5 left 99%. That is not a judgement call, it is a measured ceiling.

**The stopping rule is the unseen-cell rate, not a p-value.** When a model has to fall back to the base
rate for more than about a quarter of test bills, it has stopped modelling and started guessing.

---

## 6 · Guards against the specific ways Round 1 broke

Each of these is a bug that actually happened, turned into a check that runs automatically.

| Round-1 bug | the guard |
|---|---|
| **Leakage** — `text_versions` scored +77.9%; bills *acquire* versions by advancing | every feature declares what date it is knowable on; anything derived from post-decision actions is rejected by the harness, not by my memory |
| **Same-session contamination** — patron voting stats used the session being predicted | patron behavioural stats are computed from PRIOR sessions only, enforced in code |
| **Base-rate drift scored as skill** — the null used the training year's rate | the null is the TEST period's base rate; learned rates are recentred by the drift |
| **Incomplete outcome rule** — 1 of 8 terminal codes | outcomes cross-validated against Open States before any run; agreement rate recorded |
| **Unlearnable population read as a finding** — 10 Senate failures | any cell with fewer than 30 minority-class cases is reported as UNDERPOWERED, never scored |
| **Derived party label wrong on a knife-edge majority** | chamber majorities validated against the historical record before use |

---

## 7 · Where ADHD fits, and the rule that makes it safe

**Yes, but at one specific point and under one condition.**

**Where:** generating the *candidate stat list* in §3 — specifically the SESSION/CONTEXT group, which is
new and where I have the least prior intuition. Its value is producing hypotheses I would not reach for.

**The condition — pre-registration.** Every hypothesis it generates is written to a list, with its
predicted direction, **before** anything is measured. Then all of them are tested. **This is the guard
against the failure mode that actually bit Round 1:** finding a pattern and then constructing the reason
it makes sense. If the hypothesis list is fixed in advance, a result that fits is evidence; a result found
afterwards is a story.

**Frames, not personas.** The default frames (10-year-old, hardware engineer) would produce whimsy here.
The frames will be **disciplines with real theory about legislative outcomes**: a legislative scholar
(agenda control, gatekeeping), a survival analyst (bills die — time-to-event, censoring), a market
microstructure analyst (a docket is a queue), a fraud analyst (deviation from normal process as the
signal), and a working lobbyist (tacit knowledge that is in no dataset).

---

## 8 · Build order

1. **Harness first, with tests.** One module: load a session, apply an outcome, score a feature set, report
   Q1/Q2/Q3. Unit-tested on known inputs. **Round 1's bugs came from twenty scripts each written once and
   never checked.**
2. **Validate all 20 sessions against LIS where both exist** (2023, 2024) — record the agreement rate per
   outcome. Sessions are used only after their fidelity is measured.
3. **Pre-register** the hypothesis list (§3 plus ADHD additions).
4. **Run singles, then pairs, then triples**, with the §5 stopping rule.
5. **Report all three scores per stat**, per chamber, per control regime.
6. **Write the findings for a lobbyist**, not for a statistician — see §9.

---

## 9 · What the output is FOR

The owner intends to present these to a colleague as substantive insight about how the Virginia General
Assembly actually works — not only as product internals. So the deliverable is **two documents**:

- **The technical record** — every stat, all three scores, every caveat. The ledger.
- **The plain-English findings** — what these numbers tell a Virginia lobbyist about where bills die, what
  actually moves them, and what does not. Written for someone who lobbies, not someone who models.

**The second one is the point.** A finding nobody can explain to a colleague is not yet a finding.
