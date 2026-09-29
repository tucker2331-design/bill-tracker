---
tags: [testing, calibration, prediction, members, war-room]
updated: 2026-09-28
status: active
open_loop: Modelling exhausted (six rounds, see Verdict). Remaining: score the locked 2026 test once; carried-over bills lack a summary-wording score (HB 1515) — fix before member cards ship; the bill-level consensus-kill warning and co-patron pattern are ready to design into the War Room (owner decision).
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

## Round 5 (2026-09-28) — owner: "exhaust the options ... complicated statistics a statistician would"

**Where the misses are (2025, error analysis):** by motion — "strike from the docket" is called right only 39% of
the time (522 ballots) and unanimous kills 54%; they are 22% of the hardest-third misses. Patron-requested
withdrawals are rare (~30 bills/session in LIS history), so they are not the main story.

| tried | 2025 all | hardest third | verdict |
|---|---|---|---|
| baseline GBM | 86.09% | 67.77% | — |
| **co-sponsorship relationships** (member↔patron co-sponsorship in earlier years, reciprocity, ties to this bill's coalition, co-sponsors seated in the room) | 85.95% | 66.91% | no gain |
| same, **size-weighted ties** (a shared 3-sponsor bill counts far more than a 60-sponsor one, Fowler-style) | 86.11% | 67.87% | noise |
| **member × bill latent factors** stacked on the GBM (supervised ideal points: member position = personal + district/party projection; bill location from summary words, subject, committee, patron) | 84.65% | 64.66% | **hurts** — overfits to training bills. Learning curve on 2024 with stronger regularisation: never above the GBM at any step (84.36% → flat or down) |

**Reading:** the GBM already searches combinations of up to six inputs; the question the owner raised — identity ×
content combinations ("this member × this kind of bill") — was tested directly by the factor model and does not
generalise from first votes alone (too few ballots per member). Next: the same axes learned from ALL contested
roll calls (floor + committee, earlier years) as a single feature — `text_ideal.py`.

| tried | 2025 all | hardest third (fixed set) | verdict |
|---|---|---|---|
| **text-linked ideal points from ALL contested roll calls** (15,763 roll calls, 526k ballots, earlier years only; bill placed by its content) as a GBM feature | 85.94% | 67.30% | no gain (2024: 84.33 vs 84.36) |
| **deeper combinations** — trees combining 8–10 inputs instead of 6, slower learning, more rounds (4 settings) | 85.76–86.00% | 66.76–67.49% | no gain; every deeper setting ties or loses on 2024 AND 2025 |

**Round-5 verdict (broad tests, each rules out a family):** relationship data, member×content interactions (from
first votes or from every vote), and deeper feature combinations all leave the hardest third at 67–68%. The
information that decides those votes — how each party will line up on this bill in this room — is not in the
public voting record, however it is combined. What can still move it is NEW information, not new maths:
the team's own contact log and positions (now being built), and (owner's call, later) reading bill content.

## Consensus kills — what they are and whether we can see them coming (2026-09-29)

Owner: "22% of the hard misses are unanimous kills or strike from the dockets ... dig more into that, how does that
happen in what scenario and could we predict it?" Scripts: `consensus_kills.py` (diagnosis), `consensus_kill_model.py`
(prediction). Data: first votes 2019–2025 (2023 excluded as elsewhere).

**What they are.** 918 of 9,344 first votes (9.8%) end with every member against the bill. 73% are in subcommittees;
none are full-committee first votes (full-committee kills are voice votes, no roll call). How they die: tabled 32%,
stricken from the docket 30% (almost always the patron pulling it), continued 17%, passed by indefinitely 9%;
"sent to study with a letter" only 3%; "incorporated into another bill" ~0%.

**Theory rejected:** "killed because a twin carried the idea" is FALSE — bills whose near-twin had already advanced
were killed LESS (5.7% vs 8.9%, 2025).

**The pattern — co-patrons, not party.** In a subcommittee:

| bill | consensus-kill rate |
|---|---|
| no co-patrons, minority patron | 21.2% (1,169 bills) |
| no co-patrons, majority patron | 19.6% (1,211) |
| at least one co-patron | 6.9% (2,691) |
| 5+ co-patrons | 4.3% (1,074) |
| co-patrons from both parties | 5.3% (495) |

81% of strikes and 69–82% of every kill type are bills with no co-patrons. **Correlation, not proof:** bills without
co-patrons may be weaker or placeholder bills; the same-patron check (a patron's bills with vs without co-patrons) is
the next test before telling anyone "add co-patrons."

**Predictable in advance, from inputs we already have.** Bill-level model, trained ≤2024, tested on 2025 (1,624 bills,
142 kills): AUC 0.85; the 10% of bills it flags most are consensus kills 36% of the time (4× the 8.7% base rate) and
catch 41% of all of them. New traces (twin advanced, patron's past kill rate, filing order, day of session) add nothing.

**Why the member model still misses them — and why that is correct.** Even the riskiest bills die only about 1 in 3,
so each member's single most likely vote is still yes. The miss is genuine uncertainty (the patron's private decision),
not a modelling gap. The value is a **bill-level warning** ("bills like this die quietly about 1 in 3 times"), not a
different member guess.

## Round 6 (2026-09-29) — the remaining broad families

**Co-patrons, same-patron test** (`copatron_same_patron.py`). 167 patrons had subcommittee bills both with and without
co-patrons. Their bills WITHOUT co-patrons died unanimously 20.4% (2,374 bills) vs 6.9% WITH (2,673); within-patron
difference +13.6 points; 112 patrons worse off without, 31 better, 24 tied — sign test p ≈ 6×10⁻¹². "Weaker
patrons" is ruled out as the explanation. Still not proof that ADDING a co-patron causes survival (patrons may
recruit co-patrons for their strongest bills), but strong enough to show lobbyists as an observed pattern.

