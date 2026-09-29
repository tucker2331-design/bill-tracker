---
tags: [testing, calibration, prediction, members, war-room]
updated: 2026-09-28
status: active
open_loop: IN PROGRESS. (1) Score the locked 2026 test once. (2) Carried-over bills (e.g. HB 1515) have no summary-wording score (txt_has=0), which shifts their guesses 10-17 points — score them before any member card ships. Display is the owner's call (War Room v10 mockup).
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

## The plateau — tested from every direction (2026-09-25/26)

Owner: *"look into more to close this gap… consider things like district location composition… see if you
can 2x it."* Every attempt, same protocol (tune 2025, 2026 locked):

| added | all | other-party | party position | hardest third |
|---|---|---|---|---|
| (tuned model) | **86.2%** | 80.7% | 84.0% | — |
| subject labels (85% coverage) | 85.9% | 79.9% | 83.2% | — |
| actual subcommittee, this-session room, legislator×patron, companion's vote | 85.8% | 80.1% | 83.3% | 66.8% |
| full-text structural flags (2025 layer) | 84.9% | 78.7% | 82.8% | 66.8% |
| full-text similar bills (47% coverage) | 85.1% | 79.2% | 82.6% | 67.5% |
| ideal points, per chamber (district proxy) | 85.6% | 79.4% | 83.5% | 66.3% |
| + 2019 training year | 85.6% | 79.6% | 83.4% | 67.2% |
| training on fewer years | 84.6–85.1% | — | — | — |

**Every idea lands within ±0.6 of 86%.** The remaining error is almost entirely *which way a party goes on this
bill in this room* (ceiling with perfect party positions 97.3%). That is decided in caucus and is not in any public
record we hold. **The hardest third sits at 66–68% — inside the owner's 60–70% target.**

**Ideal points, face validity:** per chamber (a combined fit let the House swamp the Senate and made every
"moderate" a senator near zero). Dimension 1 separates the parties 100%; the most moderate include the 2024
swing-seat senators (Perry, Pekarsky, VanValkenburg) and, historically, Petersen/Lewis (D) and Vogel/Hanger (R).

**2017–18 excluded from training:** their committee roll calls carry counts but no names, so each bill's first
NAMED vote is its floor vote — 166,000 floor ballots that would have been over half the training set.

**What could still move party positions (each needs the owner):** an LLM reading each bill for its political
charge (~10k API calls, cost); Census district composition (a free key only the owner can register); the org's
own positions and contact notes (caucus-level information the public record lacks).

## Round 3 (2026-09-28) — aimed at the hardest third, owner target >80%

| added | all | hardest third |
|---|---|---|
| Census district composition (2022 maps, joined via 2023 ELECT filings) | 85.5% | 67.0% |
| "by request" bills (read from the printed bill) | — | hypothesis false: own party backed them 95% |
| attribute scan for consensus kills (companion ahead, duplicates, fiscal, co-patrons…) | — | nothing separates; best "no co-patrons" 18% vs 8% |
| **the room's seated members as a group** (each side's record on patron / subject / similar bills / map / districts) | **86.1%** | **67.8%** — best so far, rank 0.914 |
| what this room did EARLIER THE SAME DAY (LIS vote-id order) | 86.4% | 68.7% — live-hearing only, not pre-meeting |

**Verdict:** ~20 ingredients tested; the hardest third moves inside 66–69%. It is the bills whose party position is
set in caucus, which no public record carries. What could still move it needs the owner: an LLM reading each bill
for its political charge (API spend), and the org's own positions/contact notes.

**District join, done right.** The people file mixes old- and new-map district numbers for SITTING members
(Sickles listed at old 43; he holds 17) — joining on it put about half the legislature in the wrong place (the
sanity check had Mark Sickles among the least college-educated districts). Districts now come from the Nov 2023
ELECT candidate filings (2022 maps) via `finance.join_members`: Sickles 17, Kilgore 45, Shin 8, Tran 18.
Filings whose office reads "0.00" are excluded — Barry Knight's said 81 (old map) and joined him to a
Black-majority Chesapeake district.

