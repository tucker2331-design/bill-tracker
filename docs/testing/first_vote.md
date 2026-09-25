---
tags: [testing, calibration, prediction, members, war-room]
updated: 2026-09-25
status: active
open_loop: IN PROGRESS. Full-text layer waits on the 2025-26 introduced-text fetch (text_corpus/blob_text.py, owner-approved, paced). After it — freeze choices, score 2026 ONCE (it has never been loaded into a model). Display is the owner's Tier-3 call.
---

# Predicting every legislator's FIRST vote on a bill

Owner, 2026-09-25: *"focus on the first committee vote score or sub or what ever the first vote a bill hits bc
after that we know its a lot easier… becareful not to build something thats accurate when its least useful…
make sure your testing is dynamic… lets try to break 95."*

`tools/calibration/first_vote.py` (+ `gbm.py`, `text_party.py`, `text_features.py`, `stats.py`)

## Protocol — the way model builders evaluate
- **Train** 2020, 2021, 2022, 2024 · **tune** 2025 only · **2026 locked**, scored once after every choice is frozen.
- Every feature is computed by **replaying the legislature day by day**: a first vote sees only what happened on
  earlier days (earlier years, or earlier dates in the same session).
- Always reported by slice — **other-party legislators** and **whole-party position** — so a gain on the easy
  ballots cannot hide where it matters.

## The right baseline
On first votes "always guess yes" is **73.9%**, not the 84–85% of all votes. And the ceiling: if each party's
position were known perfectly, individual accuracy would be **97.3%** (other-party 96.5%). **Breaking 95% means
calling party positions ~97% right.**

## Progress on 2025 (tuning year)

| model | all | other-party | party position |
|---|---|---|---|
| basics (party, standing, venue) | 76.8% | 64.5% | 72.3% |
| + committee, patron, legislator-in-room, content, co-patrons, bill history, room memory, duplicates | 85.6% | 79.8% | 83.0% |
| + summary-word party classifier | 85.8% | 80.4% | 83.6% |
| **tuned: one-stage GBM, depth 6** | **86.2%** | **80.7%** | **84.0%** |
| two-stage (party → member) | 85.3% | 80.2% | 83.2% — not better |
| *always guess the common answer* | *73.9%* | *57.4%* | |

## Subject labels — no gain (tested 2026-09-25)
Coarse subjects cover 85% of bills (vs 20–32% for similar-bill content), added as party-on-subject and
legislator-on-subject records: 85.9% vs 86.2%, within noise. Bill-level signals have plateaued near 86%.

## Breaking 95 the way a product can — confident calls (2025, tuning year)

| call only the most confident… | all legislators | other-party |
|---|---|---|
| 30% | **99.2%** | 96.8% |
| 50% | 97.8% | 93.9% |
| 60% | 96.4% | 91.1% |
| 80% | 91.8% | 84.9% |
| 100% | 85.9% | 79.9% |

**95%+ accuracy on 67% of all first-vote ballots and 45% of other-party ballots**, with the rest flagged "too
close to call". The confidence cutoff is fixed on 2025 and carried unchanged into the 2026 test — choosing it on
2026 would be tuning on the answer.

## Traps caught, all before any number was reported
1. **Direction bug — 1,262 roll calls (2.7%) read backwards.** "Failed to report (defeated)" was treated as a kill
   motion. Fixing it moved every number up.
2. **Carryover vote copies** in the next session's file (1,816) — the same vote in training and test.
3. **The integer-mask scoring bug**, twice.
4. **Stacking trap** — word-model scores for training years came from cross-fitted models that had seen later
   years; 2025's did not. The tree over-trusted them (85.6 → 82.7). Fixed with an expanding window everywhere.
5. **Where the misses are:** unanimous tablings of ordinary bills (the patron's own party votes to table — not
   explained by duplicates, tested) and party-line splits on majority bills. Those are the targets for text.