| tried (settings fixed on 2024) | 2024 all / hard | 2025 all / hard (fixed set) | verdict |
|---|---|---|---|
| baseline GBM | 84.36 / 64.86 | 86.09 / 67.77 | — |
| regime-matched training (years with the same House majority counted twice) | 84.36 / 64.85 | 85.57 / 66.19 | worse |
| separate House and Senate models | 84.20 / 64.56 | 85.21 / 65.24 | worse |
| logistic regression alone | 82.72 / 61.31 | 84.28 / 63.75 | worse |
| GBM + logistic blend | 84.04 / 63.90 | 85.66 / 66.50 | worse |
| two-level: bill consensus-kill risk (expanding window) fed to the member model | +0.11 / +0.34 | −0.02 / −0.07 | noise |
| cleaner labels: train without strike-from-docket votes (scored on ALL votes) | +0.24 / +0.72 | −0.39 / −1.18 | does not replicate |

**Verdict after rounds 1–6:** every reasonable modelling and feature family has now been tested against the same
protocol. None moves the hardest third outside 66–68% on 2025. The only untried lever inside our own data is MORE
data: 2023 is missing from training (Open States has no 2023 committee record), but LIS's own 2023 files are cached
(`va/231/Vote.csv`: 8,071 roll calls with member-level ballots, committee votes included). Adding it needs a
refid→bill/date/motion join through History.csv and a member-ID→name join; by the earlier "+2019" test, one extra
year is worth about a point on the hardest third, not a step change.

**2023 added from LIS legacy files** (`add_2023.py`): 5,679 roll calls on 1,719 bills joined (Vote.csv → History.csv
refid → bill/date/motion, same direction and venue rules as every other year, 2022 carryover lines dropped); 136 of 141
members resolved through a suffix/nickname/first-last/unique-surname cascade (5 counted as unresolved, never guessed);
2023 co-patrons from LIS Sponsors.csv (971 bills) so 2023 does not masquerade as a no-co-patron year. Result:

| | 2024 all / hard | 2025 all / hard (fixed set) |
|---|---|---|
| original pipeline (no 2023) | 84.36 / 64.86 | 86.09 / 67.77 |
| 2023 in the features' history only | 84.36 / 64.85 | 86.08 / 67.71 |
| 2023 in history AND trained on | 84.36 / 64.86 | 86.14 / 67.90 |

Noise-level (+0.05 / +0.13 on 2025, nothing on 2024). **One more year of data does not move it either.**

## Verdict after six rounds (2026-09-29)

Every reasonable option inside our own data has been tested under one protocol (choose on 2024, score once on 2025,
2026 locked): new features (~25), relationship networks, member × content latent factors (first votes and all
526k contested ballots), deeper combinations, alternative model classes and blends, regime weighting, per-chamber
models, two-level structure, label cleaning, and an additional year of data. The hardest third stays 66–68%; overall
86%. The remaining error is how each party lines up on a specific bill in a specific room — decided privately, not
recorded in any public vote. What can still move it is NEW information: the team's own contact log and positions,
and (owner's call, later) reading bill content. Meanwhile two findings ARE usable now: the per-member labels are well
calibrated (Likely 94 / Leans ~70 / Toss-up 57 in 100), and consensus kills can be flagged at the bill level (4× base
rate in the top 10%), with the co-patron pattern holding within patrons (p ≈ 6×10⁻¹²).

## The ceiling, measured — and the hard third reverse-engineered (2026-09-29)

Owner: "would a statistician stop here? ... if we know what composes that final 30% can we reasonably predict when
a bill will end up in it?"

**1. Natural-experiment ceiling** (`twin_ceiling.py`). 734 pairs of near-identical bills (summary Jaccard ≥ 0.8) voted
separately — almost all House/Senate twins in the same session. Using one twin's ACTUAL first vote to call the other's
party positions (a cheat no forecast has):

| pairs | both parties match | patron's party | other party |
|---|---|---|---|
| all 734 | 75% | 88% | 80% |
| opposite chambers (697) | 76% | 90% | 81% |
| same venue AND same patron standing (75) | 87% | 91% | 91% |

Our model calls other-party members right 80% of the time on 2025 — **at the level of the identical-bill oracle.**
Bill content cannot say more than this; the rest depends on the particular room, people and day.

**2. The hard third by vote SHAPE** (`vote_shapes.py`, bill-level, train ≤2024, test 2025, 1,624 bills):

| shape | share | AUC | top-10% flagged are this shape |
|---|---|---|---|
| everyone for | 48% | 0.83 | 93% |
| straight party line | 24% | 0.80 | 64% |
| everyone against (consensus kill) | 9% | 0.85 | 33% |
| **mixed split** (members break from their party) | 19% | **0.58** | 30% |

Shape guessed right 59% overall (48% by always guessing "everyone for"); 83% on the quarter of bills it is surest
about. **Mixed splits are the irreducible core** — near-unpredictable before the meeting, and 28% of the hard-third
misses. Consensus kills are detectable but top out at 1-in-3, so they belong on the bill as a risk, not in a guess.

**Verdict:** stopping is now justified by measurement, not by exhaustion. The model is at the identical-bill ceiling;
the residual is mixed splits (unknowable from public data) plus consensus kills (a bill-level risk). New information —
the team's contact notes — is the only lever left, and it targets exactly the mixed-split members.