## Traps caught, all before any number was reported
1. **Direction bug — 1,262 roll calls (2.7%) read backwards.** "Failed to report (defeated)" was treated as a kill
   motion. Fixing it moved every number up.
2. **Carryover vote copies** in the next session's file (1,816) — the same vote in training and test.
3. **The integer-mask scoring bug**, twice.
4. **Stacking trap** — word-model scores for training years came from cross-fitted models that had seen later
   years; 2025's did not. The tree over-trusted them (85.6 → 82.7). Fixed with an expanding window everywhere.
5. **Where the misses are:** unanimous tablings of ordinary bills (the patron's own party votes to table — not
   explained by duplicates, tested) and party-line splits on majority bills. Those are the targets for text.

## How sure, in words a volunteer can use (2026-09-28)

Accuracy by how far the model leans, 2025 first votes (17,553 ballots, held out of training; 2025 was also the
tuning year, so read these as slightly optimistic until the locked 2026 check runs):

| label | how far it leans | share of calls | right |
|---|---|---|---|
| Likely | 80%+ either way | 70% | 94 of 100 |
| Leans | 60–80% | 20% | about 70 of 100 |
| Toss-up | 40–60% | 10% | 57 of 100 |

The War Room shows only the label; the "How sure is this?" sheet shows this table. No per-member percentages.

## Why a member gets their guess — `why_member.py` (2026-09-28)

Owner: the two raw counts on the member card were odd to an amateur and "not enough evidence." Each reason now
carries a direction and a size, measured by swapping that reason's inputs for 300 real same-party ballots
(method and the failed first attempt are in the script's docstring). HB 1515, first vote assumed Jan 2027:

- **The bill's own situation dominates for everyone.** No co-patrons / no Senate companion: −6 to −10 points per
  member. Sitting in a subcommittee, carried over: −10 to −16 (depends on the assumed vote date). The first is the
  one factor an org can change.
- Personal factors are small: Kilgore's overall record −3; the four Democrats: committee record −1 to −5, similar
  bills +4, overall record up to +6, patron record +2. District: 0 for all five.
- **Data gap found:** HB 1515 has no summary-wording score (`txt_has = 0`), and the missing score moves the
  Democrats' guesses by +10 to +17 — an artifact, not a reason. It is kept off the card and disclosed in the
  "How sure" sheet. Fix: score carried-over bills' summaries (open loop below).

## Round 4 (2026-09-28) — owner: "getting that 67 number up"

Protocol: choices fixed on 2024 (model trained 2019–2022), applied unchanged to 2025. 2026 stays locked.

| tried | 2025 all | 2025 hardest third | verdict |
|---|---|---|---|
| baseline | 86.1% | 67.8% | — |
| **missing inputs** — do ballots lacking a wording score / content / districts go wrong more? | — | with 67.5% vs without 68.1% (wording) | **no**: missing data is not where the misses are, so filling gaps won't lift it |
| party consistency — blend each member's guess toward party-mates' on the same vote (a=0.2) | 86.2% | 68.0% | noise (+0.1 / +0.2) |
| per-slice thresholds (other-party × subcommittee) | 85.4% | 70.5% | **rejected — a metric trap.** Moving thresholds changes WHICH ballots count as "hardest"; the headline rose while overall accuracy fell 0.7 points |

**Where the hard third lives:** 72% are other-party ballots (vs 48% overall) and 69% are subcommittee votes (vs 42%).

**The one untested lever — an LLM reading each bill for its political charge.** Cost, checked 2026-09-28
(Anthropic price list; Batch API is half price): ~11,600 summaries × ~400 input + ~60 output tokens ≈ **$4 on
Haiku 4.5, $8 on Sonnet 5.5, roughly $40–60 on Opus 5.5** (its thinking is always on). **Leakage risk that must be
designed out:** a model trained on public data may remember how a 2019–2025 bill actually fared, which would make
backtests look better than reality. Mitigate by sending only the summary text (no bill number, year, patron) and
asking about content, not outcome; the only fully clean test is the 2027 session. Needs the owner's go-ahead (spend
+ an API key).
